#!/usr/bin/env python3
"""
flowmap.py — 掃一個資料夾下所有 *.wf.yaml，依其中的 `to:` 連結自動生成「畫面互動流程圖」。

節點來自 YAML 的 routes（一頁多路由 = 多個可定址節點），
連結來自 `to:`（`page` / `page#stage.state` / `#stage.state`）。link:（真超連結）不計入動線。
來源即真相：改 to: 重跑即同步。需 graphviz `dot`。

用法：python3 flowmap.py <資料夾> [-o out_basename]
"""
import sys, os, re, glob, subprocess, html, yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import wfyaml   # 複用 _route_entry（路由 → node id 規則一致）


def clean_label(s):
    s = re.sub(r'<[^>]*>', '', str(s))
    s = re.sub(r'\{\{[^}]*\}\}', '', s)          # 去未替換的 {{param}}
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:28]


def _label(obj):
    for k in ('text', 'button', 'name'):
        v = obj.get(k)
        if isinstance(v, str):
            return clean_label(v)
    return ''


_INLINE_TO = re.compile(r'\[([^\]]+)\]\(to:([^)]+)\)')  # inline 動線連結 [字](to:目標)


def walk_to(obj):
    """遞迴收集 (target, label)；吃 block 級 to、button 的 to、inline [字](to:目標)。
    link:（外部真連結）不計入動線 → 不遞迴其子樹、不收其 to。"""
    edges = []
    if isinstance(obj, dict):
        t = obj.get('to')
        if isinstance(t, str) and '://' not in t:
            edges.append((t, _label(obj)))
        for k, v in obj.items():
            if k == 'link':                    # link: = 外部，不計入動線
                continue
            edges += walk_to(v)
    elif isinstance(obj, list):
        for x in obj:
            edges += walk_to(x)
    elif isinstance(obj, str):
        for m in _INLINE_TO.finditer(obj):     # inline 只有帶 to: 前綴者算動線
            edges.append((m.group(2).strip(), m.group(1)))
    return edges


def _node_of(target, base):
    t = re.sub(r'\.html$', '', str(target))
    if '://' in t:
        return None
    page, _, frag = t.partition('#')
    page = page or base
    return page + ('.' + frag if frag else '')


def extract(path):
    """回傳 (base, [(node_id, [(tgt_node, label)]), ...])。routed → 每路由一個 node。"""
    doc = yaml.safe_load(open(path)) or {}
    base = re.sub(r'\.(wf\.)?ya?ml$', '', os.path.basename(path))
    routes = doc.get('routes')
    out = []
    if not routes:
        raw = walk_to(doc)
        out.append((base, [(_node_of(t, base), lbl) for t, lbl in raw]))
    else:
        for r in routes:
            rid, prov, _label_, _ctx_ = wfyaml._route_entry(r)
            node = base + ('.' + rid if rid else '')
            raw = walk_to(prov)
            out.append((node, [(_node_of(t, base), lbl) for t, lbl in raw]))
    return base, out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    out = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv else 'flowmap'
    folder = args[0] if args else '.'
    files = sorted(set(glob.glob(os.path.join(folder, '*.wf.yaml')) + glob.glob(os.path.join(folder, '*.yaml'))))
    files = [f for f in files if '/layouts/' not in f and '/components/' not in f
             and not os.path.basename(f).startswith(('layout', 'component'))]

    nodes, edges = set(), []
    for f in files:
        _, node_edges = extract(f)
        for node, es in node_edges:
            nodes.add(node)
            seen = {}
            for tgt, lbl in es:
                if tgt and tgt != node and (tgt not in seen or (not seen[tgt] and lbl)):
                    seen[tgt] = lbl
            for tgt, lbl in seen.items():
                edges.append((node, tgt, lbl))

    # 全域去重：同一 src→tgt 只畫一條（標籤取第一個非空）
    dedup = {}
    for s, t, lbl in edges:
        if (s, t) not in dedup or (not dedup[(s, t)] and lbl):
            dedup[(s, t)] = lbl
    edges = [(s, t, lbl) for (s, t), lbl in dedup.items()]

    if len(nodes) < 2:
        print(f"  flowmap: 略過（{len(nodes)} 個畫面，需 ≥2）")
        return
    targets = {t for _, t, _ in edges}
    sources = {s for s, _, _ in edges}
    nid = lambda n: '"' + n + '"'
    lines = ['digraph flow {', '  rankdir=LR; bgcolor="white"; pad=0.3; nodesep=0.4; ranksep=0.9;',
             '  node [fontname="Helvetica", fontsize=11]; edge [fontname="Helvetica", fontsize=9, '
             'color="#6b7280", fontcolor="#6b7280", arrowsize=0.8];']
    for n in sorted(nodes):
        entry, dead = n not in targets, n not in sources
        col = '#0d9488' if entry else ('#b45309' if dead else '#9ca3af')
        lines.append(f'  {nid(n)} [shape=box, style="rounded,filled", fillcolor="#f8fafc", '
                     f'color="{col}", penwidth=1.6, label="{n}"];')
    for t in sorted(targets - nodes):
        lines.append(f'  {nid(t)} [shape=box, style="rounded,dashed", color="#dc2626", '
                     f'fontcolor="#dc2626", label="{t}\\n(無對應路由)"];')
    for s, t, lbl in edges:
        attr = f' [label="{html.escape(lbl)}"]' if lbl else ''
        lines.append(f'  {nid(s)} -> {nid(t)}{attr};')
    lines.append('}')

    dot_path = os.path.join(folder, out + '.dot')
    open(dot_path, 'w').write('\n'.join(lines))
    for fmt in ('svg', 'png'):
        subprocess.run(['dot', '-T' + fmt, dot_path, '-o', os.path.join(folder, out + '.' + fmt)], check=True)
    print(f"  flowmap: {out}.svg + .png ({len(nodes)} 畫面, {len(edges)} 連結"
          + (f", {len(targets - nodes)} dangling" if targets - nodes else "") + ")")


if __name__ == '__main__':
    main()
