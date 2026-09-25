# Into the Radius 2 简体中文汉化（ITR2 Chinese Patch）

面向 Steam 版 **Into the Radius 2**（appid `2307350`）的简体中文补丁，通过
**patch pak（`*_P.pak` / IoStore override）** 覆盖游戏内的 `en` 语言资源实现汉化。
基准版本：`Hotfix Patch 1.1.2` / Steam buildid `24024260`。

- 覆盖度：**3772 / 3772 条唯一英文原文（100%）**
  - `Game.locres` 4611 条（原 2164 + `EnglishSource` 命名空间合并 2447）
  - `EnglishSource.uasset` 3332 条中 3019 条替换为中文（IoStore override）
  - 字体：用**游戏自带的 Noto Sans SC**（20,976 个汉字）替换 3 个离线字体 `.ufont`
- 产物：`release_zh/`（不入库）与 `ITR2_Chinese_v2.zip`（发布包，**随仓库保存**——
  它同时是 `iostore_build.py` 的容器模板来源）；`dist_zh/`、`fonts/` 等中间产物用脚本生成、不入库
- **构建链零上游代码依赖**（2026 阶段一重构）：全部格式解析/构建为本仓库独立实现，
  自测与成品比对全部通过（见文末「格式实现与验证」）。
- **注意：仅凭本仓库内容无法构建**——游戏原文件（构建输入）因版权归 CM Games 有意
  不入库，需用 `collect_game_inputs.py` 在游戏机一次性采集（见「工作区依赖提醒」）。

> **仓库范围**
> 本仓库仅包含汉化补丁本身，不涉及任何内存修改工具，也不包含游戏本体资源。
> 汉化通过替换语言资源文件实现，与任何运行时内存读写工具均无耦合。

## 为什么必须打 pak

