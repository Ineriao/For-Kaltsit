import os
import json
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prompt import KALTSIT_SYSTEM_PROMPT

# ── API 客户端 ──────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

# ── 静态资源路径 ────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
ASSETS_DIR = BASE_DIR / "assets"
VOICE_DIR  = ASSETS_DIR / "voice"          # assets/voice/凯尔希思衡托/*.wav
MODEL_DIR  = ASSETS_DIR / "model"          # assets/model/*.webm
SPRITE_PATH = ASSETS_DIR / "illustration" / "立绘_凯尔希·思衡托_1.png"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[凯尔希] 后端启动 :8765")
    yield
    print("[凯尔希] 后端关闭")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态目录
if VOICE_DIR.exists():
    app.mount("/voice", StaticFiles(directory=str(VOICE_DIR)), name="voice")
if MODEL_DIR.exists():
    app.mount("/model", StaticFiles(directory=str(MODEL_DIR)), name="model")
# 挂载 assets 目录（立绘、其他资源）
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


# ── 数据模型 ────────────────────────────────────────────────
class Message(BaseModel):
    role: str   # "user" | "assistant"
    text: str

class ChatRequest(BaseModel):
    messages: list[Message]


# ── 接口 ────────────────────────────────────────────────────
@app.post("/chat")
async def chat(req: ChatRequest):
    if not client.api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY 未配置")

    # 转换为 Anthropic messages 格式
    history = [
        {"role": m.role, "content": m.text}
        for m in req.messages
        if m.role in ("user", "assistant")
    ]

    # 保证最后一条是 user
    if not history or history[-1]["role"] != "user":
        raise HTTPException(400, "最后一条消息必须是 user")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=KALTSIT_SYSTEM_PROMPT,
        messages=history,
    )

    reply = response.content[0].text
    return {"reply": reply}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/assets")
async def assets():
    """返回可用资源列表"""
    voice_files = {
        folder: [f.name for f in (VOICE_DIR / folder).iterdir() if f.suffix == ".wav"]
        for folder in ["凯尔希", "凯尔希思衡托"]
        if (VOICE_DIR / folder).exists()
    }
    model_files = [f.name for f in MODEL_DIR.iterdir() if f.suffix == ".webm"] if MODEL_DIR.exists() else []
    return {
        "voice": voice_files,
        "models": model_files,
        "sprite": SPRITE_PATH.exists()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
