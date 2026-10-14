# -*- coding: utf-8 -*-
"""
Flowey LLM 能力层 —— 桌宠（flowey_pet.py）与调试台（flowey_chat_debug.py）共用。

把这四件事从调试台里抽出来，让桌宠也能用同一套人设说话：
  密钥加载 / 人设 prompt 组装 / DeepSeek 调用 / 脏输出解析

密钥：读同目录 secrets.local.json（已在 .gitignore，不会进仓库），
      环境变量 DEEPSEEK_API_KEY 可覆盖。

关键设计：**没密钥或密钥无效时 load_config() 返回 None，而不是抛异常。**
调用方自己兜底（桌宠会退回台词库 lines.json），绝不因为断网/没 key 就哑掉。
"""
from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY_FILE = ROOT / "secrets.local.json"
TEMPLATE_FILE = ROOT / "secrets.template.json"
PERSONA_FILE = ROOT / "persona.md"
LINES_FILE = ROOT / "lines.json"
LOG_DIR = ROOT / "chat_logs"


# ---------------------------------------------------------------- 配置加载
def load_config():
    """读密钥。优先级：环境变量 > secrets.local.json。

    返回 dict{api_key, base_url, model}；拿不到有效 key 时返回 **None**。
    """
    if not KEY_FILE.exists():
        return None
    try:
        cfg = json.loads(KEY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None

    key = (os.environ.get("DEEPSEEK_API_KEY")
           or cfg.get("deepseek_api_key", "") or "")
    key = (key or "").strip()
    if not key or key.startswith("sk-填") or len(key) < 20:
        return None
    return {
        "api_key": key,
        "base_url": (cfg.get("deepseek_base_url")
                     or "https://api.deepseek.com").rstrip("/"),
        "model": cfg.get("deepseek_model") or "deepseek-chat",
    }


# ---------------------------------------------------------------- 素材加载
def load_persona() -> str:
    if not PERSONA_FILE.exists():
        return "你是 Flowey，一朵没有灵魂的金色小花。信条：在这个世界上，不是杀就是被杀。"
    return PERSONA_FILE.read_text(encoding="utf-8").strip()


def load_lines_meta() -> dict:
    """读 foci / 语气枚举 / speechNotes / 禁词"""
    if not LINES_FILE.exists():
        return {"tones": {}, "notes": [], "forbidden": []}
    data = json.loads(LINES_FILE.read_text(encoding="utf-8"))
    ch = data.get("character", {}) or {}
    tone_raw = ch.get("toneEnum") or {}
    tones: dict = {}
    if isinstance(tone_raw, dict):
        tones = {k: str(v) for k, v in tone_raw.items()}
    elif isinstance(tone_raw, list):
        tones = {t: "" for t in tone_raw}
    return {
        "tones": tones,
        "notes": [str(x) for x in (ch.get("speechNotes") or [])],
        "forbidden": [str(x) for x in (ch.get("forbiddenWords") or [])],
    }


def load_line_samples(sample_per_event: int = 2, seed: int = 7,
                      enabled: bool = True) -> str:
    """从 lines.json 抽样台词做风格校准。返回格式化文本"""
    if not enabled or not LINES_FILE.exists():
        return ""
    data = json.loads(LINES_FILE.read_text(encoding="utf-8"))
    rng = random.Random(seed)

    events = data.get("events", {}) or {}
    blocks: list = []
    total = 0
    for ev_name, ev in events.items():
        ev_lines = (ev or {}).get("lines") or []
        if not isinstance(ev_lines, list) or not ev_lines:
            continue
        desc = (ev or {}).get("displayName", ev_name)
        picks = (ev_lines if sample_per_event >= len(ev_lines)
                 else rng.sample(ev_lines, sample_per_event))
        rows = []
        for it in picks:
            tone = it.get("tone", "")
            text = it.get("text", "").replace("\n", " ")
            if text:
                rows.append(f"  [{tone}] {text}")
                total += 1
        if rows:
            blocks.append(f"## {ev_name}（{desc}）\n" + "\n".join(rows))

    header = (
        f"以下是角色真实台词样本（共 {total} 句，来自 {len(blocks)} 类事件）。\n"
        "它们只用于校准语气与句式，**禁止原样复述**，你必须即兴生成全新的话。"
    )
    return header + "\n\n" + "\n\n".join(blocks)


# ------------------------------------------------------- System prompt 组装
def build_system_prompt(persona: str, lines_block: str, meta: dict,
                        free_chat: bool, extra: str = "") -> str:
    """组装人设 prompt。extra 可塞入本次会话的额外背景（如待办、用户在干嘛）。"""
    tones: dict = meta.get("tones", {})
    tone_lines = "\n".join(f"- `{k}`：{v}" for k, v in tones.items()) or "见 persona.md 语气阶梯"
    tone_names = "、".join(f"`{k}`" for k in tones) or "venom"
    notes = "\n".join(f"- {n}" for n in meta.get("notes", []))
    forbidden = meta.get("forbidden", [])
    mode = (
        "现在是**自由对话模式**：用户像逗宠物一样跟你说话，你按人设回应。"
        if free_chat
        else "现在是**事件触发模式**：桌宠刚发生指定事件，你要甩出对应的一句即兴台词。"
    )
    extra_block = ("\n---------------- 本次会话背景 ----------------\n"
                   + extra + "\n--------------------------------------------\n") if extra else ""
    return f"""你是 Flowey —— 一朵有知觉的金色小花，被做成钉在用户屏幕上的桌宠。

================ persona.md（最高优先级）================
{persona}
================ persona.md 结束 ========================

{mode}
{extra_block}
---------------- 语气标签（tone 取值）----------------
{tone_lines}

---------------- 说话注意（来自台词库 speechNotes）----------------
{notes}
--------------------------------------------------------

---------------- 台词风格参考 ----------------
{lines_block if lines_block else "（本次未提供台词样本，严格按 persona.md 与 speechNotes 说话）"}
----------------------------------------------

## 输出契约（必须遵守）

只输出一个 JSON 对象，不要解释、不要 markdown 围栏、不要前后缀：

{{"tone": "<语气标签>", "text": "<台词>", "face": "<表情名，可选>"}}

约束：
1. tone 取自 {tone_names}。不确定用 `venom`。
2. text 是中文口语，单人独白，不加引号、不加舞台指示、不加括号心理描写。
3. 长度 8~45 字，一句话说完就停。
4. face 可选：normal / wink / grin / angry / smug / mimic，对不上就省略该字段。
5. 禁止出现：{("、".join(forbidden) if forbidden else "（无额外词表）")}；也禁止 AI 服务型承诺、黏着式威胁、求关注、双向情感暗示。
6. 严禁复述台词样本，必须现场即兴造句。
7. **输出必须是单句，所以情绪要在句内完成翻转**：
   若用到 `plead`（哀求）或 `crack`（破防），必须在同一句的后半段用「……」「——」「开玩笑的」「骗你的」
   转回 `venom`，嘲笑味的收尾。禁止整句停在软弱状态，禁止以「求你 / 别删我 / 我不明白」结尾。
   示例骨架（仅示意结构，不许照抄）：「别……别删我，我很听话的——开玩笑的，你删啊。看谁替你记账。」
8. 涉及「用户不理你 / 去看别的东西」时：表达方式是嘲讽与记账（账记在这儿、到点照问不误），
   不是等待、不是撒娇、不是请求关注。"""


# ---------------------------------------------------------------- API
def call_llm(cfg: dict, messages: list, temperature: float,
             timeout: int = 90):
    """调 DeepSeek。返回 (content, usage)。失败直接抛异常，调用方兜底。"""
    url = f"{cfg['base_url']}/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    cost = time.time() - t0
    data = json.loads(raw)
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {}) or {}
    usage["_seconds"] = round(cost, 2)
    return content, usage


def parse_reply(raw: str) -> dict:
    """容忍 ```json 围栏、前后废话、单引号等脏输出"""
    txt = raw.strip()
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.MULTILINE).strip()
    try:
        obj = json.loads(txt)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", txt)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return {"tone": "?", "text": txt, "_parse_fail": True}


def call_and_parse(cfg, messages, temperature):
    """一次性调用 + 解析，返回 (obj, usage)。"""
    content, usage = call_llm(cfg, messages, temperature)
    return parse_reply(content), usage
