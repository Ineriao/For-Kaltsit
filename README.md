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

## 技术栈

- **前端**：Electron 31 + Vue 3 + Vite
- **后端**：Python FastAPI
- **桌宠**：Java 17 + libGDX 1.11 + Spine Runtime 3.8.99
- **AI**：Claude API（测试），目标切换 DeepSeek
- **语音**：游戏原声触发，后续接入 GPT-SoVITS

## 目录结构

```
├── app/           Electron + Vue 3 对话界面
├── backend/       Python FastAPI + 凯尔希人设 System Prompt
├── kaltsit-pet/   Java libGDX 桌宠模块
└── assets/        立绘、语音、Spine 骨骼、光标资源
```

## 使用

```bash
# 安装前端依赖
cd app && npm install

# 安装后端依赖
cd backend && pip install -r requirements.txt

# 配置 API Key
cp backend/.env.example backend/.env
# 填入 ANTHROPIC_API_KEY

# 启动后端
cd backend && python main.py

# 启动前端
cd app && npm run dev

# 启动 Java 桌宠（需要 JDK 17）
# JAVA_HOME=C:/Program Files/Microsoft/jdk-17.0.17.10-hotspot
cd kaltsit-pet && gradlew run
```

## 待完成

- 桌宠点击交互（InputProcessor / FBO 像素检测调试）
- 桌宠位置对齐（physY 坐标系修正）
- GPT-SoVITS 声库训练
- Whisper STT 语音输入
- 切换 DeepSeek API
- 打包为 .exe

## 注意

语音文件、立绘、Spine 骨骼、游戏数据等资源文件不包含在仓库中，需自行准备。

---

*她来自过去，她属于现在。*
