# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""ITR2 简体中文补丁构建脚本（去 ref_ko 化·阶段一，零上游依赖）。

产物（dist_zh/）：
  pakchunk99-ZH_Locres_P.pak                —— 覆盖 Game.en/Game.locres（+ Game.locmeta）
  pakchunk99-ZH_UAsset-Windows.{pak,utoc,ucas} —— EnglishSource.uasset 的 IoStore override
  Game.zh-Hans.locres                       —— 中间产物（结构校验用）
  EnglishSource.zh-Hans.uasset.raw          —— 中间产物（补丁后 uasset）
  build_summary.json                        —— 构建统计

构建链全部使用本仓库自研模块：
  locres.py        —— locres 解析 / 装配（往返与金标准逐字节验证）
  textkey.py       —— key_hash(CityHash64×23 折叠) / source_hash(CRC32 UTF-32LE) / source_id(SHA1[:16])
  pakbuild.py      —— pyuepak 封装（重新打包与金标准 380,781 字节逐字节一致）
  uasset_text.py   —— serial 区解析 + 文本补丁（b1/b2/c 三重验证）
  iostore_build.py —— IoStore 三件套构建（模板切自金标准产物，逐字节复现验证）
  prepare_records.py —— records_with_zh.json 生成（5496 条自校验）

输入（collect_game_inputs.py 在游戏机交付到 ../game_inputs/）：
  pakchunk0-Windows.pak（取 Game.locres + Game.locmeta）、EnglishSource.uasset
  加本仓库 zh_sources.json（译文，经 prepare_records.py 汇入 records）。

产物结构目标（与金标准补丁一致）：
  locres_entries_built=4611（ns '':1231 + 'EnglishSource':3380）

