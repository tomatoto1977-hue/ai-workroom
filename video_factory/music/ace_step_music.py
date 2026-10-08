"""Local ACE-Step 1.5 music adapter for Video Factory.

Safe-by-default:
- Talks only to a locally running ACE-Step HTTP server.
- No cloud music service, login, auto-publish, or paid operation.
- Supports Japanese lyrics and selectable genre presets such as Rock and Reggae.
- Downloads only the audio returned by the local server.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


GENRE_PRESETS: dict[str, dict[str, Any]] = {
    "pop": {
        "label": "ポップ",
        "prompt": "modern Japanese pop, catchy melody, bright synths, clean drums, warm bass, clear Japanese vocals",
        "bpm": 118,
    },
    "rock": {
        "label": "ロック",
        "prompt": "energetic rock, electric guitar riffs, punchy live drums, bass guitar, dynamic chorus, clear Japanese vocals",
        "bpm": 138,
    },
    "reggae": {
        "label": "レゲエ",
        "prompt": "Japanese reggae, offbeat guitar skank, deep bass, relaxed drums, warm groove, positive clear Japanese vocals",
        "bpm": 82,
    },
    "hiphop": {
        "label": "ヒップホップ",
        "prompt": "Japanese hip hop, tight drums, deep bass, rhythmic vocal delivery, modern minimal production",
        "bpm": 92,
    },
    "edm": {
        "label": "EDM",
        "prompt": "energetic EDM, punchy kick, synth bass, bright lead, build and drop, clear Japanese vocal hook",
        "bpm": 128,
    },
    "acoustic": {
        "label": "アコースティック",
        "prompt": "warm Japanese acoustic pop, acoustic guitar, light percussion, intimate clear vocals",
        "bpm": 104,
    },
}


class AceStepError(RuntimeError):
    pass


@dataclass(frozen=True)
class AceStepConfig:
    base_url: str = "http://127.0.0.1:8001"
    timeout_s: float = 900.0
    poll_s: float = 2.0
    thinking: bool = True
    audio_format: str = "wav"
    vocal_language: str = "ja"
    model: str = "acestep-v15-turbo"


class AceStepMusicProvider:
    """Generate an original local music track through ACE-Step 1.5."""

    def __init__(self, config: AceStepConfig | None = None) -> None:
        self.config = config or AceStepConfig()

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(
            urljoin(self.config.base_url.rstrip("/") + "/", path.lstrip("/")),
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise AceStepError(f"ACE-Step request failed: {exc}") from exc
        if data.get("code", 200) != 200:
            raise AceStepError(str(data.get("error") or data))
        return data.get("data", data)

    def health(self) -> bool:
        url = urljoin(self.config.base_url.rstrip("/") + "/", "health")
        try:
            with urlopen(Request(url, method="GET"), timeout=5) as response:
                return response.status == 200
        except Exception:
            return False

    def generate(
        self,
        lyrics: str,
        output_path: Path,
        *,
        genre: str = "rock",
        duration_s: float = 30.0,
        bpm: int | None = None,
        mood: str = "",
    ) -> Path:
        key = genre.lower().strip()
        if key not in GENRE_PRESETS:
            raise ValueError(f"Unsupported genre: {genre}. Choose from {sorted(GENRE_PRESETS)}")
        if duration_s < 10 or duration_s > 600:
            raise ValueError("ACE-Step duration must be between 10 and 600 seconds.")

        preset = GENRE_PRESETS[key]
        prompt = preset["prompt"]
        if mood.strip():
            prompt += ", " + mood.strip()

        payload = {
            "prompt": prompt,
            "lyrics": lyrics,
            "thinking": self.config.thinking,
            "vocal_language": self.config.vocal_language,
            "audio_format": self.config.audio_format,
            "model": self.config.model,
            "task_type": "text2music",
            "audio_duration": float(duration_s),
            "bpm": int(bpm or preset["bpm"]),
            "inference_steps": 8,
            "use_random_seed": True,
            "batch_size": 1,
        }
        task = self._request("/release_task", payload)
        task_id = task.get("task_id")
        if not task_id:
            raise AceStepError(f"ACE-Step did not return task_id: {task}")

        deadline = time.monotonic() + self.config.timeout_s
        result: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            queried = self._request("/query_result", {"task_id_list": [task_id]})
            rows = queried if isinstance(queried, list) else queried.get("data", queried)
            if isinstance(rows, list) and rows:
                row = rows[0]
                status = row.get("status")
                if status == 2:
                    raise AceStepError(str(row.get("error") or row))
                if status == 1:
                    raw = row.get("result", "[]")
                    result = json.loads(raw) if isinstance(raw, str) else raw
                    break
            time.sleep(self.config.poll_s)

        if not result:
            raise AceStepError("ACE-Step generation timed out or returned no result.")

        item = result[0] if isinstance(result, list) else result
        audio_path = item.get("file")
        if not audio_path:
            raise AceStepError(f"ACE-Step result has no audio file: {item}")

        parsed = urlparse(audio_path)
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            raise AceStepError("Unexpected audio URL scheme from local ACE-Step server.")
        audio_url = urljoin(self.config.base_url.rstrip("/") + "/", audio_path.lstrip("/"))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urlopen(Request(audio_url, method="GET"), timeout=60) as response:
                output_path.write_bytes(response.read())
        except Exception as exc:
            raise AceStepError(f"Failed to download generated audio: {exc}") from exc

        return output_path


def available_genres() -> list[dict[str, Any]]:
    """UI-friendly genre list for the Video Factory selector."""
    return [
        {"id": key, "label": value["label"], "default_bpm": value["bpm"]}
        for key, value in GENRE_PRESETS.items()
    ]
