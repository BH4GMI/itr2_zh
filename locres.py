# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""自研 UE .locres 解析/构建模块（去 ref_ko 化·阶段一）。

字节布局（对 build 24024260 的原版与补丁版 Game.locres 双向验证；头部字段语义
经上游公开仓库 refracta/itr2-ko 的格式说明确认）::

    [0x00] 16B  magic GUID (0x7574140E, 0xFC034A67, 0x9D90154A, 0x1B7F37C3, LE)
    [0x10] u8   version = 3
    [0x11] u32  string_array_offset   字符串池的绝对偏移（构建时回填）
    [0x15] u32  保留 = 0
    [0x19] u32  total                 全部命名空间条目总数
    [0x1D] u32  n_ns                  命名空间数
          每 命名空间:
              u32  ns_hash    命名空间 key_hash（"" -> 0）
              FStr ns        命名空间名
              u32  count     条目数
              条目 × count:  [u32 key_hash][FStr key][u32 localized_index][u32 source_hash]
    [offset] u32 pool_count           字符串池（去重）条数
          池子条目 × pool_count:  [FStr localized][u32 ref_count]
              ref_count = 引用该字符串的条目数（与条目总数守恒；用于一致性校验）

FString 编码不唯一：纯 ASCII 用正长度（含结尾 NUL 的字节数），非 ASCII 用负长度
（UTF-16 码元数，同样含 NUL）；空串既可能是 len=0，也可能是 len=1+'\\0'
（原版与上游构建器写法不同，游戏均接受）。为保证 parse->build 往返**逐字节一致**，
本模块对每个字符串同时保存原始字节与解码值；修改字符串时按默认规则重新编码。
"""
import struct

MAGIC = struct.pack("<4I", 0x7574140E, 0xFC034A67, 0x9D90154A, 0x1B7F37C3)


def _read_fstr(d, off):
    """读 FString：返回 (解码文本, 原始字节含长度前缀, 新off)。"""
    start = off
    n = struct.unpack_from("<i", d, off)[0]
    off += 4
    if n == 0:
        s = ""
    elif 0 < n < 0x10000:
        s = d[off:off + n - 1].decode("utf-8", "replace")
        off += n
    elif -0x10000 < n < 0:
        u = -n
        s = d[off:off + (u - 1) * 2].decode("utf-16-le", "replace")
        off += u * 2
    else:
        raise ValueError("非法 FString 长度 %d @ 0x%X" % (n, start))
    return s, d[start:off], off


def _write_fstr(s):
    """按默认规则编码 FString（新内容用；往返走 raw 透传）。"""
    if not s:
        return struct.pack("<i", 0)
    try:
        b = s.encode("ascii")
        return struct.pack("<i", len(b) + 1) + b + b"\x00"
    except UnicodeEncodeError:
        b = s.encode("utf-16-le")
        return struct.pack("<i", -(len(b) // 2 + 1)) + b + b"\x00\x00"


class FStr(str):
    """带原始字节记忆的字符串：build 时优先写 raw（保往返一致）。"""

    __slots__ = ("raw",)

    def __new__(cls, s, raw=None):
        obj = super().__new__(cls, s)
        obj.raw = raw
        return obj


def parse_locres(data):
    """解析 .locres -> dict（含全部原始字节记忆，可供 build 往返）。"""
    if data[:16] != MAGIC:
        raise ValueError("magic GUID 不匹配")
    h = {"magic": data[:16]}
    h["version"] = data[0x10]
    if h["version"] != 3:
        raise ValueError("不支持的 locres 版本 %d" % h["version"])
    h["pool_offset"] = struct.unpack_from("<I", data, 0x11)[0]
    h["reserved"] = struct.unpack_from("<I", data, 0x15)[0]
    h["total"] = struct.unpack_from("<i", data, 0x19)[0]
    n_ns = struct.unpack_from("<i", data, 0x1D)[0]
    off = 0x21
    ns_list = []
    for _ in range(n_ns):
        nsh = struct.unpack_from("<I", data, off)[0]
        off += 4
        ns, ns_raw, off = _read_fstr(data, off)
        cnt = struct.unpack_from("<i", data, off)[0]
        off += 4
        ents = []
        for _ in range(cnt):
            kh = struct.unpack_from("<I", data, off)[0]
            off += 4
            key, key_raw, off = _read_fstr(data, off)
            sh = struct.unpack_from("<I", data, off)[0]
            ix = struct.unpack_from("<i", data, off + 4)[0]
            off += 8
            ents.append({"key_hash": kh, "key": FStr(key, key_raw),
                         "source_hash": sh, "localized_index": ix})
        ns_list.append({"ns_hash": nsh, "namespace": FStr(ns, ns_raw),
                        "count": cnt, "entries": ents})
    h["namespaces"] = ns_list
    pc = struct.unpack_from("<i", data, off)[0]
    off += 4
    pool = []
    for _ in range(pc):
        s, raw, off = _read_fstr(data, off)
        ref = struct.unpack_from("<I", data, off)[0]
        off += 4
        pool.append({"str": FStr(s, raw), "ref_count": ref})
    h["pool"] = pool
    h["_end"] = off
    return h


def _fstr_bytes(fs):
    """FStr/str -> 序列化字节（FStr 用 raw 保证往返；str 用默认规则）。"""
    if isinstance(fs, FStr) and fs.raw is not None:
        return fs.raw
    return _write_fstr(str(fs))


def build_locres(h):
    """dict -> .locres 字节。与 parse_locres 互逆（池子偏移构建后回填）。"""
    out = bytearray()
    out += h.get("magic", MAGIC)
    out += struct.pack("<B", h.get("version", 3))
    out += struct.pack("<I", 0)          # string_array_offset 占位，池子写完后回填
    out += struct.pack("<I", h.get("reserved", 0))
    ns_list = h["namespaces"]
    total = sum(len(ns["entries"]) for ns in ns_list)
    out += struct.pack("<i", h.get("total", total))
    out += struct.pack("<i", len(ns_list))
    for ns in ns_list:
        out += struct.pack("<I", ns["ns_hash"])
        out += _fstr_bytes(ns["namespace"])
        ents = ns["entries"]
        out += struct.pack("<i", len(ents))
        for e in ents:
            out += struct.pack("<I", e["key_hash"])
            out += _fstr_bytes(e["key"])
            out += struct.pack("<I", e["source_hash"])
            out += struct.pack("<i", e["localized_index"])
    struct.pack_into("<I", out, 0x11, len(out))   # 回填池子绝对偏移
    pool = h["pool"]
    out += struct.pack("<i", len(pool))
    for item in pool:
        # 兼容纯字符串与 {str, ref_count} 两种表示
        s = item["str"] if isinstance(item, dict) else item
        out += _fstr_bytes(s)
        out += struct.pack("<I", item["ref_count"] if isinstance(item, dict) else 1)
    return bytes(out)


def assemble(base, entries):
    """从 union 条目列表构建完整 .locres（build_zh 的核心装配）。

    base    = parse_locres(原版) 的返回：提供 magic/version/reserved 与
              命名空间骨架（含 ns_hash、FString 原始写法）。
    entries = [{namespace, key, key_hash, source_hash, ko}, ...]，已按
              (namespace, key) 去重。池分配按 entries 全局序首次出现，
              ref_count 为引用计数；分组写入按 base.namespaces 顺序。
    """
    # 1) 全局序分配字符串池，为每条 entry 记录池索引（不去重 entries，
    #    仅按 text 聚合到同一池下）
    pool = []
    pool_index = {}
    tagged = []
    for e in entries:
        text = e.get("ko") or e.get("source") or ""
        idx = pool_index.get(text)
        if idx is None:
            idx = len(pool)
            pool_index[text] = idx
            pool.append({"str": FStr(text), "ref_count": 0})
        pool[idx]["ref_count"] += 1
        tagged.append((e, idx))

    # 2) 按 base 的命名空间骨架分组（保持骨架顺序与组内相对顺序）
    groups = {}
    for e, idx in tagged:
        groups.setdefault(e["namespace"], []).append((e, idx))

    def _ents(pairs):
        return [{
            "key_hash": e["key_hash"], "key": FStr(e["key"]),
            "source_hash": e["source_hash"], "localized_index": idx,
        } for e, idx in pairs]

    ns_list = []
    seen = set()
    for bns in base["namespaces"]:
        name = str(bns["namespace"])
        seen.add(name)
        ns_list.append({
            "ns_hash": bns["ns_hash"],
            # 规范化编码（不透传 raw）：与游戏/上游构建器的重编码语义一致。
            # 差异点仅在空命名空间 '' 的两种合法写法（len=0 vs len=1+NUL），
            # 透传会引入 1 字节差（已对金标准逐字节验证此结论）。
            "namespace": FStr(name),
            "entries": _ents(groups.get(name, [])),
        })
    for name in groups:                          # base 中不存在的新命名空间
        if name not in seen:
            from textkey import text_key_hash
            ns_list.append({"ns_hash": text_key_hash(name),
                            "namespace": FStr(name),
                            "entries": _ents(groups[name])})

    return build_locres({
        "magic": base.get("magic", MAGIC),
        "version": base.get("version", 3),
        "reserved": base.get("reserved", 0),
        "total": sum(len(ns["entries"]) for ns in ns_list),
        "namespaces": ns_list,
        "pool": pool,
    })


def _selftest(paths):
    ok = True
    for path in paths:
        data = open(path, "rb").read()
        h = parse_locres(data)
        rebuilt = build_locres(h)
        same = rebuilt == data
        # 装配往返：条目化(ko=池译文) -> assemble -> 字节一致
        flat = []
        for ns in h["namespaces"]:
            for e in ns["entries"]:
                flat.append({"namespace": ns["namespace"], "key": e["key"],
                             "key_hash": e["key_hash"],
                             "source_hash": e["source_hash"],
                             "ko": h["pool"][e["localized_index"]]["str"]})
        reasm = assemble(h, flat)
        # assemble 是规范化重建：文件本身即规范化写法时逐字节相同
        # （金标准为上游规范化构建产物 -> 逐字节一致；原版的 ns='' 为
        # len=1+NUL 写法 -> 差 1 字节属预期，退化为语义一致验证）
        same2 = reasm == data
        if not same2:
            h3 = parse_locres(reasm)
            flat3 = [(str(ns["namespace"]), e["key"], e["key_hash"],
                      e["source_hash"], h3["pool"][e["localized_index"]]["str"])
                     for ns in h3["namespaces"] for e in ns["entries"]]
            want = [(f["namespace"], f["key"], f["key_hash"],
                     f["source_hash"], f["ko"]) for f in flat]
            same2 = flat3 == want
        ok = ok and same and same2 and h["_end"] == len(data)
        zh = sum(1 for it in h["pool"] if any("\u4e00" <= c <= "\u9fff" for c in it["str"]))
        refs = sum(it["ref_count"] for it in h["pool"])
        ns_desc = ", ".join("%r:%d" % (ns["namespace"], ns["count"]) for ns in h["namespaces"])
        print("%-46s %8d B  解析=%d/%d  ns[%s]  池@0x%X=%d(中文%d)  引用和=%d/总%d  v=%d" % (
            path.split("\\")[-1], len(data), h["_end"], len(data), ns_desc,
            h["pool_offset"], len(h["pool"]), zh, refs, h["total"], h["version"]))
        print("    引用计数守恒: %s" % ("PASS" if refs == h["total"] else "FAIL"))
        print("    往返逐字节一致: %s" % ("PASS" if same else "FAIL (rebuilt %d B)" % len(rebuilt)))
        print("    assemble 装配一致: %s%s" % ("PASS" if same2 else "FAIL (%d B)" % len(reasm),
              "（规范化写法差异，语义一致）" if same2 and reasm != data else ""))
        if not same:
            n = min(len(rebuilt), len(data))
            i = next((k for k in range(n) if rebuilt[k] != data[k]), n)
            print("    首个差异 @0x%X: %s != %s" % (i, rebuilt[i:i+8].hex(), data[i:i+8].hex()))
        if not same2:
            n = min(len(reasm), len(data))
            i = next((k for k in range(n) if reasm[k] != data[k]), n)
            print("    首个差异 @0x%X: %s != %s" % (i, reasm[i:i+8].hex(), data[i:i+8].hex()))
    return ok


if __name__ == "__main__":
    import os
    import sys

    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, os.pardir, "game_inputs", "GAME_Game.locres"),
        os.path.join(here, os.pardir, "_golden_Game.locres"),
    ]
    paths = sys.argv[1:] or [p for p in candidates if os.path.exists(p)]
    if not paths:
        print("没有可验证的 locres：在游戏机运行 collect_game_inputs.py 采集 game_inputs/，"
              "或从发布包提取成品 locres 后传入路径")
        sys.exit(1)
    sys.exit(0 if _selftest(paths) else 1)
