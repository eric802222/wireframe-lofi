from pathlib import Path
import wfyaml as wf
ROOT=Path(__file__).resolve().parents[1]

def check_mockup_assets(browser,out):
    theme=ROOT/'examples/themes/gallery.yaml';src=ROOT/'examples/gallery.wf.yaml'
    wf._load_theme(str(theme))
    html=wf.bundle([str(src)],debug=True,standalone=True)
    dest=out/'gallery-assets.html';dest.write_text(html)
    page=browser.new_page(viewport={'width':390,'height':844},java_script_enabled=False)
    page.route('**/*',lambda r:r.abort() if r.request.url.startswith(('http:','https:')) else r.continue_())
    page.goto(dest.as_uri(),wait_until='load')
    m=page.evaluate('''() => {
      let root=document.querySelector('[data-name="封面"]'),im=root.querySelector('img'),a=document.querySelector('[data-name="成員"] img'),svg=document.querySelector('[data-name="郵票圖示"] svg');
      return {loaded:im.complete&&im.naturalWidth===240,avatar:a.complete&&a.naturalWidth===240,
        fit:getComputedStyle(im).objectFit,ratio:root.clientWidth/root.clientHeight,
        background:getComputedStyle(root).backgroundImage,color:getComputedStyle(svg.querySelector('path')).fill,
        path:root.dataset.wfPath,width:im.getBoundingClientRect().width,height:im.getBoundingClientRect().height};
    }''')
    assert m['loaded'] and m['avatar'] and m['fit']=='cover',m
    assert abs(m['ratio']-.75)<.02 and m['width']>100 and m['height']>100,m
    assert m['background']=='none' and m['color']=='rgb(64, 107, 88)' and m['path'],m
    page.screenshot(path=str(out/'gallery-assets-mobile.png'))
    page.close();wf._load_theme(None)
    print('mockup named assets, SVG currentColor, image/avatar dimensions, offline bundle and debug path: OK')
