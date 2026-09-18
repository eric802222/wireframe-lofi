import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import wfyaml as wf

class AssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.d=Path(self.tmp.name)
        wf._load_theme(None)
        self.page='body:\n - image: {label: Same, ratio: 3/4}\n   name: cover\n - image: {label: Same, ratio: 1/1}\n - avatar: {label: Me, size: lg}\n   name: person\n - icon: star\n   name: mark\n'
        (self.d/'p.wf.yaml').write_text(self.page)
        (self.d/'cover.png').write_bytes((ROOT/'examples/themes/gallery.assets/cover.png').read_bytes())
        (self.d/'stamp.svg').write_text('<svg viewBox="0 0 24 24" onload="evil()"><script>evil()</script><foreignObject/><image href="https://evil"/><path fill="#123" stroke="#456" d="M0 0h24v24Z"/></svg>')
    def tearDown(self):
        wf._load_theme(None);self.tmp.cleanup()
    def load(self,data):
        p=self.d/'theme.yaml';p.write_text(yaml.safe_dump(data));wf._load_theme(str(p));return p
    def theme(self):
        return {'assets':{'cover':'cover.png','stamp':'stamp.svg'},'bindings':{'cover':{'image':'cover','fit':'cover'},'person':{'image':'cover'},'mark':{'icon':'stamp'}}}
    def test_named_only_portable_and_debug(self):
        plain=wf.compile_all(self.page,str(self.d),'p',debug=True)[0][1]
        self.load(self.theme())
        mock=wf.compile_all(self.page,str(self.d),'p',debug=True)[0][1]
        self.assertEqual(mock.count('<img src="data:image/png;base64,'),2)
        self.assertIn('object-fit:cover',mock);self.assertIn('aspect-ratio:3/4',mock)
        self.assertIn('▧ Same',mock) # identical label without name stays placeholder
        self.assertIn('wf-asset-icon',mock);self.assertIn('fill="currentColor"',mock)
        self.assertNotIn('evil',mock);self.assertNotIn('<foreignObject',mock)
        import re
        self.assertEqual(re.findall(r'data-wf-path="([^"]+)"',plain),re.findall(r'data-wf-path="([^"]+)"',mock))
        bundle=wf.bundle([str(self.d/'p.wf.yaml')],standalone=True)
        self.assertIn('data:image/png;base64,',bundle);self.assertNotIn('<script>',bundle)
        wf._load_theme(None)
        self.assertEqual(wf.compile_all(self.page,str(self.d),'p',debug=True)[0][1],plain)
    def test_missing_asset_warns_lint_and_falls_back(self):
        t=self.theme();t['assets']['cover']='missing.png'
        theme=self.load(t)
        result=wf.compile_all(self.page,str(self.d),'p')[0][1]
        self.assertNotIn('<img ',result);self.assertIn('▧ Same',result)
        r=subprocess.run([sys.executable,str(ROOT/'wfyaml.py'),'lint','--mockup',str(theme),str(self.d/'p.wf.yaml')],capture_output=True,text=True)
        self.assertEqual(r.returncode,1);self.assertIn('missing.png',r.stderr)
        r=subprocess.run([sys.executable,str(ROOT/'wfyaml.py'),'--mockup',str(theme),str(self.d/'p.wf.yaml')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0)
    def test_schema_validation_and_invalid_svg(self):
        cases=[{'assets':[]},{'assets':{'x':'https://x/a.png'}},{'assets':{'x':'a.txt'}},
               {'bindings':{'x':{'image':'undefined'}}},{'bindings':{'x':{'fit':'stretch'}}},
               {'assets':{'x':'cover.png'},'bindings':{'x':{'icon':'x'}}}]
        for t in cases:
            with self.subTest(t=t),self.assertRaises(ValueError):self.load(t)
        (self.d/'stamp.svg').write_text('invalid')
        self.load(self.theme());self.assertTrue(wf._THEME_ASSET_WARNINGS)
        self.assertIn('wf-fa',wf.compile_all(self.page,str(self.d),'p')[0][1])
    def test_structure_cannot_supply_asset_paths(self):
        for role in ('image','avatar'):
            for active in (False,True):
                if active:self.load(self.theme())
                else:wf._load_theme(None)
                with self.subTest(role=role,active=active),self.assertRaises(ValueError):
                    wf.compile_all('body: [{'+role+': {src: cover.png}}]',str(self.d),'p')

    def test_size_warnings_include_repeated_payload(self):
        (self.d/'large.png').write_bytes(b'x'*(310*1024))
        t={'assets':{'big':'large.png'},'bindings':{'cover':{'image':'big'}}}
        with contextlib.redirect_stderr(io.StringIO()) as capture:
            self.load(t)
            wf.compile_all('body:\n'+(' - image: {ratio: 1/1}\n   name: cover\n'*14),str(self.d),'p')
        self.assertIn('300KB',capture.getvalue());self.assertIn('5MB',capture.getvalue())

if __name__=='__main__':unittest.main()
