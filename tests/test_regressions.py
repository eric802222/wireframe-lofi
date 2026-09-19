"""Run: python3 -m unittest discover -s tests -v (only PyYAML required)."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfyaml as wf


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        wf._load_theme(None)
        wf._TOKENS, wf._BUNDLE, wf._DEBUG, wf._STORY = {}, False, False, None

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = self.directory / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def lint(self, path):
        # _Diag.dump binds stderr at definition time; subprocess tests cover output.
        with contextlib.redirect_stderr(io.StringIO()):
            return wf._lint_file(str(path))

    def cli(self, *args, env=None):
        return subprocess.run([sys.executable, str(ROOT / 'wfyaml.py'), *map(str, args)],
                              capture_output=True, text=True,
                              env={**os.environ, 'WF_TRACEBACK': '', **(env or {})})

    def test_direction_dict_and_duplicate_items(self):
        for direction in ('row', 'col'):
            for value in ('{gap: sm, items: [{button: A}]}', '[{button: A}]\n    items: [{button: B}]'):
                with self.subTest(direction=direction, value=value):
                    p = self.write('bad.wf.yaml', f'body:\n  - {direction}: {value}\n')
                    self.assertGreater(self.lint(p)[0], 0)
                    self.assertEqual(self.cli('lint', p).returncode, 2)
                    with self.assertRaises(wf.AuthorError):
                        wf.compile_all(p.read_text(), str(self.directory), 'bad')

    def test_grid_tracks_and_items_are_legal(self):
        p = self.write('grid.wf.yaml', 'body:\n  - grid: [fit, grow]\n    items: [{text: A}, {text: B}]\n')
        self.assertEqual(self.lint(p), (0, 0))
        html = wf.compile_all(p.read_text(), str(self.directory), 'grid')[0][1]
        self.assertIn('grid-template-columns:auto 1fr', html)

    def test_unknown_leaf_role_is_error(self):
        p = self.write('bad.wf.yaml', 'body: [{buton: A}]')
        self.assertGreater(self.lint(p)[0], 0)

    def test_leaf_constraints_share_render_validation(self):
        for text in ('progress: 2', 'avatar: {size: huge}', 'icon: no-such-icon-xyz'):
            with self.subTest(text=text):
                p = self.write('bad.wf.yaml', 'body: [{' + text + '}]')
                self.assertGreater(self.lint(p)[0], 0)

    def test_missing_extends_and_embed(self):
        for text in ('extends: layouts/missing', 'body: [{embed: components/missing}]'):
            with self.subTest(text=text):
                p = self.write('bad.wf.yaml', text)
                self.assertEqual(self.lint(p)[0], 1)
                result = self.cli('lint', p)
                self.assertIn('找不到模板', result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_component_content_and_placeholder(self):
        for key in ('content', 'placeholder'):
            with self.subTest(key=key):
                component = self.write('components/bad.wf.yaml', f'{key}: [{{row: {{gap: sm, items: []}}}}]')
                page = self.write('page.wf.yaml', 'body: [{embed: components/bad}]')
                self.assertGreater(self.lint(component)[0], 0)
                result = self.cli('lint', page)
                self.assertEqual(result.returncode, 2)
                self.assertIn(str(component), result.stderr)
                self.assertIn(key + '[0]', result.stderr)

    def test_widget_body_list_and_mapping(self):
        for body in ('[{row: {gap: sm, items: []}}]', '{row: {gap: sm, items: []}}'):
            with self.subTest(body=body):
                p = self.write('bad.wf.yaml', 'body: [{widget: {is: table, body: ' + body + '}}]')
                self.assertGreater(self.lint(p)[0], 0)
                result = self.cli('--no-lint', p)
                self.assertEqual(result.returncode, 1)
                self.assertIn('body[0].widget.body', result.stderr)

    def test_nested_relative_components(self):
        self.write('components/nested/parent.wf.yaml', 'content: [{embed: child}]')
        self.write('components/nested/child.wf.yaml', 'content: [{text: nested child}]')
        p = self.write('page.wf.yaml', 'body: [{embed: components/nested/parent}]')
        self.assertEqual(self.lint(p), (0, 0))
        self.assertIn('nested child', wf.compile_all(p.read_text(), str(self.directory), 'page')[0][1])

    def test_layout_relative_component_and_page_slot_component(self):
        self.write('layouts/components/header.wf.yaml', 'content: [{text: layout header}]')
        self.write('layouts/base.wf.yaml', 'body: [{embed: components/header}, {slot: main}]')
        self.write('components/item.wf.yaml', 'content: [{text: page slot}]')
        p = self.write('page.wf.yaml', 'extends: layouts/base\nslots: {main: [{embed: components/item}]}')
        self.assertEqual(self.lint(p), (0, 0))
        html = wf.compile_all(p.read_text(), str(self.directory), 'page')[0][1]
        self.assertIn('layout header', html)
        self.assertIn('page slot', html)

    def test_reference_cycles_include_canonical_paths(self):
        self.write('components/a.wf.yaml', 'content: [{embed: b}]')
        self.write('components/b.wf.yaml', 'content: [{embed: ./a}]')
        p = self.write('page.wf.yaml', 'body: [{embed: components/a}]')
        result = self.cli('lint', p)
        self.assertEqual(result.returncode, 2)
        self.assertIn('循環引用', result.stderr)

    def test_layout_errors_have_source_and_path_without_lint(self):
        layout = self.write('layouts/base.wf.yaml', 'body: [{row: {items: []}}]')
        page = self.write('page.wf.yaml', 'extends: layouts/base\nslots: {}')
        result = self.cli('--no-lint', page)
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(layout), result.stderr)
        self.assertIn('body[0]', result.stderr)
        self.assertNotIn('Traceback (most recent call last)', result.stderr)

    def test_traceback_flag_and_environment(self):
        p = self.write('bad.wf.yaml', 'body: [{row: {items: []}}]')
        for args, env in ((['--traceback', '--no-lint', p], {}), (['--no-lint', p], {'WF_TRACEBACK': '1'})):
            with self.subTest(args=args):
                self.assertIn('Traceback (most recent call last)', self.cli(*args, env=env).stderr)

    def test_unexpected_exceptions_are_not_swallowed(self):
        def fail():
            raise RuntimeError('internal failure')
        with self.assertRaises(RuntimeError):
            wf.cli_entry(fail)

    def test_yaml_error_includes_line_column_and_quote_hint(self):
        p = self.write('bad.wf.yaml', 'body:\n  - row: ["11:12", 照片 ×3 · [N] MB, 等待中]')
        for args in (['lint', p], ['--no-lint', p]):
            result = self.cli(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('line 2', result.stderr)
            self.assertIn('column', result.stderr)
            self.assertIn('加引號', result.stderr)
            self.assertNotIn('Traceback (most recent call last)', result.stderr)

    def test_quoted_special_characters_preserve_values(self):
        p = self.write('page.wf.yaml', 'body: [{row: ["照片 · [N] MB", "檢視, 刪除", "備註: 待定", "編號 #1"]}]')
        self.assertEqual(self.lint(p), (0, 0))
        html = wf.compile_all(p.read_text(), str(self.directory), 'page')[0][1]
        for text in ('檢視, 刪除', '備註: 待定', '編號 #1'):
            self.assertIn(text, html)

    def test_placeholders_preserve_links_and_checkboxes(self):
        rendered = wf.inline('[金額] [金額] [官方](https://example.com/[id]) [x] [ ]')
        self.assertEqual(rendered.count('class="wf-placeholder"'), 2)
        self.assertIn('href="https://example.com/[id]"', rendered)
        self.assertEqual(wf._placeholder_count('[金額] [金額] [官方](https://example.com/[id]) [x] [ ]'), 2)
        self.assertEqual(wf._placeholder_count(r'\[金額]'), 0)
        self.assertNotIn('wf-placeholder', wf.render_string('[x] 已同意'))

    def test_placeholder_count_is_informational_and_source_based(self):
        component = self.write('components/item.wf.yaml', 'content: [{text: "[金額]"}]')
        p = self.write('page.wf.yaml', 'body: [{text: "[旅伴]"}, {embed: components/item}, {embed: components/item}]')
        result = self.cli('lint', p)
        self.assertEqual(result.returncode, 0)
        self.assertIn(str(component) + ' → 1 個未定值', result.stderr)
        self.assertIn(str(p) + ' → 1 個未定值', result.stderr)
        self.assertEqual(result.stderr.count(str(component) + ' → 1 個未定值'), 1)

    def test_placeholder_rendering_in_input_image_and_avatar(self):
        for role in ('input', 'image', 'avatar'):
            with self.subTest(role=role):
                html = wf.render_leaf({role: '[待定]'}, [], {})
                if role == 'input':
                    # input 現在是真的 <input>：未定值落在 placeholder 屬性，
                    # 沒有虛線底線的視覺標記（取捨：換得可打字）
                    self.assertIn('placeholder="[待定]"', html)
                else:
                    self.assertIn('wf-placeholder', html)

    def test_bundle_titles_groups_and_stable_ids(self):
        files = [self.write('a.wf.yaml', 'title: 首頁\ngroup: 旅行\nbody: [{button: 行程, to: b}]'),
                 self.write('b.wf.yaml', 'title: 行程\ngroup: 業務\nbody: [{text: B}]'),
                 self.write('c.wf.yaml', 'title: 成員\ngroup: 旅行\nbody: [{text: C}]')]
        html = wf.bundle(list(map(str, files)))
        self.assertIn('<h2>旅行</h2>', html)
        self.assertIn('id="nav-wf-pg-a">首頁</a>', html)
        self.assertIn('href="#wf-pg-b"', html)
        self.assertLess(html.index('id="nav-wf-pg-c"'), html.index('<h2>業務</h2>'))
        for p in files:
            self.assertEqual(self.lint(p), (0, 0))

    def test_bundle_without_meta_and_route_labels(self):
        p = self.write('page.wf.yaml', 'title: 中文頁名\nroutes: [{default: true, body: [{text: A}]}, {when: {stage: approved}, body: [{text: B}]}]')
        html = wf.bundle([str(p)])
        self.assertIn('<b>中文頁名</b>', html)
        self.assertIn('id="nav-wf-pg-page">default</a>', html)
        self.assertIn('id="nav-wf-pg-page-approved">approved</a>', html)
        plain = self.write('plain.wf.yaml', 'body: [{text: A}]')
        self.assertIn('<b>plain</b>', wf.bundle([str(plain)]))

    def test_bundle_does_not_leak_link_mode_to_single_page(self):
        p = self.write('page.wf.yaml', 'body: [{button: B, to: next}]')
        wf.bundle([str(p)])
        html = wf.compile_all(p.read_text(), str(self.directory), 'page')[0][1]
        self.assertIn('href="next.html"', html)

    def test_standalone_all_internal_link_forms_and_external_links(self):
        from html.parser import HTMLParser

        class Elements(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags = []

            def handle_starttag(self, tag, attrs):
                self.tags.append((tag, dict(attrs)))

        a = self.write('a.wf.yaml', """title: 首頁
