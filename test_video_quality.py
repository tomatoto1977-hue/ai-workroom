import tempfile
import unittest
import wave
from pathlib import Path

import api


class VideoQualitySafetyTests(unittest.TestCase):
    def test_narration_removes_outline_and_timecodes(self):
        results = [{"role": "文章化AI", "text": "【0-3秒】電気代は毎月の明細から確認しましょう。\n【3-10秒】契約内容を比べるときは条件をそろえてください。\n【画面字幕】今日、明細を確認"}]
        narration = api._narration_text("電気代の見直し", results)
        self.assertNotIn("企画書", narration)
        self.assertNotIn("【", narration)
        self.assertNotIn("画面字幕", narration)
        self.assertIn("電気代", narration)

    def test_fallback_narration_is_conversational(self):
        narration = api._narration_text("サブスクの見直し", [])
        self.assertIn("ちょっと聞いてください", narration)
        self.assertLessEqual(len(narration), 650)

    def test_local_bgm_is_valid_wave_and_nonempty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bgm.wav"
            api._generate_original_bgm(path, 1)
            with wave.open(str(path), "rb") as audio:
                self.assertEqual(audio.getnchannels(), 2)
                self.assertEqual(audio.getframerate(), 22050)
                self.assertGreater(audio.getnframes(), 0)
                self.assertGreater(len(audio.readframes(100)), 0)

    def test_research_card_marks_missing_sources(self):
        text = api._research_card_text([])
        self.assertIn("調査未完了", text)

    def test_research_card_uses_actual_research_result(self):
        text = api._research_card_text([{"role": "情報収集AI", "text": "候補: 公式情報を確認"}])
        self.assertIn("公式情報を確認", text)


    def test_default_music_is_local_and_free(self):
        request = api.RunRequest(instruction="テスト")
        self.assertEqual(request.music_provider, "auto_bgm")
        self.assertFalse(api.GEMINI_TTS_ENABLED)

    def test_safety_rules_keep_human_approval_and_rights_checks(self):
        rules = api.safety_rules()
        self.assertIn("人間承認後のみ", rules)
        self.assertIn("著作権侵害", rules)
        self.assertIn("特定個人", rules)


if __name__ == "__main__":
    unittest.main()
