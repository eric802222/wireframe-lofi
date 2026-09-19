"""素材兩種模式：inline（自含單檔）/ link（引用 *.assets/ 資料夾）。

內嵌是為了老闆 demo 單檔可攜，代價是產物巨大且 97% 是 base64 —— repo 吃二進位、
AI agent 整份讀就燒掉 context（見 #52）。link 模式把素材留在資料夾裡，
產物只存相對路徑：IG 10 畫面實測 3.6 MB → 380 KB。

交換條件很明確：產物不再是單檔，要連同資料夾一起帶走。所以
`--bundle-standalone`（定義就是單檔自含）與 `--assets link` 互斥。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfyaml as wf          # noqa: E402

PNG = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010802000000907753'
                    'de0000000c4944415408d76360000000020001e221bc330000000049454e44ae426082')


class AssetModes(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, 'th.assets'))
        open(os.path.join(self.d, 'th.assets', 'p.png'), 'wb').write(PNG)
        open(os.path.join(self.d, 'th.yaml'), 'w', encoding='utf-8').write(
            "tokens:\n  color: { ink: '#111' }\n"
            "assets:\n  pic: th.assets/p.png\n"
            "bindings:\n  主圖: { image: pic }\n")
        open(os.path.join(self.d, 'p.wf.yaml'), 'w', encoding='utf-8').write(
            'viewport: 390x600\nbody:\n  - image: { label: 圖 }\n    name: 主圖\n')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)
        wf._load_theme(None)

    def _render(self, *extra):
        r = subprocess.run([sys.executable, str(ROOT / 'wfyaml.py'), '--mockup', 'th.yaml',
                            *extra, 'p.wf.yaml'], cwd=self.d, capture_output=True, text=True)
        html = ''
        out = os.path.join(self.d, 'p.html')
        if os.path.exists(out):
            html = open(out, encoding='utf-8').read()
        return r, html

    def test_inline_is_the_default(self):
        _, html = self._render()
        self.assertIn('src="data:image/png;base64,', html)

    def test_link_writes_a_relative_path(self):
        _, html = self._render('--assets', 'link')
        self.assertIn('src="th.assets/p.png"', html)
        self.assertNotIn('data:image/png;base64,', html)

    def test_link_output_is_much_smaller(self):
        _, inline = self._render()
        _, linked = self._render('--assets', 'link')
        self.assertLess(len(linked), len(inline))

    def test_standalone_bundle_rejects_link(self):
        r = subprocess.run([sys.executable, str(ROOT / 'wfyaml.py'), '--bundle-standalone',
                            '--assets', 'link', '--mockup', 'th.yaml', 'p.wf.yaml'],
                           cwd=self.d, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn('互斥', r.stderr)

    def test_unknown_mode_is_rejected(self):
        r, _ = self._render('--assets', 'whatever')
        self.assertEqual(r.returncode, 2)


if __name__ == '__main__':
    unittest.main()
