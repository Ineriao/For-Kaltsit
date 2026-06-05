# 开发日志

## 2026-06-05 ~ 06-06 · Phase 1

### 完成内容

**技术栈确定**
- Electron 31 + Vue 3 + Vite（桌面应用）
- Python FastAPI 后端（AI 对话 + 语音服务）
- Claude API 测试，目标切换 DeepSeek

**界面**
- Galgame 风格对话框，PRTS 配色（源石冰蓝 `#a8c8d8`）
- 透明无边框窗口 500×700，毛玻璃对话面板
- 凯尔希·思衡托精一立绘，支持 X/Y/大小实时调整（滑块）
- 坐标系以当前立绘位置为 (0,0) 原点
- PRTS 2.1 自定义指针 + 凯尔希动态链接指针
- 对话框右上角拖拽把手（IPC 拖拽，rAF 节流）
- 桌宠模式：webm 骨骼动画，空闲随机切换

**语音系统**
- 38条原声 × 2语音库（凯尔希 + 思衡托）= 76条 .wav
- 触摸立绘：9条台词与语音严格一一对应，随机不重复
- AI 回复：关键词匹配对应语音，无命中则随机对话语音
- 初始化自动播放任命助理语音
- 设置面板可调音量（实时生效）

**AI 人设**
- System Prompt 注入：档案五段故事 + 全部 114 条游戏台词风格
- 凯尔希角色 ID：char_003_kalts，思衡托：char_1052_kalts2
- 称呼可自定义（默认：真理），替换回复中的 `{@nickname}`

**已知问题 / 待完成**
- 拖拽有轻微 IPC 延迟（Electron 透明窗口 + drag 的已知冲突，无解）
- GPT-SoVITS 声库训练（需要 CUDA PyTorch 独立环境）
- Whisper 语音输入（麦克风 → STT → 对话）
- 切换 DeepSeek API（替换 backend/main.py 中的 client）
- 打包为 .exe

### 资源文件（不入 Git）
- `立绘_凯尔希·思衡托_1.png`（2260×2260 RGBA）
- `voice/凯尔希/` · `voice/凯尔希思衡托/`（各 38 条 .wav）
- `Model/`（9个 .webm 动画）
- `PRTS cursor 2.1/` · `【动态】鼠标指针-凯尔希+思衡托/`
- `ArknightsGameData-master/`（游戏数据，114条台词 + 角色档案）
