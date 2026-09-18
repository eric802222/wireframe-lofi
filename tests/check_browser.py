"""Real browser checks: python3 tests/check_browser.py.

Requires playwright + chromium. WFYAML_CHROMIUM optionally selects an installed binary.
Artifacts live in a temporary directory unless WFYAML_TEST_OUTPUT is set.
"""
import os
from pathlib import Path
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfyaml as wf


def main():
    with tempfile.TemporaryDirectory() as temp, sync_playwright() as p:
        out = Path(os.environ.get('WFYAML_TEST_OUTPUT') or temp)
        out.mkdir(parents=True, exist_ok=True)
        options = {'args': ['--disable-dev-shm-usage']}
        if os.environ.get('WFYAML_CHROMIUM'):
            options['executable_path'] = os.environ['WFYAML_CHROMIUM']
        browser = p.chromium.launch(**options)
        page = browser.new_page(viewport={'width': 1200, 'height': 1000}, java_script_enabled=False)
        page.route('**/*', lambda r: r.abort() if r.request.url.startswith(('http:', 'https:')) else r.continue_())
        for name, should_scroll in (('phone-home', False), ('phone-long', True)):
            src = ROOT / f'examples/{name}.wf.yaml'
            html = wf.compile_all(src.read_text(), str(src.parent), name)[0][1]
            assert '<script>' not in html
            dest = out / (name + '.html')
            dest.write_text(html)
            page.goto(dest.as_uri(), wait_until='load')
            measure = page.evaluate('''() => {
                const rect = n => {const r=n.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,height:r.height};};
                const root=document.querySelector('.wf-root');
                const main=document.querySelector('[data-name="main"]');
                return {root:rect(root),header:rect(document.querySelector('[data-name="header"]')),
                    footer:rect(document.querySelector('[data-name="footer"]')),main:rect(main),
                    client:main.clientHeight, scroll:main.scrollHeight};
            }''')
            assert measure['root']['height'] == 844, measure
            assert measure['footer']['bottom'] <= measure['root']['bottom'], measure
            assert measure['footer']['top'] >= measure['main']['bottom'] - 1, measure
            assert (measure['scroll'] > measure['client'] + 1) == should_scroll, measure
            if should_scroll:
                page.evaluate('document.querySelector("[data-name=main]").scrollTop=10000')
                after = page.evaluate('''() => ({
                    scroll:document.querySelector('[data-name="main"]').scrollTop,
                    header:document.querySelector('[data-name="header"]').getBoundingClientRect().top,
                    footer:document.querySelector('[data-name="footer"]').getBoundingClientRect().top
                })''')
                assert after['scroll'] > 0, after
                assert after['header'] == measure['header']['top'], after
                assert after['footer'] == measure['footer']['top'], after
            page.screenshot(path=str(out / (name + '.png')), full_page=True)
            page.evaluate('document.querySelector(".wf-root").classList.add("wf-show-all")')
            show = page.evaluate('''() => {
                const r=document.querySelector('.wf-root'), m=document.querySelector('[data-name="main"]');
                return {height:r.getBoundingClientRect().height,client:m.clientHeight,scroll:m.scrollHeight};
            }''')
            assert show['scroll'] <= show['client'] + 1, show
            if should_scroll:
                assert show['height'] > 844, show
            page.screenshot(path=str(out / (name + '.expanded.png')), full_page=True)
            print(name, 'fixed header/footer, independent scroll and show-all: OK')

        files = [str(ROOT / f'examples/{n}.wf.yaml') for n in ('phone-home', 'phone-long', 'deal-routes')]
        html = wf.bundle(files)
        dest = out / 'prototype.html'
        dest.write_text(html)
        page.goto(dest.as_uri(), wait_until='load')
        assert page.locator('.wf-pg:visible').count() == 1
        page.locator('#nav-wf-pg-phone-long').click()
        assert page.locator('#wf-pg-phone-long').is_visible()
        page.locator('#wf-pg-phone-long a[href="#wf-pg-phone-home"]').click()
        assert page.locator('#wf-pg-phone-home').is_visible()
        page.locator('#nav-wf-pg-deal-routes-approving-pending').click()
        assert page.locator('#wf-pg-deal-routes-approving-pending').is_visible()
        assert page.locator('#wf-pg-deal-routes-approving-pending').get_by_text('已送出，等待主管核准').is_visible()
        page.goto(dest.as_uri() + '#wf-pg-phone-long', wait_until='load')
        assert page.locator('.wf-pg:visible').count() == 1
        assert page.locator('#wf-pg-phone-long').is_visible()
        assert page.url.endswith('#wf-pg-phone-long')
        print('bundle navigation, deep link, titles/groups and routes with JS disabled: OK')

        # Dedicated fixtures exercise every internal link form, duplicate destinations,
        # native keyboard controls, responsive layout and a scripts-disabled sandbox.
        a = out / 'a.wf.yaml'
        b = out / 'b.wf.yaml'
        a.write_text("""title: 首頁
group: App
viewport: 390x844
body:
  - button: 按鈕動線
    name: next
    to: b
  - row: [{text: 卡片動線}]
    to: b
  - text: '[文字動線](to:b) · [真連結](https://example.com)'
""")
        b.write_text('viewport: 390x844\nbody: [{button: 返回, to: a}]')
        standalone_files = [str(a), str(b), files[-1]]
        standalone = wf.bundle(standalone_files, standalone=True)
        standalone_dest = out / 'standalone.html'
        standalone_dest.write_text(standalone)
        page.goto(standalone_dest.as_uri(), wait_until='load')
        initial_url = page.url
        page.keyboard.press('Tab')
        assert page.locator('#r-wf-pg-a').evaluate('(n)=>n === document.activeElement')
        page.keyboard.press('ArrowRight')
        assert page.locator('#wf-pg-b').is_visible()
        page.keyboard.press('ArrowLeft')
        assert page.locator('#wf-pg-a').is_visible()
        assert page.locator('a[href^="#"]').count() == 0
        assert page.locator('a[href="https://example.com"]').count() == 1
        ids = page.locator('[id]').evaluate_all('(ns)=>ns.map(n=>n.id)')
        assert len(ids) == len(set(ids)), ids
        for selector in ('.wf-btn', '.wf-blocklink-a', '.wf-hyperlink.wf-radio-link'):
            page.locator('#wf-pg-a ' + selector).click()
            assert page.locator('.wf-pg:visible').count() == 1
            assert page.locator('#wf-pg-b').is_visible()
            assert page.locator('#nav-wf-pg-b').evaluate('(n)=>getComputedStyle(n).backgroundColor') == 'rgb(15, 118, 110)'
            assert page.url == initial_url
            page.locator('#wf-pg-b .wf-btn').click()
            assert page.locator('#wf-pg-a').is_visible()
        page.keyboard.press('Tab')  # Enter keyboard modality before checking :focus-visible.
        page.locator('#r-wf-pg-a').focus()
        assert page.locator('#nav-wf-pg-a').evaluate('(n)=>getComputedStyle(n).outlineStyle') == 'solid'
        page.keyboard.press('ArrowRight')
        assert page.locator('#wf-pg-b').is_visible()
        assert page.url == initial_url
        page.locator('#nav-wf-pg-a').click()
        outgoing = page.locator('#wf-pg-a .wf-btn input')
        outgoing.focus()
        page.keyboard.press('Space')
        assert page.locator('#wf-pg-b').is_visible()
        page.locator('#nav-wf-pg-deal-routes-approving-pending').click()
        assert page.locator('#wf-pg-deal-routes-approving-pending').is_visible()
        assert page.url == initial_url

        for mode in (False, True):
            standalone_dest.write_text(wf.bundle(standalone_files, standalone=mode))
            page.goto(standalone_dest.as_uri(), wait_until='load')
            for width in (390, 860, 861):
                page.set_viewport_size({'width': width, 'height': 1000})
                layout = page.evaluate("""() => {
                    const nav=document.querySelector('#wf-nav'), main=document.querySelector('#wf-main');
                    const nr=nav.getBoundingClientRect(), mr=main.getBoundingClientRect();
                    return {direction:getComputedStyle(document.body).flexDirection,
                        navBottom:nr.bottom,mainTop:mr.top,navRight:nr.right,mainLeft:mr.left,
                        navScroll:nav.scrollWidth,navWidth:nav.clientWidth,
                        mainScroll:main.scrollWidth,mainWidth:main.clientWidth,
                        bodyWidth:document.body.scrollWidth,
                        canvas:document.querySelector('#wf-pg-a .wf-root').getBoundingClientRect().width};
                }""")
                assert layout['canvas'] == 390, layout
                if width <= 860:
                    assert layout['direction'] == 'column', layout
                    assert layout['mainTop'] >= layout['navBottom'] - 1, layout
                    assert layout['bodyWidth'] <= width, layout
                    if width == 390:
                        assert layout['navScroll'] > layout['navWidth'], layout
                        assert layout['mainScroll'] > layout['mainWidth'], layout
                        page.screenshot(path=str(out / ('bundle-radio-mobile.png' if mode else 'bundle-anchor-mobile.png')), full_page=True)
                else:
                    assert layout['direction'] == 'row', layout
                    assert layout['mainLeft'] >= layout['navRight'] - 1, layout
        page.set_viewport_size({'width': 1200, 'height': 1000})
        story = out / 'review.story.yaml'
        story.write_text('story: review\npage: a\nflow: [{step: 1, target: next, desc: 前往下一頁, to: b}]')
        standalone_dest.write_text(wf.bundle(standalone_files, story=str(story), standalone=True))
        page.goto(standalone_dest.as_uri(), wait_until='load')
        page.locator('#nav-wf-pg-story-review').click()
        assert page.locator('#wf-pg-story-review').is_visible()
        page.locator('#wf-pg-story-review .wf-story-step-pin').click()
        assert page.locator('#wf-pg-b').is_visible()
        assert page.url == initial_url
        standalone_dest.write_text(standalone)
        parent = out / 'sandbox.html'
        parent.write_text('<iframe sandbox src="' + standalone_dest.as_uri() + '" style="width:100%;height:900px"></iframe>')
        page.goto(parent.as_uri(), wait_until='load')
        frame = page.frames[1]
        parent_url, frame_url = page.url, frame.url
        frame.locator('#nav-wf-pg-b').click()
        assert frame.locator('#wf-pg-b').is_visible()
        frame.locator('#wf-pg-b .wf-btn').click()
        assert frame.locator('#wf-pg-a').is_visible()
        assert page.url == parent_url and frame.url == frame_url
        print('radio links, native keyboard, routes, both responsive modes and sandbox without JS: OK')

        debug_html = wf.bundle(files, debug=True)
        debug_dest = out / 'prototype.debug.html'
        debug_dest.write_text(debug_html)
        debug_page = browser.new_page(java_script_enabled=True, viewport={'width': 1200, 'height': 1000})
        debug_page.route('**/*', lambda r: r.abort() if r.request.url.startswith(('http:', 'https:')) else r.continue_())
        debug_page.goto(debug_dest.as_uri(), wait_until='load')
        debug_page.locator('#wf-dbg-mode').click()
        heading = debug_page.locator('#wf-pg-phone-home [data-name="header"] .wf-h2')
        assert heading.get_attribute('data-wf-src') == 'layouts/phone'
        assert heading.get_attribute('data-wf-path') == 'body[0].items[0]'
        heading.click()
        debug_page.locator('#wf-dbg-pop textarea').fill('縮短頁首文字')
        debug_page.locator('#wf-dbg-pop').get_by_text('存', exact=True).click()
        debug_page.reload(wait_until='load')
        debug_page.locator('#wf-dbg-exp').click()
        exported = debug_page.locator('#wf-dbg-export textarea').input_value()
        assert 'layouts/phone.wf.yaml' in exported and '[body[0].items[0]]' in exported and '縮短頁首文字' in exported
        debug_page.close()
        print('debug feedback preserves layout source/path and reload/export: OK')

        # Annotation clicks must cancel radio selection; browse clicks must switch pages.
        debug_dest.write_text(wf.bundle(standalone_files, debug=True, standalone=True))
        debug_page = browser.new_page(java_script_enabled=True)
        debug_page.route('**/*', lambda r: r.abort() if r.request.url.startswith(('http:', 'https:')) else r.continue_())
        debug_page.goto(debug_dest.as_uri(), wait_until='load')
        debug_page.locator('#wf-dbg-mode').click()
        debug_page.locator('#wf-pg-a .wf-btn').click()
        assert debug_page.locator('#wf-pg-a').is_visible()
        debug_page.locator('#wf-dbg-pop textarea').fill('調整動線按鈕')
        debug_page.locator('#wf-dbg-pop').get_by_text('存', exact=True).click()
        debug_page.locator('#wf-dbg-mode').click()
        debug_page.locator('#wf-pg-a .wf-btn').click()
        assert debug_page.locator('#wf-pg-b').is_visible()
        debug_page.locator('#wf-dbg-exp').click()
        assert '調整動線按鈕' in debug_page.locator('#wf-dbg-export textarea').input_value()
        debug_page.close()
        print('radio debug annotation cancels navigation; browse and export: OK')

        wf._load_theme(str(ROOT / 'examples/themes/inverse.yaml'))
        html = wf.compile_all('body: [{box: true, col: [{text: white card}]}]', base='theme')[0][1]
        dest = out / 'theme.html'
        dest.write_text(html)
        page.goto(dest.as_uri(), wait_until='load')
        result = page.locator('.wf-box').evaluate('(n)=>({bg:getComputedStyle(n).backgroundColor,radius:getComputedStyle(n).borderRadius})')
        assert result == {'bg': 'rgb(255, 255, 255)', 'radius': '16px'}, result
        print('theme inverse background and semantic radius: OK')
        browser.close()


if __name__ == '__main__':
    main()
