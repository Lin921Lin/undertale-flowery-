# -*- coding: utf-8 -*-
"""
Flowey LLM 对话调试台 —— 独立于桌宠，零第三方依赖（只用 urllib）。

用途：在接入桌宠之前，先用 DeepSeek 验证「人设是否立得住」。
数据源：persona.md（人格约束层）+ lines.json（台词库，抽样做风格校准）

用法：
  python flowey_chat_debug.py                      # 进入交互对话
  python flowey_chat_debug.py -m "你怎么在这"       # 单句对话
  python flowey_chat_debug.py --event double_click # 模拟桌宠事件，生成即兴台词
  python flowey_chat_debug.py --sample-per-event 4 # 每个事件抽 4 条台词做风格参考
  python flowey_chat_debug.py --no-lines           # 不带台词样本（看纯 persona 效果）

交互内命令：
  /reset   清空上下文      /temp 1.2  改温度
  /raw     打印原始回复    /sys       打印当前 system prompt
  /save    保存本轮日志    /quit 或 q 退出
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
KEY_FILE = ROOT / "secrets.local.json"
TEMPLATE_FILE = ROOT / "secrets.template.json"
PERSONA_FILE = ROOT / "persona.md"
LINES_FILE = ROOT / "lines.json"
LOG_DIR = ROOT / "chat_logs"

_NO_COLOR = os.environ.get("NO_COLOR") or not sys.stdout.isatty()


def _c(code: str) -> str:
    return "" if _NO_COLOR else code


C_FLOWER = _c("\033[93m")
C_USER = _c("\033[96m")
C_DIM = _c("\033[90m")
C_RED = _c("\033[91m")
C_RST = _c("\033[0m")


# ---------------------------------------------------------------- 配置加载
def load_config() -> dict:
    """优先级：环境变量 > secrets.local.json"""
    if not KEY_FILE.exists():
        raise SystemExit(
            f"{C_RED}[×] 找不到密钥文件：{KEY_FILE}\n"
            f"    复制 {TEMPLATE_FILE.name} 为 secrets.local.json 并填入 key。{C_RST}"
        )
    try:
        cfg = json.loads(KEY_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"{C_RED}[×] 密钥文件格式错误：{e}{C_RST}")

    key = os.environ.get("DEEPSEEK_API_KEY") or cfg.get("deepseek_api_key", "")
    key = (key or "").strip()
    if not key or key.startswith("sk-填") or len(key) < 20:
        raise SystemExit(
            f"{C_RED}[×] 密钥为空或无效，请检查 {KEY_FILE.name} 里的 deepseek_api_key。{C_RST}"
        )
    return {
        "api_key": key,
        "base_url": (cfg.get("deepseek_base_url") or "https://api.deepseek.com").rstrip("/"),
        "model": cfg.get("deepseek_model") or "deepseek-chat",
    }


# ---------------------------------------------------------------- 素材加载
def load_persona() -> str:
    if not PERSONA_FILE.exists():
        print(f"{C_DIM}[!] 未找到 persona.md，仅用内置兜底人设{C_RST}")
        return "你是 Flowey，一朵没有灵魂的金色小花。信条：在这个世界上，不是杀就是被杀。"
    return PERSONA_FILE.read_text(encoding="utf-8").strip()


def load_lines_meta() -> dict:
    """读 foci / 语气枚举 / speechNotes / 禁词"""
    if not LINES_FILE.exists():
        return {"tones": {}, "notes": [], "forbidden": []}
    data = json.loads(LINES_FILE.read_text(encoding="utf-8"))
    ch = data.get("character", {}) or {}
    tone_raw = ch.get("toneEnum") or {}
    tones: dict[str, str] = {}
    if isinstance(tone_raw, dict):
        tones = {k: str(v) for k, v in tone_raw.items()}
    elif isinstance(tone_raw, list):
        tones = {t: "" for t in tone_raw}
    return {
        "tones": tones,
        "notes": [str(x) for x in (ch.get("speechNotes") or [])],
        "forbidden": [str(x) for x in (ch.get("forbiddenWords") or [])],
    }


def load_line_samples(sample_per_event: int = 2, seed: int = 7, enabled: bool = True) -> str:
    """从 lines.json 抽样台词做风格校准。返回格式化文本"""
    if not enabled or not LINES_FILE.exists():
        return ""
    data = json.loads(LINES_FILE.read_text(encoding="utf-8"))
    rng = random.Random(seed)

    events = data.get("events", {}) or {}
    blocks: list[str] = []
    total = 0
    for ev_name, ev in events.items():
        ev_lines = (ev or {}).get("lines") or []
        if not isinstance(ev_lines, list) or not ev_lines:
            continue
        desc = (ev or {}).get("displayName", ev_name)
        picks = ev_lines if sample_per_event >= len(ev_lines) else rng.sample(ev_lines, sample_per_event)
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


# ------------------------------------------------------- OOC 校验（本地护栏）
SOFT_PATTERNS = [
    (r"一直在?(等你|看着你|守着|陪着)", "黏着式：说他一直在等/守/看"),
    (r"我(就在|都|永远|一直)?在(这里|这儿|原地|老地方)(等你|守着|看着你|不动)", "黏着式：原地等候"),
    (r"(跑不掉|躲不掉|我不会走|我不会离开|我不会消失|你甩不掉)", "黏着式威胁"),
    (r"(不会再?打扰|就不烦你|我先安静|那我闭嘴|随时都在|包在我身上|交给我吧)", "AI 服务型承诺"),
    (r"(多陪陪|陪我一会|理理我|看看我|别不理我)", "求关注"),
    (r"(你看的是他们|你笑的时候我在看|对我笑)", "双向情感暗示"),
    (r"(希望你能|愿你|祝你)[\u4e00-\u9fff]{0,6}(开心|顺利|好运)", "助手式祝福"),
]


def lint(text: str, forbidden: list[str]) -> list[str]:
    hits = [f"撞硬性禁词「{w}」" for w in forbidden if w and w in text]
    for pat, why in SOFT_PATTERNS:
        if re.search(pat, text):
            hits.append(why)
    if len(text) > 60:
        hits.append(f"过长（{len(text)} 字，建议 ≤45）")
    return hits


def build_system_prompt(persona: str, lines_block: str, meta: dict, free_chat: bool) -> str:
    tones: dict[str, str] = meta.get("tones", {})
    tone_lines = "\n".join(f"- `{k}`：{v}" for k, v in tones.items()) or "见 persona.md 语气阶梯"
    tone_names = "、".join(f"`{k}`" for k in tones) or "venom"
    notes = "\n".join(f"- {n}" for n in meta.get("notes", []))
    forbidden = meta.get("forbidden", [])
    mode = (
        "现在是**自由对话模式**：用户像逗宠物一样跟你说话，你按人设回应。"
        if free_chat
        else "现在是**事件触发模式**：桌宠刚发生指定事件，你要甩出对应的一句即兴台词。"
    )
    return f"""你是 Flowey —— 一朵有知觉的金色小花，被做成钉在用户屏幕上的桌宠。

