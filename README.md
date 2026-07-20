# For Kal'tsit

> 寄予凯尔希。

---

基于 Electron + Vue 3 + Java libGDX 构建的凯尔希·思衡托 AI 桌面助手。还原《明日方舟》游戏内凯尔希的说话风格与人设，支持对话、语音播放与 Spine 骨骼动画桌宠。

## 功能

- Galgame 风格对话界面，PRTS 配色（源石冰蓝）
- 凯尔希·思衡托精一立绘，触摸可触发对应原声台词
- AI 回复注入完整凯尔希人设（含游戏档案、114条台词、第6-17章主线剧情台词共137条）
- 关键词匹配语音播放，对话与语音严格对应
- 可自定义称呼、音量、立绘位置与大小
- PRTS 2.1 + 凯尔希动态自定义光标
- 全局点击波纹动画（源石冰蓝发光圆环）
- **Java libGDX 桌宠**：Spine 3.8 骨骼动画，原版物理引擎（重力/摩擦/弹跳），行为状态机（Relax/Sit/Sleep/Move/Special），Win32 置顶高于任务栏，像素级点击穿透
- **双向连接**：双击桌宠自动唤起 AI 对话界面，关闭对话界面自动回到桌宠
- **本地记忆**：SQLite 持久化会话、长期记忆与可恢复备份
- **本地知识库**：FTS5 关键词检索、BGE 向量检索、PDF/DOCX/图片 OCR
- **本地语音输入**：SenseVoice Small INT8，支持静音自动发送
- **桌面工具**：经用户逐项授权后读取剪贴板、文本文件、目录搜索或屏幕快照
- **诊断与恢复**：运行时监控、安全模式、数据库备份和应用更新

## 技术栈

- **前端**：Electron 43 + Vue 3 + Vite 8
- **后端**：Python 3.11 + FastAPI + SQLite
- **桌宠**：Java 17 + libGDX 1.11 + Spine Runtime 3.8.99
- **AI**：DeepSeek API
- **语音**：游戏原声播放 + SenseVoice 本地识别；GPT-SoVITS 音色合成尚未接入

## 目录结构

```
├── app/           Electron + Vue 3 对话界面
├── backend/       Python FastAPI + 凯尔希人设 System Prompt
├── kaltsit-pet/   Java libGDX 桌宠模块
└── assets/        立绘、语音、Spine 骨骼、光标资源
    ├── cursors/       PRTS 2.1 + 凯尔希动态光标
    ├── illustration/  立绘 PNG
    ├── model/         webm 透明动画
    ├── spine/         Spine 骨骼文件
    └── voice/         原声语音库
```

## 使用

```bash
# 安装前端依赖
cd app && npm install

# 准备 Python 3.11 后端环境
cd app && npm run setup:backend

# 构建 Java 桌宠与精简运行时
npm run build:pet

# 启动开发模式
npm run dev

# 构建完整 Windows 安装包
npm run build
```

首次启动会要求导入 `assets` 目录并配置 DeepSeek API Key。Key 和本地接口令牌均通过 Windows 系统加密保存。

## 交互说明

| 操作 | 效果 |
|------|------|
| 单击桌宠 | 触发 Interact 动画 |
| 双击桌宠 | 展开 AI 对话界面 |
| 对话界面 ✕ | 隐藏对话界面，桌宠继续显示 |
| 拖动桌宠 | 自由移动，松手后物理落地 |
| 系统托盘 | 展开对话、显示桌宠或退出 |

## 注意

语音文件、立绘、Spine 骨骼、游戏数据等资源文件不包含在仓库中，需自行准备。

---

*她来自过去，她属于现在。*
