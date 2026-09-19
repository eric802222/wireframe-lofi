"""文件的生成區塊不能漂掉。

詞彙表原本有五份手抄：程式碼、`list` 的 print 字串、README、SKILL.md、AGENTS.md。
沒有任何機制強迫同步，於是 max-lines / wrap 加進 DSL 之後，五份裡有四份不知道它存在 ——
AI 照著 `list` 查詞彙，拿到的是過期的世界模型。

現在只有程式碼一份，其餘生成。這個測試就是那個「強迫同步」的機制。
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfyaml as wf          # noqa: E402


class GeneratedDocsAreCurrent(unittest.TestCase):

    def test_generated_blocks_match_code(self):
        r = subprocess.run([sys.executable, str(ROOT / 'tools' / 'update_docs.py'), '--check'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_every_role_and_annotation_appears(self):
        text = wf._vocabulary_text()
        for name in wf.LEAF_ROLES:
            self.assertIn(name, text, f'角色 `{name}` 沒出現在詞彙表')
        for key in wf._ANNOTATION_KEYS:
            self.assertIn(key, text, f'節點標註 `{key}` 沒出現在詞彙表')

    def test_list_command_serves_the_same_vocabulary(self):
        r = subprocess.run([sys.executable, str(ROOT / 'wfyaml.py'), 'list', '--ring', '0'],
                           capture_output=True, text=True)
        for key in ('max-lines', 'wrap', 'text.hint', 'pin'):
            self.assertIn(key, r.stdout, f'`list` 少了 {key}')


if __name__ == '__main__':
    unittest.main()
