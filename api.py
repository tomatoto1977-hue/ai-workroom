import os, asyncio
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI

app = FastAPI(title="AI Workroom API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai-workroom.onrender.com"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
API_KEY = os.getenv("OPENAI_API_KEY", "")
client = AsyncOpenAI(api_key=API_KEY) if API_KEY else None

ROLES = [
    ("統括AI", "全体工程を統括し、各担当の成果を統合する"),
    ("市場調査AI", "市場、読者ニーズ、競合状況を整理する"),
    ("競争戦略AI", "差別化、訴求軸、競争上の注意点を整理する"),
    ("企画AI", "調査と競争戦略をもとに企画を作る"),
    ("情報収集AI", "必要な事実、数値、根拠、一次情報の確認項目を整理する"),
    ("予算AI", "制作コスト、運用コスト、収益化上の前提を整理する"),
    ("文章化AI", "企画を読者に伝わる記事・台本へ文章化する"),
    ("エビデンスAI", "事実関係、根拠不足、誤解を招く表現を点検する"),
    ("動画制作AI", "文章を動画化するための構成、素材、尺を整理する"),
    ("編集AI", "編集指示、字幕、テンポ、完成条件を整理する"),
    ("実装AI", "次に必要な実装作業と受け渡し条件を整理する"),
]

class RunRequest(BaseModel):
    instruction: str
    project: str = "AI作業室"
    max_output_tokens: int = 700

@app.get("/")
async def root():
    return {"ok": True, "service": "ai-workroom-api", "health": "/health"}

@app.get("/health")
async def health():
    return {"ok": True, "service": "ai-workroom-api", "openai_configured": bool(API_KEY), "model": MODEL}

async def ask(role: str, job: str, instruction: str, context: str, max_output_tokens: int) -> dict[str, Any]:
    if not client:
        return {"role": role, "status": "waiting_api_key", "text": "OPENAI_API_KEY未設定のため待機中"}
    prompt = f"""あなたはAI作業室の{role}です。
役割: {job}
ユーザー指示: {instruction}
プロジェクト: {context}
他担当と重複しすぎず、自分の担当成果を簡潔に作成してください。
不確かな事実は断定せず、確認が必要なら明記してください。
出力は日本語で、次工程へ渡せる実務的な内容にしてください。"""
    try:
        r = await client.responses.create(model=MODEL, input=prompt, max_output_tokens=max_output_tokens)
        return {"role": role, "status": "completed", "text": r.output_text}
    except Exception as e:
        return {"role": role, "status": "error", "text": str(e)[:300]}

@app.post("/api/orchestrate")
async def orchestrate(req: RunRequest):
    if not req.instruction.strip():
        return {"ok": False, "error": "instruction is required"}
    if not client:
        simulated = [
            ("市場調査AI", "対象読者の悩みと検索意図を整理し、需要確認項目を抽出しました。"),
            ("競争戦略AI", "競合との差別化軸と、誤解を招かない訴求ポイントを整理しました。"),
            ("情報収集AI", "必要な一次情報・数値・根拠の確認項目を整理しました。"),
            ("予算AI", "制作・運用コストと収益化の前提を確認しました。"),
            ("企画AI", "調査結果を統合し、次工程へ渡せる企画案に整理しました。"),
            ("文章化AI", "企画を読者に伝わる構成へ文章化しました。"),
            ("動画制作AI", "動画化するための尺・構成・素材案を整理しました。"),
            ("編集AI", "字幕・テンポ・編集条件を整理しました。"),
            ("実装AI", "次に必要な実装作業と受け渡し条件を整理しました。"),
            ("エビデンスAI", "根拠不足や要確認表現を点検する項目を整理しました。"),
            ("統括AI", "各担当の成果を統合し、次工程へ渡す準備を整えました。"),
        ]
        return {"ok": True, "mode": "simulation", "openai_configured": False,
                "message": "APIキー未設定。料金の発生しない安全なシミュレーションです。",
                "results": [{"role": role, "status": "simulated", "text": text} for role, text in simulated]}
    # Independent research/strategy work starts in parallel, then downstream work receives their outputs.
    first = await asyncio.gather(
        ask(*ROLES[1], req.instruction, req.project, req.max_output_tokens),
        ask(*ROLES[2], req.instruction, req.project, req.max_output_tokens),
        ask(*ROLES[4], req.instruction, req.project, req.max_output_tokens),
        ask(*ROLES[5], req.instruction, req.project, req.max_output_tokens),
    )
    context = "\n\n".join(f"{x['role']}: {x['text']}" for x in first)
    downstream = await asyncio.gather(
        ask(*ROLES[3], req.instruction, context, req.max_output_tokens),
        ask(*ROLES[6], req.instruction, context, req.max_output_tokens),
        ask(*ROLES[8], req.instruction, context, req.max_output_tokens),
        ask(*ROLES[9], req.instruction, context, req.max_output_tokens),
        ask(*ROLES[10], req.instruction, context, req.max_output_tokens),
    )
    all_context = context + "\n\n" + "\n\n".join(f"{x['role']}: {x['text']}" for x in downstream)
    manager = await ask(*ROLES[0], req.instruction, all_context, req.max_output_tokens)
    evidence = await ask(*ROLES[7], req.instruction, all_context, req.max_output_tokens)
    return {"ok": True, "mode": "openai", "openai_configured": True, "model": MODEL,
            "results": first + downstream + [evidence, manager]}
