import sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import wfyaml as wf

class ThemeLeafBindings(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory();wf._load_theme(None)
    def tearDown(self): wf._load_theme(None);self.tmp.cleanup()
    def test_all_documented_leaf_selectors_and_widget_boundary(self):
        p=Path(self.tmp.name)/'theme.yaml'
        names=['checkbox','radio','progress','progress.fill','avatar','avatars','icon','image','divider','widget','tab','tab.active','link']
        p.write_text("tokens: {color: {brand: '#123456'}}\nbindings:\n"+''.join(f"  {x}: {{background: '{{color.brand}}', border: none, radius: sm}}\n" for x in names))
        wf._load_theme(str(p));css=wf._theme_css()
        for selector in ('.wf-check-control','.wf-radio-control','.wf-progress{','.wf-progress-fill{','.wf-avatar{','.wf-avatars{','.wf-icon{','.wf-image{','.wf-hr{','.wf-widget{','.wf-tab{','.wf-tab-active{','.wf-hyperlink{'):
            self.assertIn(selector,css)
        self.assertNotIn('.wf-widget-tag{',css)
    def test_mockup_applies_to_existing_classes_only(self):
        p=Path(self.tmp.name)/'theme.yaml';p.write_text('''bindings:
  checkbox: {color: '{color.brand}', border: none}
  radio: {color: '{color.soft}'}
  progress: {background: '{color.surface}', radius: lg}
  progress.fill: {background: '{color.brand}'}
  avatar: {background: '{color.brand}', border: none}
  divider: {border-color: '{color.brand}'}
  widget: {background: '{color.surface}', border: none}
  tab.active: {background: '{color.brand}', text: inverse}
  link: {text: inverse}
tokens: {color: {inverse: '#fff', brand: '#a11', soft: '#b22', surface: '#eee'}}
''');wf._load_theme(str(p))
        html=wf.compile_all('''body:
 - checkbox: {label: Agree, checked: true}
 - radio: {label: Yes, checked: true}
 - progress: {value: .5, label: Half}
 - avatar: ME
 - divider:
 - tabs: [One, Two]
 - link: {text: Go, to: '#'}
 - widget: {is: Map, can: [pan]}
''',self.tmp.name,'p')[0][1]
        for cls in ('wf-check','wf-check-control','wf-radio','wf-radio-control','wf-choice-checked','wf-progress','wf-progress-fill','wf-avatar','wf-hr','wf-tab-active','wf-hyperlink','wf-widget','wf-widget-tag'):
            self.assertIn(cls,html)
        self.assertIn('.wf-widget-tag{',wf._theme_css()) if False else self.assertNotIn('.wf-widget-tag{',wf._theme_css())

    def test_choice_controls_are_html_not_unicode_glyphs(self):
        html=wf.compile_all('''body:
 - checkbox: {label: Agree, checked: true}
 - radio: {label: Yes, checked: false}
 - "[x] Inline checkbox"
 - "( ) Inline radio"
''',self.tmp.name,'p')[0][1]
        self.assertEqual(html.count('class="wf-check-control'), 2)
        self.assertEqual(html.count('class="wf-radio-control'), 2)
        # 勾選狀態改由真的 <input checked> 承載（原生互動），視覺仍走 .wf-*-control
        self.assertIn('type="checkbox" checked', html)
        self.assertIn('type="radio"', html)
        self.assertNotIn('☑',html)
        self.assertNotIn('◉',html)
if __name__=='__main__':unittest.main()

class UnbindableTargetWarning(unittest.TestCase):
    """綁不到的目標要出聲：死 CSS 靜默通過會讓 PM 以為改好了、RD 拿到騙人的規格。"""
    def setUp(self): self.tmp=tempfile.TemporaryDirectory();wf._load_theme(None)
    def tearDown(self): wf._load_theme(None);self.tmp.cleanup()
    def _load(self, body):
        p=Path(self.tmp.name)/'theme.yaml';p.write_text(body);wf._load_theme(str(p));return wf._THEME_WARNINGS
    def test_leaf_role_without_selector_warns(self):
        # 動態挑一個「還沒有選擇器」的葉子角色：補洞（#49 之類）之後這個測試不該假失敗
        role = next((r for r in wf.LEAF_ROLES if r not in wf._THEME_ELEMENT_SELECTORS), None)
        self.assertIsNotNone(role, '所有葉子角色都可綁了 —— 這個警示路徑要改成只保留錯字偵測')
        warnings=self._load(f"bindings:\n  {role}: {{background: surface}}\n")
        self.assertTrue(any(role in w and '不會生效' in w for w in warnings), warnings)
    def test_typo_of_known_target_suggests(self):
        warnings=self._load("bindings:\n  buton: {background: surface}\n")
        self.assertTrue(any('button' in w for w in warnings))
    def test_screen_name_target_stays_silent(self):
        self.assertEqual(self._load("bindings:\n  照片1: {background: surface}\n"), [])
    def test_kit_component_target_stays_silent(self):
        wf._KIT_COMPONENTS['product-card']={'props':[]}
        try:
            self.assertEqual(self._load("bindings:\n  product-card: {background: surface}\n"), [])
        finally:
            wf._KIT_COMPONENTS.pop('product-card',None)
