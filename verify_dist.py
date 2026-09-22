# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""对 dist_zh 产物做独立校验：
1. 用 pyuepak 读回两个 .pak，确认条目路径与大小
2. 用自研 iostore.py 读回 pakchunk99-ZH_UAsset-Windows.utoc/.ucas，确认能取出与补丁后 raw 完全一致的 EnglishSource.uasset
3. 校验 locres 可被独立解析且中文条目数正确
4. 校验裁出的 TTF 头部/名称表
"""
import json, os, struct, sys, hashlib
ROOT = r"D:\SteamLibrary\steamapps\common\itr2_zh"
sys.path.insert(0, ROOT)
DIST = os.path.join(ROOT, "dist_zh")

from pyuepak import PakFile

print("=== 1. patch pak 内容 ===")
for name in ("pakchunk99-ZH_Locres_P.pak", "pakchunk100-ZH_Fonts_P.pak"):
    p = os.path.join(DIST, name)
    pak = PakFile()
    pak.read(p)
    files = pak.list_files()
    print("%s (%d bytes) -> %d entries" % (name, os.path.getsize(p), len(files)))
    for nm in files:
        try:
            sz = len(pak.read_file(nm))
        except Exception:
            sz = "?"
        print("    %-72s %s" % (nm, sz))

print()
print("=== 2. IoStore 容器独立读回 ===")
import iostore
for stem in ("pakchunk99-ZH_UAsset-Windows",):
    base = os.path.join(DIST, stem)
    c = iostore.Container(base, verbose=True)
    paths = list(c._walk())
    print("paths:", paths)
    target = [p for p in paths if p.endswith("EnglishSource.uasset")][0]
    data = c.extract(target)
    raw = open(os.path.join(DIST, "EnglishSource.zh-Hans.uasset.raw"), "rb").read()
    print("extract size=%d raw size=%d equal=%s" % (len(data), len(raw), data == raw))
    print("sha1 extract=%s" % hashlib.sha1(data).hexdigest())
    print("sha1 raw    =%s" % hashlib.sha1(raw).hexdigest())

print()
print("=== 3. locres 独立性检查 ===")
import importlib.util
spec = importlib.util.spec_from_file_location("ko_build", os.path.join(ROOT, "ref_ko", "scripts", "build", "build_locres_patch.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
loc = open(os.path.join(DIST, "Game.zh-Hans.locres"), "rb").read()
ns, ent = m.parse_locres(loc)
zh = [e for e in ent if any("\u4e00" <= c <= "\u9fff" for c in e.get("localized", ""))]
print("entries=%d namespaces=%s 中文条目=%d" % (len(ent), [n["namespace"] for n in ns], len(zh)))
import collections
print("按命名空间:", collections.Counter(e["namespace"] for e in ent))
sample = [e for e in ent if e["namespace"] == "EnglishSource"][:3]
for e in sample:
    print("   EN key=%s -> %s" % (e["key"], e["localized"][:60].replace("\r\n", "\\r\\n")))

print()
print("=== 4. 字体文件校验 ===")
for f in ("NotoSansSC-Regular.ttf", "NotoSansSC-Bold.ttf"):
    d = open(os.path.join(ROOT, "fonts", f), "rb").read()
    num = struct.unpack_from(">H", d, 4)[0]
    tabs = {}
    for i in range(num):
        tag, csum, off, ln = struct.unpack_from(">4sIII", d, 12 + 16 * i)
        tabs[tag.decode("latin1").strip()] = (off, ln)
    head = tabs.get("head")
    magic = struct.unpack_from(">I", d, head[0] + 12)[0] if head else None
    # name table: family name (nameID 1)
    no, nl = tabs["name"]
    cnt, so = struct.unpack_from(">HH", d, no + 2)
    fam = None
    for i in range(cnt):
        pid, eid, lid, nid, ln, off = struct.unpack_from(">HHHHHH", d, no + 6 + 12 * i)
        if nid == 1:
            raw = d[no + so + off: no + so + off + ln]
            try:
                fam = raw.decode("utf-16-be") if pid == 3 else raw.decode("latin1")
            except Exception:
                fam = raw.hex()
            break
    print("%s: size=%d numTables=%d head.magic=0x%08X %s family=%r glyf=%d loca=%d" % (
        f, len(d), num, magic, "OK" if magic == 0x5F0F3CF5 else "BAD", fam,
        tabs["glyf"][1], tabs["loca"][1]))
