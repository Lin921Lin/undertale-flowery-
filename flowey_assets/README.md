# Flowey 桌宠素材库

- **来源**: undertale.wiki（Undertale Wiki，MediaWiki API `api.php?action=query&list=allimages`）
- **文件数**: 155（实时以 `preview.html` 顶部计数为准；官方精灵/对话/音频 + 黑白像素转换 + 互联网搜集 + 引擎用图）
- **浏览方式**: 打开 `preview.html`（方格底纹 = 透明通道，像素图已 pixelated 渲染）
- **注意**: 素材版权归 Toby Fox / 8-4 所有，仅限个人桌宠等非商业用途。

## 目录结构

| 目录 | 内容 | 说明 |
|---|---|---|
| `01_overworld/` | 2 | 大地图行走立绘 42×42，**桌宠首选底图** |
| `02_battle_faces/` | 17 | **主素材目录**。Flowey 全部 11 张战斗/表情（talk/laugh/appear 为**动图 GIF**）+ 6 张 Omega/Photoshop Flowey 战斗表情（smile/sweat/look_right/static + 2 个动图） |
| `03_omega_flowey/` | 10 | Photoshop/Omega Flowey 形态：表情部件（smile、sweat、look_right）、动图（laugh、photorealistic face）、概念图 |
| `04_artwork/` | 5 | 官方美术：塔罗牌、Nendoroid、Steam 卡、明信片（非透明底，做素材参考用） |
| `05_reference/` | 8 | 游戏截图与乐谱图、Toriel/Asriel 参照脸，仅参考 |
| `06_dialogue/` | 21 | **对话素材**：`TextBox.svg`（Undertale 风格对话框模板，黑底白边，自绘）+ 带头像位版本；`Dialogue_box_Ruins.png` 为截图参考（非干净素材）；`choice/`（18 件）为**战斗选择界面官方素材**（见下行） |
| `06_dialogue/choice/` | 18 | **选择按钮官方 sprite**（undertale.wiki）：`FIGHT/ACT/ITEM/MERCY_button.png`（110×42，橙色未选中态）、`*_selected.png`（黄色选中态，程序改色）、`*_alpha.png` / `*_selected_alpha.png`（透明底版）、`Red_SOUL_cursor.png`（16×16 红心选择光标）、`choice_menu.svg`（按游戏内布局拼装的界面还原样例：文本框在上 + 按钮行在下，ACT 选中演示） |
| `07_audio/` | 3 | **声音素材**：`Flowey_laugh.ogg`（官方 Flowey 笑声，6.4s）、`Omega_Flowey_saved.ogg`、`Blip_synthesized.wav`（自合成文字 blip 占位音） |
| `audio/` | 4 | **桌宠引擎实际音频**：`bgm_intro.mp3` + `sfx/`（blip_talk.wav、laugh_evil.wav、voice_mimic.wav），由 `flowey_pet.py` 调用，与 `07_audio/` 分开放置 |
| `09_monochrome/` | 50 | **像素黑白版**（2026-10-12）：`01~07` 全部官方精灵的黑白像素转换（亮度阈值 128，透明底保留），目录结构与源一一对应。GIF 帧逐帧转换，透明用调色板索引实现。由脚本批处理生成 |
| `10_internet_bw/` | 16 | **互联网搜集的像素/黑白 Flowey**（pngkit，同人来源非官方）：`evil_flowey_blackwhite_clipart_alpha.png` 为**真·黑白像素 Flowey**（透明底）；另含 6 张彩色像素 Flowey 的透明版（`*_alpha.png`）及其白底原图、1 张游戏内截图、1 张拼豆图 |

## 表情语义对照

| 文件 | 含义 | 依据 |
|---|---|---|
| `Flowey_face_mimicking_protagonist.png` | 模仿玩家操控的 Frisk（标志性空白脸） | 小林标注 ✅ 已确认 |
| `Flowey_battle_mimicking_Asriel.png` | 模仿 **Asriel**（屠杀线） | wiki 文件描述 "Flowey emulating Asriel Dreemurr in the Genocide Route"，游戏内 sprite 名 `spr_flowey_as_1` |
| `Flowey_battle_hurt.png` | 受击表情 | 游戏内战斗受击帧 |
| `Flowey_battle_spared.png` | 被放过后的表情 | 中立线战斗收尾 |
| `Flowey_battle_fatal_Neutral.png` / `_Genocide.png` | 战败/枯萎姿态（中立线/屠杀线） | 路线分支差异 |
| `Flowey_battle_winking.png` | 眨眼表情 | 桌宠彩蛋候选 |

