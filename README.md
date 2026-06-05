# For Kal'tsit

> 寄予凯尔希。

---

基于 Electron + Vue 3 构建的凯尔希·思衡托 AI 桌面助手。还原《明日方舟》游戏内凯尔希的说话风格与人设，支持对话、语音播放与立绘交互。

## 功能

- Galgame 风格对话界面，PRTS 配色
- 凯尔希·思衡托精一立绘，触摸可触发对应原声台词
- AI 回复注入完整凯尔希人设（含游戏档案与 114 条台词）
- 关键词匹配语音播放，对话与语音严格对应
- 可自定义称呼、音量、立绘位置与大小
- PRTS 自定义光标
- 桌宠模式（webm 骨骼动画）

## 技术栈

- **前端**：Electron 31 + Vue 3 + Vite
- **后端**：Python FastAPI
- **AI**：Claude API（测试），目标切换 DeepSeek
- **语音**：游戏原声触发，后续接入 GPT-SoVITS

## 使用

```bash
# 安装前端依赖
cd app && npm install

# 安装后端依赖
cd backend && pip install -r requirements.txt

# 配置 API Key
cp backend/.env.example backend/.env
# 填入 ANTHROPIC_API_KEY

# 启动
cd app && npm run dev
```

## 注意

语音文件、立绘、游戏数据等资源文件不包含在仓库中，需自行准备。

---

*她来自过去，她属于现在。*