group: App
body:
  - button: 按鈕
    to: b
  - row: [{text: 卡片}]
    to: b
  - text: '[文字動線](to:b) · [真連結](https://example.com)'
  - link: {text: 外部, to: 'https://example.org'}
""")
        b = self.write('b.wf.yaml', 'body: [{text: B}]')
        html = wf.bundle([str(a), str(b)], standalone=True)
        elements = Elements()
        elements.feed(html)
        anchors = [attr for tag, attr in elements.tags if tag == 'a']
        self.assertEqual({a['href'] for a in anchors}, {'https://example.com', 'https://example.org'})
        radios = [a for t, a in elements.tags if t == 'input' and a.get('name') == 'wfpg']
        self.assertEqual(len(radios), 5)
        self.assertEqual(len({r['id'] for r in radios}), 5)
        self.assertEqual([r['value'] for r in radios if 'checked' in r], ['wf-pg-a'])
        self.assertTrue(all(r['type'] == 'radio' and r['aria-controls'] == r['value'] for r in radios))
        self.assertNotIn('<script>', html)
        # Switching output mode in the same process must not retain radio links.
        normal = wf.bundle([str(a), str(b)])
        self.assertIn('href="#wf-pg-b"', normal)
        self.assertNotIn('name="wfpg"', normal)
        single = wf.compile_all(a.read_text(), str(self.directory), 'a')[0][1]
        self.assertIn('href="b.html"', single)

    def test_standalone_cli_implies_bundle_and_accepts_debug(self):
        a = self.write('a.wf.yaml', 'body: [{button: Next, to: b}]')
        b = self.write('b.wf.yaml', 'body: [{text: B}]')
        out = self.directory / 'standalone.html'
        for flags in (('--bundle-standalone',), ('--bundle', '--bundle-standalone', '--debug')):
            result = self.cli(*flags, '-o', out, a, b)
            self.assertEqual(result.returncode, 0, result.stderr)
            html = out.read_text()
            self.assertIn('wf-radio-nav', html)
            self.assertNotIn('href="#wf-pg-', html)
            self.assertEqual('<script>' in html, '--debug' in flags)

    def test_standalone_story_nav_and_flow(self):
        a = self.write('a.wf.yaml', 'body: [{button: Next, name: next, to: b}]')
        b = self.write('b.wf.yaml', 'body: [{text: B}]')
        story = self.write('review.story.yaml', """story: review