参考与致谢：refracta/itr2-ko（其公开仓库提供了 locres 头部字段语义与 key_hash
×23 折叠公式的线索；本仓库实现与验证数据均独立——见 THIRD-PARTY.md）。
"""
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME_INPUTS = HERE.parent / "game_inputs"
DIST = HERE / "dist_zh"
RECORDS = HERE / "records_with_zh.json"
BASE_PAK = GAME_INPUTS / "pakchunk0-Windows.pak"
UASSET = GAME_INPUTS / "EnglishSource.uasset"

GAME_LOCRES_PATH = "IntoTheRadius2/Content/Localization/Game/en/Game.locres"
GAME_LOCMETA_PATH = "IntoTheRadius2/Content/Localization/Game/Game.locmeta"
BASENAME_LOCRES = "pakchunk99-ZH_Locres_P.pak"
BASENAME_UASSET = "pakchunk99-ZH_UAsset-Windows"
IOMOUNT = "../../../Projectc/Content/ITR2/Configurations/Localization/"

# 手工补充的主菜单条目（这些字符串不在提取结果里），改为中文
EXTRA_ZH = [
    ("41C7E447418490718B2CE78EFFFAE0D7", "Start new game", "开始新游戏"),
    ("CC36858D44605D96DB012A8B5292C316", "Starting a new game will delete all Single-player saves. Are you sure?", "开始新游戏将删除所有单人存档。确定吗？"),
    ("A837DF4B4E68A3C81400B5BCE7986796", "Yes", "是"),
    ("1368F6664F6161BA319FDDABB666CEB8", "No", "否"),
    ("F3F66CB94CDD9B0AE45F8B92100FAB71", "Measurement", "计量单位"),
    ("48FEA94B43498BA0086D6BACDDABA292", "Metric", "公制"),
    ("0185BCCD483EDA65844454AC76A01419", "Imperial", "英制"),
    ("D20537AC41AB1CF99AD596893398A711", "Off", "关"),
    ("0D9E1FDA4C51A50B250D1EA0CA569138", "On", "开"),
    ("6F632A8D4F0E819C11B70D94DD088076", "Critical Damage Chance", "暴击伤害几率"),
    ("1651B78043E93A1063C7DB928F90A865", "Critical Damage Multiplier", "暴击伤害倍率"),
    ("44CB5BB84F04285E8C0A59B71B273E2B", "Please insert ammo box first", "请先放入弹药盒"),
    ("4712CCB64C555D9096DE558EC26C48F7", "Please insert magazine first", "请先放入弹匣"),
    ("7B578A434CAA59FA50AEC08E7995C7CE", "Magazine and ammo box are incompatible", "弹匣与弹药盒不兼容"),
    ("718532FA495485ACC1ACE2855CC37143", "Magazine is full - cannot continue loading", "弹匣已满，无法继续装填"),
    ("F797E76841F101620F0302AAF412B516", "Ammo box is empty - cannot continue loading", "弹药盒已空，无法继续装填"),
    ("373E49414B52687EDB2995B0C40C6BD0", "This magazine cannot be loaded from the ammo loader", "该弹匣无法通过装弹器装填"),
    ("4B6B21EE4658F6268DD5B8931E2ED491", "There is no unresolved ammo in the magazine", "弹匣中没有可处理的弹药"),
    ("013AFD64401A537A996D909322FF143D", "Not found", "未找到"),
    ("FF9B5C294C75DE489E67CF8075CF7AAD", "Finish", "完成"),
    ("F5C1F8024F9CA678C4B982BE3C26E5E5", "Start", "开始"),
    ("3A339A424B94B1582586EF8A5A0FC385", "In Progress", "进行中"),
    ("50776DA34EF627D87E0922985297741B", "UNPSC Explorer", "UNPSC 探索者"),
    ("EF1AE93746A87E656DB4D8B5D2344814", "Pass", "通过"),
    ("833004CA4C1E9D10B05FBB99B7695547", "Pass", "通过"),
    ("750BFF584257DFD856B1519B35534409", "Skip", "跳过"),
    ("47E20FEC42A3BAF0A69BEF9229FD5003", "Skip", "跳过"),
    ("6912D366473F5161D4022D9FD8F75A5F",
     "<b>Carry Load</b> Indicates how much weight the Explorer is currently carrying relative to their total capacity. <L2><b>Armor Protection Level</b>",
     "<b>负重</b>表示探索者当前携带重量占其总负重上限的比例。<L2><b>护甲防护等级</b>"),
    ("A3B1685C43EEA7B80D5820889DEC17D6", "Ammo Loader", "装弹器"),
    ("17D131D34C68A524573B94AF56DE32A7", " ", " "),
    ("EE4C460F434AEA4411EA4A9F976D6400", "Waiting for scan to complete.", "正在等待扫描完成。"),
    ("2BD7FF5A42FEAB6E3CB65DA996BD9B70", "Access mission point", "进入任务点"),
    ("47BA2E794AD4060FE50CDA967EF9E536", "I'm broken", "我坏掉了"),
    ("51D2CAE94DC1F33D24708E946420B206", "I'm broken", "我坏掉了"),
    ("8A0AC0D840310FCA66C8BDB4242F01C0", "I'm broken", "我坏掉了"),
    ("703A893C42F84072BBCB388CED98B70F", "Hey, dude!", "嘿，老兄！"),
]

sys.path.insert(0, str(HERE))
import iostore_build
import locres as L
import pakbuild
import textkey
import uasset_text


def main():
    for p in (BASE_PAK, UASSET, RECORDS):
        if not p.exists():
            raise SystemExit("缺少构建输入: %s\n"
                             "（先在游戏机运行 collect_game_inputs.py，再运行 prepare_records.py）" % p)
    DIST.mkdir(exist_ok=True)
    records = json.loads(RECORDS.read_text(encoding="utf-8"))
    print("[i] records:", len(records))

    # ---- 原版 locres / locmeta（从游戏 pak 提取）----
    files = pakbuild.read_pak(str(BASE_PAK))
    if GAME_LOCRES_PATH not in files:
        raise SystemExit("pak 中未找到 %s" % GAME_LOCRES_PATH)
    base_locres = files[GAME_LOCRES_PATH]
    locmeta = files[GAME_LOCMETA_PATH]
    base = L.parse_locres(base_locres)
    print("[i] base locres: %d entries, namespaces=%s" % (
        sum(ns["count"] for ns in base["namespaces"]),
        [str(ns["namespace"]) for ns in base["namespaces"]]))

    locres_records = [r for r in records if r["container"] == "Game.locres"]
    uasset_records = [r for r in records if r["container"] == "EnglishSource.uasset"]
    print("[i] locres records=%d uasset records=%d" % (len(locres_records), len(uasset_records)))

    # ---- union：locres 记录 -> uasset 记录（Placeholder 跳过/冲突覆盖）-> EXTRA ----
    union = {}
    for r in locres_records:
        union[(r["namespace"], r["key"])] = {
            "namespace": r["namespace"], "key": r["key"],
            "key_hash": r["key_hash"], "source_hash": r["source_hash"],
            "ko": r.get("ko") or r["source"],
        }
    added = overridden = preserved = 0
    for r in uasset_records:
        k = ("EnglishSource", r["key"])
        if r["source"] == "Placeholder text":
            preserved += int(k in union)
            continue
        if k in union:
            overridden += 1
        else:
            added += 1
        union[k] = {
            "namespace": "EnglishSource", "key": r["key"],
            "key_hash": textkey.text_key_hash(r["key"]),
            "source_hash": textkey.source_hash(r["source"]),
            "ko": r.get("ko") or r["source"],
        }
    for key, en, zh in EXTRA_ZH:
        k = ("EnglishSource", key)
        if k in union:
            overridden += 1
        else:
            added += 1
        union[k] = {
            "namespace": "EnglishSource", "key": key,
            "key_hash": textkey.text_key_hash(key),
            "source_hash": textkey.source_hash(en),
            "ko": zh,
        }

    entries = list(union.values())
    locres_bytes = L.assemble(base, entries)
    (DIST / "Game.zh-Hans.locres").write_bytes(locres_bytes)
    print("[i] assembled: %d entries -> %d bytes" % (len(entries), len(locres_bytes)))

    # 自检：重新解析产出的 locres
    h2 = L.parse_locres(locres_bytes)
    ent2 = [e for ns in h2["namespaces"] for e in ns["entries"]]
    ns_counts = {str(ns["namespace"]): len(ns["entries"]) for ns in h2["namespaces"]}
    zh_count = sum(1 for e in ent2
                   if any("\u4e00" <= c <= "\u9fff"
                          for c in h2["pool"][e["localized_index"]]["str"]))
    print("[i] rebuilt: entries=%d ns=%s 中文条目=%d" % (len(ent2), ns_counts, zh_count))
    if len(ent2) != len(entries):
        raise RuntimeError("locres 自检失败: 解析 %d != 装配 %d" % (len(ent2), len(entries)))

    # ---- locres patch pak ----
    pak_path = pakbuild.make_pak({
        GAME_LOCRES_PATH: locres_bytes,
        GAME_LOCMETA_PATH: locmeta,
    }, str(DIST / BASENAME_LOCRES))
    print("[OK] locres pak:", pak_path, os.path.getsize(pak_path))

    # ---- EnglishSource.uasset 补丁 ----
    patched_uasset, uasset_summary = uasset_text.patch(UASSET.read_bytes(), records)
    (DIST / "EnglishSource.zh-Hans.uasset.raw").write_bytes(patched_uasset)
    print("[OK] uasset patch: %d -> %d bytes, changed=%d"
          % (uasset_summary["original_size"], uasset_summary["patched_size"],
             uasset_summary["changed"]))

    # ---- IoStore 三件套 ----
    built = iostore_build.build_iostore(patched_uasset, iostore_build.load_templates())
    es_files = []
    for ext in ("utoc", "ucas", "pak"):
        p = DIST / ("%s.%s" % (BASENAME_UASSET, ext))
        p.write_bytes(built[ext])
        es_files.append(p)
    print("[OK] EnglishSource IoStore:", ", ".join(p.name for p in es_files))

    summary = {
        "base_pak": str(BASE_PAK),
        "locres_records": len(locres_records),
        "uasset_records": len(uasset_records),
        "locres_entries_built": len(entries),
        "uasset_only_added": added,
        "collision_overridden": overridden,
        "placeholder_preserved": preserved,
        "chinese_entries": zh_count,
        "uasset": uasset_summary,
        "iostore": {
            "basename": BASENAME_UASSET,
            "mount": IOMOUNT,
            "entry0_length": len(patched_uasset),
            "block_count": -(-len(patched_uasset) // iostore_build.BLOCK_SIZE) + 1,
            "files": {p.name: {"size": p.stat().st_size,
                               "sha1": hashlib.sha1(p.read_bytes()).hexdigest()}
                      for p in es_files},
        },
    }
    (DIST / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("uasset", "iostore")},
                     ensure_ascii=False, indent=2))
    print("files:", sorted(p.name for p in DIST.iterdir()))


if __name__ == "__main__":
    main()
