"""wfexport.py：tokens → DTCG，types → 型別契約，import → 回到書寫形式。

不改動 wfyaml.py 的行為。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT = os.path.join(ROOT, 'wfexport.py')

THEME = """
tokens:
  color:  { brand: '#B85A3C', surface: '#FBF7EE', link: '{color.brand}' }
  space:  { sm: 6px, lg: 1.25rem }
  font:   { body: "'Inter',sans-serif", weight: 700 }
  opacity: { faded: 0.5 }
  motion: { fast: 150ms, slow: 1.5s, spring: [0.34, 1.56, 0.64, 1] }
  shadow: { md: '0 4px 0 #2B2A33' }
  misc:   { gradient: 'linear-gradient(#fff, #000)' }
  preset: { card: { padding: '{space.sm}' } }
"""

KIT = """
components:
  stamp-card:
    props: [place, time, visits, tone]
    states: [done, next, todo]
    content:
      - col: [ "text.strong: {{place}}" ]
        box: true
  jumbo-button:
    of: button
  back-bar:
    props: [to, text]
    content:
      - col: [ "text: {{text}}" ]
"""

TYPES_MAP = "stamp-card: { visits: number, tone: [info, warn] }\n"


def write(tmp, name, text):
    path = os.path.join(tmp, name)
    open(path, 'w', encoding='utf-8').write(text)
    return path


def run(*args, cwd=ROOT):
    return subprocess.run([sys.executable, EXPORT, *args], capture_output=True, text=True, cwd=cwd)


class TokensTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.theme = write(self.tmp, 'theme.yaml', THEME)

    def test_dtcg_types(self):
        out = json.loads(run('tokens', self.theme).stdout)
        self.assertEqual(out['color']['$type'], 'color')            # 同型家族：$type 提到群組層
        self.assertEqual(out['space']['sm']['$value'], {'value': 6, 'unit': 'px'})
        self.assertEqual(out['space']['lg']['$value'], {'value': 1.25, 'unit': 'rem'})
        self.assertEqual(out['font']['body']['$type'], 'fontFamily')
        self.assertEqual(out['font']['weight']['$type'], 'fontWeight')
        self.assertEqual(out['opacity']['$type'], 'number')
        self.assertEqual(out['motion']['fast']['$value'], {'value': 150, 'unit': 'ms'})
        self.assertEqual(out['motion']['spring']['$type'], 'cubicBezier')

    def test_alias_kept_without_type(self):
        link = json.loads(run('tokens', self.theme).stdout)['color']['link']
        self.assertEqual(link['$value'], '{color.brand}')            # DTCG 同語法，原樣保留
        self.assertNotIn('$type', link)

    def test_preset_not_exported(self):
        self.assertNotIn('preset', json.loads(run('tokens', self.theme).stdout))

    def test_unmappable_skipped_with_reason(self):
        proc = run('tokens', self.theme)
        out = json.loads(proc.stdout)
        self.assertIn('shadow', out)                              # 複合型已支援
        self.assertNotIn('misc', out)                             # 沒有對應型別的才略過
        self.assertIn('tokens.misc.gradient 未匯出', proc.stderr)

    def test_rejects_non_dtcg_unit(self):
        theme = write(self.tmp, 'bad.yaml', "tokens:\n  space: { md: 2em }\n")
        proc = run('tokens', theme)
        self.assertEqual(proc.stdout.strip(), '{}')
        self.assertIn('只支援 px / rem', proc.stderr)

    def test_rejects_bad_cubic_bezier(self):
        theme = write(self.tmp, 'bez.yaml', "tokens:\n  motion: { bad: [1.5, 0, 1, 1] }\n")
        self.assertIn('x 座標', run('tokens', theme).stderr)

    def test_css_format(self):
        css = run('tokens', self.theme, '--format', 'css').stdout
        self.assertIn('--wf-brand: #B85A3C;', css)
        self.assertIn('--wf-motion-spring: cubic-bezier(0.34, 1.56, 0.64, 1);', css)
        self.assertIn('var(--wf-brand', css)                          # 別名編成 var()
        self.assertNotIn('wf-gutter', css)                            # 不夾帶線框機制的規則

    def test_ts_format(self):
        ts = run('tokens', self.theme, '--format', 'ts').stdout
        self.assertIn('"color.link": "#B85A3C"', ts)                  # 別名已解析
        self.assertIn('"motion.spring": [0.34, 1.56, 0.64, 1]', ts)
        self.assertIn('export type TokenName', ts)

    def test_unknown_format(self):
        proc = run('tokens', self.theme, '--format', 'scss')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('--format', proc.stderr)


class TypesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.kit = write(self.tmp, 'kit.yaml', KIT)
        self.map = write(self.tmp, 'map.yaml', TYPES_MAP)

    def test_untyped_props_are_strings(self):
        ts = run('types', self.kit).stdout
        self.assertIn('export type StampCardProps = {', ts)
        self.assertIn('place: string;', ts)
        self.assertIn('state?: "done" | "next" | "todo";', ts)

    def test_types_map_applies(self):
        ts = run('types', self.kit, '--types-map', self.map).stdout
        self.assertIn('visits: number;', ts)
        self.assertIn('tone: "info" | "warn";', ts)

    def test_own_to_prop_not_duplicated(self):
        ts = run('types', self.kit).stdout
        back = ts[ts.index('export type BackBarProps'):]
        back = back[:back.index('};')]
        self.assertIn('to: string;', back)
        self.assertNotIn('to?: string', back)

    def test_generated_header(self):
        self.assertIn('do not edit', run('types', self.kit).stdout)

    def test_json_format(self):
        out = json.loads(run('types', self.kit, '--format', 'json',
                             '--types-map', self.map).stdout)
        self.assertEqual(out['stamp-card']['props']['visits'], 'number')
        self.assertEqual(out['stamp-card']['states'], ['done', 'next', 'todo'])
        self.assertEqual(out['jumbo-button']['of'], 'button')

    def test_rejects_unknown_prop_type(self):
        bad = write(self.tmp, 'bad.yaml', "stamp-card: { visits: shape }\n")
        proc = run('types', self.kit, '--types-map', bad)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('型別只接', proc.stderr)

    def test_rejects_unknown_prop_name(self):
        bad = write(self.tmp, 'ghost.yaml', "stamp-card: { nope: number }\n")
        self.assertIn('不存在的 props', run('types', self.kit, '--types-map', bad).stderr)

    def test_rejects_unknown_component(self):
        bad = write(self.tmp, 'ghost2.yaml', "no-such: { a: number }\n")
        self.assertIn('沒有的元件', run('types', self.kit, '--types-map', bad).stderr)


class KitContextTest(unittest.TestCase):
    """theme 若含 kit 元件（canvas 等）的 components 規則，tokens 匯出需要同一份 kit。"""

    KIT = """
