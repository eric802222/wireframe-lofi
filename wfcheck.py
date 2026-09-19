#!/usr/bin/env python3
"""給人與 AI 讀的檢查與規格輸出。

    python3 wfcheck.py flow <file.wf.yaml> [...] [--entry <畫面>] [--stages] [--quiet]
    python3 wfcheck.py spec <file.wf.yaml> [...] [--format md|json]
    python3 wfcheck.py gaps <file.wf.yaml> [...] [--quiet]

「哪邊動線不見了」不該靠人看。這支把 `to:` 走成一張圖，報告結構上的破洞：

- **斷鏈**：`to:` 指向不存在的畫面 → error
- **孤島**：沒有任何入口的畫面（宣告的進入點除外）→ error
- **死路**：沒有任何出口的畫面 → error
- **跨階段**：動線跨越 `group:` → 預設只計數（共用畫面本來就會跨）；`--stages` 才逐條列出

`flow` 的 exit code 與 lint 一致：0 乾淨 / 1 有 warning / 2 有 error，可直接放進 CI。
`spec` 產出每頁的結構化規格（元件、狀態、動線、未定值），交付 RD 或餵給 AI 開發，
也是驗收的清單 —— 交付的不該是一份巨量 HTML。

獨立模組，不改動 wfyaml.py 的行為。
"""
import os
import re
import sys

import yaml

import flowmap
import wfyaml as wf

_PARAM = re.compile(r'\{\{(\w+)\}\}')


def _load(path):
    return yaml.safe_load(open(path, encoding='utf-8')) or {}


def _with_layout(doc, path):
    """把 extends 的 layout 併進來：layout 裡的 to:（頁首入口、底部返回）也是動線。"""
    ref = doc.get('extends')
    if not isinstance(ref, str):
        return doc
    basedir = os.path.dirname(os.path.abspath(path))
    for cand in (os.path.join(basedir, ref + '.wf.yaml'),
                 os.path.join(basedir, ref + '.yaml')):
        if os.path.isfile(cand):
            layout = _load(cand)
            break
    else:
        return doc
    params = doc.get('with') or {}
    text = yaml.safe_dump(layout, allow_unicode=True)
    text = _PARAM.sub(lambda m: str(params.get(m.group(1), m.group(0))), text)
    merged = dict(doc)
    merged['__layout'] = yaml.safe_load(text)
    return merged


def build_graph(paths):
    """→ (nodes, edges, groups)。node 是畫面（或畫面.路由）。"""
    nodes, edges, groups, pages = {}, [], {}, set()
    for path in paths:
        doc = _load(path)
        base = re.sub(r'\.(wf\.)?ya?ml$', '', os.path.basename(path))
        pages.add(base)
        groups[base] = doc.get('group') or ''
        merged = _with_layout(doc, path)
        for node, raw in flowmap.extract(path)[1]:
            nodes[node] = base
            for target, label in raw:
                if target:
                    edges.append((node, target, label or ''))
        for target, label in flowmap.walk_to(merged.get('__layout')):
            node = flowmap._node_of(target, base)
            if node:
                edges.append((base, node, label or ''))
    return nodes, edges, groups, pages


def check(paths, entries=(), quiet=False, stages=False):
    nodes, edges, groups, pages = build_graph(paths)
    errors, warnings = [], []
    page_of = lambda node: node.split('.')[0]

    known = set(nodes) | pages
    outbound, inbound = {}, {}
    for src, dst, label in edges:
        if page_of(dst) not in pages:
            errors.append(f'{src} → {dst}：目標不存在（斷鏈）' + (f'（{label}）' if label else ''))
            continue
        outbound.setdefault(page_of(src), set()).add(page_of(dst))
        if page_of(dst) != page_of(src):
            inbound.setdefault(page_of(dst), set()).add(page_of(src))

    for page in sorted(pages):
        if page in entries:
            continue
        if not inbound.get(page):
            errors.append(f'{page} 沒有任何入口（孤島畫面）')
        if not outbound.get(page):
            errors.append(f'{page} 沒有任何出口（死路）')

    crossings = []
    for page, targets in sorted(outbound.items()):
        for target in sorted(targets):
            a, b = groups.get(page, ''), groups.get(target, '')
            if a and b and a != b:
                crossings.append(f'{page} → {target} 跨越階段（{a} → {b}），確認是否刻意')
    if stages:                         # 預設不吵：共用與設定類畫面本來就會跨階段
        warnings += crossings

    if not quiet:
        for line in errors:
            print(f'error: {line}', file=sys.stderr)
        for line in warnings:
            print(f'warn:  {line}', file=sys.stderr)
        entry_note = f'；宣告的進入點：{", ".join(sorted(entries))}' if entries else ''
        print(f'info:  {len(pages)} 畫面 / {len(nodes)} 狀態 / {len(edges)} 條動線{entry_note}')
        if crossings and not stages:
            print(f'info:  {len(crossings)} 條跨階段動線（用 --stages 逐條列出）')
        print(f'═══ 動線檢查：{len(errors)} error / {len(warnings)} warning ═══')
    return errors, warnings


