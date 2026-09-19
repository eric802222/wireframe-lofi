#!/usr/bin/env python3
"""把 wireframe-lofi bundle 轉成「沙箱 iframe 友善 + 窄螢幕可用」的版本。

改兩件事，仍然零 JS：
1. nav 與頁內 to: 連結 <a href="#..."> → <label for="..."> + 隱藏 radio
   （沙箱 iframe 會攔截所有 href 導覽，跳出「離開 Claude」對話框；label 不產生導覽）
2. 補 @media：窄螢幕時側欄變成頂部橫向捲動的頁籤，畫布置中
用法：python3 mobilize.py in.html out.html
"""
import re, sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()
pages = sorted(set(re.findall(r'id="(wf-pg-[a-z0-9._-]+)"', s)))

# 1. <a href="#wf-pg-x" ...> → <label for="r-wf-pg-x" ...>（保留其餘屬性）
def to_label(m):
    attrs = m.group(2)
    return f'<label for="r-{m.group(1)}"{attrs}>'
s = re.sub(r'<a href="#(wf-pg-[a-z0-9._-]+)"([^>]*)>', to_label, s)
s = re.sub(r'</a>', '</label>', s)

# 2. 隱藏 radio 放在 body 最前面（第一頁預設選取）
radios = ''.join(
    f'<input class="wf-r" type="radio" name="wfpg" id="r-{p}"{" checked" if i == 0 else ""}>'
    for i, p in enumerate(pages))
s = s.replace('<body class="wf-bundle">', '<body class="wf-bundle">' + radios, 1)

# 3. 覆寫 :target 規則 + 窄螢幕排版
show = ''.join(
    f'body:has(#r-{p}:checked) #{p}{{display:block !important;}}'
    f'body:has(#r-{p}:checked) #nav-{p}{{background:var(--wf-brand,#0f766e);color:#fff;font-weight:600;}}'
    for p in pages)
css = f'''
.wf-r{{position:absolute;width:0;height:0;opacity:0;pointer-events:none;}}
body:has(.wf-r:checked) .wf-pg{{display:none;}}
{show}
#wf-nav label{{cursor:pointer;}}
label[for^="r-wf-pg-"]{{cursor:pointer;}}
@media (max-width:860px){{
  .wf-bundle{{flex-direction:column;align-items:stretch;}}
  #wf-nav{{position:sticky;top:0;z-index:50;width:auto;max-width:none;height:auto;max-height:none;
    display:flex;gap:6px;overflow-x:auto;padding:8px;border-right:none;
    border-bottom:1px solid var(--wf-line,#334155);-webkit-overflow-scrolling:touch;}}
  #wf-nav .wf-navgrp{{margin:0;display:flex;flex-shrink:0;}}
  #wf-nav .wf-navgrp b{{display:none;}}
  #wf-nav label{{white-space:nowrap;padding:8px 12px;border-radius:8px;min-height:36px;display:flex;align-items:center;}}
  .wf-pg{{margin:0 auto;}}
}}
'''
s = s.replace('</style>', css + '</style>', 1)
open(dst, 'w', encoding='utf-8').write(s)
print(f'  mobilized: {dst}（{len(pages)} 頁，nav 改 label/radio，補窄螢幕排版）')
