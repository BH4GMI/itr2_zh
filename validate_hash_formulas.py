# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""验证 records_with_zh.json 的哈希公式（去 ref_ko 化·阶段一）。

公式定义在 textkey.py（key_hash 的 ×23 折叠、CRC32(UTF-32LE)、SHA1 前16hex），
本脚本对全部 5496 条 records 做逐条复核，并附 CRC32 直算对照。
上游等价物 validate 脚本 importlib 加载 ref_ko——已不再需要。
"""
import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from textkey import source_hash, text_key_hash

recs = json.load(open(os.path.join(HERE, "records_with_zh.json"), encoding="utf-8"))
locres = [r for r in recs if r["container"] == "Game.locres"]
uasset = [r for r in recs if r["container"] == "EnglishSource.uasset"]
print("locres records", len(locres), "uasset records", len(uasset))

# source_hash 公式：全部 5496 条
ok = bad = 0
for r in locres + uasset:
    if source_hash(r["source"]) == r["source_hash"]:
        ok += 1
    else:
        bad += 1
print("source_hash matches: %d ok / %d bad" % (ok, bad))

# key_hash 公式：locres 记录携带的真值 key_hash
ok = bad = 0
bad_ex = []
for r in locres:
    if text_key_hash(r["key"]) == r["key_hash"]:
        ok += 1
    else:
        bad += 1
        if len(bad_ex) < 5:
            bad_ex.append((r["key"], r["key_hash"], text_key_hash(r["key"])))
print("key_hash matches: %d ok / %d bad" % (ok, bad))
for e in bad_ex:
    print("   mismatch", e)

# zlib 直算对照（公式与 zlib.crc32 同源性抽查）
alt = zlib.crc32(locres[0]["source"].encode("utf-32le")) & 0xFFFFFFFF
print("crc32 utf-32le alt:", alt, "stored:", locres[0]["source_hash"],
      "module:", source_hash(locres[0]["source"]))

sys.exit(0 if (bad == 0) else 1)
