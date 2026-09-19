"""動線完整性檢查：斷鏈、孤島、死路、跨階段。"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, 'wfcheck.py')

GOOD = {
    'home.wf.yaml': 'title: 首頁\ngroup: A\nbody: [{button: {text: 去詳情, to: detail}}]\n',
    'detail.wf.yaml': 'title: 詳情\ngroup: A\nbody: [{button: {text: 回首頁, to: home}}]\n',
}


def run(files, *args):
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, text in files.items():
            p = os.path.join(d, name)
            open(p, 'w', encoding='utf-8').write(text)
            paths.append(p)
        return subprocess.run([sys.executable, CHECK, 'flow', *paths, *args],
                              capture_output=True, text=True, cwd=ROOT)


class FlowCheckTest(unittest.TestCase):
    def test_clean_graph_passes(self):
        proc = run(GOOD)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('0 error', proc.stdout)

    def test_dangling_target_is_error(self):
        files = dict(GOOD)
        files['home.wf.yaml'] = 'title: 首頁\ngroup: A\nbody: [{button: {text: 去, to: ghost}}]\n'
        proc = run(files)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('斷鏈', proc.stderr)

    def test_island_is_error(self):
        files = dict(GOOD)
        files['lonely.wf.yaml'] = 'title: 孤島\ngroup: A\nbody: [{button: {text: 回, to: home}}]\n'
        proc = run(files)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('孤島', proc.stderr)

    def test_dead_end_is_error(self):
        files = dict(GOOD)
        files['end.wf.yaml'] = 'title: 死路\ngroup: A\nbody: [{text: 沒有出口}]\n'
        files['home.wf.yaml'] = ('title: 首頁\ngroup: A\nbody: [{button: {text: 去詳情, to: detail}},'
                                 ' {button: {text: 去死路, to: end}}]\n')
        proc = run(files)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('死路', proc.stderr)

    def test_declared_entry_is_not_an_island(self):
        files = dict(GOOD)
        files['home.wf.yaml'] = 'title: 首頁\ngroup: A\nbody: [{button: {text: 去詳情, to: detail}}]\n'
        files['detail.wf.yaml'] = 'title: 詳情\ngroup: A\nbody: [{button: {text: 回, to: home}}]\n'
        # home 沒有入口，但宣告為進入點 → 不算孤島
        proc = run(files, '--entry', 'home')
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_cross_stage_is_quiet_by_default(self):
        files = dict(GOOD)
        files['detail.wf.yaml'] = 'title: 詳情\ngroup: B\nbody: [{button: {text: 回, to: home}}]\n'
        proc = run(files)
        self.assertEqual(proc.returncode, 0)                  # 共用畫面本來就會跨，不該吵
        self.assertIn('跨階段動線', proc.stdout)

    def test_cross_stage_listed_with_flag(self):
        files = dict(GOOD)
        files['detail.wf.yaml'] = 'title: 詳情\ngroup: B\nbody: [{button: {text: 回, to: home}}]\n'
        proc = run(files, '--stages')
        self.assertEqual(proc.returncode, 1)                  # warning 不擋，但 exit 1 可在 CI 收斂
        self.assertIn('跨越階段', proc.stderr)

    def test_layout_links_count(self):
        """layout 裡的 to:（頁首入口、底部返回）也是動線，不能漏掉。"""
        files = {
            'layouts/shell.wf.yaml': 'viewport: 390x844\nbody:\n  - slot: main\n  - button: {text: 返回, to: home}\n',
            'home.wf.yaml': 'title: 首頁\ngroup: A\nbody: [{button: {text: 去詳情, to: detail}}]\n',
            'detail.wf.yaml': ('title: 詳情\ngroup: A\nextends: layouts/shell\n'
                               'slots:\n  main: [{text: 內容}]\n'),
        }
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'layouts'))
            paths = []
            for name, text in files.items():
                p = os.path.join(d, name)
                open(p, 'w', encoding='utf-8').write(text)
                if not name.startswith('layouts/'):
                    paths.append(p)
            proc = subprocess.run([sys.executable, CHECK, 'flow', *paths],
                                  capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)      # detail 的出口在 layout 裡
        self.assertNotIn('死路', proc.stderr)


if __name__ == '__main__':
    unittest.main()


class SpecExportTest(unittest.TestCase):
    """每頁規格：元件、狀態、動線、未定值 —— 交付 RD 與餵給 AI 的清單。"""

    PAGE = """title: 問書籤鳥
group: C 旅途中
routes:
  - default: true
    body:
      - "text.strong: 京都 五日散步"
      - row: [ { input: 再問一句…, grow: true }, { button: { text: 送出, to: home } } ]
      - "text.hint: 這則 [本次花費]"
  - when: { state: result }
    body:
      - button: { text: 放進小書, to: memory }
"""

    def _run(self, *args):
        with tempfile.TemporaryDirectory() as d:
            page = os.path.join(d, 'ask.wf.yaml')
            open(page, 'w', encoding='utf-8').write(self.PAGE)
            for extra in ('home', 'memory'):
                open(os.path.join(d, f'{extra}.wf.yaml'), 'w', encoding='utf-8').write(
                    f'title: {extra}\nbody: [{{text: x}}]\n')
            return subprocess.run([sys.executable, CHECK, 'spec', page, *args],
                                  capture_output=True, text=True, cwd=ROOT)

    def test_markdown_lists_states_components_flows(self):
        out = self._run().stdout
        self.assertIn('ask　問書籤鳥（C 旅途中）', out)
        self.assertIn('狀態：default / result', out)
        self.assertIn('`button`', out)
        self.assertIn('ask → home', out)
        self.assertIn('ask.result → memory', out)

    def test_undefined_values_listed(self):
        self.assertIn('[本次花費]', self._run().stdout)

    def test_json_format(self):
        import json
        spec = json.loads(self._run('--format', 'json').stdout)[0]
        self.assertEqual(spec['id'], 'ask')
        self.assertEqual(spec['states'], ['default', 'result'])
        self.assertIn('button', spec['components'])
        self.assertTrue(any(f['to'] == 'memory' for f in spec['flows']))

    def test_unknown_format_errors(self):
        proc = self._run('--format', 'xml')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('--format', proc.stderr)
