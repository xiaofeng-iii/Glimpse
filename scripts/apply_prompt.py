#!/usr/bin/env python3
import subprocess

# 获取 HEAD 版本的 memory_service.py
head_content = subprocess.check_output(['git', 'show', 'HEAD:services/memory_service.py'], text=True)
lines = head_content.split('\n')

# 修改 prompt 行
for i, line in enumerate(lines):
    if '为这张截图生成简短的中文摘要' in line:
        lines[i] = '                prompt="请直接描述画面内容和场景，不要提及载体类型（如截图、图片）。用简洁的中文描述界面元素、文字信息、操作意图和关键实体：",'
    elif '为这组截图生成一个综合的中文摘要' in line:
        lines[i] = '                prompt="请直接描述这些画面中的共同主题和关键内容，不要提及载体类型。用简洁的中文概括场景、界面、文字信息和核心实体：",'

with open('services/memory_service.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print('已应用 prompt 修改')
