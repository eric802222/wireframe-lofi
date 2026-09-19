#!/usr/bin/env python3
"""把文件裡的生成區塊從程式碼刷新。

    python3 tools/update_docs.py          # 寫回
    python3 tools/update_docs.py --check  # 只檢查有沒有漂掉（CI / 測試用）

能生成的只有「詞彙與事實」。為什麼這樣設計、怎麼上手，那些是判斷與脈絡，
生不出來也不該生 —— 它們留在區塊外面，手寫。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_ARGV = list(sys.argv)
sys.argv = [sys.argv[0]]
import wfyaml as wf          # noqa: E402

BEGIN = '<!-- BEGIN GENERATED: vocabulary -->'
END = '<!-- END GENERATED: vocabulary -->'
TARGETS = ('README.md', 'AGENTS.md', 'SKILL.md')


def block():
    return (f'{BEGIN}\n'
            f'<!-- 由 `python3 tools/update_docs.py` 從 wfyaml.py 的註冊表生成，請勿手改 -->\n\n'
            f'{wf._vocabulary_markdown()}\n\n{END}')


def main():
    check = '--check' in _ARGV
    stale = []
    for name in TARGETS:
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            continue
        text = open(path, encoding='utf-8').read()
        if BEGIN not in text:
            continue
        new = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END),
                     lambda _m: block(), text, flags=re.S)
        if new == text:
            continue
        if check:
            stale.append(name)
        else:
            open(path, 'w', encoding='utf-8').write(new)
            print(f'updated: {name}')
    if check and stale:
        print(f'文件生成區塊已過期：{", ".join(stale)}\n'
              f'請跑 `python3 tools/update_docs.py`', file=sys.stderr)
        return 1
    print('文件生成區塊與程式碼一致' if check else 'done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
