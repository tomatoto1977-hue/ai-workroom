"""
Video Factory Short-form Pipeline v15
-------------------------------------
Safe-by-default short-video pipeline:
AI image per scene -> TikTok safe-area placement -> kinetic captions -> motion
-> original/licensed audio -> optional narration -> automated QA.

This module is intentionally provider-agnostic. AI image/TTS/music providers are injected
through adapters so the core pipeline never performs external posting or paid actions
implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Protocol, Sequence, Optional
import json
import subprocess


@dataclass(frozen=True)
class SafeArea:
    width: int = 1080
    height: int = 1920
    top_px: int = 260
    right_px: int = 300
    bottom_px: int = 300
    left_px: int = 60

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return (
            self.left_px,
            self.top_px,
            self.width - self.right_px,
            self.height - self.bottom_px,
        )


@dataclass(frozen=True)
class Scene:
    scene_id: str
    duration_s: float
    visual_prompt: str
    narration: str
    headline: str
    subline: str = ""


@dataclass
class PipelineConfig:
    output_dir: Path = Path("outputs")
    safe_area: SafeArea = field(default_factory=SafeArea)
    fps: int = 30
    width: int = 1080
    height: int = 1920
    crossfade_s: float = 0.45
    ken_burns_zoom: float = 1.08
    caption_pop_s: float = 0.22
    # Readability guardrails: mobile viewers should never chase dense captions.
    max_headline_lines: int = 2
    max_subline_lines: int = 0
    bgm_bpm: int = 150
    bgm_intensity: float = 1.45
    # Local free-first music generation. The adapter is optional and never auto-publishes.
    music_provider: str = "ace_step_local"
    music_genre: str = "rock"
    music_duration_s: float = 30.0
    music_vocals: bool = True
    music_language: str = "ja"
    require_human_review: bool = True
    auto_publish: bool = False
    external_operations: bool = False
    paid_operations: bool = False
    use_narration: bool = True
    narration_required: bool = False


class AIImageProvider(Protocol):
    def generate(self, prompt: str, output_path: Path, *, width: int, height: int) -> Path:
        ...


class NarrationProvider(Protocol):
    def synthesize(self, text: str, output_path: Path) -> Path:
        ...


class MusicProvider(Protocol):
    def generate(
        self,
        lyrics: str,
        output_path: Path,
        *,
        genre: str,
        duration_s: float,
        bpm: int | None = None,
        mood: str = "",
    ) -> Path:
        ...


class SafetyError(RuntimeError):
    pass


def validate_config(cfg: PipelineConfig) -> None:
    if cfg.auto_publish:
        raise SafetyError("auto_publish must remain False")
    if cfg.external_operations:
        raise SafetyError("external_operations must remain False")
    if cfg.paid_operations:
        raise SafetyError("paid_operations must remain False")
    if cfg.width != cfg.safe_area.width or cfg.height != cfg.safe_area.height:
        raise ValueError("safe-area dimensions must match render dimensions")
    if cfg.music_provider not in {"none", "ace_step_local"}:
        raise ValueError("unsupported music provider")
    if cfg.music_duration_s < 10 or cfg.music_duration_s > 600:
        raise ValueError("music_duration_s must be between 10 and 600 seconds")
    if not cfg.music_language.strip():
        raise ValueError("music_language must not be empty")


def build_scene_prompts(topic: str, scenes: Sequence[Scene]) -> list[str]:
    """Add a consistent visual brief without copying reference videos."""
    base = (
        f"Original visual for a vertical social short about {topic}. "
        "Solid high-contrast cinematic 3D/illustrative advertising look, "
        "clear subject separation, bold shapes, no logos, no celebrities, "
        "no copyrighted characters, no screenshots of other creators, "
        "no watermarks, composition leaves the TikTok UI safe areas empty."
    )
    return [base + " Scene: " + s.visual_prompt for s in scenes]


def validate_safe_area(x: int, y: int, w: int, h: int, safe: SafeArea) -> bool:
    sx1, sy1, sx2, sy2 = safe.rect
    return x >= sx1 and y >= sy1 and x + w <= sx2 and y + h <= sy2


def validate_scene(scene: Scene) -> list[str]:
    errors: list[str] = []
    if scene.duration_s < 1.0:
        errors.append("scene duration < 1s")
    headline_lines = [line for line in scene.headline.splitlines() if line.strip()]
    subline_lines = [line for line in scene.subline.splitlines() if line.strip()]
    if len(scene.headline) > 36:
        errors.append("headline too long for mobile")
    if len(headline_lines) > 2:
        errors.append("headline exceeds 2 readable lines")
    if len(scene.subline) > 52:
        errors.append("subline too long for mobile")
    if len(subline_lines) > 0:
        errors.append("subline disabled: keep the screen to the two main headline lines")
    if not scene.visual_prompt.strip():
        errors.append("missing visual prompt")
    return errors


def run_ffmpeg(args: Sequence[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def make_qa_report(
    video_path: Path,
    *,
    cfg: PipelineConfig,
    scenes: Sequence[Scene],
    narration_path: Optional[Path] = None,
    music_path: Optional[Path] = None,
) -> dict:
    """Non-destructive final QA. Returns PASS/REVIEW; never publishes."""
    report = {
        "video": str(video_path),
        "resolution": [cfg.width, cfg.height],
        "fps": cfg.fps,
        "safe_area": asdict(cfg.safe_area),
        "human_review_required": cfg.require_human_review,
        "auto_publish": cfg.auto_publish,
        "paid_operations": cfg.paid_operations,
        "music_provider": cfg.music_provider,
        "music_genre": cfg.music_genre,
        "music": bool(music_path),
        "narration": bool(narration_path),
        "scene_errors": {},
        "checks": {},
    }

    for s in scenes:
        errs = validate_scene(s)
        if errs:
            report["scene_errors"][s.scene_id] = errs

    report["checks"]["safe_area_defined"] = True
    report["checks"]["all_scenes_valid"] = not report["scene_errors"]
    report["checks"]["music_ready"] = (
        cfg.music_provider == "none" or bool(music_path)
    )
    report["checks"]["narration_ready"] = (
        (not cfg.narration_required) or bool(narration_path)
    )
    report["checks"]["file_exists"] = video_path.exists()
    report["status"] = (
        "PASS"
        if all(report["checks"].values())
        else "REVIEW"
    )
    return report


def save_qa_report(report: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def default_short_config() -> PipelineConfig:
    """Reference-safe defaults learned from the current short-video iteration."""
    return PipelineConfig(
        crossfade_s=0.45,
        ken_burns_zoom=1.08,
        caption_pop_s=0.22,
        max_headline_lines=2,
        max_subline_lines=0,
        bgm_bpm=150,
        bgm_intensity=1.45,
        music_provider="ace_step_local",
        music_genre="rock",
        music_duration_s=30.0,
        music_vocals=True,
        music_language="ja",
        require_human_review=True,
        auto_publish=False,
        external_operations=False,
        paid_operations=False,
        use_narration=True,
        narration_required=False,
    )
