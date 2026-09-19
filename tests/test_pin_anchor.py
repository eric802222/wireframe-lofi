"""pin 的錨點檢查。

浮層的定位盒子錨在最近的 `.wf-box` / `.wf-root` 上。父容器不是 box 時，浮層會飄到
更外層去 —— 不報錯、不退化，就只是位置不對（實測：圖片角標會跑到整頁左上角）。

Compose 用 scope safety 在編譯期擋下同類問題（`align` 只存在於 BoxScope，他們明講
是為了避免舊 View 系統那種「試到對為止」）。我們沒有編譯期，用 lint 講一聲。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfyaml as wf          # noqa: E402

WARN = 'pin 的父容器不是錨點'


class PinAnchorWarning(unittest.TestCase):

    def _lint(self, body, kit=None):
        with tempfile.TemporaryDirectory() as d:
            if kit:
                os.makedirs(os.path.join(d, 'kit'), exist_ok=True)
                kp = os.path.join(d, 'kit', 'components.yaml')
                open(kp, 'w', encoding='utf-8').write(kit)
                wf._load_kit(kp, explicit=True)
            p = os.path.join(d, 'p.wf.yaml')
            open(p, 'w', encoding='utf-8').write('viewport: 390x600\nbody:\n' + body)
            return wf._lint_file(p)

    def tearDown(self):
        wf._load_kit(None)

    def test_pin_without_box_parent_warns(self):
        err, warn = self._lint('  - col:\n      - image: { label: 照片 }\n'
                               '      - { status.badge: "1", pin: top-right }\n')
        self.assertEqual(err, 0)
        self.assertGreaterEqual(warn, 1)

    def test_pin_with_box_parent_is_silent(self):
        err, warn = self._lint('  - col:\n      - image: { label: 照片 }\n'
                               '      - { status.badge: "1", pin: top-right }\n    box: true\n')
        self.assertEqual((err, warn), (0, 0))

    def test_screen_level_overlays_are_silent(self):
        # modal / sugar / 直接掛在 body 上的 pin 本來就錨在整個畫面
        for body in ('  - { text: 提示, pin: bottom, modal: true }\n',
                     '  - toast: 已儲存\n',
                     '  - { text: 底部列, pin: bottom }\n'):
            err, warn = self._lint(body)
            self.assertEqual((err, warn), (0, 0), body)

    def test_pin_inside_kit_component_is_checked(self):
        # 元件寫一次、用在十個畫面，錨點錯誤影響面更大，但走訪畫面樹時看不到元件內部
        kit = ('components:\n  bad-tile:\n    props: [label]\n    content:\n'
               '      - col:\n          - image: { label: "{{label}}" }\n'
               '          - { status.badge: "1", pin: top-right }\n')
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'kit'))
            kp = os.path.join(d, 'kit', 'components.yaml')
            open(kp, 'w', encoding='utf-8').write(kit)
            wf._load_kit(kp, explicit=True)
            err, warn = wf._lint_kit_components(kp)
            self.assertEqual(err, 0)
            self.assertGreaterEqual(warn, 1)


if __name__ == '__main__':
    unittest.main()
