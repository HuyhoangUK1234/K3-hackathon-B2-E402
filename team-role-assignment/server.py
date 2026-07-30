"""FastAPI server: serves the RoleFit AI UI and the analysis/chat endpoints."""
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from src.pipeline import analyze_all, chat_reply

load_dotenv()

app = FastAPI(title="RoleFit AI")
STATIC = Path(__file__).parent / "static"


class AnalyzeRequest(BaseModel):
    setup: dict
    members: list[dict]


class ChatRequest(BaseModel):
    message: str
    state_summary: str = ""


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "openai_key": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "github_token": bool(os.getenv("GITHUB_TOKEN", "").strip())}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    if not req.members:
        return JSONResponse(status_code=400, content={"error": "Cần ít nhất 1 thành viên."})
    try:
        return analyze_all(req.setup, req.members)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        return {"reply": chat_reply(req.message, req.state_summary)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
