# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""ITR2 本地化文本的三个哈希公式（去 ref_ko 化·阶段一）。

公式均以 build 24024260 原版 Game.locres 的 2164 条 (key, key_hash)、
(key, source_hash) 真值与 translate/zh_full 的 2393 对 (source_id, source)
全量验证通过；key_hash 的 32 位折叠系数（×23）为引擎实现细节，已用
2164 条真值逐一复核。三个公式互为独立入口，供构建与校验脚本共用。
"""
import hashlib
import zlib

try:
    from cityhash import CityHash64
except ImportError as _e:  # pragma: no cover
    raise SystemExit("缺少 cityhash 包：pip install cityhash") from _e


def source_hash(text: str) -> int:
    """locres 条目的 source_hash = CRC32(UTF-32LE 编码)。"""
    return zlib.crc32(text.encode("utf-32-le")) & 0xFFFFFFFF


def text_key_hash(text: str) -> int:
    """locres 的 key/命名空间哈希。

    CityHash64(UTF-16LE) 的 32 位折叠：low32 + high32 * 23 (mod 2^32)；
    空串特判为 0（CityHash64("") 本身非 0，引擎对空 key 直接写 0）。
    """
    if text == "":
        return 0
    hashed = CityHash64(text.encode("utf-16-le"))
    low = hashed & 0xFFFFFFFF
    high = (hashed >> 32) & 0xFFFFFFFF
    return (low + high * 23) & 0xFFFFFFFF


def source_id(text: str) -> str:
    """翻译数据的 join 键 = SHA1(UTF-8) 前 16 位 hex（zh_sources.json 的键）。"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _selftest():
    import glob
    import json
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import locres as L

    here = os.path.dirname(os.path.abspath(__file__))
    data = open(os.path.join(here, "..", "game_inputs", "GAME_Game.locres"), "rb").read()
    h = L.parse_locres(data)
    entries = [e for ns in h["namespaces"] for e in ns["entries"]]
    ok_key = sum(1 for e in entries if text_key_hash(e["key"]) == e["key_hash"])
    ok_ns = sum(1 for ns in h["namespaces"] if text_key_hash(ns["namespace"]) == ns["ns_hash"])
    ok_src = sum(1 for e in entries
                 if source_hash(h["pool"][e["localized_index"]]["str"]) == e["source_hash"])
    print("key_hash   : %d / %d" % (ok_key, len(entries)))
    print("ns_hash    : %d / %d" % (ok_ns, len(h["namespaces"])))
    print("source_hash: %d / %d" % (ok_src, len(entries)))

    pairs = []
    for f in glob.glob(os.path.join(here, "translate", "zh_full", "chunk_*.json")):
        for t in json.load(open(f, encoding="utf-8")):
            if "source_id" in t and "source" in t:
                pairs.append((t["source_id"], t["source"]))
    ok_sid = sum(1 for sid, s in pairs if source_id(s) == sid)
    print("source_id  : %d / %d" % (ok_sid, len(pairs)))

    # 独立样本：金标准（上游构建产物）中 EXTRA 注入条目的实际写入值。
    # 注：上游数据里另有两个手写 hash（0x980147F6/0xFE9C7A42）从未出现在
    # 构建产物中——它们对应撇号等文本变体，属陈旧记录；一切以公式为准。
    extras = [("Critical Damage Multiplier", 0xDB544335),
              ("Not found", 0x9DB9AD30),
              ("I'm broken", 0xAF6ECBC1),
              ("Please insert ammo box first", 0x88B2CD13)]
    ok_ex = sum(1 for s, want in extras if source_hash(s) == want)
    print("显式样本   : %d / %d" % (ok_ex, len(extras)))

    total = len(entries) * 2 + len(h["namespaces"]) + len(pairs) + len(extras)
    passed = ok_key + ok_ns + ok_src + ok_sid + ok_ex
    print("合计: %d / %d  %s" % (passed, total, "PASS" if passed == total else "FAIL"))
    return passed == total


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