page: a
flow:
  - step: 1
    target: next
    desc: 前往下一頁
    to: b
""")
        html = wf.bundle([str(a), str(b)], story=str(story), standalone=True)
        self.assertIn('id="nav-wf-pg-story-review"', html)
        self.assertIn('class="wf-story-step wf-story-step-pin wf-radio-link"', html)
        self.assertNotIn('href="#wf-pg-', html)

    def test_metadata_validation(self):
        for key in ('title', 'group'):
            p = self.write('bad.wf.yaml', f'{key}: [not, text]\nbody: []')
            self.assertGreater(self.lint(p)[0], 0)

    def test_theme_inverse_uses_shared_color_token(self):
        p = self.write('theme.yaml', 'tokens: {color: {inverse: "#fafafa"}}\nbindings: {input: {background: inverse, text: inverse}}')
        wf._load_theme(str(p))
        css = wf._theme_css()
        self.assertIn('--wf-inverse:#fafafa', css)
        self.assertIn('background:var(--wf-inverse,#ffffff)', css)
        self.assertIn('color:var(--wf-inverse,#ffffff)', css)

    def test_theme_radius_tokens_and_bindings(self):
        p = self.write('theme.yaml', 'tokens: {radius: {lg: 16px}}\nbindings: {box: {radius: lg}}')
        wf._load_theme(str(p))
        css = wf._theme_css()
        self.assertIn('--wf-radius-lg:16px', css)
        self.assertIn('border-radius:var(--wf-radius-lg,12px)', css)

    def test_theme_radius_error_is_actionable(self):
        theme = self.write('theme.yaml', 'bindings: {box: {radius: 16px}}')
        page = self.write('page.wf.yaml', 'body: [{text: A}]')
        result = self.cli('--mockup', theme, page)
        self.assertEqual(result.returncode, 1)
        for text in ('bindings.box.radius', 'tokens.radius.lg', '16px', str(theme)):
            self.assertIn(text, result.stderr)

    def test_theme_l3_refs_presets_components_and_legacy_aliases(self):
        theme = self.write('l3.yaml', """tokens:
  color:
    brand: {$value: '#123456'}
    accent: '{color.brand}'
  space: {custom: 13px}
  opacity: {hover: 0.8}
  preset:
    panel: {color: '{color.accent}', padding: '{space.custom}'}
