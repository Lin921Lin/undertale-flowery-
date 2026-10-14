# -*- coding: utf-8 -*-
"""
把 02_battle_faces 的黑底战斗素材加工成桌宠可直接使用的对齐素材。

流程（源图均为黑底白图，黑白双色）：
1. 边缘泛洪(BFS)：与画布边缘连通的近黑像素 -> 透明；被白色包围的内部黑(五官/轮廓)保留。
2. 统一画布 96x120：每个素材按「内容包围盒中心」对齐到锚点 (48, 60)。
   - talk / winking / laugh 内容尺寸完全一致(82x86)，对齐后切换像素级无缝。
   - appear 为弹出动画，整体只用一个固定偏移(取定格帧 #8 计算保持内部运动连贯)。
3. appear 只截取帧 0..8（弹出 -> 定格），定格帧时长压缩为 400ms，打包为播一次的出场 GIF。

输出到 flowey_assets/02_battle_faces_trans/：
    idle_rest.png        待机静止帧（闭嘴，上下浮动用；取 appear 定格帧，与出场末帧同构图）
    idle_talk.gif        说话时嘴动循环
    blink_wink.png       吐舌眨眼（挑衅台词 / 学 Sans、Papyrus 说话时用）
    laugh.gif            大笑循环（manic/狠话台词用）
    mimic_face.png       假关心脸 = Asriel 脸（学 Toriel/Asgore 等模仿台词用）
    frisk_face.png       Frisk 脸（模仿台词讲到重置之类的事、且不恼怒时用）
    evil_face.png        嘲讽脸（学 Sans/Papyrus 说完话后变出来的狞笑，源自互联网黑白素材）
    intro_appear.gif     出场（播一次, 8帧）
    outro_sink.gif       退场（钻地离开，播一次, 7帧：定格100ms -> 缩回消失）

所有产物统一处理：
- 2 画布像素黑色描边（OUTLINE_PX）：素材本体是白色，白底页面/文档上会和背景融在
  一起看不见轮廓，1px 太细，加粗到 2px 后深浅背景都清晰。
- 轮廓内部不允许有透明底（fill_enclosed_holes）：不与画布边缘连通的透明「洞」
  全部填实——战斗素材填黑（并进描边剪影），evil_face 填白（它本体是描边画，
  填白后和白花风格一致：白瓣黑线）。

注：受击帧 hurt 已废弃删除（太丑，破防台词改用静止帧）。
"""

import os
from collections import deque

from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "flowey_assets", "02_battle_faces")
DST = os.path.join(BASE, "flowey_assets", "02_battle_faces_trans")

CANVAS = (96, 120)   # 统一画布
ANCHOR = (48, 60)    # 内容包围盒中心的目标位置
BLACK_THRESHOLD = 40
OUTLINE_PX = 2       # 描边厚度（1px 太细，白底上看不清轮廓）
NOTCH_FILL_PX = 2    # 花瓣间凹缝封口半径（仿 UT 原版黑缝分隔；实测 k=2 最像）

INTRO_FRAMES = range(0, 8)   # appear 出场只播「弹出 + 定格」（第7帧为定格姿态，与源第8帧内容相同）
INTRO_HOLD_MS = 400          # 定格帧时长（源为 1500ms，桌宠用更干脆）

OUTRO_FRAMES = [8] + list(range(11, 17))
# 退场钻地：帧8=定格起手；帧11..16=逐帧缩回消失。
# 故意跳过帧10：那是「向上拔高」的姿势(78x96，比定格还高)，插在钻地序列里
# 视觉上就是「钻下去又冒出来一次再钻」——即用户反馈的「重复钻俩次才成功」。
OUTRO_HOLD_MS = 100          # 起手定格时长（源1500ms）


def _is_black(px):
    return px[0] < BLACK_THRESHOLD and px[1] < BLACK_THRESHOLD and px[2] < BLACK_THRESHOLD


