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
