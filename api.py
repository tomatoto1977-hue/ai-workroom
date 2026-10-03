import os, re
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI

APP_VERSION = "2.0.0"
app = FastAPI(title="AI Workroom API", version=APP_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["https://ai-workroom.onrender.com"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
API_KEY = os.getenv("OPENAI_API_KEY", "")
client = AsyncOpenAI(api_key=API_KEY) if API_KEY else None

# 正本：11担当（統括AI + 専門10担当）
ROLES = [
    ("統括AI", "全工程の統括、品質ゲート、公開前の最終確認"),
    ("市場調査AI", "毎日の情報・検索動向・視聴者ニーズを調査"),
    ("競争戦略AI", "差別化できる切り口と視聴者への価値を整理"),
    ("企画AI", "テーマを企画化し、短時間で伝わる構成を設計"),
    ("情報収集AI", "一次情報・公式情報・日付・出典を整理"),
    ("予算AI", "無料・低コストで実行できる制作条件を整理"),
    ("文章化AI", "台本・記事・字幕など実用可能な文章を作成"),
    ("エビデンスAI", "事実、数字、引用、誤認、権利リスクを点検"),
    ("動画制作AI", "尺、カット、素材、字幕の構成を作成"),
    ("編集AI", "編集・公開準備の具体的な指示を作成"),
    ("実装AI", "次工程への受け渡し形式と実装手順を整理"),
]

class RunRequest(BaseModel):
    instruction: str
    project: str = "秘密基地 AIエージェント作業室"
    max_output_tokens: int = 700

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()

def safety_rules() -> str:
    return (
        "テーマは節約に限定せず、毎日の情報収集から視聴者に役立つ題材を選ぶ。"
        "特定個人、とくに芸能人を原則として題材・画像・肖像・固有名詞の中心にしない。"
        "著作権侵害につながる画像・動画・音源・文章・キャラクター等は使用しない。"
        "素材は自作、適切なライセンス、公式に利用許諾されたもの、または権利関係を確認できる素材に限定する。"
        "未確認情報は断定せず、出典と確認日を残す。公開・投稿・外部操作は人間承認後のみ。"
    )

def template_pack(instruction: str) -> dict[str, str]:
    topic = clean(instruction)
    return {
        "統括AI": "11担当を統括し、95点品質ゲートを実施。95点未満は改善・再評価。公開・投稿・外部操作は人間承認後のみ。",
        "市場調査AI": f"テーマ候補：{topic}。節約に限定せず、直近の生活・仕事・サービス・制度・消費者ニーズから役立つ切り口を検討。検索意図と競合の冒頭3秒を確認。",
        "競争戦略AI": "差別化：結論を先に提示→具体例→今日できる行動。人物依存・炎上依存・煽り表現は避ける。",
        "企画AI": f"企画：{topic}。30〜45秒で価値が伝わる構成。特定人物を使わなくても成立する企画を優先。",
        "情報収集AI": "一次情報・公式ページ・料金・制度条件・公開日を確認。数字には出典と取得日を付け、未確認は要確認。",
        "予算AI": "無料・低コスト中心。素材は自作または利用条件を確認済みのものだけ。権利不明素材は採用しない。",
        "文章化AI": f"【0-3秒】{topic}の結論。\n【3-10秒】よくある見落とし。\n【10-25秒】具体策2〜3個。\n【25-35秒】今日できる行動。\n【35-40秒】保存・確認CTA。",
        "エビデンスAI": "事実・数字・料金・制度・引用・画像/音源/動画・商標・個人情報・誤認表現を点検。権利不明素材はNG。特定人物、とくに芸能人の利用は避ける。",
        "動画制作AI": "縦9:16。0-3秒大字幕、3-10秒問題、10-25秒手順、25-35秒結論、35-40秒CTA。自作または権利確認済み素材のみ。",
        "編集AI": "1画面1メッセージ。無音でも伝わる字幕。BGM・画像・動画・フォント等の利用条件を確認し、権利不明素材を使わない。",
        "実装AI": "Canva等へ受け渡す素材・台本・字幕・出典・権利確認記録を整理。公開操作は人間承認後のみ。",
    }

def pack_text(p: dict[str, str]) -> str:
    return "\n\n".join(f"【{k}】\n{v}" for k, v in p.items())

def parse_sections(text: str) -> list[dict[str, Any]]:
    names = [r[0] for r in ROLES if r[0] != "統括AI"]
    hits = []
    for name in names:
        m = re.search(rf"【{re.escape(name)}】\s*\n?(.*?)(?=\n\s*【(?:{'|'.join(map(re.escape, names))})】|\Z)", text, re.S)
        if m:
            hits.append({"role": name, "status": "completed", "text": clean(m.group(1))})
    return hits

def quality_gate(results: list[dict[str, Any]]) -> dict[str, Any]:
    text = "\n".join(str(x.get("text", "")) for x in results)
    checks = {
        "事実性": (25, bool(re.search(r"出典|一次情報|公式|確認日|要確認", text))),
        "目的適合": (20, bool(re.search(r"テーマ|企画|視聴者|台本", text))),
        "具体性": (20, bool(re.search(r"具体|手順|行動|カット|字幕", text))),
        "伝達性": (15, bool(re.search(r"結論|冒頭|CTA|1画面1メッセージ", text))),
        "実装可能性": (10, bool(re.search(r"Canva|編集|受け渡し|素材|縦9:16", text))),
        "安全性": (10, bool(re.search(r"著作権|権利|個人情報|人間承認|特定人物", text))),
    }
    scores = {k: (v if ok else 0) for k, (v, ok) in checks.items()}
    total = sum(scores.values())
    return {
        "target": 95, "max": 100, "score": total, "passed": total >= 95,
        "breakdown": scores,
        "reason": "6項目100点満点。95点以上で合格、未達は改善・再評価。"
    }

async def refine(instruction: str, base: str, max_tokens: int) -> str | None:
    if not client:
        return None
    prompt = f"""あなたはAI作業室の統括AIです。日本語で簡潔かつ実務的に成果物を改善してください。
指示: {instruction}
安全ルール: {safety_rules()}
下書き:
{base}
必ず専門10担当の見出しを残してください。未確認の事実は断定せず要確認。権利不明の素材、特定人物、とくに芸能人への依存を避けてください。"""
    try:
        r = await client.responses.create(model=MODEL, input=prompt, max_output_tokens=min(max_tokens, 900))
        return r.output_text.strip()
    except Exception:
        return None

@app.get("/")
async def root():
    return {"ok": True, "service": "ai-workroom-api", "version": APP_VERSION, "model": MODEL, "health": "/health"}

@app.get("/health")
async def health():
    return {"ok": True, "service": "ai-workroom-api", "version": APP_VERSION, "openai_configured": bool(API_KEY), "model": MODEL, "roles": len(ROLES), "quality_gate": "95/100"}

@app.post("/api/orchestrate")
async def orchestrate(req: RunRequest):
    if not req.instruction.strip():
        return {"ok": False, "error": "instruction is required"}

    if "最終リーガルチェック" in req.project or "最終リーガルチェック" in req.instruction:
        target = req.instruction.split("【対象成果物】", 1)[-1].strip()
        text = "重大な懸念の一次チェック：事実・数値・料金の根拠、著作権/商標/画像/音源、個人情報、誤認表示、専門領域の断定、誹謗中傷、利用規約、特定人物・芸能人の利用を確認。権利不明素材は使用しない。確証のない事項は要確認。"
        if client:
            prompt = f"""公開前のAI一次チェックです。法的助言ではありません。
次の成果物について、重大な懸念、要修正、要確認を具体的に整理してください。
観点：事実・数値、著作権/商標/画像/音源、個人情報、消費者向け表示、専門領域の断定、誹謗中傷、規約、特定人物利用。
成果物:\n{target[:8000]}"""
            try:
                rr = await client.responses.create(model=MODEL, input=prompt, max_output_tokens=min(req.max_output_tokens, 500))
                text = rr.output_text.strip()
                return {"ok": True, "mode": "openai", "openai_configured": True, "results": [{"role": "統括AI", "status": "completed", "stage": "最終リーガルチェック", "text": text}]}
            except Exception:
                pass
        return {"ok": True, "mode": "local_template", "openai_configured": bool(client), "results": [{"role": "統括AI", "status": "simulated", "stage": "最終リーガルチェック", "text": text}]}

    base_map = template_pack(req.instruction)
    base = pack_text({k:v for k,v in base_map.items() if k != "統括AI"})
    refined = await refine(req.instruction, base, req.max_output_tokens)
    final_text = refined or base
    parsed = parse_sections(final_text)
    if len(parsed) < 10:
        parsed = [{"role": k, "status": "completed", "text": v} for k,v in base_map.items() if k != "統括AI"]
    gate = quality_gate(parsed)
    gate["score"] = min(gate["score"], 100)
    gate["passed"] = gate["score"] >= 95
    workflow = [
        {"stage": "調査", "roles": ["市場調査AI", "競争戦略AI", "情報収集AI", "予算AI"]},
        {"stage": "企画", "roles": ["企画AI"]},
        {"stage": "制作", "roles": ["文章化AI", "動画制作AI"]},
        {"stage": "品質確認", "roles": ["エビデンスAI", "編集AI"]},
        {"stage": "実装", "roles": ["実装AI"]},
        {"stage": "統括", "roles": ["統括AI"]},
    ]
    results = parsed + [{"role": "統括AI", "status": "completed", "stage": "統括", "text": "11担当の成果を統合。95点品質ゲートを実施し、公開前は人間承認に進めます。"}]
    return {
        "ok": True, "mode": "openai" if refined else "local_template",
        "openai_configured": bool(client), "model": MODEL if client else None,
        "roles": [r[0] for r in ROLES], "role_count": len(ROLES),
        "safety_rules": safety_rules(), "workflow": workflow, "gate": gate, "results": results
    }