components:
  trip-map:
    of: canvas
    base: {grid: true}
    item: {use: pin}
    link: {shape: smooth}
    states: [done, todo]
  pin:
    props: [place]
    content:
      - col: [ "text.strong: {{place}}" ]
"""
    THEME = """
tokens:
  color:  { brand: '#7c3aed', brand-soft: '#ede9fe' }
  space:  { md: 14px }
  stroke: { md: 3px, dash: '8 6' }
components:
  trip-map:
    link: { stroke: '{color.brand}', stroke-width: '{stroke.md}', dash: true }
"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.kit = write(self.tmp, 'kit.yaml', self.KIT)
        self.theme = write(self.tmp, 'theme.yaml', self.THEME)

    def test_without_kit_reports_unknown_component(self):
        proc = run('tokens', self.theme)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('link', proc.stderr)

    def test_with_kit_exports(self):
        proc = run('tokens', self.theme, '--kit', self.kit)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out['color']['$type'], 'color')
        self.assertEqual(out['space']['md']['$value'], {'value': 14, 'unit': 'px'})


class CompositeTest(unittest.TestCase):
    """複合型（DTCG §9）：書寫層一行 CSS，輸出層結構化。"""

    THEME = """
tokens:
  border: { strong: '2px solid #2B2A33' }
  shadow: { sm: '0 2px 0 #2B2A33', soft: '0 6px 12px 2px rgba(0,0,0,0.18)', inner: '0 1px 2px #000 inset' }
  stroke: { md: 3px, dash: '4 10' }
"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.theme = write(self.tmp, 'theme.yaml', self.THEME)
        self.out = json.loads(run('tokens', self.theme).stdout)

    def test_border(self):
        self.assertEqual(self.out['border']['$type'], 'border')     # 單一型別家族提到群組層
        val = self.out['border']['strong']
        self.assertEqual(val['$value']['width'], {'value': 2, 'unit': 'px'})
        self.assertEqual(val['$value']['style'], 'solid')
        self.assertEqual(val['$value']['color'], '#2B2A33')

    def test_shadow_fills_optional_parts(self):
        val = self.out['shadow']['sm']['$value']
        self.assertEqual(val['offsetY'], {'value': 2, 'unit': 'px'})
        self.assertEqual(val['blur'], {'value': 0, 'unit': 'px'})
        self.assertEqual(val['spread'], {'value': 0, 'unit': 'px'})

    def test_shadow_with_spread_and_rgba(self):
        val = self.out['shadow']['soft']['$value']
        self.assertEqual(val['spread'], {'value': 2, 'unit': 'px'})
        self.assertEqual(val['color'], 'rgba(0,0,0,0.18)')     # 括號內的逗號不被切開

    def test_shadow_inset(self):
        self.assertTrue(self.out['shadow']['inner']['$value']['inset'])

    def test_stroke_dash_becomes_stroke_style(self):
        val = self.out['stroke']['dash']
        self.assertEqual(val['$type'], 'strokeStyle')
        self.assertEqual(val['$value']['dashArray'],
                         [{'value': 4, 'unit': 'px'}, {'value': 10, 'unit': 'px'}])

    def test_no_warnings(self):
        self.assertEqual(run('tokens', self.theme).stderr.strip(), '')


class ImportTest(unittest.TestCase):
    """DTCG JSON → theme 書寫形式；往返後語義不變。"""

    THEME = """