**关于 `mimicking_Asriel` 的判定**（2026-10-12 小林曾提出更像 Toriel，比对后维持 Asriel）：
- 对照图见 `05_reference/ref_Toriel_face.png` 与 `ref_Asriel_Dreemurr_face.png`；
- 该表情有 Asriel 标志性的**刘海发型**，无 Toriel 的**头顶双角**与**长垂耳**；
- wiki 文件页明确标注 Genocide Route 中模仿 Asriel，sprite 命名 `spr_flowey_as_1`（as = Asriel）。

## 做桌宠的推荐组合

- **待机**: `01_overworld/Flowey_overworld.png`（可放大 4~6 倍）
- **说话**: `02_battle_faces/Flowey_battle_talk.gif`
- **开心**: `02_battle_faces/Flowey_battle_laugh.gif`
- **受伤/生气**: `Flowey_battle_hurt.png` / `Flowey_battle_fatal_Neutral.png`
- **眨眼彩蛋**: `Flowey_battle_winking.png`
- **大 boss 彩蛋**: `03_omega_flowey/` 全套

## 备注

- 所有 PNG/GIF 均为**透明底**，可直接叠在桌面上。
- **引擎加工素材**（`02_battle_faces_trans/`，由 `make_transparent_assets.py` 生成，2026-10-12 v8.1）：
  - `idle_rest / idle_talk / blink_wink / laugh / mimic_face / frisk_face / intro_appear / outro_sink` 来自 02 官方战斗素材；
    **`evil_face.png`（嘲讽脸）来自 `10_internet_bw/evil_flowey_blackwhite_clipart_alpha.png`**（缩放二值化后对齐到 96×120 画布）。
  - 统一 **2 画布像素黑描边**（1px 太细，白底页面看不清轮廓）；
  - **轮廓内部零透明洞**：不与画布边缘连通的透明区域全部填实（战斗素材填黑并进剪影，evil_face 填白保持白瓣黑线风格）。
- `The Spriters Resource` 与 `undertale.fandom.com` 在当前网络环境完全不可达（连接被重置/403），
  Google/GitHub 等站也封着，唯一稳定来源是 `undertale.wiki` 的官方 API。
- **wiki 上 Flowey 战斗/表情精灵图已穷尽**：共 11 张（即 `Flowey_battle_*` 10 张 + `Flowey_face_*` 1 张），
  已全数纳入 02；另把 6 张 Omega/Photoshop Flowey 战斗表情并入 02 作为主素材补充，原始副本仍保留在 `03_omega_flowey/`。
- 想拿到**完整逐帧动画**（Spriters Resource 的整张 sprite sheet，含 talk/laugh 的全部中间帧）需要满足其一：
  ① 让本机 Clash 代理（127.0.0.1:7890）真正对外提供网络；② 直接丢一份本地 Undertale 解包后的 `spr_flowey_*` 给我。届时我再补拉。
- **对话 UI**：wiki 上没有独立的对话框 sprite（"Border screenshot" 是整张截图），`06_dialogue/TextBox*.svg` 为按官方样式（黑底白边像素框）自绘的可缩放模板。
- **说话声音**：Undertale 无真人配音，角色说话的声音 = 文字 blip 音效（游戏内 `snd_txt*`）。该音效 wiki 与 Fandom CDN 均未收录，
  `07_audio/Blip_synthesized.wav` 是用 Python 合成的方波 blip 占位音；拿到正版 `snd_txt*.ogg` 后直接替换同名文件即可。
  `Flowey_laugh.ogg` 为官方笑声音效（"Your Best Nightmare" 中 Flowey 的笑），可当得意/嘲讽台词的语音彩蛋。
- **像素黑白素材**（2026-10-12）：
  - `09_monochrome/` 为**程序转换**（源 = 官方精灵，亮度阈值→纯黑白，透明底）。黑白 GIF 的透明用「索引 1 = 透明哨兵色」方案实现，避开了「黑色既是描边又当透明」的冲突。
  - `10_internet_bw/` 来自 pngkit（本环境唯一可达的图床，Spriters Resource 403 / GitHub API 封 / hiclipart·pngegg 403）。
    同人来源、非官方像素，按「边缘连通 flood-fill 去白底」处理（只抠连到边缘的白，保留脸内部白色）；白底原图与 `*_alpha.png` 透明版都保留。
    「black-and-white-cute」那张实为女孩线稿（冒名），已删除。
  - 想要**官方黑白/逐帧**仍需上述两条路径（开代理 / 丢本地解包 `spr_flowey_*`）。