def strip_black_bg(im_rgba):
    """边缘泛洪：与画布边缘连通的黑色像素全部置为透明。"""
    px = im_rgba.load()
    w, h = im_rgba.size
    seen = [[False] * w for _ in range(h)]
    dq = deque()

    for x in range(w):
        for y in (0, h - 1):
            if not seen[y][x] and _is_black(px[x, y]):
                seen[y][x] = True
                dq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not seen[y][x] and _is_black(px[x, y]):
                seen[y][x] = True
                dq.append((x, y))

    while dq:
        x, y = dq.popleft()
        px[x, y] = (0, 0, 0, 0)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] \
                    and _is_black(px[nx, ny]):
                seen[ny][nx] = True
                dq.append((nx, ny))
    return im_rgba


def add_outline(fr, rgb=(0, 0, 0, 255), thickness=OUTLINE_PX):
    """给不透明内容的轮廓加 thickness 像素黑描边。

    每一轮：所有「紧贴不透明区域的透明像素」涂成描边色，然后以扩大后的
    不透明区域为基准再来一轮 -> thickness=2 就是双像素描边。
    只往透明侧扩张，不动素材本体；必须在对齐(paste_aligned)之后调用，
    这样对齐基准不受描边影响。
    """
    px = fr.load()
    w, h = fr.size
    for _ in range(max(1, int(thickness))):
        opaque = [[px[x, y][3] >= 128 for x in range(w)] for y in range(h)]
        ring = []
        for y in range(h):
            row = opaque[y]
            up = opaque[y - 1] if y > 0 else None
            dn = opaque[y + 1] if y + 1 < h else None
            for x in range(w):
                if row[x]:
                    continue
                if ((x > 0 and row[x - 1]) or (x + 1 < w and row[x + 1])
                        or (up is not None and up[x]) or (dn is not None and dn[x])):
                    ring.append((x, y))
        for x, y in ring:
            px[x, y] = rgb
    return fr


def fill_enclosed_holes(fr, rgb=(0, 0, 0, 255)):
    """把「不与画布边缘连通」的透明洞全部填实。

    小林要求：轮廓内部不允许有透明底存在——不然白底页面会从花瓣缝里透过去，
    看起来是破的。战斗素材填黑（洞本来就被描边围着，填黑并进剪影）；
    evil_face 本体是描边画，填白后和白花风格一致。
    返回填掉的像素数。
    """
    px = fr.load()
    w, h = fr.size
    outside = [[False] * w for _ in range(h)]
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if px[x, y][3] < 128 and not outside[y][x]:
                outside[y][x] = True
                dq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if px[x, y][3] < 128 and not outside[y][x]:
                outside[y][x] = True
                dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not outside[ny][nx] \
                    and px[nx, ny][3] < 128:
                outside[ny][nx] = True
                dq.append((nx, ny))
    filled = 0
    for y in range(h):
        for x in range(w):
            if px[x, y][3] < 128 and not outside[y][x]:
                px[x, y] = rgb
                filled += 1
    return fr, filled


def fill_notches_black(fr, k=NOTCH_FILL_PX):
    """把「凹进轮廓的窄缝」填成黑色（仿 UT 原版：花瓣之间是黑色分隔，不透底）。

    花瓣之间的凹缝与画布外部连通，fill_enclosed_holes 够不到；这里把
    不透明区域膨胀 k 像素把缝口封住，再从画布边缘泛洪求外部区域，
    凡「封口后仍到不了边缘」的透明像素就是凹缝 -> 填黑。
    k=2 只封 <=4px 的窄缝；头/茎之间的大间隙（>=8px）封不住，仍保持分离。
    必须在 add_outline 之后调用（描边也是不透明区的一部分）。
    """
    w, h = fr.size
    px = fr.load()
    opq = [[px[x, y][3] > 128 for x in range(w)] for y in range(h)]
    dil = [row[:] for row in opq]
    for _ in range(max(1, int(k))):
        src = [row[:] for row in dil]
        for y in range(h):
            row = src[y]
            up = src[y - 1] if y > 0 else None
            dn = src[y + 1] if y + 1 < h else None
            for x in range(w):
                if row[x]:
                    continue
                if ((x > 0 and row[x - 1]) or (x + 1 < w and row[x + 1])
                        or (up is not None and up[x])
                        or (dn is not None and dn[x])):
                    dil[y][x] = True
    outside = [[False] * w for _ in range(h)]
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not dil[y][x] and not outside[y][x]:
                outside[y][x] = True
                dq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not dil[y][x] and not outside[y][x]:
                outside[y][x] = True
                dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not outside[ny][nx] \
                    and not dil[ny][nx]:
                outside[ny][nx] = True
                dq.append((nx, ny))
    filled = 0
    for y in range(h):
        for x in range(w):
            if not opq[y][x] and not outside[y][x]:
                px[x, y] = (0, 0, 0, 255)
                filled += 1
    return fr, filled


