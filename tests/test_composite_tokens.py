import sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import wfyaml as wf

THEME = """tokens:
  font: { body: "'Noto Sans TC',sans-serif" }
  color: { soft: "#8E8E93" }
  typography:
    hint:
      $type: typography
      $value: { fontFamily: '{font.body}', fontSize: 13px, fontWeight: 400 }
  gradient:
    scrim:
      $type: gradient
      angle: 180deg
      $value:
        - { color: "rgba(0,0,0,0.6)", position: 0 }
        - { color: "rgba(0,0,0,0)", position: 1 }
bindings:
  text.hint: { typography: hint, text: soft, font-style: normal }
  box: { background: '{gradient.scrim}' }
"""

class CompositeTokens(unittest.TestCase):
    """DTCG 的 typography / gradient：字級字重是 RD 契約的一部分，不該卡在編譯器裡。"""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        p=Path(self.tmp.name)/'theme.yaml';p.write_text(THEME)
        wf._load_theme(str(p));self.css=wf._theme_css()
    def tearDown(self): wf._load_theme(None);self.tmp.cleanup()

    def test_typography_emits_one_var_per_subvalue(self):
        for var in ('--wf-typography-hint-font-family', '--wf-typography-hint-font-size',
                    '--wf-typography-hint-font-weight'):
            self.assertIn(var, self.css)
        self.assertNotIn('--wf-typography-hint-line-height', self.css)   # 沒宣告就不產出
    def test_text_role_is_bindable(self):
        rule = [l for l in self.css.split('\n') if l.startswith('.wf-hint{')]
        self.assertTrue(rule, 'text.hint 綁不到 → #48 會警告，#49 就是要解這個')
        self.assertIn('font-size:var(--wf-typography-hint-font-size)', rule[0])
        self.assertIn('font-style:normal', rule[0])
    def test_gradient_composes_css_gradient(self):
        self.assertIn('linear-gradient(180deg, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0) 100%)', self.css)
    def test_gradient_is_referenceable_as_value(self):
        self.assertIn('.wf-box{background:var(--wf-gradient-scrim', self.css)
    def test_literal_design_values_still_rejected(self):
        p=Path(self.tmp.name)/'bad.yaml'
        p.write_text("bindings:\n  text.hint: { font-size: 13px }\n")
        with self.assertRaises(Exception):
            wf._load_theme(str(p))
    def test_unknown_typography_subvalue_rejected(self):
        p=Path(self.tmp.name)/'bad2.yaml'
        p.write_text("tokens:\n  typography:\n    x:\n      $value: { fontSize: 12px, fontStyle: italic }\n")
        with self.assertRaises(Exception):
            wf._load_theme(str(p))

if __name__ == '__main__':
    unittest.main()

class CompositeExportRoundTrip(unittest.TestCase):
    """DTCG 往返：typography / gradient 是規格裡我們還沒補的兩個，補完往返才完整。"""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.p=Path(self.tmp.name)/'theme.yaml';self.p.write_text(THEME)
    def tearDown(self): wf._load_theme(None);self.tmp.cleanup()
    def test_export_uses_dtcg_composite_shape(self):
        import wfexport
        out, skipped = wfexport._tokens_to_dtcg(wf._read_yaml(str(self.p))['tokens'])
        self.assertEqual(out['typography']['$type'], 'typography')
        self.assertEqual(out['gradient']['$type'], 'gradient')
        self.assertEqual(out['typography']['hint']['$value']['fontSize'], '13px')
        self.assertEqual(out['gradient']['scrim']['$value'][0]['position'], 0)
        self.assertEqual([s for s in skipped if s[0].startswith(('typography', 'gradient'))], [])
    def test_angle_survives_round_trip_via_extensions(self):
        import wfexport
        out, _ = wfexport._tokens_to_dtcg(wf._read_yaml(str(self.p))['tokens'])
        back, _ = wfexport._dtcg_to_tokens(out)
        self.assertEqual(back['gradient']['scrim']['angle'], '180deg')
        self.assertEqual(back['typography']['hint']['$value']['fontWeight'], 400)
