# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
import json, os, math

ROOT = r"D:\SteamLibrary\steamapps\common\itr2_zh"
SRC = os.path.join(ROOT, "todo_sources.json")
OUTDIR = os.path.join(ROOT, "translate", "zh_full")
os.makedirs(OUTDIR, exist_ok=True)

with open(SRC, "r", encoding="utf-8") as f:
    todo = json.load(f)

tr = [t for t in todo if t.get("translatable")]
non = [t for t in todo if not t.get("translatable")]

# identity-fill non translatable
ident = [{"source_id": t["source_id"], "zh": t["source"]} for t in non]
with open(os.path.join(OUTDIR, "zh_identity.json"), "w", encoding="utf-8") as f:
    json.dump(ident, f, ensure_ascii=False, indent=1)

# sort by length so chunks are homogeneous-ish, then interleave so each chunk has a mix
tr_sorted = sorted(tr, key=lambda t: -t["char_len"])
NCHUNK = 12
chunks = [[] for _ in range(NCHUNK)]
for i, t in enumerate(tr_sorted):
    chunks[i % NCHUNK].append(t)

manifest = []
for i, c in enumerate(chunks):
    c = sorted(c, key=lambda t: t["source_id"])
    p = os.path.join(OUTDIR, "chunk_%02d.json" % i)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
    out = os.path.join(OUTDIR, "zh_%02d.json" % i)
    manifest.append({
        "chunk": i,
        "input": p,
        "output": out,
        "count": len(c),
        "chars": sum(t["char_len"] for t in c),
    })
    print("chunk %02d n=%4d chars=%7d -> %s" % (i, len(c), sum(t["char_len"] for t in c), os.path.basename(p)))

with open(os.path.join(OUTDIR, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)
print("total translatable", len(tr), "identity", len(ident), "chunks", NCHUNK)
