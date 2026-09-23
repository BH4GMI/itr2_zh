# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""从 game_inputs/ 采集的 NotoSansSC 字体资源中提取 TTF，并生成中文界面字体覆盖 pak。

产物：dist_zh/pakchunk100-ZH_Fonts_P.pak
覆盖：IntoTheRadius2/Content/ITR2/Fonts/{NEXT_ART_SemiBold,PTSansNarrow-Bold,PTSansNarrow-Regular}.ufont

输入：../game_inputs/NotoSansSC-{Regular,Bold}.uasset
（collect_game_inputs.py 在游戏机采集交付，本脚本不再需要游戏安装目录）。
"""
import os, struct, sys, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME_INPUTS = HERE.parent / "game_inputs"
FONTS = HERE / "fonts"
DIST = HERE / "dist_zh"
FONTS.mkdir(exist_ok=True)
DIST.mkdir(exist_ok=True)


def sfnt_tables(data, off):
    if data[off:off + 4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf"):
        return None
    num = struct.unpack_from(">H", data, off + 4)[0]
    if not (1 <= num <= 512):
        return None
    tabs = {}
    for i in range(num):
        p = off + 12 + 16 * i
        tag, csum, toff, tlen = struct.unpack_from(">4sIII", data, p)
        if toff + tlen > len(data):
            return None
        tabs[tag.decode("latin1").strip()] = (toff, tlen)
    return tabs


def carve(raw, out_path):
    """在 uasset 原始字节里定位内嵌 TTF（完整 SFNT 表集），切出并落盘。"""
    off = raw.find(b"\x00\x01\x00\x00")
    best = None
    while off >= 0:
        tabs = sfnt_tables(raw, off)
        if tabs and {"cmap", "glyf", "head", "hhea", "hmtx", "loca", "maxp", "name"} <= set(tabs):
            end = max(o + l for o, l in tabs.values())
            if best is None or end > best[1]:
                best = (off, end, tabs)
        off = raw.find(b"\x00\x01\x00\x00", off + 1)
    if not best:
        raise SystemExit("no embedded TTF in asset (%d bytes)" % len(raw))
    off, end, tabs = best
    end = (end + 3) & ~3
    # 表偏移是相对 TTF 起点的，因此切片必须从 off 开始
    ttf = raw[off:off + end]
    with open(out_path, "wb") as f:
        f.write(ttf)
    return ttf, tabs, len(raw), off


def cmap_codepoints(ttf):
    tabs = sfnt_tables(ttf, 0)
    co, cl = tabs["cmap"]
    cm = ttf[co:co + cl]
    n = struct.unpack_from(">H", cm, 2)[0]
    best = None
    for i in range(n):
        pid, eid, off = struct.unpack_from(">HHI", cm, 4 + 8 * i)
        fmt = struct.unpack_from(">H", cm, off)[0]
        if fmt in (4, 12):
            rank = {12: 2, 4: 1}[fmt]
            if best is None or rank > best[0]:
                best = (rank, off, fmt)
    if not best:
        return set()
    _, off, fmt = best
    cps = set()
    if fmt == 4:
        segx2 = struct.unpack_from(">H", cm, off + 6)[0]
        seg = segx2 // 2
        ends = struct.unpack_from(">%dH" % seg, cm, off + 14)
        starts = struct.unpack_from(">%dH" % seg, cm, off + 16 + segx2)
        for s, e in zip(starts, ends):
            if e == 0xFFFF and s == 0xFFFF:
                continue
            cps.update(range(s, e + 1))
    else:
        ngroups = struct.unpack_from(">I", cm, off + 12)[0]
        for i in range(ngroups):
            s, e, _ = struct.unpack_from(">III", cm, off + 16 + 12 * i)
            if e - s > 200000:
                continue
            cps.update(range(s, e + 1))
    return cps


def main():
    result = {}
    spec = [
        ("NotoSansSC-Regular.uasset", "NotoSansSC-Regular.ttf"),
        ("NotoSansSC-Bold.uasset", "NotoSansSC-Bold.ttf"),
    ]
    for asset, fname in spec:
        src = GAME_INPUTS / asset
        if not src.exists():
            print("[!] 缺少 %s —— 先在游戏机运行 collect_game_inputs.py" % src)
            continue
        out = str(FONTS / fname)
        try:
            ttf, tabs, rawlen, off = carve(src.read_bytes(), out)
        except SystemExit as e:
            print("[!]", e)
            continue
        cps = cmap_codepoints(ttf)
        cjk = sum(1 for cp in cps if 0x4E00 <= cp <= 0x9FFF)
        kana = sum(1 for cp in cps if 0x3040 <= cp <= 0x30FF)
        hg = sum(1 for cp in cps if 0xAC00 <= cp <= 0xD7A3)
        lat = sum(1 for cp in cps if 0x20 <= cp <= 0x7E)
        print("[OK] %s -> %s  %d bytes (asset %d, ttf@0x%X, tables=%d)" % (asset, fname, len(ttf), rawlen, off, len(tabs)))
        print("     codepoints=%d  CJK=%d  假名=%d  谚文=%d  ASCII=%d" % (len(cps), cjk, kana, hg, lat))
        result[fname] = {"bytes": len(ttf), "codepoints": len(cps), "cjk": cjk, "kana": kana, "hangul": hg, "ascii": lat}

    # 构建字体覆盖 pak
    from pyuepak import PakFile
    from pyuepak.version import PakVersion
    mapping = [
        ("IntoTheRadius2/Content/ITR2/Fonts/NEXT_ART_SemiBold.ufont", "NotoSansSC-Bold.ttf"),
        ("IntoTheRadius2/Content/ITR2/Fonts/PTSansNarrow-Bold.ufont", "NotoSansSC-Bold.ttf"),
        ("IntoTheRadius2/Content/ITR2/Fonts/PTSansNarrow-Regular.ufont", "NotoSansSC-Regular.ttf"),
    ]
    pak = PakFile()
    pak.version = PakVersion.V11
    added = []
    for logical, fname in mapping:
        p = FONTS / fname
        if not p.exists():
            print("[!] missing", p)
            continue
        pak.add_file(logical, p.read_bytes())
        added.append((logical, p.stat().st_size))
    out_pak = str(DIST / "pakchunk100-ZH_Fonts_P.pak")
    pak.write(out_pak)
    print("[OK] font pak:", out_pak, os.path.getsize(out_pak), "bytes")
    for logical, size in added:
        print("     %-70s %d" % (logical, size))

    with open(str(HERE / "font_report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
