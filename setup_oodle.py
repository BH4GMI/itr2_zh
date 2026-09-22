# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""为 pyuepak 准备 Oodle 运行库。

pyuepak 在 import 时会尝试下载 oo2core_9_win64.dll；在部分网络环境下该下载会失败或
拿到错误内容（大小/哈希不符），导致 `import pyuepak` 直接报错。本脚本改为从本机已有的
游戏目录中找一个可用的 oo2core DLL，校验后放进 pyuepak 包目录。

用法：
    python setup_oodle.py                 # 自动搜索常见 Steam 目录
    python setup_oodle.py "D:\\path\\oo2core_8_win64.dll"
"""
import ctypes
import os
import shutil
import sys

CANDIDATE_GLOBS = [
    r"C:\Program Files (x86)\Steam\steamapps\common",
    r"C:\Program Files\Steam\steamapps\common",
    r"D:\SteamLibrary\steamapps\common",
    r"E:\SteamLibrary\steamapps\common",
]
MIN_SIZE = 200 * 1024


def pyuepak_dir():
    import importlib.util
    spec = importlib.util.find_spec("pyuepak")
    if not spec or not spec.origin:
        raise SystemExit("未安装 pyuepak：pip install pyuepak cityhash")
    return os.path.dirname(spec.origin)


def looks_valid(path):
    try:
        if os.path.getsize(path) < MIN_SIZE:
            return False, "文件过小（可能是下载到的错误内容）"
        with open(path, "rb") as f:
            if f.read(2) != b"MZ":
                return False, "不是 PE 文件"
        lib = ctypes.CDLL(path)
        getattr(lib, "OodleLZ_Decompress")
        return True, "OodleLZ_Decompress 可用"
    except Exception as e:  # noqa: BLE001
        return False, "无法加载: %s" % e


def search(explicit=None):
    if explicit:
        return [explicit]
    found = []
    for base in CANDIDATE_GLOBS:
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for f in files:
                if f.lower().startswith("oo2core") and f.lower().endswith(".dll"):
                    found.append(os.path.join(root, f))
            if len(found) > 40:
                break
    return found


def main():
    target_dir = pyuepak_dir()
    target = os.path.join(target_dir, "oo2core_9_win64.dll")

    if os.path.exists(target):
        ok, why = looks_valid(target)
        if ok:
            print("[OK] 已存在可用运行库：%s（%d B，%s）" % (target, os.path.getsize(target), why))
            return
        print("[!] 现有 %s 不可用：%s，尝试替换" % (target, why))

    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    for cand in search(explicit):
        ok, why = looks_valid(cand)
        print("    检查 %s -> %s" % (cand, why))
        if ok:
            shutil.copy2(cand, target)
            print("[OK] 已复制到 %s（%d B）" % (target, os.path.getsize(target)))
            return

    raise SystemExit("[X] 未找到可用的 oo2core DLL；请手动指定路径：python setup_oodle.py <dll 路径>")


if __name__ == "__main__":
    main()