components:
  box:
    apply: [panel]
    states: {selected: {background: '{color.brand}'}, hover: {opacity: '{opacity.hover}'}}
bindings:
  chosen: {text: '{color.brand}', radius: '{space.custom}', padding: '{space.custom}'}
""")
        wf._load_theme(str(theme))
        css = wf._theme_css()
        for value in ('--wf-brand:#123456', 'padding:var(--wf-space-custom, 13px)',
                      'color:var(--wf-brand, #123456)', 'border-radius:var(--wf-space-custom, 13px)',
                      'opacity:var(--wf-opacity-hover, 0.8)', '[data-ui-state="selected"]', '[data-ui-state="hover"]'):
            self.assertIn(value, css)
        self.assertNotIn('--wf-preset', css)
        wf._load_theme(None)
        self.assertEqual(wf._theme_css(), '')

    def test_theme_l3_reference_errors(self):
        for tokens in ('color: {a: "{color.b}", b: "{color.a}"}', 'color: {a: "{color.missing}"}'):
            theme = self.write('bad-theme.yaml', 'tokens: {' + tokens + '}')
            with self.assertRaises(ValueError):
                wf._load_theme(str(theme))

    def test_collapsible_ui_state_and_grid_links_in_both_modes(self):
        from html.parser import HTMLParser

        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'wf-blocklink-a' in attrs.get('class', ''):
                    self.links.append(attrs)

        a = self.write('menu.wf.yaml', """body:
  - col: [{text: 可收合內容}]
    collapsible: 選單
    expanded: true
    ui-state: selected
  - grid: [grow, grow]
    items:
      - col: [{text: 跨欄卡片}]
        span: 2
        to: next
