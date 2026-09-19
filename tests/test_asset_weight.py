"""內嵌素材的體積警示。

素材以 base64 內嵌是刻意的：老闆 demo 要單檔可攜。人與瀏覽器沒差。
但 AI agent 整份讀進去就燒掉整個 context —— 實測一份 10 畫面的 bundle
3.39 MB、97% 是 base64（約 85 萬 token），而真正的內容只有 2.5 萬。
更糟的是那些位元組對 agent 毫無用處：它看不到圖。

所以編完就講一聲。文件擋得了讀 AGENTS.md 的 agent，擋不了沒讀的 —— 這行 note 擋得了。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfyaml as wf          # noqa: E402


class AssetWeightNote(unittest.TestCase):

    def _write(self, body):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'out.html')
        open(p, 'w', encoding='utf-8').write(body)
        return p

    def test_small_output_is_silent(self):
        self.assertEqual(wf._asset_weight_note(self._write('<html>' + 'x' * 1000)), '')

    def test_large_output_without_assets_is_silent(self):
        # 大而沒有內嵌素材 → 那是真的內容，不該勸人不要讀
        self.assertEqual(wf._asset_weight_note(self._write('<p>' + 'x' * 900_000)), '')

    def test_large_output_with_inlined_assets_warns(self):
        blob = 'data:image/png;base64,' + 'A' * 900_000
        note = wf._asset_weight_note(self._write(f'<img src="{blob}">'))
        self.assertIn('內嵌素材', note)
        self.assertIn('token', note)
        self.assertIn('.wf.yaml', note, '要指出便宜的替代做法，不能只說「不要讀」')


if __name__ == '__main__':
    unittest.main()