================ persona.md（最高优先级）================
{persona}
================ persona.md 结束 ========================

{mode}

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
def call_llm(cfg: dict, messages: list[dict], temperature: float, timeout: int = 90) -> tuple[str, dict]:
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


def call_and_parse(cfg, messages, temperature, raw=False):
    content, usage = call_llm(cfg, messages, temperature)
    if raw:
        print(f"{C_DIM}--- raw ---\n{content}\n-----------{C_RST}")
    return parse_reply(content), usage


# ---------------------------------------------------------------- 会话
class Session:
    def __init__(self, cfg, system_prompt, temperature, max_turns, forbidden, auto_relint=True):
        self.cfg = cfg
        self.system = system_prompt
        self.temp = temperature
        self.max_turns = max_turns
        self.history: list[dict] = []
        self.log: list[dict] = []
        self.forbidden = forbidden
        self.auto_relint = auto_relint

    def messages(self) -> list[dict]:
        return [{"role": "system", "content": self.system}] + self.history

    def _gen(self, raw: bool) -> tuple[dict, dict]:
        return call_and_parse(self.cfg, self.messages(), self.temp, raw=raw)

    def say(self, user_text: str, raw: bool = False) -> tuple[dict, dict]:
        self.history.append({"role": "user", "content": user_text})
        keep = self.max_turns * 2
        if len(self.history) > keep:
            self.history = self.history[-keep:]

        obj, usage = self._gen(raw)
        hits = lint(str(obj.get("text", "")), self.forbidden)
        before = hits

        # 命中护栏 -> 让模型自己重写一次（保留攻击性，换掉黏着/服务型表达）
        if hits and self.auto_relint:
            fix = (
                "你上一句被本地护栏判为 OOC：" + "；".join(hits) + "。\n"
                "要求：保留同样的语气等级与攻击性，只换掉被点名的表达 —— "
                "把「等待 / 陪伴 / 不离开 / 承诺」一律改写成居高临下的嘲讽或记账式威胁，"
                "并把长度压到 45 字以内。只输出 JSON。"
            )
            self.history.append({"role": "assistant", "content": json.dumps(obj, ensure_ascii=False)})
            self.history.append({"role": "user", "content": fix})
            obj2, usage2 = self._gen(raw)
            usage = {
                "prompt_tokens": (usage.get("prompt_tokens", 0) or 0) + (usage2.get("prompt_tokens", 0) or 0),
                "completion_tokens": (usage.get("completion_tokens", 0) or 0) + (usage2.get("completion_tokens", 0) or 0),
                "total_tokens": (usage.get("total_tokens", 0) or 0) + (usage2.get("total_tokens", 0) or 0),
                "_seconds": round((usage.get("_seconds", 0) or 0) + (usage2.get("_seconds", 0) or 0), 2),
                "_retried": True,
            }
            hits2 = lint(str(obj2.get("text", "")), self.forbidden)
            obj, hits = obj2, hits2 if hits2 else []
            if hits2:
                obj["_lint"] = hits2
            if before:
                obj["_lint_before"] = before
        elif hits:
            obj["_lint"] = hits

        self.history.append({"role": "assistant", "content": json.dumps(obj, ensure_ascii=False)})
        self.log.append({"user": user_text, "reply": obj, "usage": usage})
        return obj, usage


