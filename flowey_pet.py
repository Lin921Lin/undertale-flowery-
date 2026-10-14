# -*- coding: utf-8 -*-
"""
Flowey 桌宠 v8.2 · PyQt5 版（实时监控 + 角色模仿语音 + 黑描边 + 修钻地 + 提醒）
=====================================================================
窗口：
- 无边框 + 完全透明背景 + 始终置顶（不出现在任务栏）
- 出场 intro_appear.gif（弹出->定格）-> 待机 idle_rest.png（静止帧，不嘴动）
- 出场开始播 BGM（audio/bgm_intro.mp3，循环），右键菜单可关
- 所有素材带 2 画布像素黑描边（白底页面也能看清剪影）

对话（打字机）：
- 台词在气泡里一个字一个字出现（CHAR_MS 控制速度），气泡先按整句定尺寸
- 音效（audio/sfx/，来自小林给的录屏素材）：
    blip_talk.wav              逐字文字音（普通台词，每 BLIP_EVERY_N 个字响一次）
    voice_mimic.wav            通用变脸声（模仿 Asriel/Chara 等无专属语音时）
    laugh_evil.wav             邪恶笑声（face=laugh 的狠话）
    voice_sans/asgore/papyrus/toriel.wav
                               变脸学人说话时按 mimicOf 播对应角色语音
- 变脸（asriel/frisk 脸）台词：文字带轻微抖动（JITTER_PX）
- 右键菜单「音效」可整体开关（记住偏好）；**关掉音效那一刻**他会接一句
  lines.json 的 mute 台词（「嘘。你把我静音了。」），此时只出字不出声

实时监控（对应 lines.json 里 5 个 *_detected 事件）：
- psutil 每 MONITOR_SCAN_MS 扫一遍进程名，与各事件 processNames 匹配
- 进程**新出现**时触发对应台词（冷却走各事件的 cooldownMs=15min）
- 检测到但桌宠正在说话/游荡时，保留 MONITOR_PENDING_MS 内重试，过时不候

变脸（mimic）触发时机：
- 后台随机（开场 10min 后、冷却 15min）
- 被冷落后游荡到光标旁「骚扰」时优先变脸（独立 5min 冷却）
- 右键「说点什么」约四成概率直接变脸

变脸表情与语音规则：
- mimicOf=Sans/Papyrus -> wink 挑衅脸，说完变嘲讽 evil 脸（evil_face.png，停 2s 回待机）
- mimicOf=Toriel/Asgore -> Asriel 脸（学爸妈当然用儿子的脸）
- 模仿台词讲到重置/存档之类的事、且语气不恼怒 -> Frisk 脸
- 其余模仿台词 -> Asriel 假关心脸
- 语音跟 mimicOf 走（学谁用谁的声子），没专属语音的用通用变脸声

提醒（右键「提醒 · N」->「设置提醒…」）：
- 输入框两字段：几分钟后（1~1440）+ 提醒什么；内容框里直接粘整句
  （"10分钟后提醒我喝水"）也会自动拆成 (10, 喝水)（parse_reminder_text）
- 到点先「叮叮」两声（blip 音量临时提到 REMINDER_CHIME_VOLUME），再弹**独立大面板**
  ReminderPanel（比气泡更显眼：大字正文 + Flowey 头像 + 知道了），不再只用气泡
  reminder 台词：{what} 换成用户填的事项，8 条可选（毒舌/假温柔/阴阳/癫狂）
- 设完他会回一句 reminder_set 回执（{min}=人话时长、{what}=事项），
  不足 1 分钟说「30 秒」而不是「0 分钟」
- 到点时它正在说话 -> 不打断，延后 REMINDER_RETRY_MS 再试，且每说完一句
  立刻补check（_end_speak 里挂的钩子），最多 REMINDER_MAX_RETRY 次后插话必说
- 多条排队依次说，一次一句；菜单里点某条即可取消；最多同时挂 REMINDER_MAX_ITEMS 条，
  挂满时再设会说一句 reminder_full（{max}=上限），不静默失败
- 用墙钟 time.time() 计时（休眠醒来不会漏报）

待机动作：
- 静止帧 + 上下浮动 + 轻微左右摇摆（Lissajous，x 频率是 y 的两倍 -> 像在扭）

冷落游荡（被冷落 >=1 分钟时触发）：
- 钻地（outro_sink.gif）-> 在屏幕上 WANDER_SPOTS 处随机位置冒头（intro_appear.gif）
  各停下 WANDER_LOOK_MS 看一眼 -> 最后到鼠标光标旁说话（优先 mimic，其次 idle/peek）
- 任何鼠标操作（点击 / 拖拽 / 右键 / 滚轮）都会立刻中断游荡，回到原地待机

overworld 盆栽形态（游荡收尾触发）：
- 游荡最后一站说完后不再回待机，而是变身成游戏里那盆盆栽 Flowey
  （overworld_rest.png），并启动眨眼（随机 2.2~5.2s 闪一下 overworld_blink.png）
- 静止不浮动，随机 1~15 分钟后自动回待机（_ow_timeout）；期间**鼠标左键点击**
  即钻地离开回到待机（_ow_dig_away），拖拽在盆栽形态下失效；右键仍可开菜单
- overworld 事件台词走 lines.json（venom/meta/sweet/manic），进入时偶尔冒一句

一次性动画时序：
- intro / sink 的「播完」由 QMovie.finished 信号 + 兜底轮询双保险驱动：
  每 ONCE_GUARD_MS 查一次，动画停在末帧或超过 ONCE_HARD_LIMIT_MS 就强制收尾，
  信号丢了也不会卡死（钻地卡在土里 / 出场永远不定格）；改尺寸时若正播到
  一半，重播并原样挂回「播完回调」，状态机不会断
- 所有素材带 2 画布像素黑描边，且轮廓内部无透明洞（白底页面不透底）

BGM 规则：
- 出场起播、循环；说狠话（face=laugh，含 manic）时暂停中断，说完恢复
- 退场钻地时停止；右键菜单「音乐」可整体开关（记住偏好）

退场：
- 右键退出 -> 说完 shutdown 台词 -> outro_sink.gif 钻地离开 -> 程序退出

缩放：
- 鼠标滚轮 或 右键菜单「大小」，范围 1.5x ~ 8x，步进 0.5x，记住上次大小

交互（对应 lines.json 的事件 key）：
- 左键单击 -> double_click / 拖拽 -> drag / 右键 -> 菜单
- 10min 内开 >=3 次 -> restart / 连续陪伴 >=30min -> bond
- 冷落 >=1min -> 游荡（见上）/ 进程检测 -> *_detected（见上）
- 退出 -> shutdown（说完再钻地退场）

右键菜单（PetMenu）：
- 菜单**一弹出**他就先接一句 lines.json 的 panel_open（冷却 12s，连点不刷屏；
  盆栽形态下只冒气泡）——这条台词以前一直没人触发
- 白框样式；左侧一颗像素红心标出「当前停留项」（默认落在第一栏）
- 鼠标点选之外，键盘也可：↑↓ 移动、Enter 确定、Shift 返回上一层（顶层则关闭菜单）
- 条目：说点什么 / 提醒 · N（设置提醒… + 已挂的提醒/待办，点一下取消）/
  音乐 / 音效 / 大小 / 闭嘴 / 退出

人格约束以 persona.md 为准，tone 配额/冷却以 lines.json 的 config 为准。
素材由 make_transparent_assets.py 预处理；音效由 make_sfx.py 从录屏提取。
"""

import json
import math
import os
import random
import re
import sys
import time
from datetime import datetime, date, timedelta

from PyQt5.QtCore import (Qt, QTimer, QPoint, QRect, QSize, QUrl, pyqtSignal,
                          QTime, QDateTime, QEvent)
from PyQt5.QtGui import (QPixmap, QMovie, QPainter, QPainterPath, QColor,
                         QPen, QFont, QCursor, QIcon, QImage, QFontMetrics)
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QMenu, QAction,
                             QStyle, QDialog, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QSpinBox, QDialogButtonBox, QTabWidget,
                             QTimeEdit, QDateTimeEdit, QPushButton)

try:
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QSoundEffect
    HAS_MULTIMEDIA = True
except ImportError:                              # 某些精简环境缺 QtMultimedia
    HAS_MULTIMEDIA = False
    QSoundEffect = None

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(BASE_DIR, "flowey_assets", "02_battle_faces_trans")
LINES_JSON = os.path.join(BASE_DIR, "lines.json")
STATE_FILE = os.path.join(BASE_DIR, ".workbuddy", "pet_state.json")

INTRO_GIF = os.path.join(ASSET_DIR, "intro_appear.gif")
REST_PNG = os.path.join(ASSET_DIR, "idle_rest.png")     # 静止待机帧（不嘴动）
EYELESS_PNG = os.path.join(ASSET_DIR, "idle_eyeless.png")  # 待机无眼脸（眼球跟随用底图）
EYES_PNG = os.path.join(ASSET_DIR, "idle_eyes.png")     # 眼睛图层（96x120 全画布，整体平移）
TALK_GIF = os.path.join(ASSET_DIR, "idle_talk.gif")     # 说话时嘴动
WINK_PNG = os.path.join(ASSET_DIR, "blink_wink.png")    # 吐舌眨眼（挑衅专用）
LAUGH_GIF = os.path.join(ASSET_DIR, "laugh.gif")        # 大笑（狠话/难听话）
MIMIC_PNG = os.path.join(ASSET_DIR, "mimic_face.png")   # Asriel 假关心脸（模仿台词）
FRISK_PNG = os.path.join(ASSET_DIR, "frisk_face.png")   # Frisk 脸（模仿讲到重置且不恼怒）
EVIL_PNG = os.path.join(ASSET_DIR, "evil_face.png")     # 嘲讽脸（学 Sans/Papyrus 说完变这个）
OUTRO_GIF = os.path.join(ASSET_DIR, "outro_sink.gif")   # 退场钻地（播一次）
OVERWORLD_REST_PNG = os.path.join(ASSET_DIR, "overworld_rest.png")   # 盆栽形态（游荡后变身）
OVERWORLD_BLINK_PNG = os.path.join(ASSET_DIR, "overworld_blink.png") # 盆栽形态眨眼帧
BGM_MP3 = os.path.join(BASE_DIR, "flowey_assets", "audio", "bgm_intro.mp3")

SFX_DIR = os.path.join(BASE_DIR, "flowey_assets", "audio", "sfx")
SFX_FILES = {
    "blip": "blip_talk.wav",        # 逐字文字音
    "mimic": "voice_mimic.wav",     # 通用变脸声（模仿 Asriel/Chara 等）
    "laugh": "laugh_evil.wav",      # 邪恶笑声
    "sans": "voice_sans.wav",       # 角色模仿语音（按 mimicOf 匹配）
    "asgore": "voice_asgore.wav",
    "papyrus": "voice_papyrus.wav",
    "toriel": "voice_toriel.wav",
}
SFX_VOLUME = {"blip": 0.35, "mimic": 0.75, "laugh": 0.85,
              "sans": 0.8, "asgore": 0.8, "papyrus": 0.8, "toriel": 0.8}
# 语音跟随 mimicOf：学谁就用谁的声子（见 _speak），没有专属语音的用通用变脸声

CANVAS_W, CANVAS_H = 96, 120        # 素材画布（画布像素）
SCALE_DEFAULT = 4.0
SCALE_MIN, SCALE_MAX, SCALE_STEP = 1.5, 8.0, 0.5

INTRO_EXTRA_MS = 80                 # （保留）出场收尾缓冲，finished 驱动下暂未用到
OUTRO_EXTRA_MS = 150
ONCE_GUARD_MS = 60                  # 一次性动画完成轮询间隔（finished 的兜底）
ONCE_HARD_LIMIT_MS = 4000           # 兜底上限：finished 丢了也强制收尾，绝不卡死
BGM_VOLUME = 55                     # 0~100
CHAR_MS = 42                        # 打字机：每个字的间隔
BLIP_EVERY_N = 2                    # 每 N 个字响一次文字音（1=每个字都响）
SPEAK_LINGER_MS = 1000             # 打完字后：嘴停、字停留 1s 再收起
JITTER_PX = 1                       # 变脸时文字抖动的最大像素
BIG_SIZE = 16777215                 # QWIDGETSIZE_MAX
CLICK_SLOP_PX = 5                   # 位移小于此值算「点击」
CLICK_MAX_MS = 600                  # 超过此时长的按下不算点击
WATCH_TICK_MS = 5000                # 后台事件巡检间隔

# 待机浮动 / 扭动（幅度单位 = 画布像素，会乘以当前缩放）
SWAY_TICK_MS = 33                   # ~30fps
SWAY_PERIOD_MS = 2600.0             # 一个上下周期
SWAY_AMP_Y = 4.0                    # 上下幅度
SWAY_AMP_X = 1.6                    # 左右幅度（晃动感）

# 冷落游荡（被冷落时：钻地 -> 屏幕上几处冒头看看 -> 到鼠标光标旁说话）
WANDER_SPOTS = 4                    # 随机冒头看几处（不含最后的光标处）
WANDER_LOOK_MS = 650                # 每处冒头后停下「看看」的时长
WANDER_GAP_MS = 120                 # 钻地结束到下一处冒头之间的间隔
WANDER_COOLDOWN_MS = 60000          # 两次游荡的最小间隔
# 冷落多久（无交互）开始游荡——数值与 lines.json 的 idle.triggerMs 保持一致，
# 由配置驱动，用户改台词脚本里的 idle.triggerMs 即改此行为。
NEGLECT_WANDER_MS = 30000           # 冷落 30s 开始游荡

# 被反复戳/拽 -> 概率「钻走反抗」（沉默钻地离开再回待机）
ANNOY_THRESHOLD = 3                 # 累计达到这个次数后开始有概率反抗
ANNOY_RESET_MS = 8000               # 超过这么久没再被戳/拽，计数器清零
ANNOY_REBEL_PROB = 0.5              # 每次「够格」的戳/拽发动反抗的概率
# 反抗时「钻到其他位置躲几次」：钻地 -> 换地方冒头看一眼 -> 再钻 -> 再冒，
# 重复 REBEL_HOPS 次后才在最后一个位置回待机（不再原地待着）。
# 复用游荡的 WANDER_LOOK_MS / WANDER_GAP_MS / WANDER_MARGIN 让节奏一致。
REBEL_HOPS = 3

# 提醒大面板 / 设置提醒对话框 共用尺寸（两者必须「一样大」）
REMINDER_PANEL_W_FRAC = 0.42
REMINDER_PANEL_H_FRAC = 0.46
DIALOG_W_MIN, DIALOG_W_MAX = 440, 560
DIALOG_H_MIN, DIALOG_H_MAX = 380, 460

# 代码会主动触发（_trigger_event / pick）的事件名；启动时核对，缺了只警告不崩
CODE_EVENTS = (
    "double_click", "drag", "idle", "peek", "mimic", "bond",
    "reminder", "reminder_set", "reminder_full", "overworld", "peek_drag",
    "revert", "poke_spam", "diary_comment", "panel_open", "mute",
    "todo_add", "todo_ask", "todo_done", "todo_fail",
)
WANDER_MIMIC_COOLDOWN_MS = 300000   # 游荡骚扰时变脸学话的最小间隔
WANDER_CURSOR_DX = 0.45             # 光标处落点：窗口宽度的倍数（右偏，别压住光标）
WANDER_CURSOR_DY = 0.30             # 光标处落点：窗口高度的倍数（下偏）
WANDER_MARGIN = 12                  # 游荡落点距屏幕边缘的留白

# 实时监控（*_detected 事件）
MONITOR_SCAN_MS = 20000             # 进程名扫描间隔（与 lines.json 的 pollIntervalMs 一致）
MONITOR_PENDING_MS = 60000          # 检测到但正忙时，保留多久重试台词

