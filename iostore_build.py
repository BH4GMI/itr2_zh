# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""自研 IoStore (.utoc/.ucas/.pak) 写入端（阶段一：零上游依赖）。

用于构建 EnglishSource.uasset 的覆盖容器（pakchunk99-ZH_UAsset-Windows.*）。

设计原则：**全部结构模板从本项目已发布的成品切片推导**，不引用任何上游代码——
成品（本仓库随附的 `ITR2_Chinese_v2.zip` 内的补丁三件套）本身就是一份引擎可加载的
合法容器，其头部/伴随 pak/目录区是引擎二进制格式的事实性数据::

    utoc  = header(144B, 回填 block_count@0x1C)
          + chunk_ids(24B 固定)
          + offset_lengths(2×10B: 5B BE 逻辑偏移 + 5B BE 逻辑长度)   <- 重算
          + extra(4B 固定)
          + block entries(n×12B: 5B LE 物理偏移 + 3B LE 压缩 + 3B LE 原始 + 1B method=0)  <- 重算
          + method names(32B 固定 "Oodle"+NUL)
          + directory(固定切片: ../../../Projectc 挂载点 + 单文件目录)
    ucas  = entry0 数据（65536 分块，块间 16 对齐）+ entry1(72B 固定) <- 重算
    meta  = sha1(entry0)+0u32 + sha1(entry1)+0u32                     <- 重算
    pak   = 伴随 pak（339B 固定切片）

模板来源是**入库文件**（发布包 zip），因此换机后只需仓库本身即可重建。
验证（__main__）：
  A. 以成品 ucas 中提取的补丁版 uasset 为 entry0 重建三件 -> 与成品逐字节比对；
  B. 以游戏原版 uasset（game_inputs/）为 entry0 重建 -> 用本模块读取器读回比对（读写闭环）。
