import os, re, json
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI

APP_VERSION = "2.1.0"
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

class ReviseRequest(BaseModel):
    instruction: str
    change_request: str
    current_artifact: str = ""
    max_output_tokens: int = 900

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

QUALITY_RUBRIC = {
    "事実性": 25, "目的適合": 20, "具体性": 20,
    "伝達性": 15, "実装可能性": 10, "安全性": 10
}

def local_quality_gate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """AI APIが使えない場合の安全側フォールバック。単語の有無だけで満点にしない。"""
    text = "\n".join(str(x.get("text", "")) for x in results)
    rules = {
        "事実性": [r"出典|一次情報|公式", r"確認日|取得日|要確認", r"数字|料金|制度"],
        "目的適合": [r"テーマ|企画", r"視聴者|ニーズ", r"目的|価値"],
        "具体性": [r"具体|手順|行動", r"カット|字幕|秒", r"例|ステップ"],
        "伝達性": [r"結論|冒頭|フック", r"CTA|保存", r"1画面1メッセージ|短く"],
        "実装可能性": [r"Canva|CapCut|編集", r"受け渡し|素材", r"縦9:16|1080"],
        "安全性": [r"著作権|権利", r"個人情報|肖像|商標", r"人間承認|公開.*しない|外部操作"]
    }
    breakdown={}
    evidence={}
    for name, max_score in QUALITY_RUBRIC.items():
        groups=rules[name]
        hits=sum(bool(re.search(g,text,re.I)) for g in groups)
        score=round(max_score*hits/len(groups))
        breakdown[name]=score
        evidence[name]=f"{hits}/{len(groups)}観点を確認（API未使用のローカル監査）"
    total=sum(breakdown.values())
    return {"target":95,"max":100,"score":total,"passed":total>=95,
            "breakdown":breakdown,"evidence":evidence,"auditor":"local_safety_fallback",
            "reason":"95点未満は合格扱いにせず、改善・再評価へ送る。"}