# 提醒（右键「提醒 · N」-> 设置提醒）：倒计时 / 具体时间 / 待办事项
REMINDER_TICK_MS = 1000             # 到点检查间隔
REMINDER_RETRY_MS = 5000            # 到点时它正在说话 -> 隔多久再试
REMINDER_MAX_RETRY = 12             # 最多延后几次（约 96s），超了就插话先说
REMINDER_MAX_ITEMS = 8              # 同时最多挂几个提醒
REMINDER_MAX_MIN = 1440             # 最长 24 小时
REMINDER_DEF_MIN = 10               # 输入框默认分钟
REMINDER_CHIME_VOLUME = 0.6         # 到点「叮叮」的音量（文字音平时是 0.35）

# 待办事项（DDL）：到期前这两个时间点各弹一次「完成没」
TODO_MAX_ITEMS = 20                 # 同时最多挂几个待办
TODO_ASK_HOUR_SEC = 3600            # DDL 前 1 小时
TODO_ASK_TEN_SEC = 600              # DDL 前 10 分钟

# 日记：Flowey 专属的 .txt，自动同步「当天定的提醒与待办」，用电脑自带记事本打开
DIARY_PATH = os.path.join(BASE_DIR, "flowey_diary.txt")
DIARY_NOTE_MAX = 5                  # 日记末尾「Flowey 批注」最多留几条

# 眼球跟随鼠标（待机 rest 脸专用）：眼睛图层整体小幅平移。
# 幅度以 96x120 素材像素计：眼睛底边 y40、嘴顶 y43，往下最多挪 1px 就贴嘴了，
# 所以向下余量压得最小；左右 ±3、向上 3 都还在脸圆内部，不会跑出脸。
EYE_MAX_DX = 3.0                    # 左右最大偏移（素材像素）
EYE_MAX_DY_UP = 3.0                 # 往上看最大偏移
EYE_MAX_DY_DOWN = 1.0               # 往下看最大偏移（防碰到嘴）
EYE_REACH_PX = 180.0                # 鼠标离窗口中心多远算「看到头」（线性满幅）
EYE_TICK_MS = 60                    # 眼球刷新间隔

# 游荡后 overworld 盆栽形态：静止 + 眨眼 + 随机 1~15 分钟，戳一下变回原样、拖拽钻走
OVERWORLD_MIN_MS = 60000            # 最短静止 1 分钟
OVERWORLD_MAX_MS = 900000           # 最长静止 15 分钟
OVERWORLD_BLINK_MIN_MS = 2200       # 眨眼间隔（随机）
OVERWORLD_BLINK_MAX_MS = 5200
OVERWORLD_BLINK_HOLD_MS = 130       # 闭眼帧停留时长

# 变脸表情 / 语音规则
MIMIC_ASRIEL_OF = {"Toriel", "Asgore"}      # 学爸妈 -> Asriel 脸
MIMIC_WINK_OF = {"Sans", "Papyrus"}         # 学这俩 -> 挑衅脸，说完变嘲讽（evil 脸）
EVIL_HOLD_MS = 2000                 # 嘲讽脸停留时长，之后回待机
RESET_KEYWORDS = ("重置", "RESET", "Reset", "reset", "存档", "重来")
ANGRY_TONES = {"venom", "crack", "plead", "manic"}      # 「恼怒」的语气
MIMIC_VOICES = {"Sans": "sans", "Asgore": "asgore",
                "Papyrus": "papyrus", "Toriel": "toriel"}

# 右键菜单 / 气泡：白框主题
FRAME_RGB = (255, 255, 255)         # 边框（原来是黄色 255,210,63）
BUBBLE_FILL_RGBA = (16, 16, 22, 240)
MENU_QSS = (
    "QMenu { background: #16161c; color: #f0f0f0;"
    " border: 1px solid #ffffff; padding: 4px; }"
    "QMenu::item { padding: 5px 26px 5px 4px; }"
    "QMenu::item:selected { background: rgba(255,255,255,40); color: #ffd34d; }"
    "QMenu::item:disabled { color: #8a8a94; }"
    "QMenu::separator { height: 1px; background: #55555f; margin: 4px 8px; }"
)
# 「设置提醒」输入框：跟菜单/气泡同一套白框暗色主题。
# 关键：QWidget 兜底黑底 + 显式覆盖 QTabWidget/QTabBar/QDateTimeEdit/QCalendarWidget，
# 否则 Windows 默认风格下 tab 页/日历弹窗会透出白底，出现「有的黑底有的白底」。
DIALOG_QSS = (
    "QDialog { background: #16161c; color: #f0f0f0; border: 1px solid #ffffff; }"
    "QWidget { background: #16161c; color: #f0f0f0; }"
    "QLabel { color: #f0f0f0; background: transparent; }"
    "QLabel#hint { color: #8a8a94; font-size: 11px; }"
    "QLabel#err  { color: #ff5b5b; font-size: 11px; }"
    "QLineEdit, QSpinBox, QTimeEdit, QDateTimeEdit, QAbstractSpinBox {"
    " background: #0e0e13; color: #f0f0f0; border: 1px solid #ffffff;"
    " padding: 4px 6px; selection-background-color: #3a3a44;"
    " selection-color: #f0f0f0; }"
    "QLineEdit:focus, QSpinBox:focus, QTimeEdit:focus, QDateTimeEdit:focus"
    " { border: 1px solid #ff3b3b; }"
    "QTabWidget { background: #16161c; }"
    "QTabWidget::pane { background: #16161c; border: 1px solid #ffffff; }"
    "QTabBar::tab { background: #0e0e13; color: #f0f0f0;"
    " padding: 7px 16px; border: 1px solid #ffffff; border-bottom: none; }"
    "QTabBar::tab:selected { background: #2a2a34; color: #ffd34d; }"
    "QTabBar::tab:!selected { background: #0e0e13; }"
    "QTabBar::tab:!selected:hover { background: #1c1c24; }"
    "QPushButton { background: #0e0e13; color: #f0f0f0;"
    " border: 1px solid #ffffff; padding: 5px 14px; }"
    "QPushButton:hover { background: #2a2a34; }"
    "QPushButton:pressed { background: #3a3a44; }"
    "QDialogButtonBox { background: transparent; }"
    "QCalendarWidget { background: #16161c; color: #f0f0f0; }"
    "QCalendarWidget QWidget { color: #f0f0f0; background: #16161c; }"
    "QCalendarWidget QAbstractItemView { color: #f0f0f0; background: #16161c;"
    " selection-background-color: #2a2a34; selection-color: #f0f0f0;"
    " alternate-background-color: #1c1c24; }"
    "QCalendarWidget QAbstractItemView:disabled { color: #6a6a74; }"
    "QCalendarWidget QHeaderView::section { background: #0e0e13; color: #f0f0f0;"
    " border: 1px solid #2a2a34; }"
    "QCalendarWidget QToolButton { background: #0e0e13; color: #f0f0f0; }"
    "QCalendarWidget QToolButton:hover { background: #2a2a34; }"
    "QCalendarWidget #qt_calendar_navigationbar { background: #0e0e13; }"
    "QCalendarWidget #qt_calendar_prevmonth,"
    " QCalendarWidget #qt_calendar_nextmonth { background: #0e0e13; }"
)
# 日历弹窗（QDateTimeEdit 的子控件）单独再设一次：它是顶层 popup，
# 某些 Qt 版本不会继承父对话框的样式表，这里强制兜底成黑底。
CALENDAR_QSS = DIALOG_QSS

# 像素红心（菜单里标出当前停留项）
HEART_ROWS = [
    ".XX..XX.",      # 8 x 7 点阵
    "XXXXXXXX",
    "XXXXXXXX",
    "XXXXXXXX",
    ".XXXXXX.",
    "..XXXX..",
    "...XX...",
]
HEART_RGB = (255, 59, 59)

# tone -> 表情（face）。没配到的 tone 默认 talk（嘴动）
TONE_FACE = {
    "manic": "laugh",     # 失控/癫狂也归为「狠话」：大笑脸 + BGM 中断
    "crack": "rest",
    "plead": "rest",
}

# face == laugh 的台词 = 狠话/难听话：说的时候 BGM 中断
MEAN_FACE = "laugh"

# persona.md 硬性禁令：破防/温柔/哀求/掩饰之后，下一句必须退回 venom
EMOTIONAL_TONES = {"crack", "plead", "tender", "mask"}


# ---------------------------------------------------------------------------
# 台词库
# ---------------------------------------------------------------------------
class LineLibrary:
    """按 lines.json 的 config 取台词：tone 允许范围、冷却、避免连续重复。"""

    def __init__(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.events = data["events"]
        self.config = data["config"]
        self._last_line_id = None
        self._last_tone = None
        self._event_ts = {}

    @staticmethod
    def _now():
        return time.monotonic() * 1000.0

    def _allowed_tones(self, event):
        out = []
        for tone, rule in self.config["toneRules"].items():
            allow = rule.get("allow")
            if allow == "*" or (isinstance(allow, list) and event in allow):
                out.append(tone)
        return out

    def find_by_id(self, line_id):
        for ev in self.events.values():
            for line in ev["lines"]:
                if line["id"] == line_id:
                    return line
        return None

    def pick(self, event, force=False):
        """取一条台词；冷却未到返回 None。force=True 忽略冷却（手动触发用）。"""
        if event not in self.events:
            return None
        now = self._now()
        cooldown = self.config.get("events", {}).get(event, {}).get("cooldownMs", 0)
        last = self._event_ts.get(event)
        if not force and last is not None and (now - last) < cooldown:
            return None

        tones = set(self._allowed_tones(event))
        # 跳过残缺行（用户改脚本时漏掉 tone / text 也不会崩）
        pool = [l for l in self.events[event]["lines"]
                if l.get("tone") in tones and l.get("text")]
        if not pool:
            return None

        # 上一句是情绪化 tone -> 本轮优先回落 venom
        if self._last_tone in EMOTIONAL_TONES:
            venom_pool = [l for l in pool if l["tone"] == "venom"]
            if venom_pool:
                pool = venom_pool

        # avoidImmediateRepeat
        if self.config.get("avoidImmediateRepeat") and self._last_line_id:
            trimmed = [l for l in pool if l["id"] != self._last_line_id]
            if trimmed:
                pool = trimmed

        line = random.choice(pool)          # pickMode: uniform
        self._event_ts[event] = now
        self._last_line_id = line["id"]
        self._last_tone = line["tone"]
        return line


# ---------------------------------------------------------------------------
# 像素红心 + 菜单
# ---------------------------------------------------------------------------
def _render_pixel_grid(rows, target, rgb=None):
    """把字符点阵按整数倍放大后居中画进 target×target 的方图。

    rgb=None 时返回同尺寸的**全透明**图（菜单占位用）。
    尺寸和 QMenu 实际请求的图标尺寸一致，QIcon 会原样返回，不会被平滑缩放糊掉。
    必须在 QApplication 创建之后再调用（QPixmap 依赖 GUI 环境）。
    """
    gw = max(len(r) for r in rows)
    gh = len(rows)
    scale = max(1, min(target // gw, target // gh))
    w, h = gw * scale, gh * scale
    pm = QPixmap(target, target)
    pm.fill(Qt.transparent)
    if rgb is None:
        return pm
    painter = QPainter(pm)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(*rgb))
    ox, oy = (target - w) // 2, (target - h) // 2
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "X":
                painter.drawRect(ox + x * scale, oy + y * scale, scale, scale)
    painter.end()
    return pm


class PetMenu(QMenu):
    """右键菜单：像素红心标出当前停留项；支持键盘导航。

    - 所有条目都塞一张「透明占位图标」，这样图标列宽度固定、文字不会左右跳
    - 当前停留项（activeAction）换成红心图标
    - ↑↓ 移动、Enter 确定由 QMenu 原生负责；Shift = 返回（子菜单回父级，顶层则关闭）
    """

    _heart_icon = None
    _blank_icon = None
    _icon_size = None

    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self._ensure_icons()
        self.hovered.connect(self._on_hovered)

    # -- 图标（首次用到时才创建，此时 QApplication 已存在） ------------------
    @classmethod
    def _ensure_icons(cls):
        if cls._heart_icon is not None:
            return
        size = QApplication.style().pixelMetric(QStyle.PM_SmallIconSize)
        size = int(size) if size and size > 0 else 16
        cls._heart_icon = QIcon(_render_pixel_grid(HEART_ROWS, size, HEART_RGB))
        cls._blank_icon = QIcon(_render_pixel_grid(HEART_ROWS, size, None))
        cls._icon_size = QSize(size, size)

    # -- 红心同步 -----------------------------------------------------------
    def _leaf_actions(self):
        return [a for a in self.actions() if not a.isSeparator()]

    def _install_placeholders(self):
        """给还没有图标的条目塞透明占位图，固定图标列宽度。"""
        for act in self._leaf_actions():
            if act.icon().isNull():
                act.setIcon(self._blank_icon)

    def _paint_heart(self, target):
        for act in self._leaf_actions():
            act.setIcon(self._heart_icon if act is target else self._blank_icon)

    def _sync_heart(self):
        self._install_placeholders()
        self._paint_heart(self.activeAction())

    def _on_hovered(self, act):
        if act is not None and not act.isSeparator():
            self._paint_heart(act)

    def _first_enabled(self):
        for act in self._leaf_actions():
            if act.isEnabled():
                return act
        return None

    # -- 显示后把红心落到第一栏 ---------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        self._sync_heart()
        QTimer.singleShot(0, self._default_active)

    def _default_active(self):
        self._install_placeholders()
        if self.activeAction() is None:
            first = self._first_enabled()
            if first is not None:
                self.setActiveAction(first)
        self._paint_heart(self.activeAction())

    # -- 键盘：Shift 返回 ---------------------------------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Shift:
            parent_menu = self.parentWidget()
            if isinstance(parent_menu, QMenu):
                parent_menu.setActiveAction(self.menuAction())
                if isinstance(parent_menu, PetMenu):
                    parent_menu._paint_heart(self.menuAction())
                self.hide()
            else:
                self.close()                # 顶层菜单：Shift = 关掉
            event.accept()
            return
        super().keyPressEvent(event)        # ↑↓ / Enter 交给 QMenu
        self._sync_heart()


# ---------------------------------------------------------------------------
# 定时提醒：输入框
# ---------------------------------------------------------------------------
_TIME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:分钟|分|hours?|小时|h|min(?:ute)?s?|m)",
                      re.I)
# 「10分钟后提醒我喝水」里要剥掉的废话（反复剥前缀，直到剥不动）
_NOISE_PREFIX = ("后", "之后", "以后", "提醒我", "叫我", "让我", "提示我",
                 "记得", "去", "该", "要", "帮我", "请", "再", "就",
                 "，", ",", "、", "：", ":")


def parse_reminder_text(text):
    """从整句里拆出「分钟数 + 提醒内容」。

    支持：'10分钟后提醒我喝水' / '25 分钟 休息' / '1.5h 睡觉'。
    拆不出来返回 None（调用方就当纯内容用，分钟数取输入框的值）。
    """
    s = (text or "").strip()
    m = _TIME_RE.search(s)
    if not m:
        return None
    try:
        minutes = float(m.group(1))
    except ValueError:
        return None
    if minutes <= 0:
        return None
    rest = (s[:m.start()] + s[m.end():]).strip()
    changed = True
    while changed:                       # 反复剥前缀废话
        changed = False
        for p in _NOISE_PREFIX:
            if rest.startswith(p):
                rest = rest[len(p):].strip()
                changed = True
                break
    return minutes, rest.strip(" ，,。.、!！?？")


def humanize_minutes(minutes):
    """分钟数 -> 人话（'10 分钟' / '30 秒'）。

    小于 1 分钟要折算成秒，否则会说出「0分钟后提醒你…」这种怪话。
    """
    m = float(minutes)
    if m >= 1:
        return "%d 分钟" % int(round(m))
    return "%d 秒" % max(1, int(round(m * 60)))


