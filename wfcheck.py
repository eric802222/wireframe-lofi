#!/usr/bin/env python3
"""動線完整性檢查：孤島、死路、斷鏈、跨階段。

    python3 wfcheck.py flow <file.wf.yaml> [...] [--entry <畫面>] [--stages] [--quiet]

「哪邊動線不見了」不該靠人看。這支把 `to:` 走成一張圖，報告結構上的破洞：

- **斷鏈**：`to:` 指向不存在的畫面 → error
- **孤島**：沒有任何入口的畫面（宣告的進入點除外）→ error
- **死路**：沒有任何出口的畫面 → error
- **跨階段**：動線跨越 `group:` → 預設只計數（共用畫面本來就會跨）；`--stages` 才逐條列出

exit code 與 lint 一致：0 乾淨 / 1 有 warning / 2 有 error，可直接放進 CI。
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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] != 'flow':
        print(__doc__.strip(), file=sys.stderr)
        return 1
    rest = argv[1:]
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
