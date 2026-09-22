# Into the Radius 2 简体中文汉化（ITR2 Chinese Patch）

面向 Steam 版 **Into the Radius 2**（appid `2307350`）的简体中文补丁，通过
**patch pak（`*_P.pak` / IoStore override）** 覆盖游戏内的 `en` 语言资源实现汉化。
基准版本：`Hotfix Patch 1.1.2` / Steam buildid `24024260`。

- 覆盖度：**3772 / 3772 条唯一英文原文（100%）**
  - `Game.locres` 4611 条（原 2164 + `EnglishSource` 命名空间合并 2447）
  - `EnglishSource.uasset` 3332 条中 3019 条替换为中文（IoStore override）
  - 字体：用**游戏自带的 Noto Sans SC**（20,976 个汉字）替换 3 个离线字体 `.ufont`
- 产物：`release_zh/` 与 `ITR2_Chinese_v2.zip`（默认被 gitignore，用脚本生成）

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
├─ iostore.py                 自研 IoStore (.utoc/.ucas) 读取器
├─ build_zh.py                主构建：locres pak + EnglishSource IoStore 补丁
├─ build_font_pak.py          字体包：从游戏资源中裁出 Noto Sans SC 并覆盖 .ufont
├─ make_release.py            清理旧产物 + 组装 release_zh/ 与 zip
├─ prepare_records.py         ref_ko 原始数据 + zh_sources.json -> records_with_zh.json
├─ normalize_zh.py            术语归一（把各批次译法拉齐）
├─ verify_dist.py             产物独立校验（读回 pak / IoStore / locres / 字体）
├─ validate_hash_formulas.py  校验 source_hash / key_hash 公式
├─ make_zh_chunks.py          把待译原文切成翻译任务分片
├─ progress_vs_ko.py          覆盖率统计
├─ zh_sources.json            【翻译数据】source_id -> 简体中文（3772 条）
├─ translate/zh_full/         翻译分片原始产物（可追溯）
├─ docs/                      说明、术语表、分析与校验报告
└─ scratch/                   逆向过程中的临时探查脚本（不入库）
```

## 构建步骤

```bash
# 0) 依赖
pip install pyuepak cityhash            # IoStore/pak 读写
python setup_oodle.py                   # 给 pyuepak 准备 Oodle 运行库（见下方说明）
# 1) 取得外部参考数据（仅用于获得“英文原文清单 + 每条在 locres/uasset 中的位置”）
git clone https://github.com/refracta/itr2-ko ref_ko
# 2) 生成位置记录（把中文写进 records）
python prepare_records.py
# 3) 构建补丁产物 -> dist_zh/
python build_zh.py
python build_font_pak.py
# 4) 组装交付包 -> release_zh/ 与 ITR2_Chinese_v2.zip
python make_release.py
# 5) 校验
python verify_dist.py
```

游戏安装目录默认自动探测（`IntoTheRadius2.exe`），也可在脚本常量里写死。
安装/卸载：`release_zh/安装汉化.cmd`、`release_zh/卸载汉化.cmd`（或 `install.ps1 -Uninstall`）。

> `setup_oodle.py` 说明：pyuepak 在 import 时会联网下载 `oo2core_9_win64.dll`；本机实测该下载会拿到
> 大小/哈希都不符的文件（13 KB，期望约 1 MB），随后 `import pyuepak` 直接报错。该脚本改为从本机
> 已有游戏目录里找一个可用的 `oo2core*.dll`，校验（PE + `OodleLZ_Decompress` 可加载）后放进
> pyuepak 包目录；也可手动指定路径：`python setup_oodle.py "D:\...\oo2core_8_win64.dll"`。
> 本项目的补丁 pak 与 IoStore 容器均为**不压缩存储**，因此对 Oodle 版本不敏感（仅需能 import）。

## 已知限制

- 贴图上的文字（路牌、海报）不会变，需要单独的贴图补丁。
- `Engine.locres`（引擎层文案）未汉化，出现频率低。
- 语音仍为英文；本仓库不含音频替换。
- 游戏更新后 locres 条目与 uasset 偏移会变化，需要按新版本重新提取并重建。

## 致谢与许可

- 构建流程参考开源项目 **[refracta/itr2-ko](https://github.com/refracta/itr2-ko)**：
  IoStore 容器字节格式常量、`source_hash = CRC32(UTF-32LE)`、`key_hash = CityHash64(UTF-16LE)` 折叠算法，
  以及“locres 与 uasset 必须同时打”的结论均来自该项目；本项目按其数据格式生成中文版补丁。
  该项目未声明任何许可证，因此本仓库不复制其代码，仅在构建阶段作为可选依赖加载
  （`ref_ko/` 不入库、不分发）。依赖范围与法律说明见 [`THIRD-PARTY.md`](THIRD-PARTY.md)。
- 字体取自游戏自身资源（`NotoSansSC-Regular/Bold`），其上游为以 SIL Open Font License 1.1
  授权的 Noto Sans SC；分发字体包时随附许可证全文（见 `licenses/OFL-NotoSansSC.txt`）。
- Oodle 运行库为 Epic Games / RAD Game Tools 专有，本仓库与发布产物均不含其代码
  （自建容器采用未压缩存储，解压由游戏程序自身完成）。
- 游戏资源版权归 CM Games 所有，本项目为爱好者制作的非官方补丁，不得用于商业用途。
- 本仓库不包含游戏本体资源、`ref_ko` 原始数据与任何大体积二进制产物（见 `.gitignore`）。

### 许可证

本仓库的脚本与译文以 **Apache License 2.0** 授权，许可证全文见 [`LICENSE`](LICENSE)，
第三方内容清单与致谢见 [`NOTICE`](NOTICE) 与 [`THIRD-PARTY.md`](THIRD-PARTY.md)。

该授权不涵盖：游戏本体资源及其派生数据（版权归 CM Games）、Noto Sans SC 字体
（以 SIL OFL 1.1 授权）、Oodle 运行库（专有）。用于构建时所需的上游参考数据须自行获取，
不在本仓库授权范围内。

## 工作区依赖提醒

仓库**不能单独重建**：下列目录被 `.gitignore` 排除，内容可能变动，重建前请确认存在。

| 目录 / 文件 | 来源 | 缺失时如何处理 |
| --- | --- | --- |
| `ref_ko/` | `git clone https://github.com/refracta/itr2-ko ref_ko` | 构建必需 |
| `iostore_out/EnglishSource.uasset` | 用 `iostore.py` 从游戏 `pakchunk0-Windows.utoc/.ucas` 提取 | 重新提取（需已安装游戏） |
| 游戏安装目录 | Steam appid 2307350 | 脚本常量 `GAME` 默认 `D:\SteamLibrary\steamapps\common\IntoTheRadius2` |
| `fonts/`、`dist_zh/`、`release_zh/` | 由脚本生成 | 依次运行 `build_font_pak.py` → `build_zh.py` → `make_release.py` |
| `records_with_zh.json` | `prepare_records.py` 生成 | 重新运行该脚本 |