# ── spec：每頁的結構化規格（給 RD 與 AI，不是給瀏覽器）──────────────────
def _count_leaves(obj, tally):
    """統計用到哪些元件（含 kit 型別）。"""
    if isinstance(obj, dict):
        for key in obj:
            if key in ('__src', '__path'):
                continue
            if key in wf.LEAF_ROLES or key in wf._KIT_COMPONENTS or key == 'widget':
                tally[key] = tally.get(key, 0) + 1
        for value in obj.values():
            _count_leaves(value, tally)
    elif isinstance(obj, list):
        for item in obj:
            _count_leaves(item, tally)


def _undefined_values(obj, found):
    if isinstance(obj, str):
        found += [m for m in re.findall(r'(?<!\\)\[([^\]\[]+)\]', obj)
                  if m not in ('x', ' ', '') and not m.startswith('http')]
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k not in ('__src', '__path'):
                _undefined_values(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _undefined_values(item, found)
    return found


def page_spec(path, kit_path=None):
    """→ 一頁的規格 dict。讀既有結構，不新增語彙。"""
    if kit_path:
        wf._load_kit(kit_path, explicit=True)
    doc = _load(path)
    base = re.sub(r'\.(wf\.)?ya?ml$', '', os.path.basename(path))
    merged = _with_layout(doc, path)
    states = []
    for route in doc.get('routes') or []:
        rid = wf._route_entry(route)[0]
        states.append(rid or 'default')
    tally = {}
    _count_leaves({k: v for k, v in merged.items() if k not in ('title', 'group')}, tally)
    flows = []
    for node, raw in flowmap.extract(path)[1]:
        for target, label in raw:
            if target:
                flows.append({'from': node, 'to': target, 'label': label or ''})
    for target, label in flowmap.walk_to(merged.get('__layout')):
        node = flowmap._node_of(target, base)
        if node:
            flows.append({'from': base, 'to': node, 'label': label or ''})
    undefined = _undefined_values(merged, [])
    return {'id': base, 'title': doc.get('title') or base, 'group': doc.get('group') or '',
            'extends': doc.get('extends'), 'states': states,
            'components': dict(sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))),
            'flows': flows, 'undefined': sorted(set(undefined))}


def spec_markdown(spec):
    lines = [f"# {spec['id']}　{spec['title']}" + (f"（{spec['group']}）" if spec['group'] else ''), '']
    if spec['extends']:
        lines.append(f"頁殼：`{spec['extends']}`")
    lines.append('狀態：' + (' / '.join(spec['states']) if spec['states'] else '（單一狀態）'))
    if spec['components']:
        parts = [f'`{name}` ×{count}' for name, count in spec['components'].items()]
        lines += ['', '## 元件', '、'.join(parts)]
    if spec['flows']:
        lines += ['', '## 動線']
        for flow in spec['flows']:
            label = f"（{flow['label']}）" if flow['label'] else ''
            lines.append(f"- {flow['from']} → {flow['to']}{label}")
    if spec['undefined']:
        lines += ['', '## 未定值', '、'.join(f'`[{v}]`' for v in spec['undefined'])]
    lines.append('')
    return '\n'.join(lines)


def spec_export(paths, fmt, kit_path=None):
    specs = [page_spec(path, kit_path) for path in paths]
    if fmt == 'json':
        import json
        print(json.dumps(specs, ensure_ascii=False, indent=2))
        return
    print('\n'.join(spec_markdown(s) for s in specs))



# ── gaps：源碼「沒說的事」───────────────────────────────────────────────
# AI 讀 YAML 能知道畫面有什麼，但推不出「這裡沒有宣告空狀態」——缺席無法從內容推出來。
# 這些洞 DSL 其實表達得了（routes + when 寫狀態、note: 寫 RD 約束），只是沒人提醒。
# 所以這支不產生另一份規格文件（那會變成第四份平行製品），而是像 lint / flow 一樣
# 指出源碼哪裡有洞，修法就在源碼本身。
#
# 全部是 info 級別、exit 0：只有單一狀態有時是刻意的，不該擋 CI。
# 只查自由輸入與選擇：checkbox / radio 是二元開關，標籤本身就是規格，
# 每個都要求 note: 只會製造雜訊（拿 IG 十個畫面實測出來的）。
_INPUT_ROLES = ('input', 'select')


def _expanded_body(doc, path):
    """kit 元件裡的輸入控制項也算這一頁的規格；展開失敗就退回原樹。"""
    body = doc.get('body')
    if not isinstance(body, list):
        return doc
    try:
        basedir = os.path.dirname(os.path.abspath(path)) or '.'
        wf._ensure_kit(basedir)
        return {**doc, 'body': wf.expand(body, basedir, {})}
    except Exception:
        return doc


