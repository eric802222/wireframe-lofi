import contextlib
import io
import tempfile
import unittest
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfyaml as wf


class KitComponents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        wf._load_theme(None)
        wf._load_kit(None)
        wf._STRICT_KIT = False

    def tearDown(self):
        wf._STRICT_KIT = False
        wf._load_theme(None)
        wf._load_kit(None)
        self.tmp.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def kit(self):
        return self.write('kit/components.yaml', '''components:
  jumbo-button:
    of: button
  stamp-card:
    props: [place, time]
    states: [done, next, todo]
    content:
      - col:
          - {icon: star}
          - "text.hint: {{time}}"
          - "text.strong: {{place}}"
        box: true
''')

    def test_specialization_composition_state_and_debug_path(self):
        self.kit()
        src = '''body:
  - jumbo-button: {text: 開始冒險, to: next}
  - stamp-card: {place: 渡月橋, time: "11:08", state: next}
'''
        html = wf.compile_all(src, str(self.root), 'page', debug=True)[0][1]
        self.assertIn('class="wf-btn', html)
        self.assertIn('開始冒險', html)
        self.assertIn('wf-role-jumbo-button', html)
        self.assertIn('data-wf-role="stamp-card"', html)
        self.assertIn('data-kit-state="next"', html)
        self.assertIn('渡月橋', html)
        self.assertIn('11:08', html)
        self.assertIn('data-wf-path="body[1]"', html)
        self.assertNotIn('{{', html)

    def test_theme_owns_style_and_state_uses_tokens(self):
        kit = self.kit()
        wf._load_kit(str(kit), explicit=True)
        theme = self.write('theme.yaml', '''tokens:
  color: {surface: '#fff', brand-soft: '#fdd'}
  border: {strong: '2px solid #222'}
  space: {md: 14px, xl: 50px}
  size: {jumbo: 88px}
components:
  jumbo-button: {padding: '{space.xl}', min-height: '{size.jumbo}'}
  stamp-card:
    background: '{color.surface}'
    border: '{border.strong}'
    state.next: {box-shadow: '0 0 0 {space.md} {color.brand-soft}'}
''')
        wf._load_theme(str(theme))
        css = wf._theme_css()
        self.assertIn('.wf-role-jumbo-button{', css)
        self.assertIn('padding:var(--wf-space-xl, 50px)', css)
        self.assertIn('[data-kit-state="next"]', css)
        self.assertIn('var(--wf-brand-soft, #fdd)', css)

    def test_schema_props_state_unknown_and_kit_swap_errors(self):
        kit = self.kit()
        wf._load_kit(str(kit), explicit=True)
        bad = [
            'body: [{stamp-card: {place: A}}]',
            'body: [{stamp-card: {place: A, time: T, extra: X}}]',
            'body: [{stamp-card: {place: A, time: T, state: broken}}]',
            'body: [{missing-card: {place: A}}]',
        ]
        for i, source in enumerate(bad):
            page = self.write(f'bad{i}.wf.yaml', source)
            with contextlib.redirect_stderr(io.StringIO()):
                errors, _ = wf._lint_file(str(page))
            self.assertGreater(errors, 0, source)
        other = self.write('other.yaml', 'components: {other-card: {of: text}}')
        wf._load_kit(str(other), explicit=True)
        with contextlib.redirect_stderr(io.StringIO()):
            errors, _ = wf._lint_file(str(self.write('swap.wf.yaml', 'body: [{stamp-card: {place: A, time: T}}]')))
        self.assertGreater(errors, 0)

    def test_kit_cannot_style_and_theme_literals_are_errors(self):
        for body in (
            'components: {bad: {of: button, style: {padding: 50px}}}',
            'components: {bad: {of: missing}}',
        ):
            with self.assertRaises(ValueError):
                wf._load_kit(str(self.write('bad-kit.yaml', body)), explicit=True)
        wf._load_kit(str(self.write('valid-kit.yaml', 'components: {jumbo-button: {of: button}}')), explicit=True)
        for value in ('50px', '#B85A3C'):
            theme = self.write('bad-theme.yaml', f'components: {{jumbo-button: {{padding: "{value}"}}}}')
            with self.assertRaisesRegex(ValueError, 'tokens'):
                wf._load_theme(str(theme))
        missing = self.write('missing-token.yaml', '''tokens: {space: {md: 8px, xl: 32px}}
components: {jumbo-button: {padding: '{space.huge}'}}
''')
        with self.assertRaisesRegex(ValueError, r"space 可用：\['md', 'xl'\]"):
            wf._load_theme(str(missing))
        with self.assertRaisesRegex(ValueError, '未在 kit 宣告'):
            wf._load_theme(str(self.write('new-type.yaml', 'components: {invented-card: {padding: 0}}')))

    def test_strict_kit_rejects_leaf_widget_and_bare_box(self):
        self.kit()
        wf._STRICT_KIT = True
        page = self.write('strict.wf.yaml', '''body:
  - {text: 裸文字}
  - {box: true, items: [{text: 裸卡片}]}
  - {widget: {is: 地圖}}
  - {jumbo-button: {text: 合法}}
''')
        with contextlib.redirect_stderr(io.StringIO()):
            errors, _ = wf._lint_file(str(page))
        self.assertGreaterEqual(errors, 3)

    def test_duplicate_structure_info_needs_three_distinct_pages(self):
        files = []
        for name in ('a', 'b', 'c'):
            files.append(str(self.write(f'{name}.wf.yaml', 'body: [{box: true, col: [{text: A}, {button: Go}]}]')))
        capture = io.StringIO()
        with contextlib.redirect_stderr(capture):
            wf._duplicate_structure_info(files[:2])
        self.assertEqual(capture.getvalue(), '')
        with contextlib.redirect_stderr(capture):
            wf._duplicate_structure_info(files)
        self.assertIn('考慮抽進 kit', capture.getvalue())

    def test_cli_explicit_kit_and_strict_mode(self):
        kit = self.kit()
        good = self.write('good.wf.yaml', 'body: [{jumbo-button: {text: Go}}]')
        result = subprocess.run([sys.executable, str(ROOT / 'wfyaml.py'), 'lint', '--kit', str(kit),
                                 '--strict-kit', str(good)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        bare = self.write('bare.wf.yaml', 'body: [{button: Go}]')
        result = subprocess.run([sys.executable, str(ROOT / 'wfyaml.py'), 'lint', '--kit', str(kit),
                                 '--strict-kit', str(bare)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('strict-kit', result.stderr)


if __name__ == '__main__':
    unittest.main()
