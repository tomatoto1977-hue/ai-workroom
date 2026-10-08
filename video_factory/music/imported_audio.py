"""Imported/local audio provider for Video Factory.

Accepts audio created outside Video Factory (e.g. MusicSeed, BandLab, GarageBand)
without logging into those services or automating paid/external actions.
The file is copied into the pipeline output directory and lightly validated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


class ImportedAudioError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImportedAudioConfig:
    max_size_mb: int = 100


class ImportedAudioProvider:
    """Use a user-supplied audio file as the Video Factory music source."""

    def __init__(self, config: ImportedAudioConfig | None = None) -> None:
        self.config = config or ImportedAudioConfig()

    def validate(self, source_path: Path) -> None:
        if not source_path.exists() or not source_path.is_file():
            raise ImportedAudioError(f"Audio file not found: {source_path}")
        if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ImportedAudioError(
                f"Unsupported audio format: {source_path.suffix}. "
                f"Use one of {sorted(SUPPORTED_EXTENSIONS)}."
            )
        if source_path.stat().st_size > self.config.max_size_mb * 1024 * 1024:
            raise ImportedAudioError("Audio file is larger than the configured size limit.")

    def import_audio(self, source_path: Path, output_path: Path) -> Path:
        self.validate(source_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, output_path)
        return output_path

    def probe(self, audio_path: Path) -> dict:
        self.validate(audio_path)
        try:
            completed = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(audio_path),
                ],
                capture_output=True, text=True, check=True,
            )
            duration = float(completed.stdout.strip())
        except Exception as exc:
            raise ImportedAudioError(f"ffprobe could not read audio: {exc}") from exc
        return {"path": str(audio_path), "duration_s": duration}
