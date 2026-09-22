# 第三方内容与许可证清单（THIRD-PARTY）

本文件说明本仓库**依据、依赖或间接使用**的上游内容及其许可状态。
结论先行：**最关键的参考项目 `refracta/itr2-ko` 没有声明任何许可证**，因此本仓库只把它当作
「构建期可选依赖」，不复制其代码到本仓库，也不把它随本仓库分发。

## 1. 上游参考项目

| 上游 | 本仓库如何使用 | 许可证 | 风险 |
| --- | --- | --- | --- |
| [refracta/itr2-ko](https://github.com/refracta/itr2-ko) | `build_zh.py` 在构建时 `import` 其 `build_locres_patch.py`，复用其中的 IoStore 容器字节模板、哈希算法实现、`EnglishSource` 位置数据（`translations/*.json`） | **无**（仓库内没有 LICENSE / COPYING / NOTICE，也没有 SPDX 头或版权声明；GitHub 页面亦未标注任何许可证）→ 依著作权法默认**保留所有权利** | ⚠️ 高。公开发布本补丁需先取得作者许可，或改成独立实现 |
| [Nexus Mods 258 简中 / 304 繁中 / 145、211 日文 / 144、246 俄文](https://www.nexusmods.com/intotheradius2) | **仅阅读其公开说明页**，用于了解安装方式、字体处理与覆盖范围；未下载、未使用其任何文件或译文 | 各自作者所有（Nexus 页面条款） | 低（未使用其内容） |
| vrzwk.net / vrmoqu.com / vrmoo.top 中文汉化包 | 仅参考公开页面描述（包内文件名、字体替换做法、术语） | 未声明，且需积分/网盘获取 | 低（未获取其内容） |
| [ITR-MOD](https://github.com/orgs/ITR-MOD/repositories)（ITR2SDK、UE4SS-ITR、Tools 等） | 仅浏览目录结构作为思路参考，未使用其代码或数据 | 各仓库自定（未逐一采用） | 低 |

### 关于「模板常量」的说明

`build_zh.py` 实际依赖的上游**表达性内容**只有三小块常量（合计约 240 字节）：

- `PROJECTC_IOSTORE_HEADER`（144 B）：一份 IoStore 容器头，仅需按块数/目录长度回填几个字段；
- `PROJECTC_CHUNK_IDS`（24 B）：Unreal 自身的 chunk id 编码（包名哈希 + 类型字节）；
- `PROJECTC_ENTRY1_PAYLOAD`（72 B）：`nCoI` 魔数的容器头记录，字段为引擎格式规定的容器 id / chunk id / 类型。

这些是**引擎二进制格式的事实性数据**（不受著作权保护），但承载它们的**脚本代码**属于上游作者的表达。
若要彻底规避风险，可按 Unreal IoStore 公开格式自行重建这三块常量（本仓库的 `iostore.py` 已能独立解析
.utoc/.ucas，具备自行生成的条件）。

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
| Oodle 运行库（`oo2core_*.dll`） | 仅在本机解压游戏 pak/ucas 时调用（当前用本机另一款游戏自带的 `oo2core_8_win64.dll` 顶替）。**本仓库与发布产物均不含 Oodle 代码**：自建 IoStore 容器使用 `method 0`（未压缩存储），解压由游戏自身完成 | Epic Games / RAD 专有，禁止再分发；本地调用不构成分发 |
| Noto Sans SC 字体 | 构建字体包时从**游戏自身的资源**（`NotoSansSC-Regular/Bold.uasset`）中裁出并写回 | 上游字体为 SIL Open Font License 1.1（Google Noto）。OFL 要求分发时附带许可证全文，且不得单独售卖字体 → **发布字体包时应随附 OFL 文本** |
| 游戏本体资源（`.locres` / `.uasset` / `.ttf` / `.pak`） | 补丁的输入；发布产物包含由这些资源派生的数据（locres、uasset、字体） | 版权归 **CM Games**；属粉丝衍生补丁，不得用于商业分发 |
| 游戏文本译文 | 本仓库 `zh_sources.json` 等的简体中文译文 | 本仓库以 Apache-2.0 授权（见第 4 节） |

## 4. 本仓库自身的许可证

**Apache License 2.0**（许可证全文见 [`LICENSE`](LICENSE)，第三方清单与修改说明见 [`NOTICE`](NOTICE)）。

适用范围：

- **适用**：本仓库的构建脚本、文档，以及 `zh_sources.json` 等简体中文译文数据。
- **不适用**：游戏本体资源及其派生数据（版权归 CM Games）；Noto Sans SC 字体
  （以 SIL Open Font License 1.1 授权，许可证全文见 `licenses/OFL-NotoSansSC.txt`）；
  Oodle 运行库（Epic Games / RAD Game Tools 专有）；构建所需的 `ref_ko/` 上游参考数据。

依 Apache-2.0 第 4 条，分发本产品或其衍生作品时须：

1. 随附 `LICENSE` 全文；
2. 保留 `NOTICE` 中的署名与致谢内容；
3. 标明对原始内容的修改（本项目所作的修改已在 `NOTICE` 第一节列明）。

后续事项：若上游作者就 `refracta/itr2-ko` 给出授权答复，应记录于本文件；
如需将上游依赖降为零，可按 Unreal IoStore 公开格式自行重建容器常量并自行提取位置数据。