def finish_frame(fr, hole_rgb=(0, 0, 0, 255), notch_fill=True):
    """每帧收尾：加粗描边 -> 填死轮廓内部的透明洞 -> 凹缝填黑。

    注：头/身桥接已停用（2026-10-14 用户最终确认）——要 UT 原版的样子：
    花头浮在细茎上方，头和茎各自独立、中间透明，不要接成一体。
    notch_fill：花瓣间凹缝填黑（仿参考图的黑缝分隔），头/茎大间隙不受影响。
    """
    add_outline(fr)
    fill_enclosed_holes(fr, hole_rgb)
    if notch_fill:
        fill_notches_black(fr)
    return fr


def _content_bbox(fr):
    xs = [x for y in range(fr.height) for x in range(fr.width) if fr.getpixel((x, y))[3] > 128]
    ys = [y for y in range(fr.height) for x in range(fr.width) if fr.getpixel((x, y))[3] > 128]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


def _paste_aligned(fr, shift):
    """把帧按固定偏移贴到统一画布上。"""
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.paste(fr, shift, fr)
    return canvas


def _shift_for_bbox(bb):
    """内容包围盒中心 -> ANCHOR 所需的画布偏移。"""
    cx = (bb[0] + bb[2]) / 2.0
    cy = (bb[1] + bb[3]) / 2.0
    dx = int(round(ANCHOR[0] - cx))
    dy = int(round(ANCHOR[1] - cy))
    return (dx, dy)


def _to_palette_frame(fr):
    """RGBA 帧 -> P 模式帧。调色板: 0=白 1=黑 2=透明。"""
    w, h = fr.size
    rgba = fr.load()
    idx = Image.new("P", (w, h))
    out = idx.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = rgba[x, y]
            if a < 128:
                out[x, y] = 2
            else:
                out[x, y] = 0 if r > 128 else 1
    idx.putpalette([255, 255, 255, 0, 0, 0, 0, 0, 0])
    return idx


def _load_frames(name):
    """读源 GIF/PNG 的所有帧（RGBA，GIF 自动合成）。"""
    im = Image.open(os.path.join(SRC, name))
    n = getattr(im, "n_frames", 1)
    frames, durations = [], []
    for i in range(n):
        im.seek(i)
        durations.append(im.info.get("duration", 70))
        frames.append(strip_black_bg(im.convert("RGBA")))
    return frames, durations


def _save_gif(frames, durations, out_name, loop=None):
    """打包 GIF。loop=None 不写 NETSCAPE 循环头 = 只播一遍（出场/钻地用）；
    loop=0 无限循环（待机嘴动/大笑用）。
    注意：千万别给一次性动画写 loop=1 —— Qt 会把 NETSCAPE loop=1 播成
    「完整播 2 遍」，钻地就会看起来钻了两次才成功。
    """
    p_frames = [_to_palette_frame(f) for f in frames]
    out = os.path.join(DST, out_name)
    kw = dict(duration=durations, transparency=2, disposal=2, optimize=False)
    if loop is not None:
        kw["loop"] = loop
    p_frames[0].save(out, save_all=True, append_images=p_frames[1:], **kw)
    return out


