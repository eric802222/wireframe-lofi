import sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import wfyaml as wf

class TextTruncation(unittest.TestCase):
    """截斷是規格：RD 需要知道哪裡會截斷，所以它進 DSL 而不是留在 theme。"""
    def test_max_lines_emits_clamp_with_line_count_as_data(self):
        html = wf.render_item({'text': '很長的說明', 'max-lines': 3})
        self.assertIn('wf-clamp', html)
        self.assertIn('--wf-max-lines:3', html)
    def test_wrap_false_emits_nowrap(self):
        html = wf.render_item({'text': '單行', 'wrap': False})
        self.assertIn('wf-nowrap', html)
        self.assertNotIn('wf-clamp', html)
    def test_unset_changes_nothing(self):
        self.assertEqual(wf.render_item({'text': '原樣'}), wf.render_item({'text': '原樣', 'wrap': True}))
    def test_max_lines_and_nowrap_conflict_is_an_error(self):
        # 「最多兩行」與「不准換行」語義互斥。舊版靜默讓 max-lines 勝出 —— 規格寫了、
        # 工具默默不做，正是 theme binding 警示要抓的那種錯，不該由測試背書。
        with self.assertRaises(Exception):
            wf.render_item({'text': 'x', 'max-lines': 2, 'wrap': False})

    def test_truncation_rejected_on_containers(self):
        # wf-clamp 帶 display:-webkit-box，套在容器上會蓋掉 flex：版面壞掉卻不報錯
        for container in ({'col': ['text: a'], 'max-lines': 2},
                          {'row': ['text: a'], 'wrap': False},
                          {'grid': [1, 1], 'items': ['text: a'], 'max-lines': 3}):
            with self.assertRaises(Exception):
                wf.render_item(container)
    def test_rejects_non_semantic_values(self):
        for bad in (0, -1, '2', 1.5, True):
            with self.assertRaises(Exception):
                wf.render_item({'text': 'x', 'max-lines': bad})
        with self.assertRaises(Exception):
            wf.render_item({'text': 'x', 'wrap': 'nowrap'})
    def test_span_and_max_lines_coexist(self):
        html = wf.render_item({'text': 'x', 'span': 2, 'max-lines': 2})
        self.assertIn('grid-column:span 2', html)
        self.assertIn('--wf-max-lines:2', html)

if __name__ == '__main__':
    unittest.main()


class TruncationPassesTypoCheck(unittest.TestCase):
    """合法的 max-lines / wrap 不該被未知 key 檢查誤殺。

    #57 把它們從容器白名單拿掉（容器用會拆版面），#58 又讓葉子開始做 typo 檢查 ——
    兩個各自正確，合起來讓合法用法變成 warning。是在重做 IG demo 時踩出來的。
    """

    def test_truncation_on_leaf_is_not_an_unknown_key(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'p.wf.yaml')
            open(p, 'w', encoding='utf-8').write(
                'viewport: 390x600\nbody:\n  - text: 很長的說明\n    max-lines: 2\n'
                '  - text: 單行預覽\n    wrap: false\n')
            self.assertEqual(wf._lint_file(p), (0, 0))