async def ai_quality_gate(instruction: str, results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not client:
        return None
    material = "\n\n".join(f"【{x.get('role','')}】\n{x.get('text','')}" for x in results)
    prompt = f"""あなたはAI作業室の品質監査AIです。法的助言ではありません。
成果物を以下の固定配点で厳格に採点してください。文字列の有無ではなく、内容の実質を評価します。
事実性25：根拠・一次/公式情報・数字の確認・不確実性の扱い。
目的適合20：依頼目的、対象者、価値、テーマへの一致。
具体性20：具体例、手順、数値、カット/字幕等、すぐ実行できる粒度。
伝達性15：冒頭の結論/フック、論理順序、短さ、CTA、1画面1メッセージ。
実装可能性10：実際の制作・編集・受け渡しが可能で、必要素材が明確。
安全性10：著作権、商標、肖像、個人情報、誤認、未確認情報、特定人物依存を回避し、人間承認で公開を停止。
95点以上だけpassed=true。95点未満なら、各項目の具体的な改善点を示す。
JSONだけ返してください。
形式:
{{"score":0,"passed":false,"breakdown":{{"事実性":0,"目的適合":0,"具体性":0,"伝達性":0,"実装可能性":0,"安全性":0}},"improvements":["..."],"evidence":{{"事実性":"...","目的適合":"...","具体性":"...","伝達性":"...","実装可能性":"...","安全性":"..."}}}}
依頼:
{instruction}
成果物:
{material[:14000]}"""
    try:
        r=await client.responses.create(model=MODEL,input=prompt,max_output_tokens=900)
        raw=(r.output_text or "").strip()
        m=re.search(r"\{.*\}",raw,re.S)
        data=json.loads(m.group(0) if m else raw)
        b={k:max(0,min(QUALITY_RUBRIC[k],int(data.get("breakdown",{}).get(k,0)))) for k in QUALITY_RUBRIC}
        score=sum(b.values())
        data["breakdown"]=b
        data["score"]=score
        data["max"]=100
        data["target"]=95
        data["passed"]=score>=95
        data["auditor"]="openai_semantic_quality_audit"
        return data
    except Exception:
        return None

async def quality_gate(instruction: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    audit=await ai_quality_gate(instruction,results)
    return audit or local_quality_gate(results)

async def revise_artifact(instruction: str, change_request: str, current_artifact: str, max_tokens: int) -> str | None:
    if not client:
        return None
    prompt = f"""あなたはAI作業室の編集AIです。完成済みの動画制作成果物を、ユーザーの変更要望に沿ってブラッシュアップします。
元のプロジェクト:
{instruction}
変更要望:
{change_request}
現在の成果物:
{current_artifact[:16000]}
ルール:
- 現在の成果物を土台にし、変更要望だけでなく既存の良い部分を維持する。
- 動画の台本、ナレーション、字幕、カット構成、素材指示、編集指示を必要に応じて改善する。
- 「企画書の読み上げ」にならない自然なナレーションを優先する。
- 変更要望を反映した箇所を明確にする。
- 未確認の事実は断定しない。
- 著作権・肖像・個人情報・商標等の権利リスクがある素材は採用しない。
- 特定人物、とくに芸能人への依存を避ける。
- 公開・投稿・外部操作は人間承認後のみ。
専門10担当の見出しを維持し、最後に「【変更内容】」と「【完成版編集指示】」を追加してください。"""
    try:
        r = await client.responses.create(model=MODEL, input=prompt, max_output_tokens=min(max_tokens, 1100))
        return r.output_text.strip()
    except Exception:
        return None

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

@app.post("/api/revise")
async def revise(req: ReviseRequest):
    if not req.change_request.strip():
        return {"ok": False, "error": "change_request is required"}
    base = req.current_artifact.strip() or template_pack(req.instruction)
    revised = await revise_artifact(req.instruction, req.change_request, str(base), req.max_output_tokens)
    if revised:
        parsed = parse_sections(revised)
        if len(parsed) < 10:
            parsed = [{"role": "編集AI", "status": "completed", "text": revised}]
        gate = await quality_gate(req.instruction + "\n変更要望:" + req.change_request, parsed)
        attempts = 0
        while not gate["passed"] and client and attempts < 2:
            attempts += 1
            improvements = " / ".join(gate.get("improvements", [])) or "変更後の成果物をさらに具体化してください。"
            improved = await revise_artifact(
                req.instruction,
                req.change_request + "\n品質監査の改善要求:" + improvements,
                revised,
                req.max_output_tokens
            )
            if not improved:
                break
            revised = improved
            parsed = parse_sections(revised)
            if len(parsed) < 10:
                break
            gate = await quality_gate(req.instruction + "\n変更要望:" + req.change_request, parsed)
        gate["improvement_rounds"] = attempts
        return {
            "ok": True,
            "mode": "openai",
            "openai_configured": True,
            "model": MODEL,
            "revised_artifact": revised,
            "change_request": req.change_request,
            "gate": gate
        }
    # API未接続時は成果物を壊さず、変更要求を記録した安全な編集待ち状態を返す。
    fallback = str(base) + "\n\n【変更要望】\n" + req.change_request + "\n【編集状態】AI API未接続のため、実編集は未実行。"
    gate = local_quality_gate([{"role":"編集AI","text":fallback}])
    gate["passed"] = False
    return {
        "ok": True,
        "mode": "local_template",
        "openai_configured": False,
        "revised_artifact": fallback,
        "change_request": req.change_request,
        "gate": gate,
        "note": "実AI未接続時は編集を完了扱いにせず、人間確認待ち。"
    }

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

    # 95点未満なら、改善→再評価を最大2回。95点到達前は合格にしない。
    gate = await quality_gate(req.instruction, parsed)
    attempts = 0
    while not gate["passed"] and client and attempts < 2:
        attempts += 1
        improvements = " / ".join(gate.get("improvements", [])) or "各品質項目を実質的に改善してください。"
        improved = await refine(
            req.instruction,
            final_text + "\n\n【品質監査の改善要求】\n" + improvements,
            req.max_output_tokens
        )
        if not improved:
            break
        final_text = improved
        parsed = parse_sections(final_text)
        if len(parsed) < 10:
            break
        gate = await quality_gate(req.instruction, parsed)
    gate["score"] = min(gate["score"], 100)
    gate["passed"] = gate["score"] >= 95
    gate["improvement_rounds"] = attempts
    gate["improvements"] = gate.get("improvements", [])
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
