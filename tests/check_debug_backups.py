"""Portable backups and optional host-adapter tests (no real third-party calls)."""
from pathlib import Path


def check_debug_backups(browser, out, wf):
    wf._load_theme(None)
    a, b = out / 'a.wf.yaml', out / 'b.wf.yaml'
    a.write_text('body: [{text: A}]')
    b.write_text('body: [{text: B}]')
    bridge = (Path(wf.__file__).parent / 'examples/wf-claude-bridge.html').read_text()
    def fixture(name, with_bridge=False):
        dest = out / (name + '.html')
        dest.write_text(wf.bundle([str(a), str(b)], debug=True, standalone=True,
                                 debug_bridge=bridge if with_bridge else ''))
        return dest

    def page_for(dest, script=None):
        page = browser.new_page(viewport={'width': 1200, 'height': 900})
        page.route('**/*', lambda r: r.abort() if r.request.url.startswith(('http:', 'https:')) else r.continue_())
        if script:
            page.add_init_script(script)
        page.goto(dest.as_uri(), wait_until='load')
        return page

    record = {'src': 'a', 'path': 'body[0]', 'role': 'wf-label', 'text': 'A', 'note': 'first'}
    dest = fixture('backups')
    page = page_for(dest)
    page.evaluate('(note)=>wfReview.commit({"a|body[0]":note})', record)
    backup = page.evaluate('wfReview.markdown()')
    assert '<!-- wf-notes-json' in backup and '```json' in backup
    page.evaluate('wfReview.commit({})')
    page.evaluate('(text)=>wfReview.importMarkdown(text)', backup)
    assert page.evaluate('Object.keys(wfReview.notes()).length') == 0
    page.evaluate('(note)=>wfReview.commit({"a|body[0]":{...note,note:"newer"}})', record)
    page.evaluate('(text)=>wfReview.importMarkdown(text)', backup)
    assert page.evaluate('wfReview.notes()["a|body[0]"].note') == 'newer'
    # Old reference exports are readable, but do not replace existing local keys.
    old = '<!-- wf-notes-json\n```json\n{"b|body[0]":{"src":"b","path":"body[0]","note":"legacy"}}\n```\n-->'
    page.evaluate('(text)=>wfReview.importMarkdown(text)', old)
    assert page.evaluate('wfReview.notes()["b|body[0]"].note') == 'legacy'
    before = page.evaluate('wfReview.snapshot()')
    assert page.evaluate('''() => {try{wfReview.merge({"bad":{note:"broken"}});return false;}catch(e){return true;}}''')
    assert page.evaluate('wfReview.snapshot()') == before
    page.locator('#wf-dbg-import').click()
    page.locator('#wf-dbg-export textarea').fill('not a backup')
    page.locator('#wf-dbg-export').get_by_text('匯入並合併', exact=True).click()
    assert page.locator('#wf-dbg-export [role=status]').inner_text()
    assert page.evaluate('wfReview.snapshot()') == before
    page.locator('#wf-dbg-export textarea').fill(old)
    page.locator('#wf-dbg-export').get_by_text('匯入並合併', exact=True).click()
    assert page.locator('#wf-dbg-export').count() == 0
    page.locator('#wf-dbg-exp').click()
    with page.expect_download() as download_info:
        page.locator('#wf-dbg-export').get_by_text('下載 .md', exact=True).click()
    download = download_info.value
    restored = Path(download.path()).read_text()
    assert '<!-- wf-notes-json' in restored
    fresh = page_for(fixture('fresh-device'))
    fresh.evaluate('(text)=>wfReview.importMarkdown(text)', restored)
    assert fresh.evaluate('wfReview.notes()') == page.evaluate('wfReview.notes()')
    fresh.close()
    page.evaluate('wfReview.clear()')
    page.reload(wait_until='load')
    page.evaluate('(text)=>wfReview.importMarkdown(text)', restored)
    assert page.evaluate('Object.keys(wfReview.notes()).length') == 0
    page.close()

    # Opaque/disabled storage must not prevent editing, rendering, import or export.
    blocked = page_for(fixture('blocked-storage', True), "Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError');}})")
    blocked.evaluate('(note)=>wfReview.commit({"a|body[0]":note})', record)
    blocked.locator('#wf-dbg-mode').click()
    assert blocked.locator('.wf-dbg-status').inner_text()
    assert blocked.locator('.wf-dbg-note p').inner_text() == 'first'
    assert blocked.locator('#wf-review-send').is_hidden()
    assert 'first' in blocked.evaluate('wfReview.markdown()')
    blocked.close()

    mock = r"""window.writes=[];window.messages=[];window.getStarted=false;window.dbBodies={};
      window.activeDraft=0;window.maxDraft=0;window.holdWrites=false;window.writeResolvers=[];
      window.failNotice=true;window.failReview=false;window.failDraft=false;
      window.claude={use:async(name)=> name==='db'?{doc:(path)=>({
        get:()=>{window.getStarted=true;return new Promise(resolve=>window.resolveRemote=(body)=>resolve({exists:!!body,data:()=>body}));},
        set:async(body)=>{window.writes.push({path,body:JSON.parse(JSON.stringify(body))});
          if(path.startsWith('reviews/')&&window.failReview)throw new Error('review');
          if(path.startsWith('drafts/')){
            window.activeDraft++;window.maxDraft=Math.max(window.maxDraft,window.activeDraft);
            if(window.holdWrites)await new Promise(resolve=>window.writeResolvers.push(resolve));
            window.activeDraft--;if(window.failDraft)throw new Error('draft');}
          window.dbBodies[path]=JSON.parse(JSON.stringify(body));}
      })}:name==='comments'?{
        canSendToClaude:async()=> 'available',anchorFor:async(element)=>({id:element.id}),
        sendToClaude:async(payload)=>{window.messages.push(payload);if(window.failNotice)throw new Error('notice');}
      }:null};"""
    page = page_for(fixture('mock-host', True), mock)
    page.wait_for_function('window.getStarted')
    page.evaluate('(note)=>wfReview.commit({"a|body[0]":{...note,note:"local during load"}})', record)
    remote = {'format': 'wf-review', 'version': 1, 'notes': {
        'a|body[0]': record,
        'b|body[0]': {**record, 'src': 'b', 'note': 'remote'}},
        'revisions': {'a|body[0]': {'at': 1000, 'deleted': False}, 'b|body[0]': {'at': 1000, 'deleted': False}}, 'clearedAt': 0}
    page.evaluate('(snapshot)=>window.resolveRemote(snapshot)', remote)
    page.wait_for_function('!document.querySelector("#wf-review-send").disabled')
    assert page.evaluate('wfReview.notes()["a|body[0]"].note') == 'local during load'
    assert page.evaluate('wfReview.notes()["b|body[0]"].note') == 'remote'
    page.wait_for_function('window.writes.some(w=>w.path.startsWith("drafts/"))')
    assert page.evaluate('window.writes[0].path') != 'drafts/current'
    # Delayed writes serialize; new changes queue the newest snapshot afterwards.
    page.evaluate('window.holdWrites=true;wfReview.commit({...wfReview.notes(),"a|body[0]":{...wfReview.notes()["a|body[0]"],note:"second"}})')
    page.wait_for_function('window.writeResolvers.length === 1')
    page.evaluate('wfReview.commit({...wfReview.notes(),"a|body[0]":{...wfReview.notes()["a|body[0]"],note:"third"}})')
    page.evaluate('window.holdWrites=false;window.writeResolvers.shift()()')
    page.wait_for_function('Object.values(window.dbBodies).some(s=>s.notes&&s.notes["a|body[0]"].note==="third")')
    assert page.evaluate('window.maxDraft') == 1
    page.locator('#nav-wf-pg-b').click()
    page.evaluate('document.querySelector("#wf-review-send").click();document.querySelector("#wf-review-send").click();')
    page.wait_for_function('document.querySelector("#wf-review-send-status").textContent.includes("通知失敗")')
    assert page.evaluate('window.writes.filter(w=>w.path.startsWith("reviews/")).length') == 1
    assert page.evaluate('window.messages[0].anchor.id') == 'wf-pg-b'
    page.evaluate('window.failNotice=false;document.querySelector("#wf-review-send").click()')
    page.wait_for_function('document.querySelector("#wf-review-send-status").textContent.includes("已儲存並通知")')
    assert page.evaluate('window.writes.filter(w=>w.path.startsWith("reviews/")).length') == 1
    assert page.evaluate('window.messages.length') == 2
    page.evaluate('document.querySelector("#wf-review-send").click()')
    assert page.locator('#wf-review-send-status').inner_text() == '沒有新的變更'
    # Remote failure never discards canonical edits; explicit retry writes them.
    page.evaluate('window.failDraft=true;wfReview.commit({})')
    page.wait_for_function('document.querySelector("#wf-review-sync-status").textContent.includes("尚未同步")')
    page.evaluate('window.failDraft=false;document.querySelector("#wf-review-retry").click()')
    page.wait_for_function('Object.values(window.dbBodies).some(s=>s.notes&&Object.keys(s.notes).length===0)')
    assert page.evaluate('Object.keys(wfReview.notes()).length') == 0
    page.close()
    print('debug portable backup/download/import, deletion versions, blocked storage, host merge/serial sync/send dedup/retry mocks: OK')
