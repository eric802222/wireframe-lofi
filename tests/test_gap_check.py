"""規格缺口檢查：源碼「沒說的事」。

交付物是 YAML + 產出的 HTML —— 兩者用同一套 name / role 對得起來，AI 直接讀就夠開發。
所以這裡刻意**不**另外生一份規格文件（那會變成第四份平行製品，正是這個 repo 一路在修的病）。

唯一補不了的是「缺席」：AI 讀得到畫面有什麼，推不出「這頁沒宣告空狀態」。
這些洞 DSL 其實表達得了（routes + when 寫狀態、note: 寫 RD 約束），只是沒人提醒。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfcheck          # noqa: E402


class GapCheck(unittest.TestCase):

    def _gaps(self, body):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'p.wf.yaml')
            open(p, 'w', encoding='utf-8').write('viewport: 390x600\n' + body)
            return {kind for kind, _ in wfcheck.page_gaps(p)}

    def test_single_state_page_is_flagged(self):
        self.assertIn('states', self._gaps('body:\n  - text: 只有一種樣子\n'))

    def test_declared_variants_silence_it(self):
        self.assertNotIn('states', self._gaps(
            'routes:\n  - { id: ready, label: 一般 }\n  - { id: empty, label: 沒有資料 }\n'
            'body:\n  - text: 內容\n'))

    def test_input_without_note_is_flagged(self):
        self.assertIn('constraints', self._gaps('body:\n  - input: 訊息…\n'))

    def test_input_with_note_is_silent(self):
        self.assertNotIn('constraints', self._gaps(
            'body:\n  - input: 訊息…\n    note: 上限 500 字；失敗保留草稿\n'))

    def test_undefined_values_are_listed(self):
        self.assertIn('undefined', self._gaps('body:\n  - "text: 共 [N] 則留言"\n'))

    def test_gaps_never_block_ci(self):
        # 只有單一狀態有時是刻意的（確認頁、靜態說明頁），不該擋 CI
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'p.wf.yaml')
            open(p, 'w', encoding='utf-8').write('viewport: 390x600\nbody:\n  - input: x\n')
            self.assertEqual(wfcheck.main(['gaps', p, '--quiet']), 0)


if __name__ == '__main__':
    unittest.main()
