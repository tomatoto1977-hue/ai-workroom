import unittest

import api


class QualityGateSafetyTests(unittest.TestCase):
    def test_local_keyword_fallback_can_never_pass(self):
        # Deliberately include every keyword trigger; keyword presence is not semantic review.
        results = [{
            "role": "test",
            "text": (
                "出典 一次情報 公式 確認日 取得日 要確認 数字 料金 制度 "
                "テーマ 企画 視聴者 ニーズ 目的 価値 具体 手順 行動 "
                "カット 字幕 秒 例 ステップ 結論 冒頭 フック CTA 保存 "
                "1画面1メッセージ 短く Canva CapCut 編集 受け渡し 素材 "
                "縦9:16 1080 著作権 権利 個人情報 肖像 商標 人間承認 公開しない 外部操作"
            )
        }]
        gate = api.local_quality_gate(results)
        self.assertFalse(gate["passed"])
        self.assertLessEqual(gate["score"], 94)
        self.assertEqual(sum(gate["breakdown"].values()), gate["score"])
        self.assertLessEqual(sum(gate["breakdown"].values()), 94)
        self.assertEqual(gate["status"], "REVIEW_REQUIRED")
        self.assertEqual(gate["auditor"], "local_safety_fallback")

    def test_quality_rubric_totals_100(self):
        self.assertEqual(sum(api.QUALITY_RUBRIC.values()), 100)

    def test_eleven_roles_are_defined(self):
        self.assertEqual(len(api.ROLES), 11)
        self.assertEqual(len({role for role, _ in api.ROLES}), 11)

    def test_font_cache_is_enabled(self):
        api._video_font.cache_clear()
        api._video_font(24)
        api._video_font(24)
        self.assertGreaterEqual(api._video_font.cache_info().hits, 1)


if __name__ == "__main__":
    unittest.main()
