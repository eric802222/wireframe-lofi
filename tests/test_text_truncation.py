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
