"""Browser checks for review lists, legacy storage and mobile drawers."""
import json


def check_debug_notes(browser, out, wf):
    wf._load_theme(None)
    a, b = out / 'a.wf.yaml', out / 'b.wf.yaml'
    a.write_text('viewport: 390x600\nbody: [{text.heading: A, name: heading}, {text: Body A}]')
    b.write_text('viewport: 390x600\nbody: [{text.heading: B, name: heading}, {text: Body B}]')
    legacy = {
        'a|body[0]': {'src': 'a', 'path': 'body[0]', 'role': 'wf-h2', 'text': '舊快照', 'note': '舊註記'},
        'b|body[0]': {'src': 'b', 'path': 'body[0]', 'role': 'wf-h2', 'text': '遠端快照', 'note': '別頁註記'},
    }
    for mode in ('single', 'anchor', 'radio'):
        dest = out / ('notes-' + mode + '.html')
        dest.write_text(wf.compile_all(a.read_text(), str(out), 'a', debug=True)[0][1] if mode == 'single'
                        else wf.bundle([str(a), str(b)], debug=True, standalone=mode == 'radio'))
        page = browser.new_page(viewport={'width': 1200, 'height': 900})
        page.route('**/*', lambda r: r.abort() if r.request.url.startswith(('http:', 'https:')) else r.continue_())
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(dest.as_uri(), wait_until='load')
        key = 'wfdbg:' + dest.name
        page.evaluate('(s)=>localStorage.setItem(s.key,JSON.stringify(s.value))', {'key': key, 'value': legacy})
        page.reload(wait_until='load')
        panel = page.locator('#wf-dbg-list')
        assert not panel.is_visible()
        page.locator('#wf-dbg-mode').click()
        assert panel.is_visible()
        assert panel.locator('.wf-dbg-group').first.get_attribute('data-src') == 'a'
        first = panel.locator('article[data-key="a|body[0]"]')
        assert first.locator('code').inner_text() == 'body[0]'
        assert first.locator('small').inner_text() == '舊快照'
        first.locator('.wf-dbg-note-edit').click()
        note = '修正 <img src=x onerror=alert(1)>\n第二行'
        first.locator('textarea').fill(note)
        first.get_by_role('button', name='儲存', exact=True).click()
        assert first.locator('p').inner_text() == note
        assert panel.locator('img').count() == 0
        # Editing a note from a different page never requires navigating to its element.
        remote = panel.locator('article[data-key="b|body[0]"]')
        remote.locator('.wf-dbg-note-edit').click()
        remote.locator('textarea').fill('另一頁修正')
        remote.get_by_role('button', name='儲存', exact=True).click()
        page_note = page.locator('#wf-dbg-page-note')
        page_note.fill('A 整頁草稿')
        if mode != 'single':
            page.locator('#nav-wf-pg-b').click()
            page.wait_for_function('document.querySelector(".wf-dbg-group").dataset.src === "b"')
            assert page_note.input_value() == ''
            page_note.fill('B 整頁建議')
            panel.get_by_role('button', name='儲存整頁註記').click()
            page.locator('#nav-wf-pg-a').click()
            page.wait_for_function('document.querySelector(".wf-dbg-page-form label").textContent.includes("a.wf.yaml")')
            assert page_note.input_value() == 'A 整頁草稿'
        panel.get_by_role('button', name='儲存整頁註記').click()
        first.get_by_role('button', name='刪除註記：body[0]', exact=True).click()
        heading = page.locator('[data-name="heading"]' if mode == 'single' else '#wf-pg-a [data-name="heading"]')
        assert 'wf-dbg-has' not in heading.get_attribute('class')
        state = json.loads(page.evaluate('(key)=>localStorage.getItem(key)', key))
        assert 'a|body[0]' not in state and state['a|(整頁)']['note'] == 'A 整頁草稿'
        assert state['b|body[0]']['note'] == '另一頁修正'
        assert state['b|body[0]']['text'] == '遠端快照'
        page.reload(wait_until='load')
        page.locator('#wf-dbg-mode').click()
        assert panel.locator('article[data-key="a|body[0]"]').count() == 0
        assert panel.get_by_text('A 整頁草稿', exact=True).is_visible()
        page.set_viewport_size({'width': 390, 'height': 844})
        toggle = page.locator('#wf-dbg-list-toggle')
        assert not panel.is_visible() and toggle.is_visible()
        toggle.focus()
        page.keyboard.press('Space')
        assert panel.is_visible() and toggle.get_attribute('aria-expanded') == 'true'
        drawer, bar = panel.bounding_box(), page.locator('#wf-dbg').bounding_box()
        assert drawer['x'] >= 0 and drawer['x'] + drawer['width'] <= 390, drawer
        assert drawer['y'] >= 0 and drawer['y'] + drawer['height'] <= bar['y'], (drawer, bar)
        assert page_note.evaluate('(n)=>getComputedStyle(n).fontSize') == '16px'
        assert panel.get_by_role('button', name='收合').bounding_box()['height'] >= 40
        page.screenshot(path=str(out / ('note-drawer-' + mode + '.png')), full_page=True)
        page.keyboard.press('Escape')
        assert not panel.is_visible() and toggle.get_attribute('aria-expanded') == 'false'
        assert toggle.evaluate('(n)=>n === document.activeElement')
        toggle.click()
        if mode != 'single':
            page.locator('#nav-wf-pg-b').click()
            page.wait_for_function('document.querySelector(".wf-dbg-page-form label").textContent.includes("b.wf.yaml")')
            assert page_note.input_value() == 'B 整頁建議'
            panel.locator('article[data-key="b|(整頁)"]').get_by_role('button', name='刪除註記：(整頁)', exact=True).click()
            assert page_note.input_value() == ''
            page.locator('#nav-wf-pg-a').click()
        panel.get_by_role('button', name='收合').click()
        heading.click()
        assert page.locator('#wf-dbg-pop').is_visible() and not panel.is_visible()
        assert not toggle.is_visible()
        page.locator('#wf-dbg-pop textarea').fill('重新標註 A')
        page.locator('#wf-dbg-pop').get_by_role('button', name='存', exact=True).click()
        toggle.click()
        assert panel.get_by_text('重新標註 A', exact=True).is_visible()
        page.locator('#wf-dbg-exp').click()
        assert not panel.is_visible() and not toggle.is_visible()
        exported = page.locator('#wf-dbg-export textarea').input_value()
        assert '- (整頁) → A 整頁草稿' in exported
        assert '重新標註 A' in exported and '另一頁修正' in exported
        assert '- [(整頁)]' not in exported and 'B 整頁建議' not in exported
        page.keyboard.press('Escape')
        assert toggle.is_visible()
        page.locator('#wf-dbg-mode').click()
        assert not panel.is_visible() and not toggle.is_visible()
        page.on('dialog', lambda dialog: dialog.accept())
        page.locator('#wf-dbg-clr').click()
        assert page.evaluate('(key)=>localStorage.getItem(key)', key) is None
        page.locator('#wf-dbg-mode').click()
        toggle.click()
        assert panel.get_by_text('尚無註記', exact=True).is_visible()
        assert page_note.input_value() == ''
        assert page.locator('.wf-dbg-has').count() == 0
        assert not errors, errors
        page.close()
    # The drawer must follow the visible viewport when a keyboard/panning changes it.
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    page.add_init_script("""const vv=new EventTarget();Object.assign(vv,{height:400,offsetTop:20});
        Object.defineProperty(window,'visualViewport',{value:vv});""")
    page.route('**/*', lambda r: r.abort() if r.request.url.startswith(('http:', 'https:')) else r.continue_())
    page.goto(dest.as_uri(), wait_until='load')
    page.locator('#wf-dbg-mode').click()
    page.locator('#wf-dbg-list-toggle').click()
    box = page.locator('#wf-dbg-list').bounding_box()
    assert box['y'] >= 20 and box['y'] + box['height'] <= 420, box
    page.close()
    print('debug legacy list/edit/delete, grouped source navigation, page drafts/export, mobile drawer and keyboard viewport: OK')
