"""canvas 的 nodes / edges 命名（正名與相容別名）。"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, 'wfyaml.py')


class CanvasNamingTests(unittest.TestCase):
    """nodes / edges 為正名（與 React Flow、D3、圖論一致）；items / link 為相容別名。"""

    KIT_NEW = """
components:
  board:
    of: canvas
    base: {grid: true}
    node: {use: chip}
    edge: {shape: straight}
    states: [todo, done]
  chip:
    props: [label]
    states: [todo, done]
    content:
      - col: [ "text.strong: {{label}}" ]
        box: true
"""
    KIT_OLD = KIT_NEW.replace('node:', 'item:').replace('edge:', 'link:')

    PAGE_NEW = """viewport: 390x400
body:
  - board:
      nodes:
        - {label: 起點, at: [0.2, 0.3], state: done}
        - {label: 終點, at: [0.7, 0.6], state: todo}
      edges: [起點, 終點]
"""
    PAGE_OLD = PAGE_NEW.replace('nodes:', 'items:').replace('edges:', 'link:')

    def _render(self, kit_text, page_text):
        with tempfile.TemporaryDirectory() as d:
            kit = os.path.join(d, 'kit.yaml')
            page = os.path.join(d, 'p.wf.yaml')
            open(kit, 'w', encoding='utf-8').write(kit_text)
            open(page, 'w', encoding='utf-8').write(page_text)
            proc = subprocess.run([sys.executable, WF, '--kit', kit, page],
                                  capture_output=True, text=True, cwd=d)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return open(os.path.join(d, 'p.html'), encoding='utf-8').read()

    def test_new_names_render(self):
        html = self._render(self.KIT_NEW, self.PAGE_NEW)
        self.assertIn('wf-canvas-item', html)
        self.assertIn('wf-canvas-link', html)

    def test_old_names_still_render(self):
        self.assertIn('wf-canvas-item', self._render(self.KIT_OLD, self.PAGE_OLD))

    def test_names_can_be_mixed(self):
        """舊 kit + 新畫面（或反之）都要能跑，遷移才不必一次改完。"""
        self.assertIn('wf-canvas-link', self._render(self.KIT_OLD, self.PAGE_NEW))


if __name__ == '__main__':
    unittest.main()