tokens:
  color:  { brand: '#B85A3C', link: '{color.brand}' }
  space:  { md: 14px }
  motion: { fast: 150ms, spring: [0.34, 1.56, 0.64, 1] }
  font:   { body: "'Inter',sans-serif", weight: 700 }
  border: { strong: '2px solid #2B2A33' }
  shadow: { md: '0 4px 0 #2B2A33' }
"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.theme = write(self.tmp, 'theme.yaml', self.THEME)
        self.json = write(self.tmp, 'x.tokens.json', run('tokens', self.theme).stdout)

    def test_emits_compact_authoring_form(self):
        out = run('import', self.json).stdout
        self.assertIn('tokens:', out)
        self.assertIn("space: { md: 14px }", out)
        self.assertIn("'0 4px 0 #2B2A33'", out)                 # 複合型還原成一行
        self.assertIn("'2px solid #2B2A33'", out)
        self.assertIn('[0.34, 1.56, 0.64, 1]', out)

    def test_alias_survives(self):
        self.assertIn("link: '{color.brand}'", run('import', self.json).stdout)

    def test_quotes_font_stack_without_doubling(self):
        out = run('import', self.json).stdout
        self.assertIn('"\'Inter\',sans-serif"', out)            # 單引號字串改用雙引號包

    def test_round_trip_is_identical(self):
        back = write(self.tmp, 'back.yaml',
                     '\n'.join(run('import', self.json).stdout.splitlines()[1:]))
        again = json.loads(run('tokens', back).stdout)
        self.assertEqual(again, json.loads(open(self.json, encoding='utf-8').read()))

    def test_rejects_deeper_nesting(self):
        deep = write(self.tmp, 'deep.json', json.dumps(
            {'a': {'b': {'c': {'$type': 'color', '$value': '#fff'}}}}))
        proc = run('import', deep)
        self.assertIn('兩層', proc.stderr)


if __name__ == '__main__':
    unittest.main()
