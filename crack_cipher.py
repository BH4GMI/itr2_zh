# -*- coding: utf-8 -*-
"""#0166 / #0168 / #0170 / #0172 / #0174 五条加密本地化文本的解密器。

这 5 条文本（EnglishSource.uasset 中英中完全相同的字符串）是同一套自定义
维吉尼亚（Vigenère）密码加密的通信记录。破解得到的完整参数：

    字母表  ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ9867543210"
            （A–Z 按自然顺序占 0–25；数字段 26–35 的顺序是 9,8,6,7,5,4,3,2,1,0）
    密钥    每条消息不同，按条目顺序为 RADIUS / EXPLORER / ANOMALY / MIMICS / ARTIFACT
    算法    p = ALPHA[(ALPHA.index(c) - ALPHA.index(k[i % len(k)])) % 36]
            仅对 [A-Za-z0-9] 字符加密；空格、标点、换行一律原样保留

用法：
    python crack_cipher.py            # 解密 5 条并打印（默认读取同目录 records_with_zh.json）
    python crack_cipher.py --verify   # 额外做「反推字母表一致性」自检

报告见 docs/密文破解.md。
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

# ---------------------------------------------------------------- 破解参数
ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ9867543210"
BASE = 36
"""工作字母表：字母段自然序，数字段为 9,8,6,7,5,4,3,2,1,0。"""

# 每条密文以「头部代号行」开头，用它将记录与密钥配对。
KEYS = {
    "GEX9 D3 VOV": "RADIUS",
    "IB2 56 GIBW": "EXPLORER",
    "ZR15 TZ 6O4": "ANOMALY",
    "QW5 8Q HQ65": "MIMICS",
    "ZVD9 YO G2S": "ARTIFACT",
}

ALNUM = re.compile(r"[A-Za-z0-9]")
RECORDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "records_with_zh.json")


def decrypt(text: str, key: str, alpha: str = ALPHA) -> str:
    """按自定义字母表维吉尼亚解密；非字母数字字符原样保留。"""
    idx = {c: i for i, c in enumerate(alpha)}
    out = list(text)
    n = 0
    for j, ch in enumerate(text):
        if ALNUM.match(ch):
            out[j] = alpha[(idx[ch.upper()] - idx[key[n % len(key)]]) % BASE]
            n += 1
    return "".join(out)


def load_records(path: str = RECORDS) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_cipher_records(rec: list) -> list:
    """按头部代号行取出 5 条密文记录，并保持 KEYS 中定义的顺序。"""
    found = []
    for header, key in KEYS.items():
        hit = next((r for r in rec if header in r["source"]), None)
        if hit is not None:
            found.append((header, key, hit))
    return found


def verify_alphabet(rec: list) -> bool:
    """自检：由（密文、解出的明文、密钥）反推 a(c)，每个符号必须唯一。

    这一步同时验证「字母表 + 密钥 + 算法」三者自洽：若字母表或密钥有任何一位
    错误，反推出的 a(c) 必然在某个符号上出现两个不同取值。
    """
    votes: dict = defaultdict(Counter)
    for header, key, r in find_cipher_records(rec):
        plain = decrypt(r["source"], key)
        n = 0
        for j, ch in enumerate(r["source"]):
            if not ALNUM.match(ch):
                continue
            want = (ALPHA.index(plain[j].upper()) + ALPHA.index(key[n % len(key)])) % BASE
            votes[ch.upper()][want] += 1
            n += 1

    ok = True
    for ch in ALPHA:
        dist = votes.get(ch)
        if dist is None:
            print("  符号 %s 未在密文中出现，无法验证" % ch)
            ok = False
        elif len(dist) != 1:
            print("  符号 %s 反推不唯一：%s" % (ch, dist.most_common()))
            ok = False
    if len(votes) != BASE:
        ok = False
    return ok


def main(argv: list) -> int:
    rec = load_records()
    items = find_cipher_records(rec)
    if len(items) != len(KEYS):
        print("错误：只找到 %d / %d 条密文记录；请确认 records_with_zh.json 存在且完整。"
              % (len(items), len(KEYS)), file=sys.stderr)
        return 2

    if "--verify" in argv:
        print("字母表一致性自检：%s" % ("通过" if verify_alphabet(rec) else "失败"))
        print("字母表：%s" % ALPHA)
        print("数字段：%s" % ALPHA[26:])
        print()

    total = 0
    for header, key, r in items:
        total += sum(1 for c in r["source"] if ALNUM.match(c))
        print("=" * 78)
        print("容器：%s   文本键：%s" % (r["container"], r["key"]))
        print("source_id：%s   密钥：%s" % (r["source_id"], key))
        print("-" * 78)
        print("密文：")
        print(r["source"].replace("\r\n", "\n"))
        print("明文：")
        print(decrypt(r["source"], key).replace("\r\n", "\n"))
    print("=" * 78)
    print("共 %d 条，%d 个字母数字字符" % (len(items), total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