EVIL_SRC = os.path.join(BASE, "flowey_assets", "10_internet_bw",
                        "evil_flowey_blackwhite_clipart_alpha.png")
EVIL_FIT = (84, 88)     # 嘲讽脸内容最大尺寸（与定格脸 82x86 同档）


def _build_evil_face():
    """把互联网黑白 Flowey 素材加工成 96x120 的「嘲讽脸」。

    源图 300x313、带抗锯齿灰阶 -> 裁内容包围盒 -> 等比缩到 EVIL_FIT 内 ->
    二值化成纯黑白像素画 -> 居中对齐到画布 -> 描边 + 洞填白。
    """
    im = Image.open(EVIL_SRC).convert("RGBA")
    px = im.load()
    w, h = im.size
    xs = [x for y in range(h) for x in range(w) if px[x, y][3] > 128]
    ys = [y for y in range(h) for x in range(w) if px[x, y][3] > 128]
    im = im.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))

    scale = min(EVIL_FIT[0] / im.width, EVIL_FIT[1] / im.height)
    im = im.resize((max(1, round(im.width * scale)),
                    max(1, round(im.height * scale))), Image.LANCZOS)

    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    op = out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = im.getpixel((x, y))
            if a < 128:
                continue
            lum = (r * 299 + g * 587 + b * 114) // 1000
            v = 255 if lum > 128 else 0
            op[x, y] = (v, v, v, 255)

    shift = _shift_for_bbox(_content_bbox(out))
    aligned = finish_frame(_paste_aligned(out, shift), hole_rgb=(255, 255, 255, 255))
    aligned.save(os.path.join(DST, "evil_face.png"))
    return shift


EYE_SEARCH_YMAX = 55      # 眼睛只会在脸上半区（嘴在 y43+，茎在更下面）
EYE_AREA_MIN, EYE_AREA_MAX = 20, 120   # 眼睛连通域面积窗口（实测 4x10=40）
EYE_W_MAX, EYE_H_MIN = 8, 6            # 眼睛形状窗口：窄而高（嘴是宽而扁）


def _find_eye_boxes(im):
    """在 idle_rest.png 上自动找出两只眼睛的包围盒。

    眼睛特征：实心黑块、面积小、窄而高(w<=8, h>=6)、位于脸上半区；
    嘴（宽扁）和描边（巨大连通域）都会被窗口排除。返回 [(x0,y0,x1,y1), ...]。
    """
    px = im.load()
    w, h = im.size
    mask = [[(px[x, y][3] > 128 and sum(px[x, y][:3]) < 200)
             for x in range(w)] for y in range(h)]
    seen = [[False] * w for _ in range(h)]
    boxes = []
    for y in range(h):
        for x in range(w):
            if mask[y][x] and not seen[y][x]:
                stack = [(x, y)]
                seen[y][x] = True
                pts = []
                while stack:
                    cx, cy = stack.pop()
                    pts.append((cx, cy))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = cx + dx, cy + dy
                        if (0 <= nx < w and 0 <= ny < h and mask[ny][nx]
                                and not seen[ny][nx]):
                            seen[ny][nx] = True
                            stack.append((nx, ny))
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                bw, bh = x1 - x0 + 1, y1 - y0 + 1
                if (EYE_AREA_MIN <= len(pts) <= EYE_AREA_MAX
                        and bw <= EYE_W_MAX and bh >= EYE_H_MIN
                        and y1 <= EYE_SEARCH_YMAX):
                    boxes.append((x0, y0, x1, y1))
    # 一对眼睛：y 中心接近、分居左右
    boxes.sort(key=lambda b: (b[1], b[0]))
    if len(boxes) >= 2:
        pairs = [boxes[i:i + 2] for i in range(len(boxes) - 1)]
        best = min(pairs, key=lambda p: abs(p[0][1] - p[1][1]))
        if abs(best[0][1] - best[1][1]) <= 2 and best[0][0] < best[1][0]:
            return best
    raise SystemExit(f"眼睛自动检测失败：候选 {boxes}")


