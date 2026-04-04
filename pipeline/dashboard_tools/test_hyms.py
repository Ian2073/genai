with open('C:/Users/kuosh/AppData/Roaming/Code/User/History/-2d639/hyms.py', 'r', encoding='utf-8') as f:
    text = f.read()
print("Contains 'Workbench':", 'Workbench' in text or '專案資產調整' in text)
print("Contains 'Playground':", 'Playground' in text or '一般 AI 工具' in text)
print("Contains 'toggleStoryInputMode':", 'toggleStoryInputMode' in text)
