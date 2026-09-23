# 第三方内容与许可证清单（THIRD-PARTY）

本文件说明本仓库**依据、依赖或间接使用**的上游内容及其许可状态。
结论先行：参考项目 `refracta/itr2-ko` **没有声明任何许可证**，因此本仓库已将其依赖降为零：
不复制其代码、不加载其代码、不分发其数据文件，仅在实现文件格式时**参考其公开说明中的
格式事实**（字节布局与哈希公式），并以游戏原文件与发布成品逐字节验证全部实现。

## 1. 上游参考项目

| 上游 | 本仓库如何使用 | 许可证 | 风险 |
| --- | --- | --- | --- |
| [refracta/itr2-ko](https://github.com/refracta/itr2-ko) | 仅**阅读**其公开源码/说明，确认格式事实：`source_hash = CRC32(UTF-32LE)`、`key_hash` 的 CityHash64×23 折叠、locres 头部字段语义（版本/池偏移/条目布局）、“locres 与 uasset 必须同时打”的结论。**未复制、未加载**其任何代码与数据文件（历史：2026 阶段一重构前，构建脚本曾 `importlib` 加载其代码） | **无**（仓库内没有 LICENSE / COPYING / NOTICE，也没有 SPDX 头或版权声明；GitHub 页面亦未标注任何许可证）→ 依著作权法默认**保留所有权利** | 低（仅参考了不受著作权保护的格式事实；实现独立并经逐字节验证）。公开发布本补丁仍建议知会作者并保留本致谢 |
| [Nexus Mods 258 简中 / 304 繁中 / 145、211 日文 / 144、246 俄文](https://www.nexusmods.com/intotheradius2) | **仅阅读其公开说明页**，用于了解安装方式、字体处理与覆盖范围；未下载、未使用其任何文件或译文 | 各自作者所有（Nexus 页面条款） | 低（未使用其内容） |
| vrzwk.net / vrmoqu.com / vrmoo.top 中文汉化包 | 仅参考公开页面描述（包内文件名、字体替换做法、术语） | 未声明，且需积分/网盘获取 | 低（未获取其内容） |
| [ITR-MOD](https://github.com/orgs/ITR-MOD/repositories)（ITR2SDK、UE4SS-ITR、Tools 等） | 仅浏览目录结构作为思路参考，未使用其代码或数据 | 各仓库自定（未逐一采用） | 低 |

### 关于「格式常量」的说明

IoStore 容器头 / chunk id / 容器记录等字节模板，本仓库**不引用任何上游脚本里的常量**：
`iostore_build.py` 的模板直接**切片自已发布成品**（`pakchunk99-ZH_UAsset-Windows.{utoc,ucas,pak}`
三件套，本项目自己发布的 v2 产物），并回填字段重建。这些是引擎二进制格式的
**事实性数据**（不受著作权保护），且已逐字节复现验证。

## 2. Python 依赖

| 包 | 用途 | 许可证 |
| --- | --- | --- |
| [pyuepak](https://pypi.org/project/pyuepak/) 0.2.8 | 读写 `.pak`（V11，构建补丁包） | MIT License |
| [cityhash](https://pypi.org/project/cityhash/) 0.4.10 | Unreal `FTextKey` 的 CityHash64 折叠 | MIT |
| [cryptography](https://pypi.org/project/cryptography/) 49.0.0 | 被 pyuepak 间接依赖（AES） | Apache-2.0 OR BSD-3-Clause |

以上均为宽松许可，可自由使用与再分发（保留版权声明即可）。

## 3. 运行库与美术资源

| 内容 | 说明 | 许可 / 风险 |
| --- | --- | --- |
| Oodle 运行库（`oo2core_*.dll`） | 仅在本机解压游戏 pak/ucas 时调用（`iostore.py` 自动发现 Steam 库与 pyuepak 自带的 DLL）。**本仓库与发布产物均不含 Oodle 代码**：自建 IoStore 容器使用 `method 0`（未压缩存储），解压由游戏自身完成 | Epic Games / RAD 专有，禁止再分发；本地调用不构成分发 |
| Noto Sans SC 字体 | 构建字体包时从**游戏自身的资源**（`NotoSansSC-Regular/Bold.uasset`）中裁出并写回 | 上游字体为 SIL Open Font License 1.1（Google Noto）。OFL 要求分发时附带许可证全文，且不得单独售卖字体 → **发布字体包时应随附 OFL 文本** |
| 游戏本体资源（`.locres` / `.uasset` / `.ttf` / `.pak`） | 补丁的输入（由 `collect_game_inputs.py` 一次性采集到 `game_inputs/`）；发布产物包含由这些资源派生的数据（locres、uasset、字体） | 版权归 **CM Games**；属粉丝衍生补丁，不得用于商业分发 |
| 游戏文本译文 | 本仓库 `zh_sources.json` 等的简体中文译文 | 本仓库以 Apache-2.0 授权（见第 4 节） |

## 4. 本仓库自身的许可证

**Apache License 2.0**（许可证全文见 [`LICENSE`](LICENSE)，第三方清单与修改说明见 [`NOTICE`](NOTICE)）。

适用范围：

- **适用**：本仓库的构建脚本、文档，以及 `zh_sources.json` 等简体中文译文数据。
- **不适用**：游戏本体资源及其派生数据（版权归 CM Games）；Noto Sans SC 字体
  （以 SIL Open Font License 1.1 授权，许可证全文见 `licenses/OFL-NotoSansSC.txt`）；
  Oodle 运行库（Epic Games / RAD Game Tools 专有）。

依 Apache-2.0 第 4 条，分发本产品或其衍生作品时须：

1. 随附 `LICENSE` 全文；
2. 保留 `NOTICE` 中的署名与致谢内容；
3. 标明对原始内容的修改（本项目所作的修改已在 `NOTICE` 第一节列明）。

后续事项：若上游作者就 `refracta/itr2-ko` 给出授权答复，应记录于本文件。
（历史结论已达成：将上游依赖降为零——容器常量已改为成品切片，位置数据已改为
从游戏原文件自提取，构建链不再加载上游代码。）
