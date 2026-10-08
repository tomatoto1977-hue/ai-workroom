from pathlib import Path
import tempfile

from imported_audio import ImportedAudioProvider, ImportedAudioError


def test_missing_file_is_rejected() -> None:
    provider = ImportedAudioProvider()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            provider.validate(Path(tmp) / "missing.wav")
        except ImportedAudioError:
            return
        raise AssertionError("missing audio should be rejected")


def test_unsupported_extension_is_rejected() -> None:
    provider = ImportedAudioProvider()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "track.exe"
        p.write_bytes(b"not audio")
        try:
            provider.validate(p)
        except ImportedAudioError:
            return
        raise AssertionError("unsupported format should be rejected")


if __name__ == "__main__":
    test_missing_file_is_rejected()
    test_unsupported_extension_is_rejected()
    print("PASS")
