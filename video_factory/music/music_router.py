"""Unified music routing for Video Factory.

Providers:
- ace_step_local: fully local generation
- suno_manual: create a Suno-ready prompt package; user generates/downloads manually
- imported_audio: import an existing WAV/MP3/M4A/etc.
- none: no music

No provider in this module logs into third-party services, pays for services,
or publishes content automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ace_step_music import AceStepMusicProvider
from .imported_audio import ImportedAudioProvider
from .suno_prompt import SunoPrompt, build_suno_prompt


MUSIC_PROVIDERS = {
    "none",
    "ace_step_local",
    "suno_manual",
    "imported_audio",
}


@dataclass(frozen=True)
class MusicRequest:
    provider: str = "ace_step_local"
    topic: str = ""
    lyrics: str = ""
    genre: str = "rock"
    mood: str = "energetic, catchy, positive"
    duration_s: float = 30.0
    bpm: int | None = None
    source_path: Path | None = None
    language: str = "Japanese"


@dataclass(frozen=True)
class MusicPlan:
    provider: str
    status: str
    action: str
    output_path: Path | None = None
    suno_prompt: SunoPrompt | None = None


def validate_music_request(request: MusicRequest) -> None:
    if request.provider not in MUSIC_PROVIDERS:
        raise ValueError(f"Unsupported music provider: {request.provider}")
    if request.duration_s < 10 or request.duration_s > 600:
        raise ValueError("duration_s must be between 10 and 600 seconds")
    if request.provider == "imported_audio" and request.source_path is None:
        raise ValueError("source_path is required for imported_audio")
    if request.provider == "suno_manual" and not request.lyrics.strip():
        raise ValueError("lyrics are required to build a Suno prompt")


def plan_music(request: MusicRequest, output_dir: Path) -> MusicPlan:
    """Create a safe music plan without performing external account operations."""
    validate_music_request(request)
    output_dir.mkdir(parents=True, exist_ok=True)

    if request.provider == "none":
        return MusicPlan(
            provider="none",
            status="ready",
            action="No music will be added.",
        )

    if request.provider == "suno_manual":
        prompt = build_suno_prompt(
            topic=request.topic,
            lyrics=request.lyrics,
            genre=request.genre,
            mood=request.mood,
            duration_s=int(request.duration_s),
            language=request.language,
        )
        prompt_path = output_dir / "suno_prompt.txt"
        prompt_path.write_text(prompt.as_text(), encoding="utf-8")
        return MusicPlan(
            provider="suno_manual",
            status="manual_required",
            action="Paste suno_prompt.txt into Suno, generate/download the audio, then import it as imported_audio.",
            output_path=prompt_path,
            suno_prompt=prompt,
        )

    if request.provider == "imported_audio":
        target = output_dir / ("music_external" + request.source_path.suffix.lower())
        ImportedAudioProvider().import_audio(request.source_path, target)
        return MusicPlan(
            provider="imported_audio",
            status="ready",
            action="Imported user-supplied audio; continue to QA and human review.",
            output_path=target,
        )

    target = output_dir / "music_ace_step.wav"
    AceStepMusicProvider().generate(
        request.lyrics,
        target,
        genre=request.genre,
        duration_s=request.duration_s,
        bpm=request.bpm,
        mood=request.mood,
    )
    return MusicPlan(
        provider="ace_step_local",
        status="ready",
        action="Generated local ACE-Step audio; continue to QA and human review.",
        output_path=target,
    )


def provider_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": "ace_step_local",
            "label": "ACE-Step（ローカルAI）",
            "automation": "automatic_local",
            "best_for": "自動生成・日本語ボーカル",
        },
        {
            "id": "suno_manual",
            "label": "Suno（手動生成）",
            "automation": "manual_external",
            "best_for": "高品質な歌入り曲の候補作成",
        },
        {
            "id": "imported_audio",
            "label": "外部音源",
            "automation": "import_only",
            "best_for": "MusicSeed / BandLab / GarageBand等の書き出し音源",
        },
        {
            "id": "none",
            "label": "音楽なし",
            "automation": "disabled",
            "best_for": "ナレーション中心の動画",
        },
    ]
