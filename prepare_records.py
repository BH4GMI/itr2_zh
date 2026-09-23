# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""生成 records_with_zh.json（去 ref_ko 化·阶段一）。

上游版本的输入是 ref_ko 的 records_with_ko.json / unique_sources_with_ko.json
（外部仓库的派生数据，未获许可不可分发）。本版本**全部输入来自仓库自有或
游戏自身**，零上游依赖::

    输入  game_inputs/GAME_Game.locres      原版 locres（2164 条真值）
          game_inputs/EnglishSource.uasset  原版 uasset（3332 条真值）
          zh_sources.json                   本仓库译文（source_id -> 中文）
    输出  records_with_zh.json              与 build_zh.py 的消费字段一一对应

真值来源与公式：
  - locres 记录的 namespace/key/key_hash/source_hash/localized_index
    直接取自原版 locres 解析（locres.py）；source 取池内英文
    （原版 en 容器中 localized == source，已对 2164 条 CRC32 全量验证）。
  - uasset 记录的 key/source/text_offset/end 取自原版 serial 区
    （uasset_text.py，3332 条全量验证）。
  - source_id = SHA1(UTF-8)[:16]（textkey.py，2393+3332 对全量验证）。

注意：本脚本不再需要 ref_ko/；locres 缺失时会尝试从
game_inputs/pakchunk0-Windows.pak 现场提取。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_INPUTS = os.path.join(HERE, "..", "game_inputs")
ZH_SOURCES = os.path.join(HERE, "zh_sources.json")
OUT = os.path.join(HERE, "records_with_zh.json")
LOCRES = os.path.join(GAME_INPUTS, "GAME_Game.locres")
UASSET = os.path.join(GAME_INPUTS, "EnglishSource.uasset")
BASE_PAK = os.path.join(GAME_INPUTS, "pakchunk0-Windows.pak")

LOCRES_LOGICAL = "IntoTheRadius2/Content/Localization/Game/en/Game.locres"

EXPECT_LOCRES = 2164
EXPECT_UASSET = 3332
EXPECT_PLACEHOLDER = 183


def load_zh():
    with open(ZH_SOURCES, encoding="utf-8") as f:
        return json.load(f)


def ensure_locres(zh):
    """locres 缺失时从 pak 提取（只要 pakchunk0 在就有完整输入）。"""
    if os.path.exists(LOCRES):
        return
    if not os.path.exists(BASE_PAK):
        raise SystemExit(
            "缺少 %s\n请先运行 collect_game_inputs.py 收集游戏输入"
            "（需要 game_inputs/GAME_Game.locres 或 pakchunk0-Windows.pak）" % LOCRES)
    sys.path.insert(0, HERE)
    from pakbuild import read_pak
    files = read_pak(BASE_PAK)
    if LOCRES_LOGICAL not in files:
        raise SystemExit("pak 中未找到 %s" % LOCRES_LOGICAL)
    with open(LOCRES, "wb") as f:
        f.write(files[LOCRES_LOGICAL])
    print("已从 pak 提取 Game.locres -> %s" % LOCRES)


def main():
    import locres as L
    import uasset_text as U
    from textkey import source_id

    zh = load_zh()
    ensure_locres(zh)

    # ---- locres 侧 2164 条 ----
    info = L.parse_locres(open(LOCRES, "rb").read())
    records = []
    for ns in info["namespaces"]:
        for e in ns["entries"]:
            source = info["pool"][e["localized_index"]]["str"]
            records.append({
                "record_id": "locres|%s|%s|%d" % (ns["namespace"] or "<default>",
                                                  e["key"], e["source_hash"]),
                "container": "Game.locres",
                "record_type": "locres",
                "namespace": ns["namespace"],
                "key": e["key"],
                "key_hash": e["key_hash"],
                "source_hash": e["source_hash"],
                "localized_index": e["localized_index"],
                "source": source,
                "source_id": source_id(source),
            })

    # ---- uasset 侧 3332 条 ----
    from textkey import source_hash
    uinfo = U.parse_serial(open(UASSET, "rb").read())
    for e in uinfo["entries"]:
        records.append({
            "record_id": "uasset|%s|%s|%s" % (uinfo["namespace"], e["key"],
                                              source_id(e["source"])),
            "container": "EnglishSource.uasset",
            "record_type": "uasset",
            "namespace": uinfo["namespace"],
            "key": e["key"],
            "source_hash": source_hash(e["source"]),
            "source": e["source"],
            "source_id": source_id(e["source"]),
            "text_offset": e["text_offset"],
            "end": e["end"],
        })

    # ---- join 译文 ----
    untranslated = 0
    for r in records:
        tr = zh.get(r["source_id"])
        if str(tr or "").strip():
            r["ko"] = tr
        else:
            r["ko"] = r["source"]
            untranslated += 1

    # ---- 自校验 ----
    n_locres = sum(1 for r in records if r["container"] == "Game.locres")
    n_uasset = len(records) - n_locres
    n_ph = sum(1 for r in records if r["source"] == "Placeholder text")
    ok = True

    def check(label, got, want):
        nonlocal ok
        same = got == want
        ok = ok and same
        print("  %-38s %s (got=%r want=%r)" % (label, "PASS" if same else "FAIL", got, want))

    print("records 自校验:")
    check("locres 记录数", n_locres, EXPECT_LOCRES)
    check("uasset 记录数", n_uasset, EXPECT_UASSET)
    check("Placeholder 条目数", n_ph, EXPECT_PLACEHOLDER)
    check("总记录数", len(records), EXPECT_LOCRES + EXPECT_UASSET)
    check("未译条数（应为 0）", untranslated, 0)
    check("每条都有 key/source/source_id/ko",
          all(r.get("key") is not None and r.get("source") is not None
              and r.get("source_id") and r.get("ko") is not None for r in records), True)
    check("每条都有 source_hash（含 uasset 侧）",
          all(isinstance(r.get("source_hash"), int) for r in records), True)
    # 抽样：与 docs/ko_analysis.md 的真值对照
    s = next((r for r in records if r["key"] == "F788FDF944AEB13854066B8FEE70441B"), None)
    check("样本 F788 的 source_id", s and s["source_id"], "a48441d354606e91")
    check("样本 F788 的 source_hash", s and s["source_hash"], 4160172254)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)
    print("写出 %s (%d 条, %.1f KB)  校验: %s"
          % (OUT, len(records), os.path.getsize(OUT) / 1024,
             "PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
