import contextlib
import io
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfyaml as wf


class CanvasComponents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        wf._load_theme(None)
        wf._load_kit(None)

    def tearDown(self):
        wf._load_theme(None)
        wf._load_kit(None)
        self.tmp.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def kit(self, shape='smooth', anchors='', arrow=''):
        return self.write('kit/components.yaml', f'''components:
  stamp-card:
    props: [place, time]
    states: [done, next, todo]
    content:
      - col: [{{icon: star}}, "text.hint: {{{{time}}}}", "text.strong: {{{{place}}}}"]
        box: true
  trip-map:
    of: canvas
    base:
      asset: arashiyama
      ratio: 4/3
{anchors}    item: {{use: stamp-card}}
    link: {{shape: {shape}{arrow}}}
    states: [done, next, todo]
''')

    def theme(self):
        self.write('map.svg', '<svg viewBox="0 0 4 3"><rect width="4" height="3" fill="#ddd"/></svg>')
        return self.write('theme.yaml', '''assets: {arashiyama: map.svg}
tokens:
  color: {brand: '#b44', brand-soft: '#fdd', surface: '#eee'}
  stroke: {md: 4px, dash: '8 6'}
  space: {md: 8px}
components:
  trip-map:
    base: {background: '{color.surface}'}
    link: {stroke: '{color.brand}', stroke-width: '{stroke.md}', dash: true}
    item.state.next: {box-shadow: '0 0 0 {space.md} {color.brand-soft}'}
''')

    def page_source(self, first_at='[0.22, 0.83]', link='[竹林小徑, 渡月橋]'):
        return f'''body:
  - trip-map:
      items:
        - {{place: 竹林小徑, at: {first_at}, state: done, time: "08:40"}}
        - {{place: 渡月橋, at: [0.50, 0.42], state: next, to: next-page, time: "11:00"}}
      link: {link}
'''

    def test_canvas_uses_asset_html_items_and_only_link_svg_geometry(self):
        wf._load_kit(str(self.kit()), explicit=True)
        wf._load_theme(str(self.theme()))
        html = wf.compile_all(self.page_source(), str(self.root), 'map', debug=True)[0][1]
        self.assertIn('wf-role-trip-map', html)
        self.assertIn('wf-canvas-base-img', html)
        self.assertIn('data:image/svg+xml;base64,', html)
        self.assertEqual(html.count('<path'), 1)
        self.assertNotIn('<circle', html)
        self.assertIn('C 360 830 360 420 500 420', html)
        self.assertIn('wf-role-stamp-card', html)
        self.assertIn('data-kit-state="next"', html)
        self.assertIn('next-page.debug.html', html)
        self.assertIn('data-wf-path="body[0].trip-map.items[1]"', html)

    def test_canvas_theme_link_base_and_item_rules_remain_token_only(self):
        wf._load_kit(str(self.kit()), explicit=True)
        wf._load_theme(str(self.theme()))
        css = wf._theme_css()
        self.assertIn('.wf-role-trip-map .wf-canvas-base{background:var(--wf-surface, #eee)', css)
        self.assertIn('.wf-role-trip-map .wf-canvas-link{stroke:var(--wf-brand, #b44)', css)
        self.assertIn('stroke-dasharray:var(--wf-stroke-dash, 8 6)', css)
        self.assertIn('.wf-canvas-item[data-kit-state="next"]', css)

        literal = self.write('literal.yaml', '''assets: {arashiyama: map.svg}
components: {trip-map: {link: {stroke-width: 4px}}}
''')
        with self.assertRaisesRegex(ValueError, 'tokens'):
            wf._load_theme(str(literal))
        missing_dash = self.write('missing-dash.yaml', '''assets: {arashiyama: map.svg}
tokens: {color: {brand: '#b44'}}
components: {trip-map: {link: {stroke: '{color.brand}', dash: true}}}
''')
        with self.assertRaisesRegex(ValueError, 'tokens.stroke.dash'):
            wf._load_theme(str(missing_dash))

    def test_anchors_are_optional_and_links_resolve_semantic_values(self):
        anchors = '''      anchors:
        竹林小徑: [0.22, 0.83]
        渡月橋: [0.50, 0.42]
'''
        wf._load_kit(str(self.kit(shape='straight', anchors=anchors)), explicit=True)
        source = self.page_source(first_at='[0.22, 0.83]').replace(', at: [0.22, 0.83]', '').replace(', at: [0.50, 0.42]', '')
        html = wf.compile_all(source, str(self.root), 'map')[0][1]
        self.assertIn('L 500 420', html)
        self.assertIn('▧ arashiyama', html)

    def test_grid_and_blank_canvases_need_no_asset_or_link(self):
        kit = self.write('generic.yaml', '''components:
  seat-chip: {props: [seat], states: [free, taken], content: [{text: "{{seat}}"}]}
  seat-map:
    of: canvas
    base: {grid: true, ratio: 3/2}
    item: {use: seat-chip}
    states: [free, taken]
  note-board:
    of: canvas
    base: {blank: true, ratio: 1/1}
    item: {use: seat-chip}
    states: [free, taken]
''')
        wf._load_kit(str(kit), explicit=True)
        html = wf.compile_all('body: [{seat-map: {items: [{seat: A1, at: [0.2, 0.3], state: free}]}}]',
                              str(self.root), 'seat')[0][1]
        self.assertIn('wf-canvas-base-grid', html)
        self.assertNotIn('<svg class="wf-canvas-link-layer"', html)
        wf._load_theme(str(self.write('empty-theme.yaml', 'tokens: {}')))

    def test_arrow_is_link_geometry_and_uses_unique_marker_id(self):
        wf._load_kit(str(self.kit(arrow=', arrow: true')), explicit=True)
        html = wf.compile_all(self.page_source(), str(self.root), 'map')[0][1]
        self.assertEqual(html.count('<path'), 2)
        self.assertIn('marker-end="url(#wf-canvas-arrow-', html)
        self.assertIn('wf-canvas-link-arrow', html)

    def test_canvas_schema_and_page_values_fail_fast(self):
        bad_kits = (
            'components: {pin: {of: canvas, base: {asset: a}, item: {use: missing}}}',
            'components: {chip: {of: text}, pin: {of: canvas, base: {grid: false}, item: {use: chip}}}',
            'components: {chip: {of: text}, pin: {of: canvas, base: {blank: true}, item: {use: chip}, link: {shape: bent}}}',
        )
        for body in bad_kits:
            with self.assertRaises(ValueError):
                wf._load_kit(str(self.write('bad-kit.yaml', body)), explicit=True)

        wf._load_kit(str(self.kit()), explicit=True)
        invalid = (
            self.page_source(first_at='[1.2, 0.2]'),
            self.page_source().replace('state: done', 'state: lost'),
            self.page_source(link='[不存在, 渡月橋]'),
            self.page_source().replace(', at: [0.22, 0.83]', ''),
        )
        for i, source in enumerate(invalid):
            page = self.write(f'bad-{i}.wf.yaml', source)
            with contextlib.redirect_stderr(io.StringIO()):
                errors, _ = wf._lint_file(str(page))
            self.assertGreater(errors, 0, source)

    def test_mockup_requires_asset_mapping_but_missing_file_can_fallback(self):
        wf._load_kit(str(self.kit()), explicit=True)
        with self.assertRaisesRegex(ValueError, '未定義素材'):
            wf._load_theme(str(self.write('no-assets.yaml', 'tokens: {}')))
        capture = io.StringIO()
        with contextlib.redirect_stderr(capture):
            wf._load_theme(str(self.write('missing-file.yaml', 'assets: {arashiyama: missing.png}')))
        self.assertIn('使用佔位', capture.getvalue())


if __name__ == '__main__':
    unittest.main()
