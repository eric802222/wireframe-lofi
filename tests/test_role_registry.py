"""角色註冊表的不變式。

單獨成檔而不是塞進 test_regressions.py：那個檔已經裝了六個互不相干的類別，
「regression」不是一個職責。而且所有人都往同一個檔尾追加，平行 PR 必然撞在最後一行
（這批 PR 已經解過三次同樣的衝突）。
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfyaml as wf          # noqa: E402

class RoleRegistryInvariants(unittest.TestCase):
    """角色的三張平行表由註冊表導出 —— #48 那類「補了兩張、漏第三張」不該再發生。"""

    def test_every_role_is_bindable_or_says_why_not(self):
        for name in wf.LEAF_ROLES:
            spec = wf._ROLE_SPECS[name]
            self.assertTrue(bool(spec.selector) != bool(spec.unthemable_reason),
                            f'{name}: 要嘛有選擇器，要嘛講明為什麼綁不到，不能兩者皆有或皆無')

    def test_longer_role_prefixes_sort_first(self):
        # render_leaf / lint 靠 next(r for r in LEAF_ROLES if r in node) 挑角色，
        # 'text' 若排在 'text.title' 前面，標題會被當成一般文字算出去。
        for i, name in enumerate(wf.LEAF_ROLES):
            for later in wf.LEAF_ROLES[i + 1:]:
                self.assertFalse(later.startswith(name + '.'),
                                 f'`{later}` 必須排在 `{name}` 前面')

    def test_text_class_and_selectors_derive_from_registry(self):
        self.assertEqual(wf.TEXT_CLASS,
                         {n: s.text_class for n, s in wf._ROLE_SPECS.items() if s.text_class})
        for name, spec in wf._ROLE_SPECS.items():
            if spec.selector:
                self.assertEqual(wf._THEME_ELEMENT_SELECTORS[name], spec.selector)

    def test_annotation_keys_have_one_definition(self):
        import re as _re
        src = open(os.path.join(ROOT, 'wfyaml.py'), encoding='utf-8').read()
        literal = _re.findall(r"\{'name', 'to', 'note', 'spotlight'", src)
        self.assertEqual(len(literal), 1,
                         '節點級標註只能有 _ANNOTATION_KEYS 一個定義（曾經有三份手抄複本）')


if __name__ == "__main__":
    unittest.main()
