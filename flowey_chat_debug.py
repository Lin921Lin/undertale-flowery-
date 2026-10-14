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

# LLM 能力（密钥加载 / 人设组装 / DeepSeek 调用）统一放在 flowey_llm.py，
# 桌宠 flowey_pet.py 与调试台共用同一套人设，避免两份实现漂移。
import flowey_llm as LLM
from flowey_llm import (load_config, load_persona, load_lines_meta,
                        load_line_samples, build_system_prompt,
                        call_llm, parse_reply)

ROOT = LLM.ROOT
LOG_DIR = LLM.LOG_DIR

_NO_COLOR = os.environ.get("NO_COLOR") or not sys.stdout.isatty()


def _c(code: str) -> str:
    return "" if _NO_COLOR else code


C_FLOWER = _c("\033[93m")
C_USER = _c("\033[96m")
C_DIM = _c("\033[90m")
C_RED = _c("\033[91m")
C_RST = _c("\033[0m")


# （load_config / load_persona / load_lines_meta / load_line_samples 已迁到
#  flowey_llm.py，本文件顶部 import 复用，桌宠与调试台共用同一份实现。）


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


# （build_system_prompt / call_llm / parse_reply 已迁到 flowey_llm.py，
#  本文件顶部 import 复用。call_and_parse 带终端打印，属于 UI 层，留在这里。）


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
    if cfg is None:                     # load_config 不再抛异常，这里统一给提示
        raise SystemExit(
            f"{C_RED}[×] 密钥缺失或无效。\n"
            f"    复制 {LLM.TEMPLATE_FILE.name} 为 {LLM.KEY_FILE.name} 并填入 "
            f"deepseek_api_key，或设置环境变量 DEEPSEEK_API_KEY。{C_RST}")
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
