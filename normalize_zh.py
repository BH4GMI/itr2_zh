# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""术语归一：把各分片翻译中分歧的译法拉齐，并回写 zh_sources.json / records_with_zh.json。"""
import json, os, collections

ROOT = r"D:\SteamLibrary\steamapps\common\itr2_zh"
ZH = os.path.join(ROOT, "zh_sources.json")

# 顺序敏感：长词/特定词在前
REPL = [
    ("畸变区", "扭曲区"),
    ("畸变", "扭曲"),
    ("变异", "异变"),
    ("异化", "异变"),
    ("异变者", "异变体"),
    ("徽章", "臂章"),
    ("区块", "区域"),
    ("禁区", "半径"),
    ("弹夹", "弹匣"),
    ("藏身处", "藏匿点"),
    ("装甲板", "护甲板"),
    ("庇护所", "避难所"),
    ("弹药箱", "弹药盒"),
]

# 逐条定点修正：{英文原文: 正确中文}
FIX_BY_SOURCE = {
    "RadiusInputConfig": "RadiusInputConfig",
    "Host the Radius": "主持半径",
}

with open(ZH, encoding="utf-8") as f:
    d = json.load(f)
recs = json.load(open(os.path.join(ROOT, "records_with_zh.json"), encoding="utf-8"))
sid2src = {r["source_id"]: r["source"] for r in recs}

counts = collections.Counter()
changed = 0
for sid, txt in list(d.items()):
    new = txt
    for a, b in REPL:
        if a in new:
            counts[(a, b)] += new.count(a)
            new = new.replace(a, b)
    src = sid2src.get(sid)
    if src in FIX_BY_SOURCE and new != FIX_BY_SOURCE[src]:
        counts[("<fix>", src)] += 1
        new = FIX_BY_SOURCE[src]
    if new != txt:
        d[sid] = new
        changed += 1

with open(ZH, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=0)

# 重建位置记录
for r in recs:
    z = d.get(r["source_id"])
    if z:
        r["ko"] = z
with open(os.path.join(ROOT, "records_with_zh.json"), "w", encoding="utf-8") as f:
    json.dump(recs, f, ensure_ascii=False)

print("已改写条目:", changed, "/", len(d))
for (a, b), n in counts.most_common():
    print("   %-8s -> %-8s %d 处" % (a, b, n))

# 复查残余分歧
resid = collections.Counter()
for v in d.values():
    for t in ("变异", "异化", "畸变", "徽章", "区块", "禁区", "弹夹", "藏身处", "装甲板", "庇护所", "弹药箱"):
        resid[t] += v.count(t)
print("残余:", {k: v for k, v in resid.items() if v})
