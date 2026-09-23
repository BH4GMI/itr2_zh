# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""对 dist_zh 产物做独立校验（去 ref_ko 化·阶段一）：
1. 用 pyuepak 读回全部 patch .pak，确认条目路径与大小
2. 用自研 iostore.py 读回 pakchunk99-ZH_UAsset-Windows.{utoc,ucas}，
   确认取出的 EnglishSource.uasset 与补丁 raw 完全一致
3. 用自研 locres.py 解析产出 locres：结构、命名空间、中文条目
4. fonts/ 存在时校验裁出的 TTF 头部/名称表（不存在则明示跳过：
   TTF 不入库，字体链路见 make_release.py）
"""
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist_zh"
sys.path.insert(0, str(HERE))

from pyuepak import PakFile

print("=== 1. patch pak 内容 ===")
paks = sorted(DIST.glob("*.pak"))
if not paks:
    raise SystemExit("dist_zh 下没有 .pak —— 先运行 build_zh.py")
for p in paks:
    pak = PakFile()
    pak.read(str(p))
    files = pak.list_files()
    print("%s (%d bytes) -> %d entries" % (p.name, p.stat().st_size, len(files)))
    for nm in files:
        try:
            sz = len(pak.read_file(nm))
        except Exception:
            sz = "?"
        print("    %-72s %s" % (nm, sz))

print()
print("=== 2. IoStore 容器独立读回 ===")
import iostore
stem = str(DIST / "pakchunk99-ZH_UAsset-Windows")
c = iostore.Container(stem, verbose=True)
paths = list(c._walk())
print("paths:", paths)
target = [p for p in paths if p.endswith("EnglishSource.uasset")][0]
data = c.extract(target)
raw = (DIST / "EnglishSource.zh-Hans.uasset.raw").read_bytes()
print("extract size=%d raw size=%d equal=%s" % (len(data), len(raw), data == raw))
print("sha1 extract=%s" % hashlib.sha1(data).hexdigest())
print("sha1 raw    =%s" % hashlib.sha1(raw).hexdigest())
if data != raw:
    raise SystemExit("FAIL: IoStore 读回内容与补丁 raw 不一致")

print()
print("=== 3. locres 独立性检查 ===")
import locres as L
loc = (DIST / "Game.zh-Hans.locres").read_bytes()
h = L.parse_locres(loc)
ents = [dict(e, _ns=str(ns["namespace"])) for ns in h["namespaces"] for e in ns["entries"]]
zh = [e for e in ents
      if any("\u4e00" <= c <= "\u9fff" for c in h["pool"][e["localized_index"]]["str"])]
ns_counts = {str(ns["namespace"]): len(ns["entries"]) for ns in h["namespaces"]}
print("entries=%d namespaces=%s 中文条目=%d" % (len(ents), ns_counts, len(zh)))
# 结构断言：与金标准补丁结构一致（4611 = 1231 + 3380；key 集合同源于原版+EXTRA）
if len(ents) != 4611 or ns_counts != {"": 1231, "EnglishSource": 3380}:
    raise SystemExit("FAIL: 结构与金标准不符: entries=%d ns=%s" % (len(ents), ns_counts))
if len(zh) == 0:
    raise SystemExit("FAIL: 没有中文条目")
sample = [e for e in ents if e["_ns"] == "EnglishSource"][:3]
for e in sample:
    t = h["pool"][e["localized_index"]]["str"]
    print("   EN key=%s -> %s" % (e["key"], t[:60].replace("\r\n", "\\r\\n")))

print()
print("=== 4. 字体文件校验 ===")
fonts = HERE / "fonts"
if not (fonts / "NotoSansSC-Regular.ttf").exists():
    print("fonts/ 不存在 —— 跳过（TTF 不入库；字体 pak 链路见 make_release.py）")
else:
    for f in ("NotoSansSC-Regular.ttf", "NotoSansSC-Bold.ttf"):
        d = (fonts / f).read_bytes()
        num = struct.unpack_from(">H", d, 4)[0]
        tabs = {}
        for i in range(num):
            tag, csum, off, ln = struct.unpack_from(">4sIII", d, 12 + 16 * i)
            tabs[tag.decode("latin1").strip()] = (off, ln)
        head = tabs.get("head")
        magic = struct.unpack_from(">I", d, head[0] + 12)[0] if head else None
        no, nl = tabs["name"]
        cnt, so = struct.unpack_from(">HH", d, no + 2)
        fam = None
        for i in range(cnt):
            pid, eid, lid, nid, ln, off = struct.unpack_from(">HHHHHH", d, no + 6 + 12 * i)
            if nid == 1:
                rawn = d[no + so + off: no + so + off + ln]
                try:
                    fam = rawn.decode("utf-16-be") if pid == 3 else rawn.decode("latin1")
                except Exception:
                    fam = rawn.hex()
                break
        print("%s: size=%d numTables=%d head.magic=0x%08X %s family=%r glyf=%d loca=%d" % (
            f, len(d), num, magic, "OK" if magic == 0x5F0F3CF5 else "BAD", fam,
            tabs["glyf"][1], tabs["loca"][1]))

print()
print("verify_dist: 完成（IoStore 读回不一致会提前退出）")