class AlarmDialog(QDialog):
    """「设置提醒」输入框：三种模式（两种原闹钟模式 + 待办事项）。

    1) 倒计时：N 时 N 分 N 秒后响（默认 10 分钟）。
    2) 具体时间：选今天/明天的 HH:mm（已过则自动顺延到明天）。
    3) 待办事项：填内容 + DDL（截止日期时间），到期前 1 小时 / 10 分钟会来问完成没。
    备注可选。确定后 value() 返回一个 dict（见 value 文档）。
    """

    TAB_COUNTDOWN, TAB_CLOCK, TAB_TODO = 0, 1, 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置提醒")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self.setStyleSheet(DIALOG_QSS)

        title = QLabel("⏰  设个提醒", self)
        title.setObjectName("hint")
        title.setStyleSheet("color:#ff5b5b; font-size:20px; font-weight:bold;")

        tabs = QTabWidget(self)

        # 模式一：倒计时
        cd = QWidget()
        cdl = QVBoxLayout(cd)
        cdl.setContentsMargins(10, 14, 10, 10)
        hl = QHBoxLayout()
        hl.setSpacing(12)
        self._sb_h = self._mk_spin(0, 23, 0, "时")
        self._sb_m = self._mk_spin(0, 59, REMINDER_DEF_MIN, "分")
        self._sb_s = self._mk_spin(0, 59, 0, "秒")
        hl.addWidget(self._sb_h)
        hl.addWidget(self._sb_m)
        hl.addWidget(self._sb_s)
        hl.addStretch(1)
        cdl.addWidget(QLabel("倒计时：过这么久之后响", self))
        cdl.addLayout(hl)
        cdl.addStretch(1)

        # 模式二：具体时间
        sp = QWidget()
        spl = QVBoxLayout(sp)
        spl.setContentsMargins(10, 14, 10, 10)
        self._time = QTimeEdit(self)
        self._time.setDisplayFormat("HH:mm")
        self._time.setTime(QTime.currentTime())
        self._time.setMinimumWidth(160)
        self._time.setFont(QFont("Microsoft YaHei", 14))
        self._time.timeChanged.connect(self._update_time_hint)
        self._time_hint = QLabel(self)
        self._time_hint.setObjectName("hint")
        self._time_hint.setStyleSheet("color:#9fd3ff;")
        spl.addWidget(QLabel("具体时间：选钟点", self))
        spl.addWidget(self._time)
        spl.addWidget(self._time_hint)
        spl.addStretch(1)

        # 模式三：待办事项（带 DDL）
        td = QWidget()
        tdl = QVBoxLayout(td)
        tdl.setContentsMargins(10, 14, 10, 10)
        self._todo_text = QLineEdit(self)
        self._todo_text.setPlaceholderText("要做什么，例如：交挑战杯申报书")
        self._todo_text.setFont(QFont("Microsoft YaHei", 12))
        self._ddl = QDateTimeEdit(self)
        self._ddl.setCalendarPopup(True)
        self._ddl.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._ddl.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self._ddl.setMinimumWidth(230)
        self._ddl.setFont(QFont("Microsoft YaHei", 13))
        self._ddl.dateTimeChanged.connect(self._update_ddl_hint)
        # 日历弹窗是顶层 popup，部分 Qt 版本不继承父对话框样式表，强制兜底黑底
        try:
            self._ddl.calendarWidget().setStyleSheet(CALENDAR_QSS)
        except Exception:
            pass
        self._ddl_hint = QLabel(self)
        self._ddl_hint.setObjectName("hint")
        self._ddl_hint.setStyleSheet("color:#9fd3ff;")
        self._ddl_hint.setWordWrap(True)
        tdl.addWidget(QLabel("待办事项：要做什么", self))
        tdl.addWidget(self._todo_text)
        tdl.addSpacing(10)
        tdl.addWidget(QLabel("DDL（截止时间）", self))
        tdl.addWidget(self._ddl)
        tdl.addWidget(self._ddl_hint)
        tdl.addStretch(1)

        tabs.addTab(cd, "倒计时")
        tabs.addTab(sp, "具体时间")
        tabs.addTab(td, "待办事项")
        self._tabs = tabs

        self._note = QLineEdit(self)
        self._note.setPlaceholderText("备注（可选），例如：喝水")

        self._err = QLabel("", self)
        self._err.setObjectName("err")
        self._err.hide()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                self)
        btns.button(QDialogButtonBox.Ok).setText("确定")
        btns.button(QDialogButtonBox.Cancel).setText("取消")
        btns.accepted.connect(self._try_accept)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.addWidget(title)
        lay.addSpacing(12)
        lay.addWidget(tabs, 1)
        lay.addSpacing(10)
        self._note_label = QLabel("备注", self)   # 待办页用不到，切页时隐藏
        lay.addWidget(self._note_label)
        lay.addWidget(self._note)
        tabs.currentChanged.connect(self._on_tab_changed)
        self._on_tab_changed(tabs.currentIndex())
        lay.addWidget(self._err)
        lay.addSpacing(10)
        lay.addWidget(btns, 0, Qt.AlignRight)

        # 与「到点提醒」大面板同尺寸（用户要求两个页面一样大）
        scr = QApplication.primaryScreen().availableGeometry()
        w = min(DIALOG_W_MAX, max(DIALOG_W_MIN,
                                  int(scr.width() * REMINDER_PANEL_W_FRAC)))
        h = min(DIALOG_H_MAX, max(DIALOG_H_MIN,
                                  int(scr.height() * REMINDER_PANEL_H_FRAC)))
        self.resize(w, h)
        self._update_time_hint()
        self._update_ddl_hint()

    def _mk_spin(self, lo, hi, val, suf):
        sb = QSpinBox(self)
        sb.setRange(lo, hi)
        sb.setValue(val)
        sb.setSuffix(" " + suf)
        sb.setFixedWidth(96)
        sb.setFont(QFont("Microsoft YaHei", 14))
        return sb

    def _update_time_hint(self):
        t = self._time.time()
        now = datetime.now()
        dt = datetime(now.year, now.month, now.day, t.hour(), t.minute())
        if dt <= now:
            self._time_hint.setText("⏭  时间已过，会在 明天 %s 响"
                                    % t.toString("HH:mm"))
        else:
            self._time_hint.setText("🕒  会在 今天 %s 响" % t.toString("HH:mm"))

    def _on_tab_changed(self, idx):
        """待办页有自己的内容输入框，别再露出「备注」那一排。"""
        is_todo = (idx == self.TAB_TODO)
        self._note_label.setVisible(not is_todo)
        self._note.setVisible(not is_todo)

    def _update_ddl_hint(self):
        """DDL 页提示：到期前 1 小时 / 10 分钟会来问你完成没。"""
        dt = self._ddl.dateTime()
        try:
            ddl = dt.toPyDateTime()
        except Exception:
            ddl = datetime.now()
        now = datetime.now()
        delta = (ddl - now).total_seconds()
        if delta <= 0:
            self._ddl_hint.setText("⏭  这个时间已经过了，白痴。")
        else:
            self._ddl_hint.setText(
                "🕒  到期前 1 小时 和 10 分钟，我会来问你做完了没。")

    def _try_accept(self):
        self._err.hide()
        idx = self._tabs.currentIndex()
        if idx == self.TAB_COUNTDOWN:
            if (self._sb_h.value() == 0 and self._sb_m.value() == 0
                    and self._sb_s.value() == 0):
                self._err.setText("倒计时不能为零，白痴。")
                self._err.show()
                return
        elif idx == self.TAB_TODO:
            if not self._todo_text.text().strip():
                self._err.setText("待办事项总得写点什么吧。")
                self._err.show()
                return
            if self._ddl.dateTime().toPyDateTime() <= datetime.now():
                self._err.setText("DDL 得是还没到的时间，白痴。")
                self._err.show()
                return
        self.accept()

    def value(self):
        """返回本次设置的结果 dict；非法返回 None。

        kind == "countdown"：{"kind","at","text","tomorrow":False,"clock":False}
        kind == "clock"    ：{"kind","at","text","tomorrow","clock":True}
        kind == "todo"     ：{"kind","text","ddl"（DDL 的 epoch 秒）,"at":ddl}
        """
        idx = self._tabs.currentIndex()
        if idx == self.TAB_TODO:
            text = self._todo_text.text().strip()
            if not text:
                return None
            ddl_dt = self._ddl.dateTime().toPyDateTime()
            if ddl_dt <= datetime.now():
                return None
            ddl = ddl_dt.timestamp()
            return {"kind": "todo", "text": text, "ddl": ddl, "at": ddl,
                    "tomorrow": False, "clock": False}
        if idx == self.TAB_COUNTDOWN:
            text = self._note.text().strip()
            h = self._sb_h.value()
            m = self._sb_m.value()
            s = self._sb_s.value()
            if h == 0 and m == 0 and s == 0:
                return None
            at = time.time() + h * 3600 + m * 60 + s
            return {"kind": "countdown", "at": at, "text": text,
                    "tomorrow": False, "clock": False}
        text = self._note.text().strip()
        t = self._time.time()
        now = datetime.now()
        dt = datetime(now.year, now.month, now.day, t.hour(), t.minute())
        tomorrow = dt <= now
        if tomorrow:
            dt += timedelta(days=1)
        return {"kind": "clock", "at": dt.timestamp(), "text": text,
                "tomorrow": tomorrow, "clock": True}


class ReminderPanel(QDialog):
    """到点提醒用的大面板：独立置顶窗口，大字显示提醒内容 + Flowey 头像 + 知道了。

    比原来的气泡更显眼、更像「提醒弹窗」；点「知道了」/Esc/回车 关闭。
    同一时刻只用一个实例（FloweyPet._reminder_panel 复用），新提醒来了刷新文字。
    """

    def __init__(self, parent=None, avatar=None):
        super().__init__(None,
                         Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setStyleSheet(DIALOG_QSS)
        self.setMinimumSize(360, 240)     # 实际尺寸由 _show_reminder_panel 按屏 1/6 固定

        title = QLabel("⏰  Flowey 的提醒", self)
        title.setObjectName("hint")
        title.setStyleSheet("color:#ff5b5b; font-size:18px; font-weight:bold;")

        row = QHBoxLayout()
        if avatar is not None and not avatar.isNull():
            av = QLabel(self)
            av.setPixmap(avatar.scaled(96, 96, Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation))
            av.setFixedSize(96, 96)
            row.addWidget(av)
            self._avatar = av
        else:
            self._avatar = None
        self._body = QLabel("", self)
        self._body.setWordWrap(True)
        self._body.setFont(QFont("Microsoft YaHei", 20))
        self._body.setStyleSheet("color:#f2f2f2; background:transparent;")
        self._body.setMinimumWidth(360)
        row.addWidget(self._body, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok, self)
        btn = btns.button(QDialogButtonBox.Ok)
        btn.setText("知道了")
        btn.setFont(QFont("Microsoft YaHei", 14))
        btns.accepted.connect(self.accept)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.addWidget(title)
        lay.addSpacing(14)
        lay.addLayout(row)
        lay.addStretch(1)                 # 大字面板留白，按钮落到底部
        lay.addWidget(btns, 0, Qt.AlignRight)

    def set_text(self, text):
        self._body.setText(text)
        self._body.setMinimumHeight(0)
        self._body.setMaximumHeight(BIG_SIZE)
        # 不再 adjustSize：面板尺寸由外部按屏幕 1/6 固定，避免被短内容撑小

    def set_avatar(self, avatar):
        """换头像（改名/缩放后刷新，别让面板挂着旧尺寸的图）。"""
        if self._avatar is not None and avatar is not None and not avatar.isNull():
            self._avatar.setPixmap(avatar.scaled(96, 96, Qt.KeepAspectRatio,
                                                 Qt.SmoothTransformation))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self.accept()
        else:
            super().keyPressEvent(event)


# 「完成没」问询框：UT 战斗选项框款式——纯黑底 + 白粗框，只保留框内内容
UTBOX_QSS = (
    "QDialog { background: #000000; border: 5px solid #ffffff; }"
    "QLabel { background: transparent; color: #f0f0f0; }"
)


def _pixel_text_pixmap(text, rgb="#f0f0f0", px=15, scale=2):
    """把文字按小号「无抗锯齿」渲染后整数倍放大，得到 Undertale 式像素字。

    必须在 QApplication 创建之后调用（QFontMetrics/QImage 依赖 GUI 环境）。
    """
    font = QFont("Microsoft YaHei", px)
    font.setStyleStrategy(QFont.NoAntialias)
    fm = QFontMetrics(font)
    w = fm.horizontalAdvance(text) + 4
    h = fm.height() + 4
    small = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    small.fill(Qt.transparent)
    p = QPainter(small)
    p.setFont(font)
    p.setPen(QColor(rgb))
    p.drawText(2, fm.ascent() + 2, text)
    p.end()
    return QPixmap.fromImage(small.scaled(w * scale, h * scale,
                                          Qt.IgnoreAspectRatio,
                                          Qt.FastTransformation))


class _ClickLabel(QLabel):
    """可点击的选项标签（红心 + 像素字合成图，见 TodoCheckDialog._refresh）。"""

    def __init__(self, idx, cb, parent=None):
        super().__init__(parent)
        self._idx = idx
        self._cb = cb
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, ev):
        self._cb(self._idx)


