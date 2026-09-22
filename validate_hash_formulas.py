# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
import json, os, sys, zlib, shutil

ROOT = r"D:\SteamLibrary\steamapps\common\itr2_zh"
sys.path.insert(0, os.path.join(ROOT, "ref_ko", "scripts", "build"))

import importlib.util
spec = importlib.util.spec_from_file_location("ko_build", os.path.join(ROOT, "ref_ko", "scripts", "build", "build_locres_patch.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

recs = json.load(open(os.path.join(ROOT, "records_with_zh.json"), encoding="utf-8"))
locres = [r for r in recs if r["container"] == "Game.locres"]
uasset = [r for r in recs if r["container"] == "EnglishSource.uasset"]
print("locres records", len(locres), "uasset records", len(uasset))

# validate source_hash formula
ok = bad = 0
for r in locres + uasset:
    if m.source_hash(r["source"]) == r["source_hash"]:
        ok += 1
    else:
        bad += 1
print("source_hash matches: %d ok / %d bad" % (ok, bad))

# validate key_hash formula on locres records (they carry key_hash)
ok = bad = 0
bad_ex = []
for r in locres:
    if m.text_key_hash(r["key"]) == r["key_hash"]:
        ok += 1
    else:
        bad += 1
        if len(bad_ex) < 5:
            bad_ex.append((r["key"], r["key_hash"], m.text_key_hash(r["key"])))
print("key_hash matches: %d ok / %d bad" % (ok, bad))
for e in bad_ex:
    print("   mismatch", e)

# zlib alternative check
alt = zlib.crc32(locres[0]["source"].encode("utf-32le")) & 0xFFFFFFFF
print("crc32 utf-32le alt:", alt, "stored:", locres[0]["source_hash"], "module:", m.source_hash(locres[0]["source"]))