UE 挂载时先读 pak、再读松散文件，因此把 `Game.locres` 以松散文件放进
`Content\Localization\Game\zh-Hans\` **不会生效**；`-CULTURE=zh-Hans` 也不是本作正确的切换方式
（引擎只 stage 了 `en` 的 ICU 数据）。正确做法是让带 `_P` 后缀的 patch pak 在基础 pak 之后挂载，
直接覆盖 `en` 资源。

## 目录结构

```
├─ textkey.py                 三种哈希：key_hash(CityHash64×23 折叠) / source_hash(CRC32 UTF-32LE) / source_id(SHA1[:16])
├─ locres.py                  自研 UE .locres v3 解析 / 装配（parse/build 往返逐字节）
├─ uasset_text.py             EnglishSource.uasset serial 文本区解析 + 文本补丁
├─ pakbuild.py                自研 patch pak 构建（pyuepak 封装）
├─ iostore_build.py           自研 IoStore (.utoc/.ucas) 写入端
├─ iostore.py                 自研 IoStore 读取器（Oodle 惰性加载）
├─ collect_game_inputs.py     【游戏机端】采集构建输入 -> game_inputs/ 交付
├─ prepare_records.py         game_inputs + zh_sources.json -> records_with_zh.json
├─ build_zh.py                主构建：locres pak + EnglishSource IoStore 补丁 -> dist_zh/
├─ build_font_pak.py          字体包：从 game_inputs 的 uasset 裁出 Noto Sans SC 覆盖 .ufont
├─ make_release.py            组装 release_zh/ 与 ITR2_Chinese_v2.zip
├─ verify_dist.py             产物独立校验（读回 pak / IoStore / locres / 字体）
├─ validate_hash_formulas.py  逐条校验 source_hash / key_hash 公式（5496 条）
├─ setup_oodle.py             （可选）修复 pyuepak 自动下载失败的 Oodle DLL
├─ zh_sources.json            【翻译数据】source_id -> 简体中文（3772 条）
├─ records_with_zh.json       位置记录 + 译文（prepare_records.py 生成，5496 条）
├─ translate/zh_full/         翻译分片原始产物（可追溯）
├─ normalize_zh.py            【翻译阶段·历史】术语归一
├─ make_zh_chunks.py          【翻译阶段·历史】把待译原文切分为翻译任务分片
├─ progress_vs_ko.py          【翻译阶段·历史】覆盖率统计（需当时的 ref_ko 数据快照）
├─ docs/                      说明、术语表、分析与校验报告
│  ├─ 汉化说明.md             安装与使用说明
│  ├─ glossary_zh.md          术语表（原文 -> 中文对照口径）
│  ├─ ko_analysis.md          上游韩化资源清点（该资源不随本仓库分发）
│  ├─ merge_report.md         合并与校验报告
│  └─ 剧情与世界观.md         ⚠️【全文剧透】游戏剧情、世界观与结局分歧完整文档
└─ scratch/                   逆向过程中的临时探查脚本（不入库）
```

## 构建步骤

```bash
# 0) 依赖
pip install pyuepak cityhash            # pak 读写 / CityHash64
# 1) 在游戏机采集构建输入（一次性；需已安装游戏），把 game_inputs/ 传回本机仓库旁
python collect_game_inputs.py --game-dir "D:\...\IntoTheRadius2" --out D:\game_inputs
#    采集：pakchunk0-Windows.pak、EnglishSource.uasset、NotoSansSC-*.uasset 等（SHA256 清单校验）
# 2) 生成位置记录（把中文写进 records）
python prepare_records.py
# 3) 构建补丁产物 -> dist_zh/
python build_zh.py
python build_font_pak.py
# 4) 组装交付包 -> release_zh/ 与 ITR2_Chinese_v2.zip
python make_release.py
# 5) 校验
python verify_dist.py
python validate_hash_formulas.py
```

游戏安装目录只在第 1 步（游戏机端采集）需要；本机构建全部基于 `game_inputs/`，
**不需要游戏安装、不需要 `ref_ko/`（上游参考仓库已不再被任何脚本加载）**。
安装/卸载：`release_zh/安装汉化.cmd`、`release_zh/卸载汉化.cmd`（或 `install.ps1 -Uninstall`）。

> **Oodle 说明**：pyuepak 在 import 时会联网下载 `oo2core_9_win64.dll`，实测该下载可能拿到
> 大小/哈希不符的坏文件导致 `import pyuepak` 报错——此时运行 `python setup_oodle.py`
> 从本机游戏目录找一个可用 `oo2core*.dll` 顶替（`iostore.py` 解压压缩容器时也会自动发现
> Steam 库与 pyuepak 自带的 Oodle）。本项目的补丁 pak 与 IoStore 容器均为**不压缩存储**，
> 对 Oodle 版本不敏感；只有读取游戏原版压缩 pak/ucas 时才需要解压能力。

## 格式实现与验证（2026 阶段一重构）

各模块的自测均可单独运行（`python <模块>.py`），关键结论：

| 模块 | 实现内容 | 验证 |
| --- | --- | --- |
| `textkey.py` | `key_hash = CityHash64(UTF-16LE)` 低32+高32×23 折叠；`source_hash = CRC32(UTF-32LE)`；`source_id = SHA1(UTF-8)[:16]` | 6727/6727 样本命中；`validate_hash_formulas.py` 对 5496 条 records 全量复核 0 bad |
| `locres.py` | v3 布局：magic/version/池偏移回填、命名空间分组、字符串池 `[FStr][ref_count]` | 原版 146,633 B 与金标准 379,964 B parse→build 往返**逐字节一致**；ref_count 守恒 |
| `uasset_text.py` | serial 区 3332 条解析；文本替换 + `0xD0` serial_size 回写；ko==source 原字节保留 | patch(ko=source) **逐字节==原版**；假译文回读全中；与补丁成品 key 序/大小一致 |
| `pakbuild.py` | pyuepak 封装的 V11 patch pak 打包 | 与金标准 pak **380,781 B 逐字节一致** |
| `iostore_build.py` | utoc/ucas/伴生 pak 写入端（未压缩 method 0） | 金标准三件套**逐字节复现**；round-trip 读回一致 |

**成品比对**：从游戏输入独立重建的 6 个二进制产物（locres pak、uasset pak/utoc/ucas、
补丁 raw、字体 pak）与已发布 v2 成品**全部逐字节一致**；发布包其余文本文件除
有意更新的文案外也逐字节一致（LICENSE/NOTICE/OFL 与成品仅 CRLF/LF 换行风格差异，内容一致）。

## 已知限制

- 贴图上的文字（路牌、海报）不会变，需要单独的贴图补丁。
- `Engine.locres`（引擎层文案）未汉化，出现频率低。
- 语音仍为英文；本仓库不含音频替换。
- 游戏更新后 locres 条目与 uasset 偏移会变化，需要按新版本重新采集并重建。

## 致谢与许可

- 文件格式事实与哈希公式线索参考开源项目 **[refracta/itr2-ko](https://github.com/refracta/itr2-ko)**：
  `source_hash = CRC32(UTF-32LE)`、`key_hash` 的 CityHash64 折叠方式、locres 头部字段语义，
  以及“locres 与 uasset 必须同时打”的结论均来自该项目的公开说明。本仓库的解析/构建代码为
  **独立实现**（经游戏原文件与成品逐字节验证），未复制、未加载其任何代码与数据文件。
  该项目未声明任何许可证；依赖范围与法律说明见 [`THIRD-PARTY.md`](THIRD-PARTY.md)。
- 字体取自游戏自身资源（`NotoSansSC-Regular/Bold`），其上游为以 SIL Open Font License 1.1
  授权的 Noto Sans SC；分发字体包时随附许可证全文（见 `licenses/OFL-NotoSansSC.txt`）。
- Oodle 运行库为 Epic Games / RAD Game Tools 专有，本仓库与发布产物均不含其代码
  （自建容器采用未压缩存储，解压由游戏程序自身完成）。
- 游戏资源版权归 CM Games 所有，本项目为爱好者制作的非官方补丁，不得用于商业用途。
- 本仓库不包含游戏本体资源与任何大体积二进制产物（见 `.gitignore`）。

### 许可证

本仓库的脚本与译文以 **Apache License 2.0** 授权，许可证全文见 [`LICENSE`](LICENSE)，
第三方内容清单与致谢见 [`NOTICE`](NOTICE) 与 [`THIRD-PARTY.md`](THIRD-PARTY.md)。

该授权不涵盖：游戏本体资源及其派生数据（版权归 CM Games）、Noto Sans SC 字体
（以 SIL OFL 1.1 授权）、Oodle 运行库（专有）。

## 工作区依赖提醒（重要：仓库不能单独构建）

**仅凭本仓库内容无法构建完整安装包。** 构建必需的游戏原文件（`../game_inputs/`，约 52 MB）
因版权原因**有意不入库、不分发**——这是设计决定，不是遗漏：

| 原因 | 说明 |
| --- | --- |
| 版权红线 | 补丁产物（`Game.locres`、`EnglishSource.uasset`、字体 pak）全部**派生自游戏原文件**，游戏资源版权归 CM Games。原文件与其派生数据均不得入库或随仓库分发（见 `THIRD-PARTY.md` 第 3 节） |

除该采集包外，构建所需的**全部创作性内容**均在仓库内（脚本、3772 条译文、容器模板、
许可证与文档）。补入 `game_inputs/` 后即可**逐字节重建**完整安装包（已实测：重建产物与
随仓库保存的发布包 10/10 项逐字节一致）。

| 目录 / 文件 | 来源 | 缺失时如何处理 |
| --- | --- | --- |
| `../game_inputs/`（pakchunk0-Windows.pak、EnglishSource.uasset、NotoSansSC-*.uasset、GAME_Game.locres 等） | 游戏机运行 `collect_game_inputs.py` 采集交付 | 重新采集（需一台装有游戏的机器） |
| `zh_sources.json` | 翻译数据（入库） | —— |
| `fonts/`、`dist_zh/`、`release_zh/`、`records_with_zh.json` | 由脚本生成 | 依次运行 `prepare_records.py` → `build_zh.py` / `build_font_pak.py` → `make_release.py` |

`ref_ko/`（上游参考仓库）**已不再需要**——构建链的全部格式实现均为独立实现
（历史：早期构建脚本曾通过 `importlib` 加载其代码，2026 阶段一重构已移除）。
