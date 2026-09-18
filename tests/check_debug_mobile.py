"""Mobile debug checks, run through tests/check_browser.py."""
from pathlib import Path


def check_debug_mobile(browser, out, wf, files):
    wf._load_theme(None)
    for mode in ('single', 'anchor', 'radio'):
        html = (wf.compile_all(Path(files[0]).read_text(), str(Path(files[0]).parent),
                               'phone-home', debug=True)[0][1] if mode == 'single'
                else wf.bundle(files, debug=True, standalone=mode == 'radio'))
        dest = out / ('mobile-debug-' + mode + '.html')
        dest.write_text(html)
        page = browser.new_page(viewport={'width': 390, 'height': 844})
        page.route('**/*', lambda r: r.abort() if r.request.url.startswith(('http:', 'https:')) else r.continue_())
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(dest.as_uri(), wait_until='load')
        if mode != 'single':
            nav, bar = page.locator('#wf-nav').bounding_box(), page.locator('#wf-dbg').bounding_box()
            assert nav['y'] + nav['height'] < bar['y'], (nav, bar)
            page.locator('#nav-wf-pg-phone-long').click()
            assert page.locator('#wf-pg-phone-long').is_visible()
            page.locator('#nav-wf-pg-phone-home').click()
        page.locator('#wf-dbg-mode').click()
        heading = page.locator('.wf-pg:visible [data-name="header"] .wf-h2' if mode != 'single'
                               else '[data-name="header"] .wf-h2')
        heading.click()
        pop, bar = page.locator('#wf-dbg-pop').bounding_box(), page.locator('#wf-dbg').bounding_box()
        assert pop['x'] >= 0 and pop['x'] + pop['width'] <= 390, pop
        assert pop['y'] >= 0 and pop['y'] + pop['height'] <= bar['y'], (pop, bar)
        assert page.locator('#wf-dbg-pop').evaluate('(n)=>n.style.top === "" && n.style.left === ""')
        assert page.locator('#wf-dbg-pop textarea').evaluate('(n)=>getComputedStyle(n).fontSize') == '16px'
        for button in page.locator('#wf-dbg button, #wf-dbg-pop button').all():
            assert button.bounding_box()['height'] >= 40
        # Desktop/mobile transitions while editing must set/clear inline coordinates.
        page.set_viewport_size({'width': 1200, 'height': 900})
        page.wait_for_function('getComputedStyle(document.querySelector("#wf-dbg-pop")).position === "absolute" && document.querySelector("#wf-dbg-pop").style.top !== ""')
        page.set_viewport_size({'width': 390, 'height': 844})
        page.wait_for_function('document.querySelector("#wf-dbg-pop").style.top === ""')
        page.locator('#wf-dbg-pop textarea').fill('手機標註 ' + mode)
        page.locator('#wf-dbg-pop').get_by_text('存', exact=True).click()
        page.reload(wait_until='load')
        page.locator('#wf-dbg-exp').click()
        export = page.locator('#wf-dbg-export')
        box = export.bounding_box()
        assert box['width'] > 350 and box['y'] >= 0 and box['y'] + box['height'] <= 844, box
        assert '手機標註 ' + mode in export.locator('textarea').input_value()
        assert export.get_by_text('關閉', exact=True).bounding_box()['height'] >= 40
        export.get_by_text('關閉', exact=True).click()
        assert page.locator('#wf-dbg').is_visible()
        page.locator('#wf-dbg-mode').click()
        heading.click()
        page.locator('#wf-dbg-exp').click()
        assert page.locator('#wf-dbg-pop').count() == 0
        export.get_by_text('關閉', exact=True).click()
        assert not errors, errors
        page.screenshot(path=str(out / ('debug-mobile-' + mode + '.png')), full_page=True)
        page.close()

    # A controlled visualViewport exercises keyboard occlusion and panning events.
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    page.add_init_script("""const vv=new EventTarget();
        Object.assign(vv,{height:844,offsetTop:0});
        Object.defineProperty(window,'visualViewport',{value:vv});""")
    page.route('**/*', lambda r: r.abort() if r.request.url.startswith(('http:', 'https:')) else r.continue_())
    page.goto(dest.as_uri(), wait_until='load')
    page.locator('#wf-dbg-mode').click()
    page.locator('.wf-pg:visible [data-name="header"] .wf-h2').click()
    page.evaluate('visualViewport.height=400;visualViewport.offsetTop=20;visualViewport.dispatchEvent(new Event("resize"));')
    for selector in ('#wf-dbg', '#wf-dbg-pop'):
        box = page.locator(selector).bounding_box()
        assert box['y'] >= 20 and box['y'] + box['height'] <= 420, (selector, box)
    page.locator('#wf-dbg-exp').click()
    box = page.locator('#wf-dbg-export').bounding_box()
    assert box['y'] >= 20 and box['y'] + box['height'] <= 420, box
    page.evaluate('visualViewport.height=844;visualViewport.offsetTop=0;visualViewport.dispatchEvent(new Event("scroll"));')
    assert page.locator('#wf-dbg-export').bounding_box()['height'] > box['height']
    page.close()
    print('mobile debug single/anchor/radio, touch targets, resize, save/reload/export and simulated keyboard: OK')
