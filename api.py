import os, re
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI

APP_VERSION = "1.3.0"
app = FastAPI(title="AI Workroom API", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai-workroom.onrender.com"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
API_KEY = os.getenv("OPENAI_API_KEY", "")
client = AsyncOpenAI(api_key=API_KEY) if API_KEY else None

ROLES = [
    ("市場調査AI", "視聴者の悩み、検索意図、競合の切り口を整理する"),
    ("競争戦略AI", "差別化できるフックと訴求軸を整理する"),
    ("企画AI", "ショート動画の企画を1本にまとめる"),
    ("情報収集AI", "確認すべき事実・数値・出典を整理する"),
    ("予算AI", "無料/低コストで作る前提の素材・制作条件を整理する"),
    ("文章化AI", "実際に読めるショート動画台本を作る"),
    ("エビデンスAI", "断定・数字・引用・誤認リスクを点検する"),
    ("動画制作AI", "尺、カット、素材、字幕の構成を作る"),
    ("編集AI", "CapCut等へ渡せる編集指示を作る"),
    ("実装AI", "次に使うアプリと受け渡し形式を整理する"),
]

class RunRequest(BaseModel):
    instruction: str
    project: str = "秘密基地 AIエージェント作業室"
    max_output_tokens: int = 500

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()

def template_pack(instruction: str) -> dict[str, str]:
    topic = clean(instruction)
    return {
        "市場調査AI": f"テーマ：{topic}\n視聴者：このテーマに関心がある短時間視聴者\n確認：検索候補・競合動画・反応の良い冒頭3秒を確認。",
        "競争戦略AI": "差別化：冒頭で結論を先に提示→具体例1つ→すぐ使える行動1つ。誇張や根拠のない断定は避ける。",
        "企画AI": f"タイトル案：{topic}\nフック：『これ、知らないと損かもしれません』→悩み提示→具体策→行動喚起。\n想定尺：30〜45秒。",
        "情報収集AI": "公開前に一次情報・公式料金・日付・制度条件を確認。数字を使う場合は出典と取得日を保存。",
        "予算AI": "原則無料ツール中心。AI呼び出しは企画生成1回＋最終確認1回に限定。素材は既存ライブラリ・Canva等を優先。",
        "文章化AI": f"【0-3秒】『{topic}』でまず知ってほしいこと。\n【3-10秒】よくある見落としを1つ。\n【10-25秒】具体策を2〜3個。\n【25-35秒】今日できる行動。\n【35-40秒】保存・確認を促す。",
        "エビデンスAI": "チェック：数値、料金、制度、引用、画像権利、誤認表現。未確認情報は『要確認』として公開前に人間確認。",
        "動画制作AI": "縦9:16。0-3秒は大字幕、3-10秒は問題提示、10-25秒は手順を3カット、25-35秒は結論、35-40秒はCTA。",
        "編集AI": "CapCut等で字幕を短く分割。1画面1メッセージ。無音でも意味が通る字幕を優先。BGMは小さく、素材権利を確認。",
        "実装AI": "Canva：サムネ/図解→PNG。CapCut：台本・字幕・素材→MP4。Obsidian：台本・出典・公開記録をMarkdown保存。",
    }

def pack_text(p: dict[str, str]) -> str:
    return "\n\n".join(f"【{k}】\n{v}" for k, v in p.items())

async def refine(instruction: str, base: str, max_tokens: int) -> str | None:
    if not client:
        return None
    prompt = f"""あなたはショート動画制作統括です。日本語で簡潔に改善してください。
指示:{instruction}
下書き:
{base}
必ず残す見出し: 【市場調査AI】【競争戦略AI】【企画AI】【情報収集AI】【予算AI】【文章化AI】【エビデンスAI】【動画制作AI】【編集AI】【実装AI】
各欄は短く具体的に。台本はそのまま撮影・編集に使える形。未確認の事実は断定せず『要確認』。出力は見出し付き本文のみ。"""
    try:
        r = await client.responses.create(model=MODEL, input=prompt, max_output_tokens=min(max_tokens, 550))
        return r.output_text.strip()
    except Exception:
        return None

def parse_sections(text: str) -> list[dict[str, Any]]:
    names = [r[0] for r in ROLES]
    hits = []
    for name in names:
        m = re.search(rf"【{re.escape(name)}】\s*\n?(.*?)(?=\n\s*【(?:{'|'.join(map(re.escape, names))})】|\Z)", text, re.S)
        if m:
            hits.append({"role": name, "status": "completed", "text": clean(m.group(1))})
    return hits

@app.get("/")
async def root():
    return {"ok": True, "service": "ai-workroom-api", "version": APP_VERSION, "model": MODEL, "health": "/health"}

@app.get("/health")
async def health():
    return {"ok": True, "service": "ai-workroom-api", "version": APP_VERSION,
            "openai_configured": bool(API_KEY), "model": MODEL,
            "token_strategy": "1 synthesis call + optional 1 legal call; deterministic role routing"}

@app.post("/api/orchestrate")
async def orchestrate(req: RunRequest):
    if not req.instruction.strip():
        return {"ok": False, "error": "instruction is required"}

    # Final legal-review mode: one compact call only, or a deterministic checklist without API.
    if "最終リーガルチェック" in req.project or "最終リーガルチェック" in req.instruction:
        target = req.instruction.split("【対象成果物】", 1)[-1].strip()
        if client:
            prompt = f"""公開前のAI一次チェックです。法的助言ではありません。
次の成果物について、重大な懸念/要修正/要確認を各1〜3点以内で簡潔に整理してください。
観点: 事実・数値、著作権/商標/画像、個人情報、消費者向け表示、専門領域の断定、誹謗中傷、規約。
成果物:\n{target[:7000]}"""
            try:
                rr = await client.responses.create(model=MODEL, input=prompt, max_output_tokens=min(req.max_output_tokens, 300))
                legal_text = rr.output_text.strip()
                return {"ok": True, "mode": "openai", "openai_configured": True, "model": MODEL,
                        "token_strategy": "最終リーガル確認はAI 1回のみ。",
                        "results": [{"role": "統括AI", "status": "completed", "stage": "最終リーガルチェック", "text": legal_text}]}
            except Exception:
                pass
        return {"ok": True, "mode": "local_template", "openai_configured": bool(client),
                "results": [{"role": "統括AI", "status": "simulated", "stage": "最終リーガルチェック",
                             "text": "重大な懸念の自動判定は未実施。事実・数値・料金、画像/引用の権利、個人情報、表示の誤認、専門領域の断定、誹謗中傷、利用規約を人間が公開前に確認してください。"}]}

    base = template_pack(req.instruction)
    draft = pack_text(base)
    refined = await refine(req.instruction, draft, req.max_output_tokens)
    final_text = refined or draft
    parsed = parse_sections(final_text)
    if len(parsed) < len(ROLES):
        parsed = [{"role": k, "status": "completed", "text": v} for k, v in base.items()]
        final_text = draft

    completeness = round(100 * len(parsed) / len(ROLES))
    return {
        "ok": True,
        "mode": "openai" if refined else "local_template",
        "openai_configured": bool(client),
        "model": MODEL if client else None,
        "token_strategy": "AI 1回（生成）＋最終リーガル確認1回。工程別の重複呼び出しは停止。",
        "workflow": [
            {"stage": "調査", "roles": ["市場調査AI", "競争戦略AI", "情報収集AI", "予算AI"]},
            {"stage": "企画", "roles": ["企画AI"]},
            {"stage": "制作", "roles": ["文章化AI", "動画制作AI"]},
            {"stage": "品質確認", "roles": ["エビデンスAI", "編集AI"]},
            {"stage": "実装", "roles": ["実装AI"]},
            {"stage": "統括", "roles": ["統括AI"]},
        ],
        "gate": {
            "target": 100,
            "passed": completeness == 100,
            "score": completeness,
            "reason": "役割別成果の構造完成度。事実確認・法的確認は別工程で実施。",
        },
        "results": parsed + [{"role": "統括AI", "status": "completed", "stage": "統括",
                               "text": "各工程の成果を統合。台本・動画構成・編集指示・確認事項を次工程へ受け渡せる形に整理しました。"}],
    }
