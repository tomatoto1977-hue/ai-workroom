from pathlib import Path

from video_factory.music.ace_step_music import (
    AceStepConfig,
    AceStepMusicProvider,
    available_genres,
)


def main() -> None:
    genres = available_genres()
    assert {"rock", "reggae", "pop", "hiphop", "edm", "acoustic"} == {
        item["id"] for item in genres
    }

    provider = AceStepMusicProvider(AceStepConfig())
    assert provider.config.base_url == "http://127.0.0.1:8001"

    print("ACE-Step provider configuration test: PASS")
    print("Genres:", ", ".join(item["label"] for item in genres))
    print("Generation test is skipped unless a local ACE-Step API is running.")


if __name__ == "__main__":
    main()
