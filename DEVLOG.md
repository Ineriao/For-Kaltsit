# 开发日志

## 2026-06-07 · Phase 2

### 完成内容

**Java libGDX 桌宠模块（kaltsit-pet）**
- Spine 3.8.99 骨骼动画加载（Building 基建皮肤）
- GLFW 透明无边框窗口
- 原版 `Plane.java` 物理引擎（重力 800/空气摩擦 100/地面摩擦 500）
- 行为状态机：RELAX(55%) / SIT(10%) / SLEEP(6%) / MOVE_L(12%) / MOVE_R(12%) / SPECIAL(5%)
- `InputProcessor` 接口处理鼠标事件（参照 ArkPets 源码）
- FBO 离屏渲染，用于像素级点击穿透检测
- Win32 `SetWindowPos(HWND_TOPMOST)` 置顶，高于任务栏
- IPC Server 监听 Electron 发来的指令（show/hide/quit/touch）
- 左右移动时 Spine `scaleX` 翻转，正确转向

**Electron 端**
- PetMode 改用 `Relax_alpha.webm`（PNG序列帧经 ffmpeg 合并为 VP9 Alpha WebM）
- 对话框毛玻璃透明度降低（`rgba(8,10,14,0.35)`）
- 全局点击波纹动画（源石冰蓝发光圆环）
- 桌宠模式双击展开对话，右键弹原生菜单

**资源整理**
```
assets/
├── cursors/    PRTS 2.1 光标 + 凯尔希动态光标
├── illustration/  立绘 PNG
├── model/webm  基建 webm 动画
├── spine/      Spine 骨骼文件
└── voice/      原声语音库
reference/
└── ArknightsGameData-master/
```

### 遗留问题（下次继续）

1. **桌宠位置偏高**：physY 坐标系与屏幕对齐计算有偏差，角色没站在任务栏上
2. **点击交互无响应**：FBO 像素检测 Y 坐标翻转或 `GLFW_MOUSE_PASSTHROUGH` 时机问题
3. **Sit/Sleep 截断**：动画骨骼超出窗口底边，需调整骨骼 Y 偏移或加大窗口高度

---

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

**语音系统**
- 38条原声 × 2语音库（凯尔希 + 思衡托）= 76条 .wav
- 触摸立绘：9条台词与语音严格一一对应，随机不重复
- AI 回复：关键词匹配对应语音，无命中则随机对话语音
- 初始化自动播放任命助理语音
- 设置面板可调音量（实时生效）

**AI 人设**
- System Prompt 注入：档案五段故事 + 全部 114 条游戏台词风格
- 称呼可自定义（默认：真理），替换回复中的 `{@nickname}`

### 已知问题
- Electron 无边框透明窗口的 `-webkit-app-region: drag` 与子元素交互冲突（Electron 已知 bug）
- 拖拽通过右上角把手 IPC 实现，有轻微延迟


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