""")
        b = self.write('next.wf.yaml', 'body: [{text: Next}]')
        self.assertEqual(self.lint(a), (0, 0))
        for mode in (False, True):
            html = wf.bundle([str(a), str(b)], standalone=mode)
            self.assertIn('<details class="wf-collapsible" open', html)
            self.assertIn('data-ui-state="selected"', html)
            parser = Links()
            parser.feed(html)
            self.assertEqual(parser.links[0]['style'], 'grid-column:span 2')

    def test_avatar_group_counts_overflow_and_all_boundaries(self):
        for members, visible, overflow in (([], 0, None), (['我'], 1, None), (['我', '伴', '友'], 3, None), (['我', '伴', '友', '家', '同'], 4, '+2')):
            with self.subTest(members=members):
                html = wf.render_leaf({'avatars': {'items': members, 'max': 3}}, [], {})
                self.assertEqual(html.count('class="wf-avatar wf-avatar-md"'), visible)
                if overflow:
                    self.assertIn(overflow, html)
        p = self.write('page.wf.yaml', 'body: [{avatars: {items: [我, 伴, 友, 家], max: 3}}]')
        self.assertEqual(self.lint(p), (0, 0))

    def test_invalid_avatar_groups_are_lint_errors(self):
        for value in ('{items: [我], max: 0}', '{items: x}', '{items: [我], max: true}', '{items: [我, {src: x}], max: 1}'):
            p = self.write('bad.wf.yaml', 'body: [{avatars: ' + value + '}]')
            self.assertGreater(self.lint(p)[0], 0)

    def test_map_is_widget_with_capabilities_and_markers(self):
        p = self.write('page.wf.yaml', 'body: [{map: {label: 今日路線, markers: [飯店, 車站]}}]')
        self.assertEqual(self.lint(p), (0, 0))
        html = wf.compile_all(p.read_text(), str(self.directory), 'page')[0][1]
        for text in ('wf-map', '◫ 示意', '今日路線', 'markers', '⊙ 飯店', '⊙ 車站'):
            self.assertIn(text, html)
        self.assertNotIn('<script>', html)

    def test_invalid_map_values_are_lint_errors(self):
        for value in ('{markers: x}', '{markers: [1]}', '{can: x}', '{src: https://example.com}'):
            p = self.write('bad.wf.yaml', 'body: [{map: ' + value + '}]')
            self.assertGreater(self.lint(p)[0], 0)

    def test_project_overlay_token_in_referenced_component(self):
        self.write('wf.tokens.yaml', 'overlay: {banner: {pin: top, layer: notify}}')
        self.write('components/item.wf.yaml', 'content: [{banner: [{text: Hello}]}]')
        p = self.write('page.wf.yaml', 'body: [{embed: components/item}]')
        self.assertEqual(self.lint(p), (0, 0))

    def test_parameterized_component_leaf_values(self):
        component = self.write('components/item.wf.yaml', 'content: [{avatar: {label: "{{name}}", size: "{{size}}"}}]')
        self.assertEqual(self.lint(component), (0, 0))
        p = self.write('page.wf.yaml', 'body: [{embed: components/item, with: {name: 我, size: sm}}]')
        self.assertEqual(self.lint(p), (0, 0))
        html = wf.compile_all(p.read_text(), str(self.directory), 'page')[0][1]
        self.assertIn('wf-avatar-sm', html)
        self.assertIn('>我</div>', html)

    def test_missing_required_component_parameter_is_error(self):
        self.write('components/item.wf.yaml', 'content: [{avatar: {size: "{{size}}"}}]')
        page = self.write('page.wf.yaml', 'body: [{embed: components/item}]')
        self.assertGreater(self.lint(page)[0], 0)

    def test_layout_parameters_supplied_by_routes(self):
        self.write('layouts/base.wf.yaml', 'body: [{avatar: {label: 我, size: "{{size}}"}}]')
        page = self.write('page.wf.yaml', 'extends: layouts/base\nroutes: [{default: true, with: {size: sm}}, {when: {stage: approved}, with: {size: lg}}]')
        self.assertEqual(self.lint(page), (0, 0))
        results = wf.compile_all(page.read_text(), str(self.directory), 'page')
        self.assertIn('wf-avatar-sm', results[0][1])
        self.assertIn('wf-avatar-lg', results[1][1])

    def test_parameter_substitution_preserves_unknown_parameters(self):
        self.assertEqual(wf._subst('Hello {{name}} / {{unknown}}', {'name': '我'}), 'Hello 我 / {{unknown}}')

    def test_conditional_unknown_leaf_is_not_skipped(self):
        p = self.write('bad.wf.yaml', 'body: [{when: {state: pending}, buton: A}]')
        self.assertGreater(self.lint(p)[0], 0)

    def test_invalid_top_level_shapes_are_errors(self):
        for key, value in (('slots', '[]'), ('with', '[]'), ('routes', '{}')):
            p = self.write('bad.wf.yaml', f'{key}: {value}\nbody: []')
            self.assertGreater(self.lint(p)[0], 0)

    def test_all_official_examples_lint_and_compile(self):
        files = sorted((ROOT / 'examples').rglob('*.wf.yaml'))
        self.assertGreaterEqual(len(files), 10)
        for p in files:
            with self.subTest(path=p):
                self.assertEqual(self.lint(p), (0, 0))
                if 'layouts' not in p.parts and 'components' not in p.parts:
                    results = wf.compile_all(p.read_text(), str(p.parent), p.name.replace('.wf.yaml', ''))
                    self.assertTrue(results)
                    self.assertTrue(all('<script>' not in h for _, h in results))
        wf._load_theme(str(ROOT / 'examples/themes/inverse.yaml'))
        wf._theme_css()


if __name__ == '__main__':
    unittest.main()


class InteractiveFormTests(unittest.TestCase):
    """表單葉子渲染成真的 HTML 控制項：互動由瀏覽器原生提供，仍零 JS。"""

    def test_input_is_a_real_input(self):
        html = wf.render_leaf({'input': {'placeholder': '打一句', 'value': '已填'}}, [], {})
        self.assertTrue(html.startswith('<input '))
        self.assertIn('value="已填"', html)
        self.assertIn('placeholder="打一句"', html)

    def test_select_is_a_real_select_with_options(self):
        html = wf.render_leaf({'select': {'text': '台北', 'options': ['台北', '台中']}}, [], {})
        self.assertTrue(html.startswith('<select '))
        self.assertIn('<option>台北</option>', html)
        self.assertIn('<option>台中</option>', html)

    def test_choice_has_native_input_and_label(self):
        html = wf.render_leaf({'checkbox': {'label': '同意', 'checked': True}}, [], {})
        self.assertIn('type="checkbox" checked', html)
        self.assertIn('<label class="wf-choice-label"', html)   # 點文字也能勾

    def test_radio_group_shares_name(self):
        a = wf.render_leaf({'radio': {'label': '郵寄', 'group': '收件'}}, [], {})
        b = wf.render_leaf({'radio': {'label': '電子', 'group': '收件'}}, [], {})
        self.assertIn('name="收件"', a)
        self.assertIn('name="收件"', b)                          # 同組互斥

    def test_reveals_emits_css_only_rule(self):
        wf._REVEAL_RULES.clear()
        wf.render_leaf({'checkbox': {'label': '我要收據', 'reveals': '發票欄位'}}, [], {})
        css = wf._reveal_css()
        self.assertIn(':not(:checked)', css)
        self.assertIn('[data-name="發票欄位"]', css)
        self.assertIn('display:none', css)

    def test_choice_rejects_unknown_key(self):
        with self.assertRaises(ValueError):
            wf.render_leaf({'checkbox': {'label': 'x', 'onClick': 'doThing()'}}, [], {})


class SectionTests(unittest.TestCase):
    """section：帶語義的一段（SDUI 的 ViewLayout → Section → Component 中間層）。"""

    def test_section_renders_as_named_container(self):
        html = wf.render_item({'section': '今日路線', 'body': [{'text': '內容'}]})
        self.assertIn('data-section="今日路線"', html)
        self.assertIn('wf-section', html)
        self.assertIn('data-name="今日路線"', html)      # 同時可被 theme 綁定
        self.assertIn('內容', html)

    def test_section_label_is_not_rendered_text(self):
        """段名是語義標記，不自動變成畫面上的標題（要顯示就自己寫 text.heading）。"""
        html = wf.render_item({'section': '快速紀錄', 'body': [{'text': '內容'}]})
        self.assertNotIn('>快速紀錄<', html)

    def test_collapsed_section_uses_native_details(self):
        html = wf.render_item({'section': '快速紀錄', 'collapsed': True,
                               'body': [{'text': '內容'}]})
        self.assertIn('<details', html)                  # 零 JS 可展開
        self.assertIn('<summary class="wf-summary">快速紀錄</summary>', html)

    def test_section_requires_body_list(self):
        with self.assertRaises(ValueError):
            wf.render_item({'section': '沒有內容'})


class SectionExpansionTests(unittest.TestCase):
    """section 的 body 也要被 expand 走訪，否則藏在裡面的 kit 元件／embed 會靜默失效。"""

    KIT = """
