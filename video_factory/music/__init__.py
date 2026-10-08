"""Video Factory music providers."""

from .ace_step_music import AceStepConfig, AceStepMusicProvider, available_genres
from .imported_audio import ImportedAudioConfig, ImportedAudioProvider, ImportedAudioError
from .suno_prompt import SunoPrompt, build_suno_prompt
from .music_router import MusicRequest, MusicPlan, plan_music, provider_catalog, validate_music_request

__all__ = [
    "AceStepConfig",
    "AceStepMusicProvider",
    "available_genres",
    "ImportedAudioConfig",
    "ImportedAudioProvider",
    "ImportedAudioError",
    "SunoPrompt",
    "build_suno_prompt",
    "MusicRequest",
    "MusicPlan",
    "plan_music",
    "provider_catalog",
    "validate_music_request",
]