def _build_eye_layers():
    """把 idle_rest.png 拆成「无眼脸」+「全画布眼睛图层」。

    眼睛跟随鼠标需要两件东西：
    - idle_eyeless.png：把眼睛区域用周边脸色填掉的脸（作为待机底图）
    - idle_eyes.png：96x120 透明画布、只有两只眼睛（叠加层，整体平移即可）
    拆分位置自动检测（见 _find_eye_boxes），日后素材重生成也保持一致。
    """
    rest = Image.open(os.path.join(DST, "idle_rest.png")).convert("RGBA")
    boxes = _find_eye_boxes(rest)
    px = rest.load()

    # 周边脸色：取左眼左侧 2px 处的像素（脸内部，必为实心）
    sx0, sy0, _, sy1 = boxes[0]
    fill = px[max(0, sx0 - 2), (sy0 + sy1) // 2]

    eyeless = rest.copy()
    ep = eyeless.load()
    for x0, y0, x1, y1 in boxes:
        for y in range(max(0, y0 - 1), min(CANVAS[1], y1 + 2)):
            for x in range(max(0, x0 - 1), min(CANVAS[0], x1 + 2)):
                ep[x, y] = fill
    eyeless.save(os.path.join(DST, "idle_eyeless.png"))

    eyes = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    epx = eyes.load()
    for x0, y0, x1, y1 in boxes:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                epx[x, y] = px[x, y]
    eyes.save(os.path.join(DST, "idle_eyes.png"))
    return [( "idle_eyeless.png", f"眼框={boxes} 填色={fill}"),
            ("idle_eyes.png", f"眼框={boxes}")]


OW_SRC = os.path.join(BASE, "flowey_assets", "01_overworld")
OW_SCALE = 2.0          # 42x42 像素图放大到 84x84，与定格脸(82x86)同档，切换不跳变


def _build_overworld():
    """把 01_overworld 的 Flowey_overworld(.blink).png 加工成桌宠 overworld 形态。

    源是 42x42 的 Undertale 像素精灵（透明底），与本桌宠 96x120 画布 / 2px 黑描边
    / 无内部透明洞的规范一致处理：NEAREST 放大保持像素清晰 -> 按内容中心对齐到
    ANCHOR -> 描边 + 填死内部透明洞。产物：overworld_rest.png / overworld_blink.png。
    """
    out = []
    for src, name in [("Flowey_overworld.png", "overworld_rest.png"),
                      ("Flowey_overworld_blink.png", "overworld_blink.png")]:
        im = Image.open(os.path.join(OW_SRC, src)).convert("RGBA")
        if OW_SCALE != 1.0:
            im = im.resize((max(1, round(im.width * OW_SCALE)),
                            max(1, round(im.height * OW_SCALE))), Image.NEAREST)
        shift = _shift_for_bbox(_content_bbox(im))
        aligned = finish_frame(_paste_aligned(im, shift))
        aligned.save(os.path.join(DST, name))
        out.append((name, f"shift={shift} 源={src}"))
    return out


def main():
    os.makedirs(DST, exist_ok=True)
    report = []

    # ---- 待机 / 眨眼 / 大笑 / 受击：按各自内容包围盒对齐 ----
    for name, out_gif in [
        ("Flowey_battle_talk.gif", "idle_talk.gif"),
        ("Flowey_battle_laugh.gif", "laugh.gif"),
    ]:
        frames, durs = _load_frames(name)
        shift = _shift_for_bbox(_content_bbox(frames[0]))
        aligned = [finish_frame(_paste_aligned(f, shift)) for f in frames]
        _save_gif(aligned, durs, out_gif, loop=0)
        report.append((out_gif, f"{len(frames)}帧 loop=0 shift={shift}"))

    for name, out_png in [
        ("Flowey_battle_winking.png", "blink_wink.png"),
        ("Flowey_battle_mimicking_Asriel.png", "mimic_face.png"),
        ("Flowey_face_mimicking_protagonist.png", "frisk_face.png"),
    ]:
        frames, _ = _load_frames(name)
        shift = _shift_for_bbox(_content_bbox(frames[0]))
        aligned = finish_frame(_paste_aligned(frames[0], shift))
        aligned.save(os.path.join(DST, out_png))
        report.append((out_png, f"shift={shift}"))

    # ---- 嘲讽脸：学 Sans/Papyrus 说完话后变出来的狞笑（互联网黑白素材）----
    # 本体是描边画（内部大片透明），洞填白 -> 白瓣黑线，和白花风格一致。
    evil = _build_evil_face()
    report.append(("evil_face.png", f"shift={evil}"))

    # ---- overworld 形态：游荡结束后变身的盆栽 Flowey（含眨眼帧）----
    report.extend(_build_overworld())

    # ---- 出场：截取弹出+定格（源第7/8帧内容相同，取到第7帧即可），整体用一个偏移 ----
    # 定格帧同时用作「待机静止帧」：它是闭嘴的完整花，且与出场末帧构图完全一致，
    # 出场 -> 待机零跳变。
    frames, durs = _load_frames("Flowey_battle_appear.gif")
    idxs = list(INTRO_FRAMES)
    durs_intro = [durs[i] for i in idxs[:-1]] + [INTRO_HOLD_MS]
    shift = _shift_for_bbox(_content_bbox(frames[idxs[-1]]))
    aligned = [finish_frame(_paste_aligned(frames[i], shift)) for i in idxs]
    _save_gif(aligned, durs_intro, "intro_appear.gif")
    total = sum(durs_intro)
    report.append(("intro_appear.gif",
                   f"{len(idxs)}帧 loop=1 shift={shift} 定格{INTRO_HOLD_MS}ms(源1500ms) 总时长≈{total}ms"))

    # 必须先存好 idle_rest.png，眼睛图层才读得到新图
    aligned[-1].save(os.path.join(DST, "idle_rest.png"))
    report.append(("idle_rest.png", f"静止待机帧(取 appear 定格帧) shift={shift}"))

    # ---- 眼睛图层：待机脸拆成无眼底图 + 可平移的眼睛（眼球跟随鼠标用）----
    report.extend(_build_eye_layers())

    # ---- 退场钻地：定格起手 -> 缩回消失。沿用 intro 的 shift（对齐定格帧），
    #      花根朝下缩小消失，视觉上就是"缩回土里" ----
    idxs_out = list(OUTRO_FRAMES)
    durs_out = [OUTRO_HOLD_MS] + [durs[i] for i in idxs_out[1:]]
    aligned_out = [finish_frame(_paste_aligned(frames[i], shift)) for i in idxs_out]
    _save_gif(aligned_out, durs_out, "outro_sink.gif")
    report.append(("outro_sink.gif",
                   f"{len(idxs_out)}帧 loop=1 总时长≈{sum(durs_out)}ms"))

    # ---- 清理废弃产物 ----
    stale = os.path.join(DST, "hurt.png")
    if os.path.exists(stale):
        os.remove(stale)
        print("已删除废弃素材: hurt.png")

    # ---- 校验输出 ----
    for fname, note in report:
        path = os.path.join(DST, fname)
        im = Image.open(path)
        n = getattr(im, "n_frames", 1)
        bbs, holes = [], []
        for i in range(n):
            im.seek(i)
            fr = im.convert("RGBA")
            bbs.append(_content_bbox(fr))
            holes.append(fill_enclosed_holes(fr.copy())[1])
        ok = all(b is not None for b in bbs)
        centers = {(round((b[0] + b[2]) / 2), round((b[1] + b[3]) / 2)) for b in bbs if b}
        print(f"{fname}: {note}")
        print(f"   校验: {n}帧 全部非空={ok} 内容中心集合={sorted(centers)} "
              f"内部透明洞={sum(holes)}")
        if not ok:
            raise SystemExit(f"{fname} 存在空帧！")
        if sum(holes):
            raise SystemExit(f"{fname} 轮廓内部还有 {sum(holes)} 个透明洞！")


if __name__ == "__main__":
    main()
