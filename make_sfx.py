# -*- coding: utf-8 -*-
"""从录屏 mp4 提取桌宠音效：
    blip_talk.wav    逐字文字音（从 13.6s 的连续 blip 里挑一个干净的单音）
    voice_mimic.wav  变脸说话的整段声音（裁掉头尾静音）——通用变脸声（Asriel/Chara）
    laugh_evil.wav   邪恶笑声（裁掉头尾静音）
    voice_sans.wav / voice_asgore.wav / voice_papyrus.wav / voice_toriel.wav
                     四个角色的模仿语音（变脸学人说话时按 mimicOf 播放）
输出到 flowey_assets/audio/sfx/
"""
import os
import subprocess
import wave

import numpy as np

FF = r"C:\Users\zxl14\.workbuddy\binaries\python\envs\default\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
SRC_BASE = r"C:\Users\zxl14\Documents\xwechat_files\wxid_j4tbcxu0l62c12_e94c\msg\video\2026-10"
BASE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(BASE, "_sfx_tmp")
DST = os.path.join(BASE, "flowey_assets", "audio", "sfx")
SR = 44100

SRC = {
    "talk": "0082a31a3e85a398e55d57b757562347.mp4",
    "mimic": "f635227d5abe94ba3fb6cdf34d09967c.mp4",
    "laugh": "3535697fd9dcc94bd413587bf6c6798f.mp4",
}
# 变脸 / 笑声的裁剪区间（秒），依据包络分析
MIMIC_RANGE = (0.62, 4.58)
LAUGH_RANGE = (0.34, 2.92)

# 四角色模仿语音：文件名 + 包络分析得到的有声区间（录屏前段是静音/操作声）
VOICE_SRCS = {
    "sans": ("b1d26a6358eea21998e447f8b69dd6c1.mp4", (1.82, 4.70)),
    "asgore": ("1d5ce44700024cc82c2f4fbed9aa73c4.mp4", (4.53, 9.33)),
    "papyrus": ("abcc7ed77312fcb33926e93ec8c79f53.mp4", (3.68, 8.59)),
    "toriel": ("5fdc8beaca8c966bf4f9db2b0d92aaea.mp4", (1.54, 5.58)),
}


def load(name):
    """解码成 float32 单声道。name 可以是 SRC 的 key，或直接给文件名。"""
    src = os.path.join(SRC_BASE, SRC.get(name, name))
    wav = os.path.join(TMP, name.split(".")[0] + "_%d.wav" % SR)
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", src, "-vn", "-ac", "1", "-ar", str(SR),
                    "-c:a", "pcm_s16le", wav], check=True)
    with wave.open(wav, "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def save(path, a, fade_in_ms=3, fade_out_ms=15, peak_db=-1.5):
    a = a.copy()
    pk = np.max(np.abs(a))
    if pk > 0:
        a *= (10 ** (peak_db / 20.0)) / pk
    n_in = int(SR * fade_in_ms / 1000.0)
    n_out = int(SR * fade_out_ms / 1000.0)
    if n_in:
        a[:n_in] *= np.linspace(0.0, 1.0, n_in)
    if n_out:
        a[-n_out:] *= np.linspace(1.0, 0.0, n_out)
    pcm = np.clip(a * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return len(a) / SR


def segments(a, win_ms=5, rel_db=25):
    """返回 [(是否有声, 起止样本)]。"""
    win = int(SR * win_ms / 1000.0)
    rms = np.array([np.sqrt(np.mean(a[i:i + win] ** 2))
                    for i in range(0, len(a) - win, win)])
    db = 20 * np.log10(np.maximum(rms, 1e-9))
    on = db > (db.max() - rel_db)
    out, start, val = [], 0, on[0]
    for i, v in enumerate(on):
        if v != val:
            out.append((bool(val), start * win, i * win))
            val, start = v, i
    out.append((bool(val), start * win, len(on) * win))
    return out


def pick_blip(a, target_ms=85.0):
    """从连续 blip 录音里挑一个干净、时长接近 target、响度高的单音。"""
    segs = segments(a)
    cands = []
    for i, (on, s, e) in enumerate(segs):
        if not on:
            continue
        dur = (e - s) / SR * 1000.0
        if not (45 <= dur <= 140):
            continue
        prev_off = segs[i - 1][0] if i > 0 else False
        next_off = segs[i + 1][0] if i + 1 < len(segs) else False
        if prev_off or next_off:              # 前后必须都是静音
            continue
        pad = int(SR * 0.006)
        s2, e2 = max(0, s - pad), min(len(a), e + pad)
        rms = np.sqrt(np.mean(a[s2:e2] ** 2))
        score = rms - 0.0016 * abs(dur - target_ms)   # 时长偏离惩罚
        cands.append((score, dur, s2, e2, rms))
    cands.sort(reverse=True)
    print("  候选单音 %d 个，最优: %.0fms rms=%.4f" % (len(cands), cands[0][1], cands[0][4]))
    _, dur, s, e, _ = cands[0]
    return a[s:e]


def main():
    os.makedirs(DST, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)

    talk = load("talk")
    blip = pick_blip(talk)
    d = save(os.path.join(DST, "blip_talk.wav"), blip, fade_in_ms=2, fade_out_ms=8)
    print("blip_talk.wav    %.0fms" % (d * 1000))

    mic = load("mimic")
    s, e = int(MIMIC_RANGE[0] * SR), int(MIMIC_RANGE[1] * SR)
    d = save(os.path.join(DST, "voice_mimic.wav"), mic[s:e], fade_in_ms=25, fade_out_ms=120)
    print("voice_mimic.wav  %.2fs" % d)

    lg = load("laugh")
    s, e = int(LAUGH_RANGE[0] * SR), int(LAUGH_RANGE[1] * SR)
    d = save(os.path.join(DST, "laugh_evil.wav"), lg[s:e], fade_in_ms=20, fade_out_ms=160)
    print("laugh_evil.wav   %.2fs" % d)

    # ---- 四角色模仿语音（按包络裁剪，去掉录屏前段的静音/操作声）----
    for key, (fn, (t0, t1)) in VOICE_SRCS.items():
        a = load(fn)
        s, e = int(t0 * SR), int(min(t1, len(a) / SR) * SR)
        d = save(os.path.join(DST, "voice_%s.wav" % key), a[s:e],
                 fade_in_ms=25, fade_out_ms=140)
        print("voice_%-8s %.2fs  (%.2fs~%.2fs)" % (key, d, t0, t1))

    print()
    for f in sorted(os.listdir(DST)):
        print("  ", f, os.path.getsize(os.path.join(DST, f)), "bytes")


if __name__ == "__main__":
    main()