def print_reply(obj: dict, usage: dict) -> None:
    tone = obj.get("tone", "?")
    text = obj.get("text", "")
    face = obj.get("face")
    extra = f" {C_DIM}face={face}{C_RST}" if face else ""
    print(f"{C_FLOWER}Flowey{C_RST} {C_DIM}[{tone}]{C_RST}{extra} {text}")
    if obj.get("_parse_fail"):
        print(f"{C_RED}       ! JSON 解析失败，已原样输出{C_RST}")
    if usage.get("_retried"):
        print(f"{C_DIM}       ↺ 首版撞护栏（{'；'.join(obj.get('_lint_before', []))}），已重写{C_RST}")
    if obj.get("_lint"):
        print(f"{C_RED}       ⚠ 重写后仍存疑：{'；'.join(obj['_lint'])}{C_RST}")
    u = usage or {}
    print(
        f"{C_DIM}       tokens in={u.get('prompt_tokens','?')} out={u.get('completion_tokens','?')} "
        f"total={u.get('total_tokens','?')} | {u.get('_seconds','?')}s{C_RST}"
    )


def save_log(sess: Session, tag: str = "chat") -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    p = LOG_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{tag}.json"
    p.write_text(
        json.dumps({"system": sess.system, "turns": sess.log}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return p


def check_key(cfg) -> bool:
    """快速连通性自检"""
    try:
        content, usage = call_llm(
            cfg,
            [{"role": "user", "content": "回复两个字：收到"}],
            temperature=0.0,
            timeout=30,
        )
        print(f"{C_FLOWER}[✓] 密钥可用{C_RST} model={cfg['model']} "
              f"latency={usage.get('_seconds')}s echo={content[:40]!r}")
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        print(f"{C_RED}[×] HTTP {e.code}: {body}{C_RST}")
    except Exception as e:
        print(f"{C_RED}[×] 连接失败：{e}{C_RST}")
    return False


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Flowey LLM 对话调试台")
    ap.add_argument("-m", "--message", help="单句对话模式")
    ap.add_argument("--event", help="模拟桌宠事件，如 double_click / idle / shutdown")
    ap.add_argument("--temp", type=float, default=1.05, help="温度，默认 1.05")
    ap.add_argument("--samples", type=int, default=2, help="每个事件抽样几条台词，默认 2，0=不用台词样本")
    ap.add_argument("--seed", type=int, default=7, help="台词抽样随机种子")
    ap.add_argument("--turns", type=int, default=8, help="保留多少轮上下文，默认 8")
    ap.add_argument("--raw", action="store_true", help="打印模型原始回复")
    ap.add_argument("--check", action="store_true", help="只做密钥连通性自检")
    ap.add_argument("--no-relint", action="store_true", help="关闭本地护栏与自动重写")
    ap.add_argument("--save", action="store_true", help="结束自动保存日志")
    args = ap.parse_args()

    cfg = load_config()
    if args.check:
        sys.exit(0 if check_key(cfg) else 1)

    persona = load_persona()
    meta = load_lines_meta()
    lines_block = load_line_samples(
        sample_per_event=args.samples, seed=args.seed, enabled=args.samples > 0
    )
    system = build_system_prompt(persona, lines_block, meta, free_chat=not args.event)
    sys_chars = len(system)

    print(f"{C_DIM}[i] model={cfg['model']} temp={args.temp} system={sys_chars}字 "
          f"台词样本={'开' if args.samples else '关'} 护栏={'开' if not args.no_relint else '关'} "
          f"密钥={cfg['api_key'][:7]}...{C_RST}")

    sess = Session(cfg, system, args.temp, args.turns, meta.get("forbidden", []),
                   auto_relint=not args.no_relint)

    # 事件模式
    if args.event:
        prompt = f"触发事件：{args.event}。按人设甩一句台词，只输出 JSON。"
        obj, usage = sess.say(prompt, raw=args.raw)
        print_reply(obj, usage)
        if args.save:
            print(f"{C_DIM}[✓] 已保存：{save_log(sess, args.event)}{C_RST}")
        return

    # 单句模式
    if args.message:
        obj, usage = sess.say(args.message, raw=args.raw)
        print_reply(obj, usage)
        if args.save:
            print(f"{C_DIM}[✓] 已保存：{save_log(sess, 'single')}{C_RST}")
        return

    # 交互模式
    greeting = {"tone": "sweet", "text": "Howdy！我是 Flowey。一朵名叫 Flowey 的花。……哦，是你在调试我？", "_preset": True}
    print(f"{C_FLOWER}Flowey{C_RST} {C_DIM}[{greeting['tone']}]{C_RST} {greeting['text']}")
    print(f"{C_DIM}输入 /reset /temp N /raw /sys /save /quit 查看命令；Ctrl+C 退出{C_RST}")

    while True:
        try:
            line = input(f"{C_USER}你>{C_RST} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C_DIM}（退出）{C_RST}")
            break
        if not line:
            continue
        if line.lower() in ("q", "quit", "exit", "/quit"):
            break
        if line == "/reset":
            sess.history.clear()
            print(f"{C_DIM}（上下文已清空）{C_RST}")
            continue
        if line == "/raw":
            args.raw = not args.raw
            print(f"{C_DIM}（原始输出：{'开' if args.raw else '关'}）{C_RST}")
            continue
        if line == "/sys":
            print(f"{C_DIM}{system}{C_RST}")
            continue
        if line == "/save":
            print(f"{C_DIM}[✓] 已保存：{save_log(sess)}{C_RST}")
            continue
        if line.startswith("/temp"):
            try:
                sess.temp = float(line.split()[1])
                print(f"{C_DIM}（温度 -> {sess.temp}）{C_RST}")
            except Exception:
                print(f"{C_DIM}（用法：/temp 1.2）{C_RST}")
            continue
        if line.startswith("/"):
            print(f"{C_DIM}（未知命令：{line}）{C_RST}")
            continue

        try:
            obj, usage = sess.say(line, raw=args.raw)
            print_reply(obj, usage)
        except urllib.error.HTTPError as e:
            print(f"{C_RED}[×] HTTP {e.code}: {e.read().decode('utf-8','ignore')[:300]}{C_RST}")
        except Exception as e:
            print(f"{C_RED}[×] 调用失败：{e}{C_RST}")

    if args.save or sess.log:
        print(f"{C_DIM}[✓] 日志：{save_log(sess)}{C_RST}")


if __name__ == "__main__":
    main()
