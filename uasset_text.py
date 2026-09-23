# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""EnglishSource.uasset 的 serial 文本区解析（去 ref_ko 化·阶段一）。

布局（对 build 24024260 原版文件验证，entry_count=3332、Placeholder=183
与上游数据统计一致；text_offset/end 供 records 与阶段二补丁使用）::

    [0xD0] u64 serial_size            序列化数据区字节数
          serial_start = 文件长 - serial_size
    [serial_start + 2] FStr namespace  (必须为 'EnglishSource')
          i32 entry_count
          条目 × entry_count:
              FStr key    FText 的 key
              FStr text   英文源文（text_offset 指向此长度字段，end 为其结束）
          文件余量 ~8B（footer）

阶段二的 patch 语义：按 text_offset 原位替换 text FString（长度可变），
随后回写 0xD0 处的 serial_size——本模块先提供解析与回读校验。
"""
import struct


def read_fstr(data, off):
    """读 FString -> (文本, 新off)。"""
    n = struct.unpack_from("<i", data, off)[0]
    off += 4
    if n == 0:
        return "", off
    if 0 < n < 1_000_000:
        return data[off:off + n - 1].decode("utf-8", "replace"), off + n
    if n < 0:
        u = -n
        return data[off:off + (u - 1) * 2].decode("utf-16-le", "replace"), off + u * 2
    raise ValueError("非法 FString 长度 %d @ 0x%X" % (n, off - 4))


def parse_serial(data):
    """解析 serial 文本区 -> {'namespace','entries'}。

    entries 每条含 key/source/text_offset/end；text_offset 指向 text 的
    长度字段，end 为该 text 的结束偏移（补丁替换的区间）。
    """
    serial_size = struct.unpack_from("<Q", data, 0xD0)[0]
    serial_start = len(data) - serial_size
    if serial_size <= 0 or serial_start >= len(data):
        raise ValueError("serial_size 非法: %d" % serial_size)
    ns, p = read_fstr(data, serial_start + 2)
    if ns != "EnglishSource":
        raise ValueError("namespace 非法: %r @0x%X" % (ns, serial_start + 2))
    count = struct.unpack_from("<i", data, p)[0]
    p += 4
    entries = []
    for _ in range(count):
        key, p = read_fstr(data, p)
        text_off = p
        text, p = read_fstr(data, p)
        entries.append({"key": key, "source": text,
                        "text_offset": text_off, "end": p})
    return {"namespace": ns, "entries": entries,
            "serial_start": serial_start, "serial_size": serial_size,
            "parsed_end": p}


def _write_fstr(text):
    """FString 编码（与 locres 同引擎规则：ASCII→正长度；含非 ASCII→负长度 UTF-16）。"""
    if text == "":
        return struct.pack("<i", 0)
    try:
        b = text.encode("ascii")
        return struct.pack("<i", len(b) + 1) + b + b"\x00"
    except UnicodeEncodeError:
        b = text.encode("utf-16-le")
        return struct.pack("<i", -(len(b) // 2 + 1)) + b + b"\x00\x00"


def patch(raw, records, write_fstr=None):
    """按 records 的 ko 替换 serial 区文本 -> (补丁后字节, summary)。

    语义：
      - 仅替换每条的 text 长度字段到 end 的区间；key 区与文件头零变更；
      - ko == source（或 ko 缺失）时直接拷贝原文区间，**零字节变更**；
      - 结束后回写 0xD0 的 serial_size（= 新文件长 - serial_start）；
      - 自检：patch 后重新 parse_serial，逐条比对 key 与期望译文。
    """
    write_fstr = write_fstr or _write_fstr
    recs = sorted((r for r in records if r.get("container") == "EnglishSource.uasset"),
                  key=lambda r: r["text_offset"])
    if not recs:
        raise ValueError("records 中没有 EnglishSource.uasset 条目")
    # 记录必须与 raw 逐条匹配（偏移/原文/结束位）
    for r in recs:
        parsed, end = read_fstr(raw, r["text_offset"])
        if parsed != r["source"] or end != r["end"]:
            raise ValueError("records 与 raw 不匹配 @0x%X: key=%s"
                             % (r["text_offset"], r.get("key", "?")))

    serial_size0 = struct.unpack_from("<Q", raw, 0xD0)[0]
    serial_start = len(raw) - serial_size0

    out = bytearray()
    cursor = 0
    changed = 0
    for r in recs:
        text = r.get("ko") or r["source"]
        out += raw[cursor:r["text_offset"]]
        if text == r["source"]:
            out += raw[r["text_offset"]:r["end"]]      # 未变更：原文区间原字节
        else:
            out += write_fstr(text)
            changed += 1
        cursor = r["end"]
    out += raw[cursor:]
    struct.pack_into("<Q", out, 0xD0, len(out) - serial_start)

    # 自检：回读补丁文件，逐条比对
    info = parse_serial(bytes(out))
    if len(info["entries"]) != len(recs):
        raise ValueError("patch 自检条目数不符: %d != %d"
                         % (len(info["entries"]), len(recs)))
    for r, e in zip(recs, info["entries"]):
        want = r.get("ko") or r["source"]
        if e["key"] != r["key"] or e["source"] != want:
            raise ValueError("patch 自检失败: key=%s" % r["key"])

    summary = {
        "entries": len(recs),
        "changed": changed,
        "original_size": len(raw),
        "patched_size": len(out),
        "serial_start": serial_start,
        "patched_serial_size": len(out) - serial_start,
    }
    return bytes(out), summary


def _selftest():
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "game_inputs", "EnglishSource.uasset")
    data = open(path, "rb").read()
    info = parse_serial(data)
    ents = info["entries"]
    ph = sum(1 for e in ents if e["source"] == "Placeholder text")
    ok = True

    def check(label, got, want):
        nonlocal ok
        same = got == want
        ok = ok and same
        print("  %-34s %s  (got=%r want=%r)" % (label, "PASS" if same else "FAIL", got, want))

    print("EnglishSource.uasset serial 解析:")
    check("namespace", info["namespace"], "EnglishSource")
    check("entry_count", len(ents), 3332)
    check("Placeholder text 条目数", ph, 183)
    # 样本对照 ko_analysis.md 的 record_id
    sample = next((e for e in ents if e["key"] == "348ADCEF4C776BAC12F92EA36AD2F59B"), None)
    check("样本 Dovetail source", sample and sample["source"],
          "\r\nOnly for firearms with Dovetail mount.")
    # text_offset/end 区间一致性：逐条回读必须等于 source
    bad = [e for e in ents if read_fstr(data, e["text_offset"])[0] != e["source"]]
    check("text_offset 回读一致条数", len(bad), 0)
    # serial 区边界
    check("serial 区解析位置合理", info["parsed_end"] <= len(data), True)

    # ---- patch 三重验证 ----
    # b1: ko == source 全程原字节拷贝 -> 输出逐字节等于原文件
    same_records = [{"container": "EnglishSource.uasset", "key": e["key"],
                     "source": e["source"], "ko": e["source"],
                     "text_offset": e["text_offset"], "end": e["end"]}
                    for e in ents]
    p1, s1 = patch(data, same_records)
    check("b1 patch(ko=source) 逐字节==原版", p1 == data, True)

    # b2: 假译文 -> 重编码 -> parse 回读全中
    fake_records = [dict(r, ko=r["source"] + "·汉") for r in same_records]
    p2, s2 = patch(data, fake_records)
    info2 = parse_serial(p2)
    back_ok = all(e["source"] == (r["source"] + "·汉")
                  for r, e in zip(fake_records, info2["entries"]))
    check("b2 假译文回读全中", back_ok, True)
    check("b2 变更条数", s2["changed"], len(ents))
    check("b2 serial_size 回读自洽",
          struct.unpack_from("<Q", p2, 0xD0)[0] == len(p2) - info2["serial_start"], True)

    # c: 成品（补丁版）结构对照：key 序必须与原版完全一致
    sys.path.insert(0, here)
    from iostore_build import load_release_files, read_entry
    g_utoc, g_ucas, _ = load_release_files()
    gold = read_entry(g_utoc, g_ucas, 0)
    ginfo = parse_serial(gold)
    check("c 金标准条目数", len(ginfo["entries"]), len(ents))
    check("c key 序与原版完全一致",
          [e["key"] for e in ginfo["entries"]] == [e["key"] for e in ents], True)
    diff_text = sum(1 for a, b in zip(ginfo["entries"], ents) if a["source"] != b["source"])
    check("c 成品译文差异条数>3000", diff_text > 3000, True)

    print("  总计: %s" % ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
