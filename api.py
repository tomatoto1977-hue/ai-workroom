import os, asyncio
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI

app = FastAPI(title="AI Workroom API", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai-workroom.onrender.com"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
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
    return {"ok": True, "service": "ai-workroom-api", "version": "1.2.0", "health": "/health"}

@app.get("/health")
async def health():
    return {"ok": True, "service": "ai-workroom-api", "version": "1.2.0",
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

    # 品質ゲート：完了しただけでは合格にせず、品質判定AIが数値評価を行う。
    # 95点未満なら改善→再点検を最大3ラウンド行う。
    evidence = next((x for x in results if x["role"] == "エビデンスAI"), None)
    improvement_rounds = []
    quality_score = 0
    passed = False

    async def judge_quality(round_no: int, material: str) -> dict[str, Any]:
        prompt = f"""品質ゲート判定です。ラウンド{round_no}。
ユーザー指示: {req.instruction}
成果物:
{material}
100点満点で厳密に採点してください。
基準: 事実性25、目的適合20、具体性20、伝達性15、実装可能性10、安全性10。
JSONのみで返してください: {{"score":0,"issues":["..."],"improvements":["..."]}}
scoreは0〜100の整数。"""
        if not client:
            return {"score": 82, "issues": ["OPENAI_API_KEY未設定"], "improvements": ["API接続後に実品質判定"]}
        try:
            r = await client.responses.create(model=MODEL, input=prompt, max_output_tokens=400)
            import json
            raw = r.output_text.strip()
            data = json.loads(raw)
            return {"score": max(0, min(100, int(data.get("score", 0)))),
                    "issues": data.get("issues", []), "improvements": data.get("improvements", [])}
        except Exception as e:
            return {"score": 0, "issues": [f"品質判定エラー: {str(e)[:180]}"], "improvements": []}

    material = "\n".join(f"{x['role']}: {x['text']}" for x in results if x.get("status") == "completed")
    for round_no in range(1, 4):
        judged = await judge_quality(round_no, material)
        quality_score = judged["score"]
        improvement_rounds.append({"round": round_no, **judged})
        if quality_score >= 95:
            passed = True
            break
        if round_no < 3 and judged["improvements"]:
            improve_prompt = (
                f"品質ゲート{quality_score}点。以下の改善点をすべて反映して、次工程へ渡せる完成版に更新してください。"
                f"改善点: {judged['improvements']}\n現成果:\n{material}"
            )
            improved = await ask("統括AI", ROLES[0][1], req.instruction, improve_prompt, req.max_output_tokens)
            improved["stage"] = f"改善ラウンド{round_no}"
            results.append(improved)
            if improved["status"] == "completed":
                material += "\n\n【改善版】\n" + improved["text"]

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
            "score": quality_score,
            "reason": "95点以上のみ合格。未達時は改善→再点検を最大3ラウンド実施",
            "improvement_rounds": improvement_rounds
        },
        "results": results,
    }
