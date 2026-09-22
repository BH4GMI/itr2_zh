# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""ITR2 简体中文补丁构建脚本（基于 refracta/itr2-ko 的构建逻辑适配）

产物（dist_zh/）：
  pakchunk99-ZH_Locres_P.pak          —— 覆盖 IntoTheRadius2/Content/Localization/Game/en/Game.locres（+ Game.locmeta）
  pakchunk99-ZH_UAsset-Windows.{pak,utoc,ucas} —— EnglishSource.uasset 的 IoStore override（mount ../../../Projectc/...）

参考与致谢：refracta/itr2-ko（MIT 风格开源项目，提供 IoStore 容器模板与字节级补丁逻辑）。
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(r"D:\SteamLibrary\steamapps\common\itr2_zh")
GAME = Path(r"D:\SteamLibrary\steamapps\common\IntoTheRadius2")
KO_SCRIPT = ROOT / "ref_ko" / "scripts" / "build" / "build_locres_patch.py"
DIST = ROOT / "dist_zh"

# 载入韩方构建模块，复用其经过验证的解析/打包/补丁函数
spec = importlib.util.spec_from_file_location("ko_build", KO_SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

m.patch_pyuepak_oodle_nullable_args()

m.DIST = DIST
m.RECORDS = ROOT / "records_with_zh.json"
m.BASE_PAK_CANDIDATES = [GAME / "IntoTheRadius2" / "Content" / "Paks" / "pakchunk0-Windows.pak"]
m.BASE_ENGLISHSOURCE_CANDIDATES = [ROOT / "iostore_out" / "EnglishSource.uasset"]
m.ENGLISHSOURCE_LOCRES_META_CANDIDATES = []          # 不需要：key_hash 用公式自行计算（已对 2164 条样本验证 100% 命中）
m.ENGLISHSOURCE_BASENAME = "pakchunk99-ZH_UAsset-Windows"
m.LOCRES_BASENAME = "pakchunk99-ZH_Locres_P.pak"

# 韩方手工补充的主菜单条目（这些字符串不在提取结果里），改为中文
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
m.EXTRA_ENGLISHSOURCE_LOCRES_ENTRIES = [
    {"key": k, "source": en, "ko": zh} for k, en, zh in EXTRA_ZH
]


def main():
    DIST.mkdir(parents=True, exist_ok=True)
    base_pak = m.first_existing(m.BASE_PAK_CANDIDATES)
    records = m.load_json(m.RECORDS)
    print("[i] base pak:", base_pak)
    print("[i] records:", len(records))

    base_locres = m.extract_pak_file(base_pak, m.GAME_LOCRES_PATH)
    locmeta = m.extract_pak_file(base_pak, m.GAME_LOCMETA_PATH)
    namespaces, base_entries = m.parse_locres(base_locres)
    print("[i] base locres: %d entries, namespaces=%s" % (len(base_entries), [n["namespace"] for n in namespaces]))

    locres_records = [r for r in records if r["container"] == "Game.locres"]
    uasset_records = [r for r in records if r["container"] == "EnglishSource.uasset"]
    print("[i] locres records=%d uasset records=%d" % (len(locres_records), len(uasset_records)))

    union = {}
    for r in locres_records:
        union[(r["namespace"], r["key"])] = {
            "namespace": r["namespace"],
            "key": r["key"],
            "key_hash": r["key_hash"],
            "source_hash": r["source_hash"],
            "ko": r.get("ko") or r["source"],
        }
    added = overridden = preserved = 0
    for r in uasset_records:
        k = ("EnglishSource", r["key"])
        if r["source"] == "Placeholder text":
            preserved += int(k in union)
            continue
        e = {
            "namespace": "EnglishSource",
            "key": r["key"],
            "key_hash": m.text_key_hash(r["key"]),
            "source_hash": m.source_hash(r["source"]),
            "ko": r.get("ko") or r["source"],
        }
        if k in union:
            overridden += 1
        else:
            added += 1
        union[k] = e
    for extra in m.EXTRA_ENGLISHSOURCE_LOCRES_ENTRIES:
        k = ("EnglishSource", extra["key"])
        if k in union:
            overridden += 1
        else:
            added += 1
        union[k] = {
            "namespace": "EnglishSource",
            "key": extra["key"],
            "key_hash": m.text_key_hash(extra["key"]),
            "source_hash": m.explicit_or_computed_source_hash(extra),
            "ko": extra["ko"],
        }

    entries = list(union.values())
    locres = m.build_locres(namespaces, entries)
    locres_path = DIST / "Game.zh-Hans.locres"
    locres_path.write_bytes(locres)

    # 自检：重新解析产出的 locres
    ns2, ent2 = m.parse_locres(locres)
    zh_count = sum(1 for e in ent2 if any("\u4e00" <= c <= "\u9fff" for c in e.get("localized", "")))
    print("[i] rebuilt locres: entries=%d (中文条目 %d)" % (len(ent2), zh_count))
    assert len(ent2) == len(entries)

    pak_path = m.make_pak(m.LOCRES_BASENAME, locres, locmeta)
    print("[OK] locres pak:", pak_path, pak_path.stat().st_size)

    patched_uasset, uasset_summary = m.patch_englishsource_uasset(records)
    (DIST / "EnglishSource.zh-Hans.uasset.raw").write_bytes(patched_uasset)
    es_files, es_summary = m.build_englishsource_iostore(patched_uasset)
    print("[OK] EnglishSource IoStore:", ", ".join(p.name for p in es_files))

    summary = {
        "base_pak": str(base_pak),
        "locres_records": len(locres_records),
        "uasset_records": len(uasset_records),
        "locres_entries_built": len(entries),
        "uasset_only_added": added,
        "collision_overridden": overridden,
        "placeholder_preserved": preserved,
        "chinese_entries": zh_count,
        "uasset": uasset_summary,
        "iostore": es_summary,
    }
    (DIST / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("uasset", "iostore")}, ensure_ascii=False, indent=2))
    print("uasset entries:", uasset_summary["uasset_entries"], "changed:", uasset_summary["translated_or_changed_entries"])
    print("files:", [p.name for p in sorted(DIST.iterdir())])


if __name__ == "__main__":
    main()