def _collect_inputs(obj, found, label=None):
    """→ [(角色, 值的簡短描述, 有沒有 note)]。"""
    if isinstance(obj, dict):
        role = next((r for r in _INPUT_ROLES if r in obj), None)
        if role:
            value = obj[role]
            desc = value if isinstance(value, str) else (
                (value or {}).get('placeholder') or (value or {}).get('label') or '') if isinstance(value, dict) else ''
            found.append((role, str(desc)[:24], bool(obj.get('note'))))
        for k, v in obj.items():
            if k not in ('__src', '__path', 'note'):
                _collect_inputs(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _collect_inputs(item, found)
    return found


def page_gaps(path):
    """→ [(kind, 訊息)]。只報「源碼沒說的事」，不重講源碼已經說的。"""
    doc = _load(path)
    base = re.sub(r'\.(wf\.)?ya?ml$', '', os.path.basename(path))
    merged = _expanded_body(_with_layout(doc, path), path)
    out = []

    states = [wf._route_entry(r)[0] or 'default' for r in (doc.get('routes') or [])]
    if len(states) <= 1:
        out.append(('states', f'{base} 只有單一狀態 —— 空／錯誤／載入態都沒有宣告'
                              f'（用 routes: 加變體，元件內以 when: 切換）'))

    inputs = _collect_inputs(merged, [])
    bare = [f'`{desc or role}`' for role, desc, has_note in inputs if not has_note]
    if bare:
        out.append(('constraints', f'{base} 有 {len(bare)} 個輸入控制項沒有 note: 約束'
                                   f'（{"、".join(bare[:3])}{"…" if len(bare) > 3 else ""}）'
                                   f' —— 長度、必填、失敗行為這些 DSL 沒有語彙，寫在 note: 裡'))

    undefined = sorted(set(_undefined_values(merged, [])))
    if undefined:
        out.append(('undefined', f'{base} 有 {len(undefined)} 處未定值：'
                                 f'{"、".join(undefined[:4])}{"…" if len(undefined) > 4 else ""}'))
    return out


def gaps(paths, quiet=False):
    total = []
    for path in paths:
        total += [(path, kind, msg) for kind, msg in page_gaps(path)]
    if not quiet:
        for _, _, msg in total:
            print(f'info:  {msg}')
        by_kind = {}
        for _, kind, _ in total:
            by_kind[kind] = by_kind.get(kind, 0) + 1
        summary = '、'.join(f'{k} {v}' for k, v in sorted(by_kind.items())) or '無'
        print(f'═══ 規格缺口：{len(paths)} 畫面 / {len(total)} 項（{summary}）═══')
        print('（info 級別，不影響 exit code：只有單一狀態有時是刻意的）')
    return total


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ('flow', 'spec', 'gaps'):
        print(__doc__.strip(), file=sys.stderr)
        return 1
    cmd, rest = argv[0], argv[1:]
    if cmd == 'gaps':
        paths = [a for a in rest if not a.startswith('-')]
        if not paths:
            print('usage: wfcheck.py gaps <file.wf.yaml> [...] [--quiet]', file=sys.stderr)
            return 1
        gaps(paths, quiet='--quiet' in rest)
        return 0                      # info 級別，永遠不擋 CI
    if cmd == 'spec':
        fmt = next((rest[i + 1] for i, a in enumerate(rest) if a == '--format' and i + 1 < len(rest)), 'md')
        kit = next((rest[i + 1] for i, a in enumerate(rest) if a == '--kit' and i + 1 < len(rest)), None)
        paths = [a for a in rest if not a.startswith('-') and a not in (fmt, kit)]
        if not paths:
            print('usage: wfcheck.py spec <file.wf.yaml> [...] [--format md|json] [--kit <kit.yaml>]',
                  file=sys.stderr)
            return 1
        if fmt not in ('md', 'json'):
            print(f'error: spec 的 --format 只接受 md / json（收到 {fmt!r}）', file=sys.stderr)
            return 1
        spec_export(paths, fmt, kit)
        return 0
    entries = {rest[i + 1] for i, a in enumerate(rest) if a == '--entry' and i + 1 < len(rest)}
    quiet, stages = '--quiet' in rest, '--stages' in rest
    skip = entries | {'--entry', '--quiet', '--stages'}
    paths = [a for a in rest if not a.startswith('-') and a not in skip]
    if not paths:
        print('usage: wfcheck.py flow <file.wf.yaml> [...] [--entry <畫面>]', file=sys.stderr)
        return 1
    errors, warnings = check(paths, entries, quiet, stages)
    return 2 if errors else (1 if warnings else 0)


if __name__ == '__main__':
    sys.exit(main())