class TodoCheckDialog(QDialog):
    """DDL 到期前问「完成没」的 UT 战斗选项框款弹窗。

    外观 = Undertale 战斗框：纯黑底 + 白粗框，只保留框内内容（无标题栏）。
    选项「完成 / 未完成」是像素字，红心光标停在当前项，选中的像素字变黄，
    默认选第一项。左右/上下键切换，回车 / 空格 / 鼠标点击确认，
    Esc = 先不回答（不改状态）。
    """

    OPTS = ("完成", "未完成")
    SEL_YELLOW = "#ffd34d"      # 选中项像素字的颜色（UT 黄）

    def __init__(self, text, eta, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.NoDropShadowWindowHint)
        self.setStyleSheet(UTBOX_QSS)
        self.setAttribute(Qt.WA_StyledBackground, True)   # 让 QSS 的白粗框真正画出来
        self.setModal(True)
        self.setFocusPolicy(Qt.StrongFocus)   # 必须可接收键盘焦点
        self._sel = 0
        self._choice = None          # True=完成 / False=未完成 / None=没回答
        # 兜底：焦点万一落在子控件上，键盘事件也统一路由到 keyPressEvent
        QApplication.instance().installEventFilter(self)

        q = QLabel("「%s」" % (text or "（没写内容）"), self)
        q.setWordWrap(True)
        q.setFont(QFont("Microsoft YaHei", 14))
        q.setStyleSheet("color:#f0f0f0;")

        ask = QLabel(self)
        ask.setPixmap(_pixel_text_pixmap("你完成了吗", "#f0f0f0", px=15, scale=2))

        eta_l = QLabel(eta, self)
        eta_l.setStyleSheet("color:#8a8a94; font-size:12px;")

        self._opts = []
        orow = QHBoxLayout()
        orow.setSpacing(56)
        for i, name in enumerate(self.OPTS):
            lab = _ClickLabel(i, self._pick, self)
            orow.addWidget(lab)
            self._opts.append(lab)
        orow.addStretch(1)

        tip = QLabel("← → 选择，回车 / 点击 确定", self)
        tip.setStyleSheet("color:#8a8a94; font-size:11px;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 22)
        lay.addWidget(q)
        lay.addSpacing(6)
        lay.addWidget(ask)
        lay.addSpacing(4)
        lay.addWidget(eta_l)
        lay.addSpacing(24)
        lay.addLayout(orow)
        lay.addSpacing(10)
        lay.addWidget(tip)
        self._refresh()

    def _refresh(self):
        """重画两个选项：当前项 = 红心 + 黄色像素字，其余 = 透明占位 + 白色像素字。"""
        for i, lab in enumerate(self._opts):
            sel = (i == self._sel)
            heart = _render_pixel_grid(HEART_ROWS, 18, HEART_RGB if sel else None)
            txt = _pixel_text_pixmap(self.OPTS[i],
                                     self.SEL_YELLOW if sel else "#f0f0f0",
                                     px=15, scale=2)
            w = heart.width() + 8 + txt.width()
            h = max(heart.height(), txt.height())
            pm = QPixmap(w, h)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.drawPixmap(0, (h - heart.height()) // 2, heart)
            p.drawPixmap(heart.width() + 8, (h - txt.height()) // 2, txt)
            p.end()
            lab.setPixmap(pm)

    def _pick(self, i):
        self._sel = i
        self._refresh()
        self._confirm()

    def _confirm(self):
        self._choice = (self._sel == 0)
        self.accept()

    def showEvent(self, ev):
        super().showEvent(ev)
        # Windows 下 Qt.Tool 无边框窗口弹出后经常不激活、拿不到键盘焦点，
        # 左右键/回车就会全无反应 —— 显示后强制激活窗口并抢焦点。
        QTimer.singleShot(0, self._grab_focus)

    def _grab_focus(self):
        self.activateWindow()
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress and (obj is self or self.isAncestorOf(obj)):
            self.keyPressEvent(ev)
            return True
        return super().eventFilter(obj, ev)

    def mousePressEvent(self, ev):
        # 点框内任意空白处 = 确认当前选中项（点选项标签则由 _ClickLabel 先处理）
        if ev.button() == Qt.LeftButton:
            self._confirm()
        else:
            super().mousePressEvent(ev)

    def keyPressEvent(self, event):
        k = event.key()
        if k in (Qt.Key_Left, Qt.Key_Up):
            self._sel = 0
            self._refresh()
        elif k in (Qt.Key_Right, Qt.Key_Down):
            self._sel = 1
            self._refresh()
        elif k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self._confirm()
        elif k == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def choice(self):
        """True=完成 / False=未完成 / None=没回答（Esc）。"""
        return self._choice


# ---------------------------------------------------------------------------
# 台词气泡
# ---------------------------------------------------------------------------
class SpeechBubble(QWidget):
    """无边框透明置顶气泡，带小尾巴指向桌宠；文字逐字出现。"""

    typed_out = pyqtSignal()            # 整句打完时发出

    MAX_W = 300
    PAD_H, PAD_V = 12, 10
    TAIL_H, TAIL_W = 9, 18
    RADIUS = 10

    def __init__(self):
        super().__init__(None,
                         Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._label.setFont(QFont("Microsoft YaHei", 10))
        self._label.setStyleSheet("color: #f2f2f2; background: transparent;")

        self._anchor = QRect()
        self._full = ""
        self._idx = 0
        self._duration = 0
        self._on_char = None
        self._jitter = False

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        self._type_timer = QTimer(self)
        self._type_timer.timeout.connect(self._on_type_tick)

    def show_line(self, text, duration_ms, anchor_rect, char_ms=CHAR_MS,
                  on_char=None, jitter=False):
        """逐字显示。on_char(字符, 序号) 用于播放文字音；jitter 文字抖动。"""
        self._hide_timer.stop()
        self._type_timer.stop()

        self._anchor = QRect(anchor_rect)
        self._full = text
        self._idx = 0
        self._duration = duration_ms
        self._on_char = on_char
        self._jitter = jitter

        # 先按完整文本量好尺寸，之后逐字填充就不会让气泡越变越大。
        # 注意：必须先解除上一次 setFixedSize 留下的约束，否则 adjustSize/尺寸
        # 会被旧高度夹住，气泡高度会继承上一句的尺寸。
        self._label.setMinimumHeight(0)
        self._label.setMaximumHeight(BIG_SIZE)
        self._label.setFixedWidth(self.MAX_W)
        self._label.setText(text)
        lh = self._label.heightForWidth(self.MAX_W)
        if lh <= 0:
            self._label.adjustSize()
            lh = self._label.height()
        lw = self.MAX_W
        w = lw + 2 * self.PAD_H
        h = lh + 2 * self.PAD_V
        self.resize(w, h + self.TAIL_H)
        self._label.setFixedSize(lw, lh)
        self._label.setText("")
        self._label.move(self.PAD_H, self.PAD_V)

        self.reposition()
        self.show()
        self.raise_()
        self._type_timer.start(int(char_ms))

    def _on_type_tick(self):
        if self._idx >= len(self._full):
            self._type_timer.stop()
            self._label.move(self.PAD_H, self.PAD_V)     # 抖动归位
            self._hide_timer.start(int(self._duration))
            self.typed_out.emit()
            return
        self._idx += 1
        self._label.setText(self._full[:self._idx])
        if self._on_char is not None:
            self._on_char(self._full[self._idx - 1], self._idx)
        if self._jitter:
            self._label.move(
                self.PAD_H + random.randint(-JITTER_PX, JITTER_PX),
                self.PAD_V + random.randint(-JITTER_PX, JITTER_PX))

    def dismiss(self):
        """立刻收起（停止打字与定时隐藏）。"""
        self._type_timer.stop()
        self._hide_timer.stop()
        self.hide()

    def update_anchor(self, anchor_rect):
        self._anchor = QRect(anchor_rect)
        self.reposition()

    def reposition(self):
        if self._anchor.isNull():
            return
        scr = QApplication.primaryScreen().availableGeometry()
        x = self._anchor.center().x() - self.width() // 2
        y = self._anchor.top() - self.height() - 2
        x = max(scr.left() + 4, min(x, scr.right() - self.width() - 4))
        if y < scr.top() + 4:               # 上方放不下就翻到下方
            y = self._anchor.bottom() + 2
        self.move(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w = self.width()
        body_h = self.height() - self.TAIL_H

        path = QPainterPath()
        path.addRoundedRect(1.5, 1.5, w - 3, body_h - 3, self.RADIUS, self.RADIUS)
        cx = w // 2
        tail = QPainterPath()
        tail.moveTo(cx - self.TAIL_W // 2, body_h - 3)
        tail.lineTo(cx, body_h + self.TAIL_H - 3)
        tail.lineTo(cx + self.TAIL_W // 2, body_h - 3)
        tail.closeSubpath()
        shape = path.united(tail)

        painter.fillPath(shape, QColor(*BUBBLE_FILL_RGBA))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(*FRAME_RGB, 235), 2))     # 白框
        painter.drawPath(shape)


# ---------------------------------------------------------------------------
# 桌宠
# ---------------------------------------------------------------------------
class FloweyPet(QWidget):
    PRESET_SIZES = [("小 2×", 2.0), ("中 3×", 3.0), ("大 4×", 4.0), ("特大 6×", 6.0)]

    def __init__(self):
        super().__init__()
        self._state = "intro"          # intro -> idle -> wander -> outro
        self._face = "rest"            # rest / talk / wink / laugh / mimic / intro / sink
        self._speaking = False
        self._quitting = False
        self._bond_done = False
        self._start_ts = time.monotonic() * 1000.0
        self._last_interaction = self._start_ts
        self._last_wander_mimic = 0.0
        self._sway_t = 0.0
        # 冷落游荡
        self._last_wander = self._start_ts
        self._wander_gen = 0           # 代际计数：作废掉在途的 QTimer 回调
        self._wander_queue = []
        # 一次性动画（intro/sink）播完回调（QMovie.finished + 兜底轮询双保险）
        self._once_movie = None
        self._once_done = None
        self._once_deadline = 0.0
        self._once_timer = QTimer(self)
        self._once_timer.timeout.connect(self._once_guard)
        # 学 Sans/Papyrus 说完话 -> 变嘲讽脸一小会儿
        self._pending_evil = False
        # 提醒（右键「提醒 · N」-> 设置提醒）
        self._reminders = []           # 闹钟类：[{id, at(墙钟秒), text, retries, clock, tomorrow}]
        self._reminder_seq = 0
        self._reminder_panel = None    # 到点提醒用的大面板（复用同一实例）
        self._todos = []               # 待办事项：[{id, text, ddl(墙钟秒), done, asked_hour, asked_ten}]
        self._todo_seq = 0
        self._diary_log = []           # 当天定的提醒/待办流水（含已响/已取消/已完成），供日记同步

        # 被反复戳/拽 -> 概率钻走反抗（先甩一句 poke_spam 再钻）
        self._pressed_in_wander = False
        self._annoy_count = 0
        self._annoy_last = 0.0
        self._rebel_pending = False
        self._rebel_gen = 0             # 代际计数：作废掉在途的反抗回调
        self._rebel_hops_left = 0

        # overworld 盆栽形态（游荡后变身）：眨眼循环 + 静止 1~15 分钟计时
        self._ow_blink_timer = QTimer(self)
        self._ow_blink_timer.setSingleShot(True)
        self._ow_blink_timer.timeout.connect(self._ow_blink_tick)
        self._ow_still_timer = QTimer(self)
        self._ow_still_timer.setSingleShot(True)
        self._ow_still_timer.timeout.connect(self._ow_timeout)

        self._scale = self._load_scale()
        self._music_on = bool(self._load_state().get("music", True))
        self._sfx_on = bool(self._load_state().get("sfx", True))
        self._line_duration = 0

        self._lib = LineLibrary(LINES_JSON)
        self._bubble = SpeechBubble()

        self._init_assets()
        self._init_window()
        self._init_bgm()
        self._init_sfx()
        self._init_monitor()
        self._init_timers()
        self._init_intro()
        self._init_drag()
        self._warn_missing_events()     # 台词脚本缺事件只警告不崩（协调用）
        self._sync_diary()          # 建好当天专属日记（空也先立起来）

    # ------------------------------------------------------------------
    # 状态文件（缩放持久化 + 反复开关计数）
    # ------------------------------------------------------------------
    def _load_state(self):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_state(self, **kw):
        st = self._load_state()
        st.update(kw)
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(st, f)
        except OSError:
            pass

    def _load_scale(self):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                sc = float(json.load(f).get("scale", SCALE_DEFAULT))
        except (OSError, ValueError, TypeError):
            sc = SCALE_DEFAULT
        return max(SCALE_MIN, min(SCALE_MAX, sc))

    # ------------------------------------------------------------------
    # 素材
    # ------------------------------------------------------------------
    def _init_assets(self):
        target = self._target_size()

        self._intro_movie = QMovie(INTRO_GIF)
        self._talk_movie = QMovie(TALK_GIF)
        self._laugh_movie = QMovie(LAUGH_GIF)
        self._outro_movie = QMovie(OUTRO_GIF)
        for mv in (self._intro_movie, self._talk_movie,
                   self._laugh_movie, self._outro_movie):
            if not mv.isValid():
                raise FileNotFoundError("GIF 加载失败")
            mv.setScaledSize(target)
        self._talk_movie.setCacheMode(QMovie.CacheAll)
        # 一次性动画只播一遍：素材侧已不写 NETSCAPE 循环头（PyQt5 没有暴露
        # QMovie.setLoopCount，文件头是唯一开关——GIF loop=1 会被 Qt 播成两遍）
        # 播完信号：intro/sink 的收尾全靠它
        self._intro_movie.finished.connect(self._on_once_finished)
        self._outro_movie.finished.connect(self._on_once_finished)

        # 保留原始尺寸位图，缩放时重采样（不要覆盖 _orig_*）
        # 待机底图用「无眼脸」，眼睛由 _eyes_label 单独叠加（眼球跟随鼠标）
        self._orig_rest = QPixmap(EYELESS_PNG)
        if self._orig_rest.isNull():
            self._orig_rest = QPixmap(REST_PNG)   # 拆层素材缺失 -> 退回整脸，禁用跟眼
        self._eyes_ok = not self._orig_rest.isNull()
        self._orig_eyes = QPixmap(EYES_PNG)
        self._eyes_ok = self._eyes_ok and not self._orig_eyes.isNull()
        self._orig_wink = QPixmap(WINK_PNG)
        self._orig_mimic = QPixmap(MIMIC_PNG)
        self._orig_frisk = QPixmap(FRISK_PNG)
        self._orig_evil = QPixmap(EVIL_PNG)
        for pix in (self._orig_rest, self._orig_wink,
                    self._orig_mimic, self._orig_frisk, self._orig_evil):
            if pix.isNull():
                raise FileNotFoundError("PNG 加载失败")
        self._rest_pix = self._scale_pix(self._orig_rest)
        self._eyes_pix = self._scale_pix(self._orig_eyes) if self._eyes_ok else None
        self._avatar_pix = self._make_avatar()      # 脸+眼睛（弹窗头像用）
        self._wink_pix = self._scale_pix(self._orig_wink)
        self._mimic_pix = self._scale_pix(self._orig_mimic)
        self._frisk_pix = self._scale_pix(self._orig_frisk)
        self._evil_pix = self._scale_pix(self._orig_evil)

        # overworld 盆栽形态（游荡后变身用）
        self._orig_overworld = QPixmap(OVERWORLD_REST_PNG)
        self._orig_overworld_blink = QPixmap(OVERWORLD_BLINK_PNG)
        for pix in (self._orig_overworld, self._orig_overworld_blink):
            if pix.isNull():
                raise FileNotFoundError("overworld PNG 加载失败")
        self._overworld_pix = self._scale_pix(self._orig_overworld)
        self._overworld_blink_pix = self._scale_pix(self._orig_overworld_blink)

    def _target_size(self):
        return QSize(int(round(CANVAS_W * self._scale)),
                     int(round(CANVAS_H * self._scale)))

    def _scale_pix(self, pix):
        return pix.scaled(self._target_size(), Qt.IgnoreAspectRatio,
                          Qt.FastTransformation)

    def _make_avatar(self):
        """把眼睛图层叠回无眼待机脸上 -> 一张完整头像（弹窗/面板用）。

        底图是拆过眼的 `idle_eyeless.png`，直接拿它当头像就是一张「没有眼睛」
        的脸；这里按眼睛图层的原位（整画布同坐标系）画回去。拆层素材缺失时
        `_eyes_ok` 为假，退回整脸，不会重复画一双眼睛。
        """
        base = QPixmap(self._rest_pix)
        if self._eyes_ok and self._eyes_pix is not None and not self._eyes_pix.isNull():
            p = QPainter(base)
            p.drawPixmap(0, 0, self._eyes_pix)
            p.end()
        return base

    # ------------------------------------------------------------------
    # 窗口
    # ------------------------------------------------------------------
    def _init_window(self):
        w, h = self._target_size().width(), self._target_size().height()
        self.setFixedSize(w, h)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("Flowey")

        # label 尺寸 == 窗口，待机时在窗口内做小幅位移实现浮动（内容四周留白足够）
        self._label = QLabel(self)
        self._label.setGeometry(0, 0, w, h)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # 眼睛叠加层：与 _label 同几何，叠在脸上方；只在待机 rest 脚本显示，
        # 由 _eye_tick 按鼠标位置整体小幅平移（眼球跟随）。
        self._eyes_label = QLabel(self)
        self._eyes_label.setGeometry(0, 0, w, h)
        self._eyes_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        if self._eyes_ok and self._eyes_pix is not None:
            self._eyes_label.setPixmap(self._eyes_pix)
        self._gaze = (0, 0)     # 当前眼球偏移（窗口像素）
        self._eyes_label.hide()

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 80,
                  screen.bottom() - self.height() - 40)

    # ------------------------------------------------------------------
    # 定时器
    # ------------------------------------------------------------------
    def _init_timers(self):
        self._speak_timer = QTimer(self)
        self._speak_timer.setSingleShot(True)
        self._speak_timer.timeout.connect(self._end_speak)

        # 嘲讽脸（学 Sans/Papyrus 说完话后）停留一小会儿再回待机
        self._evil_timer = QTimer(self)
        self._evil_timer.setSingleShot(True)
        self._evil_timer.timeout.connect(self._evil_timeout)

        self._bubble.typed_out.connect(self._on_typed_out)

        self._watch_timer = QTimer(self)
        self._watch_timer.timeout.connect(self._on_watch_tick)
        self._watch_timer.start(WATCH_TICK_MS)

        # 待机浮动/扭动
        self._sway_timer = QTimer(self)
        self._sway_timer.timeout.connect(self._on_sway_tick)

        # 眼球跟随鼠标（待机 rest 脸）
        self._eye_timer = QTimer(self)
        self._eye_timer.timeout.connect(self._eye_tick)
        self._eye_timer.start(EYE_TICK_MS)

        # 提醒：每秒看一眼有没有到点的
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._reminder_tick)
        self._reminder_timer.start(REMINDER_TICK_MS)

    # ------------------------------------------------------------------
    # BGM（出场起播，循环；说狠话时中断）
    # ------------------------------------------------------------------
    def _init_bgm(self):
        self._bgm_ready = False
        self._player = None
        if not HAS_MULTIMEDIA or not os.path.exists(BGM_MP3):
            return
        self._player = QMediaPlayer(self)
        self._player.setMedia(QMediaContent(QUrl.fromLocalFile(BGM_MP3)))
        self._player.setVolume(BGM_VOLUME)
        self._player.mediaStatusChanged.connect(self._on_media_status)
        self._bgm_ready = True

    def _on_media_status(self, status):
        """播到结尾自动从头循环。"""
        if (self._bgm_ready and self._music_on
                and status == QMediaPlayer.EndOfMedia):
            self._player.setPosition(0)
            self._player.play()

    def _bgm_start(self):
        """出场调用：从头开始播。"""
        if self._bgm_ready and self._music_on:
            self._player.setPosition(0)
            self._player.play()

    def _bgm_duck(self):
        """说狠话：中断（暂停，记住位置）。"""
        if self._bgm_ready and self._music_on \
                and self._player.state() == QMediaPlayer.PlayingState:
            self._player.pause()

    def _bgm_restore(self):
        """狠话说完：接着刚才的位置继续。"""
        if self._bgm_ready and self._music_on:
            self._player.play()

    def _bgm_toggle(self, on):
        self._music_on = bool(on)
        self._save_state(music=self._music_on)
        if not self._bgm_ready:
            return
        if self._music_on:
            self._player.play()
        else:
            self._player.pause()

    def _bgm_stop(self):
        if self._bgm_ready:
            self._player.stop()

    # ------------------------------------------------------------------
    # 音效（说话文字音 / 变脸语音 / 邪恶笑声）
    # ------------------------------------------------------------------
    def _init_sfx(self):
        self._sfx = {}
        if not HAS_MULTIMEDIA or QSoundEffect is None:
            return
        for key, fn in SFX_FILES.items():
            path = os.path.join(SFX_DIR, fn)
            if not os.path.exists(path):
                continue
            eff = QSoundEffect(self)
            eff.setSource(QUrl.fromLocalFile(path))
            eff.setVolume(SFX_VOLUME[key])
            self._sfx[key] = eff

    def _play_sfx(self, key):
        if not self._sfx_on:
            return
        eff = self._sfx.get(key)
        if eff is not None:
            eff.play()

    def _stop_oneshot_sfx(self):
        """掐掉整段语音（变脸各角色/笑声），文字音无需处理。"""
        for key in ("mimic", "laugh", "sans", "asgore", "papyrus", "toriel"):
            eff = self._sfx.get(key)
            if eff is not None and eff.isPlaying():
                eff.stop()

    def _on_char_blip(self, char, idx):
        """逐字文字音：跳过空白，每 BLIP_EVERY_N 个字响一次。"""
        if char.strip() and idx % BLIP_EVERY_N == 0:
            self._play_sfx("blip")

    def _on_typed_out(self):
        """整句打完 -> 嘴立刻停（不再 talk 动），字停留 1s 后收起。"""
        if not self._speaking:
            return
        # 说完话：talk 脸立刻切回静止，让「字停留 1s」期间嘴巴不动
        if self._face == "talk":
            self._set_face("rest")
        self._speak_timer.start(self._line_duration + 150)

    # ------------------------------------------------------------------
    # 出场 -> 待机
    # ------------------------------------------------------------------
    def _init_intro(self):
        self._bgm_start()                   # 出场即播 BGM
        self._play_once("intro", self._after_intro)

    def _after_intro(self):
        if self._state != "intro":
            return
        self._state = "idle"
        self._set_face("rest")              # 待机 = 静止帧，嘴不动
        self._sway_timer.start(SWAY_TICK_MS)

        # 开场白：固定用 dc_01（Howdy！我是 Flowey…），取不到就随机
        greet = self._lib.find_by_id("dc_01") or self._lib.pick("double_click")
        if greet:
            QTimer.singleShot(300, lambda: self._speak(greet))

        # 反复开关检测（10 分钟内 >=3 次）
        if self._check_restart():
            QTimer.singleShot(6500, lambda: self._trigger_event("restart"))

    # ------------------------------------------------------------------
    # 待机浮动 + 扭动
    # ------------------------------------------------------------------
    def _on_sway_tick(self):
        self._sway_t += SWAY_TICK_MS
        w = 2.0 * math.pi / SWAY_PERIOD_MS
        s = self._scale
        # x 用两倍频率 -> 轨迹是个横 8 字，看起来像原地扭一扭
        dx = int(round(SWAY_AMP_X * s * math.sin(2.0 * w * self._sway_t)))
        dy = int(round(SWAY_AMP_Y * s * math.sin(w * self._sway_t)))
        self._label.move(dx, dy)
        self._sync_eyes_pos()

    # ------------------------------------------------------------------
    # 眼球跟随鼠标（待机 rest 脸）
    # ------------------------------------------------------------------
    def _sync_eyes_pos(self):
        """眼睛叠加层贴着主画面走（含浮动位移 + 当前眼球偏移）。"""
        if not self._eyes_label.isVisible():
            return
        gx, gy = self._gaze
        lp = self._label.pos()
        self._eyes_label.move(lp.x() + gx, lp.y() + gy)

    def _eye_tick(self):
        if not self._eyes_label.isVisible():
            return
        # 鼠标相对窗口中心的方向 -> 线性映射到限幅偏移（180px 内到满幅）
        g = self.mapToGlobal(self.rect().center())
        dx = QCursor.pos().x() - g.x()
        dy = QCursor.pos().y() - g.y()
        s = self._scale
        mx = EYE_MAX_DX * s
        gx = max(-mx, min(mx, dx / EYE_REACH_PX * mx))
        span = (EYE_MAX_DY_UP if dy < 0 else EYE_MAX_DY_DOWN) * s
        gy = max(-span, min(span, dy / EYE_REACH_PX * span))
        self._gaze = (int(round(gx)), int(round(gy)))
        self._sync_eyes_pos()

    def _update_eyes(self, kind=None):
        """按当前脸开合眼睛叠加层。

        关键：待机底图 `idle_eyeless.png` 是**拆掉了眼睛**的脸——所以只要画面
        停在 rest 脸上，就必须把眼睛图层叠回去，跟状态无关。以前这里多写了
        `self._state == "idle"`，于是非 idle 状态下说一句 rest 脸台词（比如
        退出时抽到 crack 语气的 shutdown、游荡收尾的 idle 台词）就会整句露着
        「没有眼睛」的脸——也就是「有的时候会没有眼睛」。
        """
        kind = self._face if kind is None else kind
        if kind == "rest" and self._eyes_ok:
            self._eyes_label.show()
            self._eyes_label.raise_()
            self._sync_eyes_pos()
        else:
            self._gaze = (0, 0)
            self._eyes_label.hide()

    # ------------------------------------------------------------------
    # 表情
    # ------------------------------------------------------------------
    def _set_face(self, kind):
        self._face = kind
        if kind == "laugh":
            self._talk_movie.stop()
            self._label.setMovie(self._laugh_movie)
            self._laugh_movie.start()
        elif kind == "talk":
            self._laugh_movie.stop()
            self._label.setMovie(self._talk_movie)
            self._talk_movie.start()
        elif kind == "wink":
            self._stop_once_face()
            self._talk_movie.stop()
            self._laugh_movie.stop()
            self._label.setPixmap(self._wink_pix)
        elif kind in ("asriel", "mimic"):        # mimic 是旧别名
            self._stop_once_face()
            self._talk_movie.stop()
            self._laugh_movie.stop()
            self._label.setPixmap(self._mimic_pix)
        elif kind == "frisk":
            self._stop_once_face()
            self._talk_movie.stop()
            self._laugh_movie.stop()
            self._label.setPixmap(self._frisk_pix)
        elif kind == "evil":
            self._stop_once_face()
            self._talk_movie.stop()
            self._laugh_movie.stop()
            self._label.setPixmap(self._evil_pix)
        elif kind == "overworld":
            # 盆栽形态：静态脸（眨眼由 _ow_* 定时器单独切帧）
            self._stop_once_face()
            self._talk_movie.stop()
            self._laugh_movie.stop()
            self._intro_movie.stop()
            self._outro_movie.stop()
            self._label.setPixmap(self._overworld_pix)
        elif kind == "intro":
            # 冒头（游荡时用；出场 _init_intro 也走这里）
            self._stop_once_face()
            self._talk_movie.stop()
            self._laugh_movie.stop()
            self._outro_movie.stop()
            self._label.setMovie(self._intro_movie)
            self._intro_movie.jumpToFrame(0)
            self._intro_movie.start()
        elif kind == "sink":
            self._stop_once_face()
            self._talk_movie.stop()
            self._laugh_movie.stop()
            self._intro_movie.stop()
            self._label.setMovie(self._outro_movie)
            self._outro_movie.jumpToFrame(0)
            self._outro_movie.start()       # 重新从头播（退场只播一次）
        else:                                    # rest
            self._stop_once_face()
            self._talk_movie.stop()
            self._laugh_movie.stop()
            self._label.setPixmap(self._rest_pix)
        self._update_eyes(kind)

    def _stop_once_face(self):
        """切到非一次性表情：作废还没触发的「播完回调」。"""
        self._once_movie = None
        self._once_done = None
        self._once_timer.stop()

    def _on_once_finished(self):
        """intro / sink 播完（QMovie.finished）-> 收尾。"""
        if self.sender() is not self._once_movie:
            return
        self._once_fire()

    def _once_guard(self):
        """兜底轮询：finished 万一没来（缩放重建动画、解码异常等）也别把
        状态机卡死——动画已到末帧、或超过硬上限，就强制收尾。"""
        mv = self._once_movie
        if mv is None:
            self._once_timer.stop()
            return
        played_out = (mv.state() == QMovie.NotRunning
                      and mv.currentFrameNumber() >= mv.frameCount() - 1)
        if played_out or time.monotonic() * 1000.0 >= self._once_deadline:
            self._once_fire()

    def _once_fire(self):
        """一次性动画收尾（幂等）：finished 信号和兜底轮询谁先到都只执行一次。"""
        self._once_timer.stop()
        cb, self._once_movie, self._once_done = self._once_done, None, None
        if cb:
            cb()

    def _play_once(self, kind, done):
        """切到一次性动画（intro/sink），播完自动回调 done。

        双保险收尾：QMovie.finished 信号 + _once_timer 兜底轮询（动画停在
        末帧 / 超过 ONCE_HARD_LIMIT_MS 就强制收尾）。之前只靠信号，一旦信号
        丢失（比如播到一半被改尺寸重建了动画），钻地就永远停在土里——
        也就是「钻地会卡住」。
        """
        self._stop_once_face()
        self._set_face(kind)
        self._once_movie = self._intro_movie if kind == "intro" else self._outro_movie
        self._once_done = done
        self._once_deadline = time.monotonic() * 1000.0 + ONCE_HARD_LIMIT_MS
        self._once_timer.start(ONCE_GUARD_MS)

    # ------------------------------------------------------------------
    # 缩放
    # ------------------------------------------------------------------
    def _apply_scale(self, new_scale):
        new_scale = round(max(SCALE_MIN, min(SCALE_MAX, new_scale)) / SCALE_STEP) * SCALE_STEP
        new_scale = round(new_scale, 2)
        if abs(new_scale - self._scale) < 1e-9:
            return

        center = self.frameGeometry().center()
        self._scale = new_scale
        target = self._target_size()
        w, h = target.width(), target.height()

        self.setFixedSize(w, h)
        self._label.setGeometry(0, 0, w, h)

        self._rest_pix = self._scale_pix(self._orig_rest)
        if self._eyes_ok:
            self._eyes_pix = self._scale_pix(self._orig_eyes)
            self._eyes_label.setPixmap(self._eyes_pix)
            self._eyes_label.setGeometry(0, 0, w, h)
        self._avatar_pix = self._make_avatar()      # 头像跟着缩放重建
        self._wink_pix = self._scale_pix(self._orig_wink)
        self._mimic_pix = self._scale_pix(self._orig_mimic)
        self._frisk_pix = self._scale_pix(self._orig_frisk)
        self._evil_pix = self._scale_pix(self._orig_evil)
        self._overworld_pix = self._scale_pix(self._orig_overworld)
        self._overworld_blink_pix = self._scale_pix(self._orig_overworld_blink)

        # 一次性动画播到一半被改尺寸：重播并保留「播完回调」。
        # 之前这里直接 _set_face(self._face) 会把回调作废 -> 钻地/出场永远
        # 等不到收尾，状态机整个卡死（「钻地会卡住」的另一个来源）。
        once_kind = self._face if (self._face in ("intro", "sink")
                                   and self._once_movie is not None) else None
        once_cb = self._once_done

        # GIF 重新缩放：只改 scaledSize。
        # 千万别动 cacheMode（旧代码 CacheNone->CacheAll 来回切）：切完之后
        # QMovie 会坏掉——之后再 start() 也不会真正播放（state 直接停在
        # 末帧 NotRunning），finished 永远不来，钻地就卡死在土里。
        for mv in (self._intro_movie, self._talk_movie,
                   self._laugh_movie, self._outro_movie):
            mv.setScaledSize(target)

        if once_kind is not None:
            self._play_once(once_kind, once_cb)  # 重新起播，回调原样挂回
        else:
            self._set_face(self._face)           # 按新尺寸重新贴当前画面
        self._gaze = (0, 0)                  # 缩放后眼球偏移清零，别带着旧偏移错位
        self._label.move(0, 0)
        self._sync_eyes_pos()
        self._sway_t = 0.0

        self.move(center.x() - w // 2, center.y() - h // 2)
        self._bubble.update_anchor(self.frameGeometry())
        self._save_state(scale=new_scale)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self._wander_abort()
        self._apply_scale(self._scale + (SCALE_STEP if delta > 0 else -SCALE_STEP))
        event.accept()

    # ------------------------------------------------------------------
    # 说话
    # ------------------------------------------------------------------
    def _resolve_face(self, line):
        """台词 -> 表情。

        优先级：
        1. 台词自带 face（wink / laugh / mimic=asriel 别名）
        2. 模仿台词（有 mimicOf）：
           - 学 Sans / Papyrus -> wink 挑衅脸（说完变嘲讽 evil 脸）
           - 学 Toriel / Asgore -> asriel 脸（学爸妈当然用儿子的脸）
           - 讲到重置/存档之类的事、且语气不恼怒 -> frisk 脸
           - 其余模仿 -> asriel 假关心脸
        3. 按 tone 兜底（manic -> laugh，crack/plead -> rest），默认 talk（嘴动）
        """
        face = line.get("face")
        if face:
            return "asriel" if face == "mimic" else face
        mimic_of = line.get("mimicOf")
        if mimic_of:
            if mimic_of in MIMIC_WINK_OF:
                return "wink"
            if mimic_of in MIMIC_ASRIEL_OF:
                return "asriel"
            if (line.get("tone", "") not in ANGRY_TONES
                    and any(w in line.get("text", "") for w in RESET_KEYWORDS)):
                return "frisk"
            return "asriel"
        return TONE_FACE.get(line.get("tone", ""), "talk")

    def _mimic_voice_key(self, line):
        """模仿台词 -> 用哪条角色语音；没有专属语音的（Asriel/Chara）用通用变脸声。"""
        return MIMIC_VOICES.get(line.get("mimicOf"), "mimic")

    def _speak(self, line):
        # 防御：游荡还在半途时被插话（正常流程不会发生）-> 先把游荡收掉
        if self._state == "wander" and self._wander_queue:
            self._wander_abort()
        self._speaking = True
        face = self._resolve_face(line)
        self._set_face(face)
        if face == MEAN_FACE:               # 狠话/难听话 -> BGM 中断
            self._bgm_duck()

        # 语音跟 mimicOf 走（学谁用谁的声子），不跟表情走——
        # 学 Sans/Papyrus 用的是 wink 脸，语音照样得是 sans/papyrus 的
        mimic_of = line.get("mimicOf")
        if mimic_of:
            voice_key = MIMIC_VOICES.get(mimic_of, "mimic")
        elif face == MEAN_FACE:
            voice_key = "laugh"
        else:
            voice_key = None
        has_voice = voice_key is not None   # 有整段语音就不再逐字响 blip

        # 逐字显示；变脸台词带抖动。打完字后固定停留 SPEAK_LINGER_MS（1s），
        # 这 1s 内由 _on_typed_out 把 talk 脸切回静止 -> 嘴巴不动。
        self._line_duration = SPEAK_LINGER_MS
        self._bubble.show_line(
            line.get("text", ""), self._line_duration, self.frameGeometry(),
            char_ms=CHAR_MS,
            on_char=None if has_voice else self._on_char_blip,
            jitter=face in ("asriel", "frisk"),
        )

        # 学 Sans/Papyrus 说完话要变嘲讽脸
        self._pending_evil = mimic_of in MIMIC_WINK_OF

        # 整段语音
        self._stop_oneshot_sfx()
        if voice_key:
            self._play_sfx(voice_key)

    def _end_speak(self):
        self._speaking = False
        self._bubble.dismiss()
        self._stop_oneshot_sfx()
        self._bgm_restore()                 # 狠话说完，BGM 继续
        evil = self._pending_evil           # 学 Sans/Papyrus 说完 -> 变嘲讽脸
        self._pending_evil = False
        if self._quitting:
            self._start_outro()
            return
        self._set_face("rest")
        # 只有游荡已走到「最后说话」这步（队列空了）才收回 idle；
        # 半途被插话时不动游荡状态，让在途的钻地/冒头继续走完。
        entered_ow = False
        if self._state == "wander" and not self._wander_queue:
            self._enter_overworld()          # 游荡收尾 -> 变盆栽形态静坐
            entered_ow = True
        # 学 Sans/Papyrus 说完 -> 变嘲讽脸（overworld 接管时跳过，避免覆盖盆栽脸）
        if evil and not entered_ow:
            self._set_face("evil")
            self._evil_timer.start(EVIL_HOLD_MS)
        # 说完一句就顺手看看有没有被挡住的提醒要补说（提醒别迟到太久）
        if self._reminders and not self._quitting:
            QTimer.singleShot(0, self._reminder_tick)

    def _evil_timeout(self):
        """嘲讽脸看够了 -> 回待机（期间被打断/换了表情就不动）。"""
        self._evil_timer.stop()
        if self._face == "evil" and not self._speaking and not self._quitting:
            self._set_face("rest")

    # ------------------------------------------------------------------
    # 提醒（倒计时 / 具体时间 / 待办事项）——右键「提醒 · N」-> 设置提醒
    # ------------------------------------------------------------------
    def _add_reminder(self, at, text, tomorrow=False, clock=False):
        """挂一个提醒（倒计时/具体时间）。at = 墙钟 epoch 秒（已折算好）。"""
        if self._quitting:
            return False
        if len(self._reminders) >= REMINDER_MAX_ITEMS:
            return False
        self._reminder_seq += 1
        rid = self._reminder_seq
        self._reminders.append({
            "id": rid,
            "at": float(at),
            "text": text,
            "retries": 0,
            "clock": clock,
            "tomorrow": tomorrow,
        })
        self._reminders.sort(key=lambda r: r["at"])
        # 同步到当天专属日记
        self._diary_log.append({
            "id": rid,
            "kind": "alarm",
            "date": date.today().isoformat(),
            "at": float(at),
            "text": text,
            "status": "pending",
            "tomorrow": tomorrow,
            "clock": clock,
        })
        self._sync_diary()
        return True

    def _cancel_reminder(self, rid):
        before = len(self._reminders)
        self._reminders = [r for r in self._reminders if r["id"] != rid]
        changed = len(self._reminders) != before
        if changed:
            for e in self._diary_log:
                if e["id"] == rid and e["status"] == "pending":
                    e["status"] = "cancelled"
            self._sync_diary()
        return changed

    @staticmethod
    def _reminder_eta(r):
        if r.get("clock"):                       # 具体时间：直接显示钟点
            fire = datetime.fromtimestamp(r["at"])
            now = datetime.now()
            if fire.date() == now.date():
                return "今天 %s" % fire.strftime("%H:%M")
            return "明天 %s" % fire.strftime("%H:%M")
        secs = int(round(r["at"] - time.time()))
        if secs <= 0:
            return "马上"
        if secs < 60:
            return "%d 秒后" % secs
        mins, rest = divmod(secs, 60)
        if mins < 60:
            return "%d 分 %d 秒后" % (mins, rest) if rest else "%d 分钟后" % mins
        hours, left = divmod(mins, 60)
        return "%d 小时 %d 分后" % (hours, left) if left else "%d 小时后" % hours

    def _reminder_tick(self):
        """到点了就说。一次只说一条，剩下的下一秒继续。

        顺带巡检待办事项：DDL 前 1 小时 / 10 分钟弹问「完成没」。
        """
        if self._quitting:
            return
        self._todo_tick()
        if not self._reminders:
            return
        now = time.time()
        for r in list(self._reminders):
            if now < r["at"]:
                break                                   # 按 at 升序，后面的更晚
            # 正忙着（在说话 / 出场 / 钻地）就延后，别把话说断；
            # 待机 / 游荡 / overworld 盆栽形态下都照常弹面板
            if self._speaking or self._state in ("outro", "ow_sink", "intro",
                                                   "rebel_sink"):
                r["retries"] += 1
                if r["retries"] <= REMINDER_MAX_RETRY:
                    r["at"] = now + REMINDER_RETRY_MS / 1000.0
                    self._reminders.sort(key=lambda x: x["at"])
                    continue
            self._reminders.remove(r)
            self._fire_reminder(r)
            break
            # 一次一句：说完再轮到下一条（下一秒会再走到这里）

    def _fire_reminder(self, r):
        """到点：弹一个独立的大面板（比气泡更显眼），先「叮叮」两声。"""
        if self._quitting:
            return
        if self._state == "wander":
            self._wander_abort()            # 提醒优先，游荡先收回（overworld 不动）
        self._reminder_chime()
        line = self._lib.pick("reminder", force=True)
        if line is None:
            return
        line = dict(line)
        line["text"] = line["text"].replace("{what}", r["text"])
        self._show_reminder_panel(line)
        # 同步到日记：这条已响
        for e in self._diary_log:
            if e["id"] == r["id"] and e["status"] == "pending":
                e["status"] = "fired"
        self._sync_diary()

    def _show_reminder_panel(self, line):
        """复用同一个 ReminderPanel 实例：固定成屏幕约 1/6 大小并居中显示；
        已开就刷新文字并置顶。"""
        if self._reminder_panel is None or not self._reminder_panel.isVisible():
            # 头像 = 无眼待机脸 + 眼睛图层（底图本身没眼睛，直接用会是张瞎脸）
            self._reminder_panel = ReminderPanel(self, self._avatar_pix)
        scr = QApplication.primaryScreen().availableGeometry()
        # 与「设置提醒」对话框共用同一套尺寸常量 -> 两个页面一样大
        w = min(DIALOG_W_MAX, max(DIALOG_W_MIN,
                                  int(scr.width() * REMINDER_PANEL_W_FRAC)))
        h = min(DIALOG_H_MAX, max(DIALOG_H_MIN,
                                  int(scr.height() * REMINDER_PANEL_H_FRAC)))
        self._reminder_panel.resize(w, h)
        self._reminder_panel.set_text(line.get("text", ""))
        self._reminder_panel.move(
            scr.left() + (scr.width() - w) // 2,
            scr.top() + (scr.height() - h) // 2)
        if not self._reminder_panel.isVisible():
            self._reminder_panel.show()
        else:
            self._reminder_panel.raise_()

    def _reminder_chime(self):
        """到点先「叮叮」两声（复用文字音 blip，音量临时提高）。"""
        eff = self._sfx.get("blip")
        if eff is None or not self._sfx_on:
            return
        old = eff.volume()
        eff.setVolume(REMINDER_CHIME_VOLUME)
        eff.play()
        QTimer.singleShot(180, eff.play)                    # 第二声
        QTimer.singleShot(420, lambda: eff.setVolume(old))   # 音量还回去

    # ------------------------------------------------------------------
    # 待办事项（带 DDL）：到期前 1h / 10min 问完成没，完成与否同步日记
    # ------------------------------------------------------------------
    def _add_todo(self, ddl, text):
        """挂一个待办事项。ddl = 截止时间的 epoch 秒。"""
        if self._quitting:
            return False
        if len(self._todos) >= TODO_MAX_ITEMS:
            return False
        self._todo_seq += 1
        rid = self._todo_seq
        self._todos.append({
            "id": rid,
            "text": text,
            "ddl": float(ddl),
            "done": False,
            "asked_hour": False,
            "asked_ten": False,
        })
        self._todos.sort(key=lambda t: t["ddl"])
        self._diary_log.append({
            "id": rid,
            "kind": "todo",
            "date": date.today().isoformat(),
            "at": float(ddl),
            "text": text,
            "status": "pending",
            "done": False,
        })
        self._sync_diary()
        return True

    def _cancel_todo(self, rid):
        before = len(self._todos)
        self._todos = [t for t in self._todos if t["id"] != rid]
        changed = len(self._todos) != before
        if changed:
            for e in self._diary_log:
                if e["id"] == rid and e.get("kind") == "todo":
                    e["status"] = "cancelled"
            self._sync_diary()
        return changed

    def _set_todo_done(self, rid, done):
        """标记待办完成/未完成，并同步日记。"""
        for t in self._todos:
            if t["id"] == rid:
                t["done"] = bool(done)
                break
        else:
            return False
        for e in self._diary_log:
            if e["id"] == rid and e.get("kind") == "todo":
                e["done"] = bool(done)
                e["status"] = "done" if done else "undone"
        self._sync_diary()
        return True

    @staticmethod
    def _todo_eta(t):
        """待办的剩余时间文案（给菜单/弹窗用）。"""
        secs = int(round(t["ddl"] - time.time()))
        if secs <= 0:
            return "已过期"
        mins, rest = divmod(secs, 60)
        if mins < 60:
            return "还剩 %d 分钟" % max(1, mins)
        hours, left = divmod(mins, 60)
        if hours < 24:
            return "还剩 %d 小时 %d 分" % (hours, left)
        days = hours // 24
        return "还剩 %d 天 %d 小时" % (days, hours % 24)

    def _todo_tick(self):
        """每 tick 检查：DDL 前 1 小时 / 10 分钟各问一次完成没。"""
        if not self._todos or self._quitting:
            return
        now = time.time()
        for t in list(self._todos):
            if t["done"]:
                continue
            ddl = t["ddl"]
            if now >= ddl - TODO_ASK_HOUR_SEC and not t["asked_hour"]:
                t["asked_hour"] = True
                self._ask_todo_done(t)
            elif now >= ddl - TODO_ASK_TEN_SEC and not t["asked_ten"]:
                t["asked_ten"] = True
                self._ask_todo_done(t)

    def _ask_todo_done(self, t):
        """DDL 前问「完成没」：先甩一句（todo_ask），说完再弹 UT 对话框。

        用户答「完成」-> todo_done；答「未完成」-> todo_fail；Esc 不回答则
        不改状态、也不回话（他自己都懒得理你）。结果都会同步进日记。
        台词脚本缺对应事件时静默跳过，只保留弹窗功能。
        """
        if self._quitting:
            return
        line = self._lib.pick("todo_ask", force=True)
        delay = 0
        if line is not None:
            said = dict(line)
            said["text"] = (line.get("text", "")
                            .replace("{what}", t["text"] or "（没写内容）")
                            .replace("{eta}", self._todo_eta(t)))
            if self._state == "idle" and not self._speaking:
                self._speak(said)
                delay = self._speech_ms(said)
        QTimer.singleShot(delay, lambda: self._todo_popup(t))

    def _todo_popup(self, t):
        """弹「完成 / 未完成」对话框（居中），并根据回答回一句。"""
        if self._quitting:
            return
        if not any(x["id"] == t["id"] for x in self._todos):
            return                                  # 期间被删了就别问了
        dlg = TodoCheckDialog(t["text"], self._todo_eta(t), self)
        dlg.adjustSize()
        scr = QApplication.primaryScreen().availableGeometry()
        dlg.move(scr.center().x() - dlg.width() // 2,
                 scr.center().y() - dlg.height() // 2)
        if dlg.exec_() != QDialog.Accepted:
            return
        choice = dlg.choice()
        if choice is None:              # Esc：没回答，不改状态
            return
        self._set_todo_done(t["id"], choice)
        line = self._lib.pick("todo_done" if choice else "todo_fail",
                              force=True)
        if line is None or self._quitting or self._state != "idle":
            return
        said = dict(line)
        said["text"] = (line.get("text", "")
                        .replace("{what}", t["text"] or "（没写内容）")
                        .replace("{eta}", self._todo_eta(t)))
        self._speak(said)

    def _sync_diary(self):
        """把「当天定的提醒与待办」写入 Flowey 专属日记（flowey_diary.txt）。

        用电脑自带的记事本即可打开；每次设/取消/响铃都重写一次，保持同步。
        """
        today = date.today().isoformat()
        L = []
        L.append("=" * 48)
        L.append("  Flowey 的日记  （自动同步 · 用电脑自带记事本打开即可）")
        L.append("=" * 48)
        L.append("  日期：%s    更新：%s"
                 % (today, datetime.now().strftime("%H:%M:%S")))
        L.append("")

        # ---- 提醒（倒计时 / 具体时间）----
        L.append("【提醒】")
        a_total = 0
        a_pending = 0
        for e in self._diary_log:
            if e.get("kind") == "todo":
                continue
            if e["date"] != today or e["status"] == "cancelled":
                continue
            a_total += 1
            fire = datetime.fromtimestamp(e["at"])
            if e["status"] == "pending":
                a_pending += 1
                tag = "待响"
            else:
                tag = "已响"
            when = ("明天 " if e.get("tomorrow") else "今天 ") \
                + fire.strftime("%H:%M")
            content = e["text"] or "（无备注）"
            L.append("  [%s] %s   %s" % (tag, when, content))
        if a_total == 0:
            L.append("  （今天还没有设提醒）")

        # ---- 待办事项（带 DDL，完成与否同步到这里）----
        L.append("")
        L.append("【待办事项】")
        t_total = 0
        t_done = 0
        for e in self._diary_log:
            if e.get("kind") != "todo":
                continue
            if e["date"] != today or e["status"] == "cancelled":
                continue
            t_total += 1
            ddl_dt = datetime.fromtimestamp(e["at"])
            when = ddl_dt.strftime("%m-%d %H:%M")
            if e.get("done") or e["status"] == "done":
                tag = "已完成"
                t_done += 1
            elif e["status"] == "undone":
                tag = "未完成"
            else:
                tag = "待办"
            content = e["text"] or "（没写内容）"
            L.append("  [%s] DDL %s   %s" % (tag, when, content))
        if t_total == 0:
            L.append("  （今天还没有待办事项）")

        L.append("")
        L.append("-" * 48)
        L.append("  提醒 %d 条（待响 %d）    待办 %d 条（已完成 %d）"
                 % (a_total, a_pending, t_total, t_done))

        # ---- Flowey 自己的批注（每次打开日记他补一句，只留最近几条）----
        notes = self._diary_notes()
        if notes:
            L.append("")
            L.append("【Flowey 批注】")
            for hhmm, txt in notes[-DIARY_NOTE_MAX:]:
                L.append("  · %s  %s" % (hhmm, txt))

        try:
            with open(DIARY_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(L) + "\n")
        except OSError:
            pass

    def _diary_notes(self):
        """读回批注（存状态文件，日记被重写也不会丢）。"""
        notes = self._load_state().get("diaryNotes", [])
        return [n for n in notes if isinstance(n, list) and len(n) == 2]

    def _add_diary_note(self, text):
        """追加一条批注（只留最近 DIARY_NOTE_MAX 条）。"""
        notes = self._diary_notes()
        notes.append([datetime.now().strftime("%H:%M"), text])
        self._save_state(diaryNotes=notes[-DIARY_NOTE_MAX:])

    def _open_diary(self):
        """打开专属日记：先让他以小花口吻评价一句（并写进日记批注），再开记事本。"""
        line = self._lib.pick("diary_comment", force=True)
        if line is not None:
            today = date.today().isoformat()
            n = sum(1 for e in self._diary_log
                    if e["date"] == today and e["status"] != "cancelled")
            said = dict(line)
            said["text"] = line.get("text", "").replace(
                "{n}", str(n) if n else "零")
            if self._state == "idle" and not self._speaking and not self._quitting:
                self._speak(said)
            self._add_diary_note(said["text"])     # 这句也留在日记里
        self._sync_diary()              # 先确保是最新的
        try:
            os.startfile(DIARY_PATH)    # Windows：.txt 默认用记事本
        except Exception:
            import subprocess
            try:
                if sys.platform.startswith("darwin"):
                    subprocess.run(["open", DIARY_PATH])
                else:
                    subprocess.run(["xdg-open", DIARY_PATH])
            except Exception:
                pass

    def _ask_reminder(self):
        """右键「设置提醒…」：弹输入框 -> 挂提醒 / 挂待办 -> 让他回一句。"""
        if self._quitting:
            return
        dlg = AlarmDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        res = dlg.value()
        if not res:
            return
        if res.get("kind") == "todo":
            self._ask_reminder_todo(res)
            return
        at = res["at"]
        text = res.get("text", "")
        tomorrow = res.get("tomorrow", False)
        clock = res.get("clock", False)
        if not self._add_reminder(at, text, tomorrow, clock):
            # 挂满了（其他失败原因前面已排除）-> 说一句，别让点击石沉大海
            full = self._lib.pick("reminder_full", force=True)
            if full and not self._speaking and self._state == "idle":
                full = dict(full)
                full["text"] = full["text"].replace(
                    "{max}", str(REMINDER_MAX_ITEMS))
                self._speak(full)
            return
        line = self._lib.pick("reminder_set", force=True)
        if line is None:
            return
        line = dict(line)
        # {min}：倒计时显示「X分钟后」，具体时间显示「今天/明天 HH:MM」
        if clock:
            fire = datetime.fromtimestamp(at)
            min_disp = ("明天 " if tomorrow else "今天 ") + fire.strftime("%H:%M")
        else:
            min_disp = humanize_minutes((at - time.time()) / 60.0)
        line["text"] = (line["text"].replace("{min}", min_disp)
                                   .replace("{what}", text or "提醒"))
        if self._speaking:                  # 别把正在说的话掐了
            self._speak_timer.stop()
            self._end_speak()
        if self._state != "idle":           # 出场/退场动画中：只记下，不出声
            return
        self._speak(line)

    def _ask_reminder_todo(self, res):
        """待办事项分支：挂待办 + 同步日记 + 让他回一句（复用 reminder_set）。"""
        text = res.get("text", "")
        ddl = res["ddl"]
        if not self._add_todo(ddl, text):
            full = self._lib.pick("reminder_full", force=True)
            if full and not self._speaking and self._state == "idle":
                full = dict(full)
                full["text"] = full["text"].replace(
                    "{max}", str(TODO_MAX_ITEMS))
                self._speak(full)
            return
        # 优先用专门的待办回执（{what} 内容 / {eta} 剩余时间）；
        # 脚本里没写 todo_add 就回退 reminder_set（{min} 用 DDL 钟点）
        line = (self._lib.pick("todo_add", force=True)
                or self._lib.pick("reminder_set", force=True))
        if line is None:
            return
        line = dict(line)
        ddl_dt = datetime.fromtimestamp(ddl)
        line["text"] = (line.get("text", "")
                        .replace("{what}", text or "待办")
                        .replace("{eta}", self._todo_eta({"ddl": ddl}))
                        .replace("{min}", ddl_dt.strftime("%m-%d %H:%M")))
        if self._speaking:
            self._speak_timer.stop()
            self._end_speak()
        if self._state != "idle":
            return
        self._speak(line)

    # ------------------------------------------------------------------
    # 退场：钻地离开
    # ------------------------------------------------------------------
    def _start_outro(self):
        if self._state == "outro":
            return
        self._state = "outro"
        self._bubble.dismiss()
        if self._reminder_panel is not None:
            self._reminder_panel.close()
        self._stop_oneshot_sfx()
        self._sway_timer.stop()
        self._label.move(0, 0)
        self._bgm_stop()
        self._play_once("sink", lambda: QTimer.singleShot(OUTRO_EXTRA_MS,
                                                          QApplication.quit))

    def _warn_missing_events(self):
        """启动时核对代码会触发的事件是否都在 lines.json 里。

        台词脚本由用户自由编辑——缺了某个事件只打印警告、相关互动静默跳过，
        绝不让程序崩溃（「他改台词不影响我运作」）。
        """
        missing = [e for e in CODE_EVENTS if e not in self._lib.events]
        if missing:
            print("[flowey] 警告：lines.json 缺少事件 %s，对应互动将静默跳过"
                  % missing)

    def _trigger_event(self, event, force=False):
        """取台词并说话；冷却未到返回 False（force 用于右键手动触发，可打断当前台词）。"""
        if self._state != "idle" or self._quitting:
            return False
        if self._speaking and not force:
            return False
        line = self._lib.pick(event, force=force)
        if line is None:
            return False
        self._speak(line)
        return True

    # ------------------------------------------------------------------
    # 实时监控：检测 Steam / 微信 / 浏览器 / 视频 / 办公软件进程
    # ------------------------------------------------------------------
    def _init_monitor(self):
        self._psutil = None
        self._proc_targets = {}
        for ev, cfg in self._lib.config["events"].items():
            names = cfg.get("processNames")
            if names:
                self._proc_targets[ev] = {n.lower() for n in names}
        self._proc_seen = {}            # ev -> 上次扫描是否在运行
        self._mon_pending = {}          # ev -> 检测到但没说成的时间戳
        self._last_scan = 0.0
        if not self._proc_targets:
            return
        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            pass                        # 没装 psutil 就静默跳过监控

    def _monitor_tick(self, now):
        """扫描进程；新出现的触发台词。忙时记入 pending 稍后重试。

        扫描按 MONITOR_SCAN_MS 节流，但 pending 重试每个巡检 tick 都要跑
        （否则「说话时检测到、说完再补」的机制会被扫描节流一起挡掉）。
        """
        if self._psutil is None or not self._proc_targets:
            return
        if now - self._last_scan >= MONITOR_SCAN_MS:
            self._last_scan = now
            try:
                running = set()
                for p in self._psutil.process_iter(["name"]):
                    nm = p.info.get("name")
                    if nm:
                        running.add(nm.lower())
            except Exception:
                return                      # 权限/快照竞态等，下轮再扫
            for ev, targets in self._proc_targets.items():
                found = bool(running & targets)
                was = self._proc_seen.get(ev)
                self._proc_seen[ev] = found
                if found and not was:       # 只在「新出现」时触发，不反复打扰
                    self._mon_pending[ev] = now
        # 重试：检测到时正在说话/游荡 -> MONITOR_PENDING_MS 内再试，过时不候
        for ev, ts in list(self._mon_pending.items()):
            if now - ts > MONITOR_PENDING_MS:
                del self._mon_pending[ev]
                continue
            if self._trigger_event(ev):
                del self._mon_pending[ev]

    # ------------------------------------------------------------------
    # 后台巡检：监控 / bond / mimic / 冷落游荡
    # ------------------------------------------------------------------
    def _on_watch_tick(self):
        now = time.monotonic() * 1000.0
        # 进程扫描无论忙闲都要跑：就算此刻在说话，也要记录「出现了」这个事实
        self._monitor_tick(now)
        if self._state != "idle" or self._speaking or self._quitting:
            return
        cfg = self._lib.config["events"]

        # 连续陪伴 >=30min（全库唯一允许 tender 的事件）
        if not self._bond_done and now - self._start_ts >= cfg["bond"]["triggerMs"]:
            self._bond_done = True
            if self._trigger_event("bond"):
                return

        # 变脸（开场 10min 后；冷却由 pick 按 mimic 的 cooldownMs 管）
        if now - self._start_ts >= cfg["mimic"]["triggerMs"]:
            if self._trigger_event("mimic"):
                return

        # 被冷落 -> 游荡（钻地 / 四处冒头 / 到光标旁说话）。
        # 阈值由 lines.json 的 idle.triggerMs 驱动（用户改脚本即改行为），
        # 这里用 .get 兜底，万一该字段被删也不会崩。
        neglect_ms = self._lib.config.get("events", {}).get(
            "idle", {}).get("triggerMs", NEGLECT_WANDER_MS)
        if (now - self._last_interaction >= neglect_ms
                and now - self._last_wander >= WANDER_COOLDOWN_MS):
            self._start_wander(now)

    # ------------------------------------------------------------------
    # 冷落游荡：钻地 -> 屏幕上几处冒头看看 -> 到鼠标光标旁说话
    # ------------------------------------------------------------------
    def _start_wander(self, now):
        if self._state != "idle" or self._quitting or self._speaking:
            return
        self._state = "wander"
        self._wander_gen += 1
        self._last_wander = now
        self._bubble.dismiss()
        self._sway_timer.stop()
        self._label.move(0, 0)
        self._update_eyes()                 # 底图是无眼脸 -> 眼睛图层跟着保留
        self._wander_queue = self._make_wander_spots()
        self._wander_dig(self._wander_gen)

    def _make_wander_spots(self):
        """造一串落点：前面几处随机，最后是鼠标光标旁边。"""
        scr = QApplication.primaryScreen().availableGeometry()
        w, h = self.width(), self.height()
        m = WANDER_MARGIN
        x0, x1 = scr.left() + m, max(scr.left() + m, scr.right() - w - m)
        y0, y1 = scr.top() + m, max(scr.top() + m, scr.bottom() - h - m)

        cur = self.frameGeometry().topLeft()
        spots = []
        tries = 0
        while len(spots) < WANDER_SPOTS and tries < WANDER_SPOTS * 30:
            tries += 1
            x, y = random.randint(x0, x1), random.randint(y0, y1)
            if abs(x - cur.x()) < w * 0.7 and abs(y - cur.y()) < h * 0.7:
                continue                    # 太近，换个地方
            spots.append(QPoint(x, y))

        # 最后：鼠标光标附近（右下方，别压住光标）
        c = QCursor.pos()
        x = c.x() + int(w * WANDER_CURSOR_DX)
        y = c.y() + int(h * WANDER_CURSOR_DY)
        spots.append(QPoint(max(x0, min(x, x1)), max(y0, min(y, y1))))
        return spots

    def _wander_alive(self, gen):
        return gen == self._wander_gen and self._state == "wander"

    def _wander_dig(self, gen):
        """在当前处钻地，然后去下一处冒头。"""
        if not self._wander_alive(gen):
            return
        self._label.move(0, 0)
        self._play_once("sink", lambda: QTimer.singleShot(
            WANDER_GAP_MS, lambda: self._wander_pop(gen)))

    def _wander_pop(self, gen):
        """传送到下一处并冒头；还有下一处就继续钻地，最后一处则说话。"""
        if not self._wander_alive(gen) or not self._wander_queue:
            return
        self.move(self._wander_queue.pop(0))
        self._bubble.update_anchor(self.frameGeometry())
        follow = self._wander_dig if self._wander_queue else self._wander_talk
        self._play_once("intro", lambda: QTimer.singleShot(
            WANDER_LOOK_MS, lambda: follow(gen)))

    def _wander_talk(self, gen):
        """游荡的收尾：在光标旁说一句（优先变脸学人说话，其次 idle / peek）。

        说完（或没话说）后不再回待机，而是变身成 overworld 盆栽形态静坐。
        """
        if not self._wander_alive(gen):
            return
        line = self._pick_neglect_line()
        if line is not None:
            self._speak(line)               # 说完 _end_speak 会转 _enter_overworld
        else:
            self._enter_overworld()

    def _pick_neglect_line(self):
        """冷落台词：被冷落了还专门跑过来骚扰你，多半是要变脸学人说话。"""
        now = time.monotonic() * 1000.0
        if now - self._last_wander_mimic >= WANDER_MIMIC_COOLDOWN_MS:
            line = self._lib.pick("mimic", force=True)
            if line is not None:
                self._last_wander_mimic = now
                return line
        order = ["peek", "idle"] if random.random() < 0.5 else ["idle", "peek"]
        for event in order:
            line = self._lib.pick(event)
            if line is not None:
                return line
        return self._lib.pick("idle", force=True) or self._lib.pick("peek", force=True)

    def _wander_abort(self):
        """用户插手了：立刻作废在途回调并回到原地待机。"""
        if self._state != "wander":
            return
        self._wander_gen += 1               # 让在途的 singleShot 回调全部失效
        self._wander_queue = []
        self._state = "idle"
        self._label.move(0, 0)
        if not self._speaking:
            self._set_face("rest")
            self._sway_timer.start(SWAY_TICK_MS)

    # ------------------------------------------------------------------
    # 游荡结束 -> overworld 盆栽形态：静坐 + 眨眼 + 点击钻走
    # ------------------------------------------------------------------
    def _enter_overworld(self):
        """游荡收尾后变身成游戏里那盆盆栽 Flowey，静静坐着。

        - 不浮动（停 sway），换静态盆栽脸
        - 启动眨眼循环（overworld_blink 帧闪一下再回常态）
        - 随机 1~15 分钟后自动回到待机（_ow_timeout）
        - 期间鼠标「戳一下」(quick tap) -> 变回原样（_ow_poke_revert）；拖拽 -> 钻地离开（_ow_dig_away）
        - 偶尔用气泡冒一句 overworld 台词（不动脸、不算 speaking）
        """
        if self._quitting:
            return
        self._state = "overworld"
        self._wander_gen += 1               # 作废任何残留的游荡回调
        self._wander_queue = []
        self._bubble.dismiss()
        self._sway_timer.stop()
        self._label.move(0, 0)
        self._last_interaction = time.monotonic() * 1000.0  # 离开后至少再 idle 60s 才重游荡
        self._set_face("overworld")

        line = self._lib.pick("overworld", force=True)
        if line is not None:
            self._bubble.show_line(
                line["text"], line["durationMs"], self.frameGeometry(),
                char_ms=CHAR_MS, on_char=self._on_char_blip)

        self._ow_schedule_blink()
        self._ow_still_timer.start(
            random.randint(OVERWORLD_MIN_MS, OVERWORLD_MAX_MS))

    def _ow_schedule_blink(self):
        if self._state != "overworld":
            return
        self._ow_blink_timer.start(
            random.randint(OVERWORLD_BLINK_MIN_MS, OVERWORLD_BLINK_MAX_MS))

    def _ow_blink_tick(self):
        if self._state != "overworld":
            return
        self._label.setPixmap(self._overworld_blink_pix)
        QTimer.singleShot(OVERWORLD_BLINK_HOLD_MS, self._ow_blink_back)

    def _ow_blink_back(self):
        if self._state != "overworld":
            return
        self._label.setPixmap(self._overworld_pix)
        self._ow_schedule_blink()

    def _ow_timeout(self):
        """静止 1~15 分钟到了：自动回到待机（不钻地，自然收场）。"""
        if self._state != "overworld":
            return
        self._ow_blink_timer.stop()
        self._leave_overworld()

    def _leave_overworld(self):
        """从盆栽形态自然回到待机（无钻地动画）。"""
        self._state = "idle"
        self._label.move(0, 0)
        self._set_face("rest")
        if not self._quitting:
            self._sway_timer.start(SWAY_TICK_MS)

    def _ow_dig_away(self):
        """用户点击盆栽形态：钻地离开，回到待机。"""
        if self._state != "overworld":
            return
        self._ow_blink_timer.stop()
        self._ow_still_timer.stop()
        self._bubble.dismiss()
        self._label.move(0, 0)
        self._state = "ow_sink"             # 钻地期间屏蔽其它触发
        self._play_once("sink", self._ow_dig_done)

    def _ow_dig_done(self):
        self._state = "idle"
        self._set_face("rest")
        if not self._quitting:
            self._sway_timer.start(SWAY_TICK_MS)

    def _ow_poke_revert(self):
        """用户戳了一下盆栽形态（小花）：从小花变回原样（Flowey 本尊脸）。

        不是钻地逃跑，而是被你戳得「现出原形」——回到待机本尊脸、恢复浮动，
        并阴阳怪气两句（revert 事件台词）。戳一下就够了，不用拖。
        """
        if self._state != "overworld":
            return
        self._ow_blink_timer.stop()
        self._ow_still_timer.stop()
        self._bubble.dismiss()
        self._label.move(0, 0)
        self._state = "idle"
        self._set_face("rest")
        if not self._quitting:
            self._sway_timer.start(SWAY_TICK_MS)
        # 戳醒了，说两句（force 忽略冷却，避免连续戳时只变脸不说话）
        self._trigger_event("revert", force=True)

    # ------------------------------------------------------------------
    # 反复开关检测
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 被反复戳/拽 -> 概率钻走反抗
    # ------------------------------------------------------------------
    def _bump_annoy(self):
        """每被戳/拽一次累计恼火；达到阈值后有概率发动「钻走反抗」。

        返回 True 表示已发动反抗（调用方不要再正常说话）。
        超过 ANNOY_RESET_MS 没再被戳/拽，计数器清零，重新累计。
        """
        now_ms = time.monotonic() * 1000.0
        if now_ms - self._annoy_last > ANNOY_RESET_MS:
            self._annoy_count = 0
        self._annoy_count += 1
        self._annoy_last = now_ms
        if (self._annoy_count >= ANNOY_THRESHOLD
                and random.random() < ANNOY_REBEL_PROB):
            self._annoy_count = 0
            self._annoy_rebel()
            return True
        return False

    def _annoy_rebel(self):
        """被戳/拽烦了：甩一句（poke_spam）-> 钻地离开 -> 之后回待机。

        台词脚本里没有 poke_spam 就退回原来的沉默反抗（不说话直接钻走），
        保证改台词不会让功能失效。
        """
        if self._state == "wander":
            self._wander_abort()
        if self._quitting or self._rebel_pending:
            return
        if self._speaking:                  # 正在说话也照常打断，确保反抗能发动
            self._speak_timer.stop()
            self._end_speak()
        if self._state != "idle":
            return
        line = self._lib.pick("poke_spam", force=True)
        if line is None:
            self._rebel_sink_now()          # 脚本没写这句 -> 老行为：沉默钻走
            return
        self._rebel_pending = True
        self._speak(line)
        # 等这句说（打）完再钻，别把话掐在半路
        delay = self._speech_ms(line)
        QTimer.singleShot(delay, self._rebel_after_line)

    def _speech_ms(self, line):
        """这句台词大概要说多久（打字 + 停留），用于安排后续动作。"""
        n = len(line.get("text", ""))
        return int(n * CHAR_MS + SPEAK_LINGER_MS + 400)

    def _rebel_after_line(self):
        """话说完了 -> 钻地离开；期间用户又戳出别的状况就作罢。"""
        if self._quitting:
            return
        self._rebel_pending = False
        if self._state != "idle" or self._speaking:
            return
        self._rebel_sink_now()

    def _rebel_sink_now(self):
        """被戳烦了的反抗：甩完话钻地离开 -> 钻到别处冒头、再钻、再冒，
        躲 REBEL_HOPS 次后才回待机（不再原地待着，像游荡那样换地方躲）。"""
        self._bubble.dismiss()
        self._sway_timer.stop()
        self._label.move(0, 0)
        self._state = "rebel_sink"          # 钻地/游荡期间屏蔽其它触发
        self._rebel_gen += 1
        self._rebel_hops_left = REBEL_HOPS
        self._play_once("sink", lambda: self._rebel_relocate(self._rebel_gen))

    def _rebel_relocate(self, gen):
        """钻到新位置冒头；还没躲够次数就继续钻，躲够了就回待机。"""
        if gen != self._rebel_gen or self._quitting:
            return
        if self._rebel_hops_left <= 0:
            self._rebel_settle(gen)
            return
        self.move(self._rebel_next_spot())
        self._bubble.update_anchor(self.frameGeometry())
        self._rebel_hops_left -= 1
        self._play_once("intro", lambda: QTimer.singleShot(
            WANDER_LOOK_MS, lambda: self._rebel_dig_again(gen)))

    def _rebel_dig_again(self, gen):
        """在新位置停留看一眼后，再钻地准备去下一处。"""
        if gen != self._rebel_gen or self._quitting:
            return
        self._label.move(0, 0)
        self._play_once("sink", lambda: self._rebel_relocate(gen))

    def _rebel_next_spot(self):
        """选一个离当前位置不太近的随机屏幕落点（复用游荡的留白/边距规则）。"""
        scr = QApplication.primaryScreen().availableGeometry()
        w, h = self.width(), self.height()
        m = WANDER_MARGIN
        x0, x1 = scr.left() + m, max(scr.left() + m, scr.right() - w - m)
        y0, y1 = scr.top() + m, max(scr.top() + m, scr.bottom() - h - m)
        cur = self.frameGeometry().topLeft()
        for _ in range(WANDER_SPOTS * 30):
            x, y = random.randint(x0, x1), random.randint(y0, y1)
            if abs(x - cur.x()) < w * 0.7 and abs(y - cur.y()) < h * 0.7:
                continue                    # 太近，换个地方
            return QPoint(x, y)
        return QPoint(x0, y0)               # 兜底：实在没找到就用左上合法点

    def _rebel_settle(self, gen):
        """躲够了：在当前（最后一个）位置回待机。"""
        if gen != self._rebel_gen or self._quitting:
            return
        self._state = "idle"
        self._set_face("rest")
        self._sway_timer.start(SWAY_TICK_MS)
        self._last_interaction = time.monotonic() * 1000.0

    def _check_restart(self):
        try:
            now = time.time()
            window = self._lib.config["events"]["restart"]["windowMs"] / 1000.0
            starts = self._load_state().get("starts", [])
            recent = [t for t in starts if isinstance(t, (int, float))
                      and now - t <= window]
            recent.append(now)
            self._save_state(starts=recent)
            return len(recent) >= self._lib.config["events"]["restart"]["minTriggers"]
        except (OSError, KeyError):
            return False

    # ------------------------------------------------------------------
    # 鼠标交互
    # ------------------------------------------------------------------
    def _init_drag(self):
        self._dragging = False
        self._drag_offset = QPoint(0, 0)
        self._press_pos = QPoint(0, 0)
        self._press_ts = 0.0

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._pressed_in_wander = (self._state == "wander")
        self._wander_abort()                # 用户插手：游荡立刻收工
        self._dragging = True
        self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
        self._press_pos = event.globalPos()
        self._press_ts = time.monotonic() * 1000.0
        self.setCursor(Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            if self._state == "overworld":
                return                      # 盆栽形态不动，拖也拖不动
            self.move(event.globalPos() - self._drag_offset)
            self._bubble.update_anchor(self.frameGeometry())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self._dragging:
            return
        self._dragging = False
        self.setCursor(Qt.ArrowCursor)
        moved = (event.globalPos() - self._press_pos).manhattanLength()
        elapsed = time.monotonic() * 1000.0 - self._press_ts
        self._last_interaction = time.monotonic() * 1000.0

        if self._state == "overworld":
            # 盆栽形态（小花）：戳一下（quick tap）-> 变回原样；拖拽 -> 钻地离开（保留）
            if moved < CLICK_SLOP_PX and elapsed <= CLICK_MAX_MS:
                self._ow_poke_revert()
            else:
                self._ow_dig_away()
            event.accept()
            return

        if moved < CLICK_SLOP_PX and elapsed <= CLICK_MAX_MS:
            # 单击 = 戳他一下；被戳烦了有概率直接钻走反抗
            if not self._bump_annoy():
                self._trigger_event("double_click")
        else:
            if self._pressed_in_wander:
                # 游荡冒头「挡住屏幕」被拖走 -> 专门台词（已在 lines.json）
                self._trigger_event("peek_drag", force=True)
            else:
                # 普通拖拽；被反复拖拽也有概率钻走反抗
                if not self._bump_annoy():
                    self._trigger_event("drag")
        event.accept()

    def contextMenuEvent(self, event):
        self._wander_abort()
        # 菜单开着也算「有人在陪着」，别趁机钻走；弹出那一刻先接一句 panel_open
        self._last_interaction = time.monotonic() * 1000.0
        self._say_panel_open()
        menu, acts = self._build_menu()
        chosen = menu.exec_(event.globalPos())
        self._last_interaction = time.monotonic() * 1000.0
        if chosen is None:
            return
        if chosen is acts["say"]:
            self._random_chat()
        elif chosen is acts["music"]:
            self._bgm_toggle(acts["music"].isChecked())
        elif chosen is acts["sfx"]:
            self._sfx_on = acts["sfx"].isChecked()
            self._save_state(sfx=self._sfx_on)
            if self._sfx_on:
                self._play_sfx("blip")          # 开回来：响一声当作确认
            else:
                self._stop_oneshot_sfx()
                self._say_mute()            # 关音效 -> 接本来就写好的 mute 台词
        elif chosen is acts["hush"]:
            self._speak_timer.stop()
            self._end_speak()               # 复用：恢复 BGM、回待机脸
        elif chosen is acts["quit"]:
            self._quit_with_farewell()

    # ------------------------------------------------------------------
    # 菜单 / 静音的台词（lines.json 里 panel_open、mute 两条一直没人触发）
    # ------------------------------------------------------------------
    def _say_panel_open(self):
        """右键菜单一弹出就说一句 panel_open（打破第四面墙）。

        冷却走 lines.json 的 config.events.panel_open.cooldownMs（12s），
        所以连点菜单不会刷屏；他正在说话时不打断（等他讲完再说）。
        overworld 盆栽形态下只能冒气泡——那时没法动脸。
        """
        if self._quitting or self._speaking:
            return False
        if self._state not in ("idle", "overworld"):
            return False
        line = self._lib.pick("panel_open")
        if line is None:
            return False
        if self._state == "overworld":
            self._bubble.show_line(
                line.get("text", ""), line.get("durationMs", 4000),
                self.frameGeometry(), char_ms=CHAR_MS,
                on_char=self._on_char_blip)
        else:
            self._speak(line)
        return True

    def _say_mute(self):
        """关掉音效时接一句 mute（「嘘。你把我静音了。」那组台词）。

        用户主动操作优先：正在说话也先收掉当前那句再吐槽。
        音效此刻已经关了，所以这句只出字、不出声——正应了 mu_05。
        冷却走 lines.json 的 config.events.mute.cooldownMs（8s）。
        """
        if self._quitting:
            return False
        if self._state not in ("idle", "overworld"):
            return False
        line = self._lib.pick("mute", force=True)
        if line is None:
            return False
        if self._state == "overworld":
            self._bubble.show_line(
                line.get("text", ""), line.get("durationMs", 4000),
                self.frameGeometry(), char_ms=CHAR_MS,
                on_char=self._on_char_blip)
            return True
        if self._speaking:                  # 主动打断：他要说的是「你把我静音了」
            self._speak_timer.stop()
            self._end_speak()
        self._speak(line)
        return True

    def _build_menu(self):
        """构建右键菜单（PetMenu：白框 + 像素红心 + 键盘导航）。

        注意：条目一旦带图标，Qt 就不再画勾选标记，所以「音乐/音效」的开关
        状态直接写进文字（：开 / ：关），当前大小用 √ 标出。
        """
        menu = PetMenu(parent=self)
        menu.setStyleSheet(MENU_QSS)

        a_say = QAction("说点什么", self)
        a_music = QAction("音乐：%s" % ("开" if self._music_on else "关"), self)
        a_music.setCheckable(True)
        a_music.setChecked(self._music_on)
        if not self._bgm_ready:
            a_music.setEnabled(False)
        a_sfx = QAction("音效：%s" % ("开" if self._sfx_on else "关"), self)
        a_sfx.setCheckable(True)
        a_sfx.setChecked(self._sfx_on)
        if not self._sfx:
            a_sfx.setEnabled(False)
        a_hush = QAction("闭嘴", self)
        a_quit = QAction("退出", self)

        size_menu = PetMenu("大小 · %.1f×" % self._scale, menu)
        size_menu.setStyleSheet(MENU_QSS)
        for label, sc in self.PRESET_SIZES:
            text = label + ("  √" if abs(self._scale - sc) < 1e-6 else "")
            a = size_menu.addAction(text)
            a.setCheckable(True)
            a.setChecked(abs(self._scale - sc) < 1e-6)
            a.triggered.connect(lambda _checked, s=sc: self._apply_scale(s))
        size_menu.addSeparator()
        tip = size_menu.addAction("鼠标滚轮也可缩放")
        tip.setEnabled(False)

        # 提醒：顶层「设置提醒…」一步到位；挂着提醒/待办时多一个子菜单可逐个取消
        a_remind = QAction("设置提醒…", self)
        a_remind.triggered.connect(
            lambda: QTimer.singleShot(0, self._ask_reminder))
        a_book = QAction("打开日记", self)
        a_book.triggered.connect(
            lambda: QTimer.singleShot(0, self._open_diary))
        remind_menu = None
        n_all = len(self._reminders) + len(self._todos)
        if n_all:
            remind_menu = PetMenu("提醒 · %d" % n_all, menu)
            remind_menu.setStyleSheet(MENU_QSS)
            for item in self._reminders:       # 闹钟类：点一下 = 取消这条
                act = remind_menu.addAction("取消：%s（%s）" % (
                    item["text"], self._reminder_eta(item)))
                act.triggered.connect(
                    lambda _c, rid=item["id"]: self._cancel_reminder(rid))
            for t in self._todos:              # 待办：点一下 = 取消这条
                mark = "已完成 " if t["done"] else ""
                act = remind_menu.addAction("%s取消：%s（DDL %s，%s）" % (
                    mark, t["text"],
                    datetime.fromtimestamp(t["ddl"]).strftime("%m-%d %H:%M"),
                    self._todo_eta(t)))
                act.triggered.connect(
                    lambda _c, rid=t["id"]: self._cancel_todo(rid))

        menu.addAction(a_say)
        if remind_menu is not None:
            menu.addAction(remind_menu.menuAction())
        menu.addAction(a_remind)
        menu.addAction(a_book)
        menu.addAction(a_music)
        menu.addAction(a_sfx)
        menu.addMenu(size_menu)
        menu.addAction(a_hush)
        menu.addSeparator()
        menu.addAction(a_quit)
        return menu, {"say": a_say, "music": a_music, "sfx": a_sfx,
                      "hush": a_hush, "quit": a_quit}

    def _random_chat(self):
        """手动触发（右键「说点什么」，忽略冷却）。

        约四成概率直接来一段「变脸学人说话」——这正是要求的效果之一；
        其余从日常事件里随机挑。
        """
        if random.random() < 0.4 and self._trigger_event("mimic", force=True):
            return
        for event in random.sample(
                ["double_click", "drag", "idle", "peek", "restart"], 5):
            if self._trigger_event(event, force=True):
                return

    def _quit_with_farewell(self):
        """退出：先说 shutdown 台词，说完 _end_speak 会转钻地退场再退出。"""
        if self._quitting:
            return
        self._quitting = True
        line = self._lib.pick("shutdown", force=True)
        if line:
            self._speak(line)
        else:
            self._start_outro()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    pet = FloweyPet()
    pet.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