components:
  metric-card:
    props: [label, value]
    content:
      - col: [ "text.hint: {{label}}", "text.title: {{value}}" ]
        box: true
"""

    def test_kit_component_inside_section_expands(self):
        with tempfile.TemporaryDirectory() as d:
            kit = os.path.join(d, 'kit.yaml')
            page = os.path.join(d, 'p.wf.yaml')
            open(kit, 'w', encoding='utf-8').write(self.KIT)
            open(page, 'w', encoding='utf-8').write(
                'viewport: 390x600\nbody:\n'
                '  - section: 指標\n'
                '    body:\n'
                '      - metric-card: {label: 待處理, value: "128"}\n')
            wf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'wfyaml.py')
            proc = subprocess.run([sys.executable, wf_path, '--kit', kit, page],
                                  capture_output=True, text=True, cwd=d)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            html = open(os.path.join(d, 'p.html'), encoding='utf-8').read()
            self.assertIn('待處理', html)
            self.assertIn('data-wf-role="metric-card"', html)


class LeafSiblingKeyTypos(unittest.TestCase):
    """葉子的 sibling 屬性打錯字要出聲：leaf 的「值」有 shape，掛在旁邊的屬性沒人管。"""

    def _lint(self, body):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'p.wf.yaml')
            open(p, 'w', encoding='utf-8').write('viewport: 390x600\nbody:\n' + body)
            return wf._lint_file(p)

    def test_typo_on_leaf_sibling_warns(self):
        err, warn = self._lint('  - text: 內容\n    gorw: true\n')
        self.assertEqual(err, 0)
        self.assertGreaterEqual(warn, 1, '`gorw` 會被靜默丟掉，必須出聲')

    def test_real_sibling_attributes_stay_silent(self):
        err, warn = self._lint('  - text: 內容\n    grow: true\n    name: 標題\n    to: other\n')
        self.assertEqual((err, warn), (0, 0), '合法 sibling 不該誤報')


class LinkRoleMisuse(unittest.TestCase):
    """`link:` 的 to: 原樣輸出成 href；拿它寫站內導航會得到死連結，且全程無聲。"""

    def _lint(self, body):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'p.wf.yaml')
            open(p, 'w', encoding='utf-8').write('viewport: 390x600\nbody:\n' + body)
            return wf._lint_file(p)

    def test_internal_target_on_link_warns(self):
        err, warn = self._lint('  - link: { text: 取消, to: feed }\n')
        self.assertEqual(err, 0)
        self.assertGreaterEqual(warn, 1)

    def test_real_external_urls_stay_silent(self):
        for url in ('https://example.com', 'mailto:a@b.c', '#top'):
            err, warn = self._lint(f'  - link: {{ text: 連結, to: "{url}" }}\n')
            self.assertEqual((err, warn), (0, 0), url)
