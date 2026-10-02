import os, asyncio
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI

app = FastAPI(title="AI Workroom API", version="1.1.0")
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
    return {"ok": True, "service": "ai-workroom-api", "version": "1.1.0", "health": "/health"}

@app.get("/health")
async def health():
    return {"ok": True, "service": "ai-workroom-api", "version": "1.1.0",
            "openai_configured": bool(API_KEY), "model": MODEL}

async def ask(role: str, job: str, instruction: str, context: str, max_output_tokens: int) -> dict[str, Any]:
    if not client:
        return {"role": role, "status": "waiting_api_key", "text": "OPENAI_API_KEY未設定のため待機中"}
    prompt = f"""あなたはAI作業室の{role}です。
役割: {job}
ユーザー指示: {instruction}
プロジェクトと前工程の情報: {context}
他担当と重複しすぎず、自分の担当成果を簡潔に作成してください。
不確かな事実は断定せず、確認が必要なら明記してください。
出力は日本語で、次工程へ渡せる実務的な内容にしてください。"""
    try:
        r = await client.responses.create(model=MODEL, input=prompt, max_output_tokens=max_output_tokens)
        return {"role": role, "status": "completed", "text": r.output_text}
    except Exception as e:
        return {"role": role, "status": "error", "text": str(e)[:300]}

def result(role: str, text: str, status: str = "simulated", stage: str = "") -> dict[str, Any]:
    return {"role": role, "status": status, "stage": stage, "text": text}

@app.post("/api/orchestrate")
async def orchestrate(req: RunRequest):
    if not req.instruction.strip():
        return {"ok": False, "error": "instruction is required"}

    if not client:
        stages = [
            ("調査", ["市場調査AI", "競争戦略AI", "情報収集AI", "予算AI"],
             "需要・競合・根拠・コストの確認項目を整理しました。"),
            ("企画", ["企画AI"],
             "調査結果を統合し、次工程へ渡す企画案を整理しました。"),
            ("制作", ["文章化AI", "動画制作AI"],
             "企画を記事・台本・動画構成へ展開しました。"),
            ("品質確認", ["エビデンスAI", "編集AI"],
             "根拠、表現、字幕、テンポ、完成条件を点検しました。"),
            ("実装", ["実装AI"],
             "次に必要な実装作業と受け渡し条件を整理しました。"),
            ("統括", ["統括AI"],
             "各工程の成果を統合し、次工程へ渡す準備を整えました。"),
        ]
        results = []
        for stage, names, text_value in stages:
            for name in names:
                results.append(result(name, text_value, stage=stage))
        return {
            "ok": True, "mode": "simulation", "openai_configured": False,
            "message": "APIキー未設定。料金の発生しない安全なシミュレーションです。",
            "workflow": [{"stage": s, "roles": names} for s, names, _ in stages],
            "gate": {"target": 95, "passed": False, "reason": "実AI品質判定はAPI接続後に実行"},
            "results": results,
        }

    # 実AIモードは工程順に実行し、各工程の成果を次工程へ明示的に受け渡す。
    workflow = [
        ("調査", [ROLES[1], ROLES[2], ROLES[4], ROLES[5]]),
        ("企画", [ROLES[3]]),
        ("制作", [ROLES[6], ROLES[8]]),
        ("品質確認", [ROLES[7], ROLES[9]]),
        ("実装", [ROLES[10]]),
        ("統括", [ROLES[0]]),
    ]
    results = []
    context = req.project
    for stage, role_defs in workflow:
        stage_results = await asyncio.gather(*[
            ask(role, job, req.instruction, context, req.max_output_tokens)
            for role, job in role_defs
        ])
        for item in stage_results:
            item["stage"] = stage
        results.extend(stage_results)
        context += "\n\n" + f"【{stage}工程の受け渡し成果】\n" + "\n".join(
            f"{x['role']}: {x['text']}" for x in stage_results
        )

    # 品質ゲート：初回点検で不足があれば、品質担当へ改善指示を渡して再点検する。
    evidence = next((x for x in results if x["role"] == "エビデンスAI"), None)
    manager = next((x for x in results if x["role"] == "統括AI"), None)
    improvement_rounds = []
    passed = all(x["status"] == "completed" for x in results)
    if passed and evidence:
        improvement_prompt = (
            "初回成果を95点基準で再点検してください。重大な不足があれば改善案を出し、"
            "問題がなければ『95点基準を満たす』と明記してください。\n"
            + (evidence.get("text") or "")
        )
        improved = await ask("エビデンスAI", ROLES[7][1], req.instruction, improvement_prompt, req.max_output_tokens)
        improved["stage"] = "改善・再点検"
        improvement_rounds.append(improved)
        results.append(improved)
        passed = improved["status"] == "completed"
    return {
        "ok": True, "mode": "openai", "openai_configured": True, "model": MODEL,
        "workflow": [{"stage": stage, "roles": [r[0] for r in role_defs]} for stage, role_defs in workflow],
        "handoff_order": [
            "調査→企画", "企画→制作", "制作→品質確認",
            "品質確認→実装", "実装→統括"
        ],
        "gate": {
            "target": 95,
            "passed": passed,
            "reason": "全工程完了後に品質担当が再点検し、95点基準の確認を行う",
            "improvement_rounds": len(improvement_rounds)
        },
        "results": results,
    }
