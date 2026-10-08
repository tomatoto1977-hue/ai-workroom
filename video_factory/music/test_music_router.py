from pathlib import Path
import tempfile

from music_router import MusicRequest, plan_music, validate_music_request


def test_none_provider() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan = plan_music(MusicRequest(provider="none"), Path(tmp))
        assert plan.status == "ready"


def test_suno_manual_creates_prompt_package() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan = plan_music(
            MusicRequest(
                provider="suno_manual",
                topic="節約",
                lyrics="[Chorus]\nその節約、逆に損してない？",
                genre="rock",
            ),
            Path(tmp),
        )
        assert plan.status == "manual_required"
        assert plan.output_path is not None
        assert plan.output_path.exists()
        assert "Suno" in plan.action


def test_import_requires_source() -> None:
    try:
        validate_music_request(MusicRequest(provider="imported_audio"))
    except ValueError:
        return
    raise AssertionError("imported_audio must require source_path")


if __name__ == "__main__":
    test_none_provider()
    test_suno_manual_creates_prompt_package()
    test_import_requires_source()
    print("PASS")
