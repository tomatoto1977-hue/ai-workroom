"""Suno prompt builder for Video Factory.

This module does not call Suno or perform account/payment actions.
It creates a structured prompt and lyrics package that can be pasted into
Suno manually, then the downloaded audio can be imported through
ImportedAudioProvider.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SunoPrompt:
    style: str
    lyrics: str
    notes: str

    def as_text(self) -> str:
        return (
            f"[Style]\n{self.style}\n\n"
            f"[Lyrics]\n{self.lyrics}\n\n"
            f"[Production Notes]\n{self.notes}"
        )


def build_suno_prompt(
    *,
    topic: str,
    lyrics: str,
    genre: str = "rock",
    mood: str = "energetic, catchy, positive",
    duration_s: int = 30,
    language: str = "Japanese",
) -> SunoPrompt:
    """Build a concise, original Suno-ready brief for a short social video."""
    style = (
        f"{genre}, {mood}, modern short-form social media song, "
        f"clear {language} vocals, memorable hook, strong rhythm, "
        f"clean commercial-style production, no artist imitation"
    )
    notes = (
        f"Theme: {topic}. Target length: about {duration_s} seconds. "
        "Start with a hook in the first seconds. Keep the chorus easy to understand. "
        "Use original melody and wording; do not imitate named artists or copyrighted songs."
    )
    return SunoPrompt(style=style, lyrics=lyrics.strip(), notes=notes)


if __name__ == "__main__":
    example = build_suno_prompt(
        topic="節約のつもりが逆に損している習慣",
        lyrics="[Verse]\nまとめ買い 使い切れなきゃムダ\n[Chorus]\nその節約 逆に損してない？",
    )
    print(example.as_text())