"""
import hashlib
import math
import os
import struct
import zipfile

BLOCK_SIZE = 65536
ALIGN = 16
META_SIZE = 48          # sha1(20) + u32(4)，两条 meta 各一份

REPO = os.path.dirname(os.path.abspath(__file__))
GAME_INPUTS = os.path.join(REPO, os.pardir, "game_inputs")
# 模板来源：本项目已发布成品（随仓库保存的发布包）
RELEASE_ZIP = os.path.join(REPO, "ITR2_Chinese_v2.zip")
UASSET_ENTRY = "ITR2_Chinese_v2/pakchunk99-ZH_UAsset-Windows"


def read_entry(utoc, ucas, index):
    """从未压缩的 IoStore 容器字节里取出指定条目（轻量读取，不依赖 Oodle）。"""
    (_, header_size, n_entries, _, _, _, _, _) = struct.unpack_from("<IIIIIIII", utoc, 0x10)
    ol = header_size + 12 * n_entries
    blocks_off = ol + 10 * n_entries + 4
    bs = struct.unpack_from("<I", utoc, 0x2C)[0]
    logical_offset = int.from_bytes(utoc[ol + 10 * index: ol + 10 * index + 5], "big")
    logical_len = int.from_bytes(utoc[ol + 10 * index + 5: ol + 10 * index + 10], "big")
    out = bytearray()
    pos_in = logical_offset % bs
    remaining = logical_len
    for bi in range(logical_offset // bs, (logical_offset + logical_len + bs - 1) // bs):
        b = utoc[blocks_off + 12 * bi: blocks_off + 12 * bi + 12]
        phys = int.from_bytes(b[:5], "little")
        csz = int.from_bytes(b[5:8], "little")
        data = ucas[phys: phys + csz]
        take = min(bs - pos_in, remaining)
        out += data[pos_in: pos_in + take]
        remaining -= take
        pos_in = 0
    return bytes(out)


def load_release_files():
    """从入库发布包取出模板来源三件套字节。"""
    if not os.path.exists(RELEASE_ZIP):
        raise SystemExit("缺少模板来源 %s（发布包随仓库保存，不应缺失）" % RELEASE_ZIP)
    with zipfile.ZipFile(RELEASE_ZIP) as zf:
        return (zf.read(UASSET_ENTRY + ".utoc"),
                zf.read(UASSET_ENTRY + ".ucas"),
                zf.read(UASSET_ENTRY + ".pak"))


def load_templates():
    """从成品三件套切出全部固定模板。"""
    utoc, ucas, companion_pak = load_release_files()
    (_, header_size, n_entries, n_blocks, block_entry_size,
     n_methods, method_name_len, bs) = struct.unpack_from("<IIIIIIII", utoc, 0x10)
    dir_size = struct.unpack_from("<I", utoc, 0x30)[0]
    chunk_ids = utoc[header_size: header_size + 12 * n_entries]
    ol = header_size + 12 * n_entries
    extra = utoc[ol + 10 * n_entries: ol + 10 * n_entries + 4]
    blocks_off = ol + 10 * n_entries + len(extra)
    methods = utoc[blocks_off + n_blocks * block_entry_size:
                   blocks_off + n_blocks * block_entry_size + n_methods * method_name_len]
    # meta = sha1(20) + u32(4) × 2 = 48 字节，位于文件末尾；目录区紧接其前
    directory = utoc[len(utoc) - META_SIZE - dir_size: len(utoc) - META_SIZE]
    assert directory.find(b"../../../") >= 0, "目录区定位失败"
    return {
        "header": bytearray(utoc[:header_size]),
        "chunk_ids": chunk_ids,
        "extra": extra,
        "methods": methods,
        "directory": directory,
        "entry1": read_entry(utoc, ucas, 1),
        "companion_pak": companion_pak,
    }


def _align16(n):
    return (n + ALIGN - 1) // ALIGN * ALIGN


def build_iostore(entry0, tpl):
    """entry0: 覆盖资产字节 -> {'utoc','ucas','pak'}。"""
    n0 = max(1, math.ceil(len(entry0) / BLOCK_SIZE))
    entry1 = tpl["entry1"]
    ucas = bytearray()
    blocks = []
    for bi in range(n0):
        chunk = entry0[bi * BLOCK_SIZE: (bi + 1) * BLOCK_SIZE]
        phys = _align16(len(ucas))
        ucas += b"\x00" * (phys - len(ucas))
        ucas += chunk
        blocks.append(phys.to_bytes(5, "little")
                      + len(chunk).to_bytes(3, "little")
                      + len(chunk).to_bytes(3, "little") + b"\x00")
    phys1 = _align16(len(ucas))
    ucas += b"\x00" * (phys1 - len(ucas))
    ucas += entry1
    blocks.append(phys1.to_bytes(5, "little")
                  + len(entry1).to_bytes(3, "little")
                  + len(entry1).to_bytes(3, "little") + b"\x00")
    tail = _align16(len(ucas)) - len(ucas)
    ucas += b"\x00" * tail

    ol = (0).to_bytes(5, "big") + len(entry0).to_bytes(5, "big")
    ol += (n0 * BLOCK_SIZE).to_bytes(5, "big") + len(entry1).to_bytes(5, "big")
    meta = (hashlib.sha1(entry0).digest() + b"\x00\x00\x00\x00"
            + hashlib.sha1(entry1).digest() + b"\x00\x00\x00\x00")

    header = bytearray(tpl["header"])
    struct.pack_into("<I", header, 0x1C, len(blocks))
    struct.pack_into("<I", header, 0x30, len(tpl["directory"]))

    utoc = (bytes(header) + tpl["chunk_ids"] + ol + tpl["extra"]
            + b"".join(blocks) + tpl["methods"] + tpl["directory"] + meta)
    assert len(meta) == META_SIZE
    return {"utoc": utoc, "ucas": bytes(ucas), "pak": bytes(tpl["companion_pak"])}


def _selftest():
    ok = True
    g_utoc, g_ucas, g_pak = load_release_files()

    # A) 以成品补丁版 uasset 重建 -> 与成品三件套逐字节比对
    tpl = load_templates()
    entry0 = read_entry(g_utoc, g_ucas, 0)
    built = build_iostore(entry0, tpl)
    for name, mine, gold in (("utoc", built["utoc"], g_utoc),
                             ("ucas", built["ucas"], g_ucas),
                             ("pak", built["pak"], g_pak)):
        same = mine == gold
        ok = ok and same
        print("A) %-4s %7d / %7d B  %s" % (name, len(mine), len(gold),
                                           "逐字节一致 PASS" if same else "FAIL"))
        if not same:
            n = min(len(mine), len(gold))
            i = next((k for k in range(n) if mine[k] != gold[k]), n)
            print("     首差 @0x%X: %s != %s" % (i, mine[i:i+8].hex(), gold[i:i+8].hex()))

    # B) 游戏原版 uasset 重建 + 读取器 round-trip（不落盘）
    orig_path = os.path.join(GAME_INPUTS, "EnglishSource.uasset")
    if not os.path.exists(orig_path):
        print("B) 跳过：缺少 %s（游戏机运行 collect_game_inputs.py 采集）" % orig_path)
        return ok
    orig = open(orig_path, "rb").read()
    built2 = build_iostore(orig, tpl)
    back = read_entry(built2["utoc"], built2["ucas"], 0)
    same = back == orig
    ok = ok and same
    print("B) 原件(%dB) 重建容器读回: %s" % (len(orig), "round-trip PASS" if same else "FAIL"))
    print("   新容器: utoc=%dB ucas=%dB pak=%dB" % (
        len(built2["utoc"]), len(built2["ucas"]), len(built2["pak"])))
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
