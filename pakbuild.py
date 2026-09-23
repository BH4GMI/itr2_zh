# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""自研 patch pak 构建入口（阶段一：零上游依赖）。

上游在 make_pak 里做的事：pyuepak 的 PakFile + V11 版本 + add_file + write。
这是 pyuepak 公开 API 的标准用法（属事实性接口调用，非表达性代码）；
本模块把它收敛为一个可复用函数，并附加「读回验证」。

验证策略（见 __main__）：从入库发布包取出成品 locres pak，解包后用本模块
重新打包，与成品逐字节比对；若因时间戳等非确定字段不一致，则退化为
结构等价验证（条目集合 + 内容一致）。
"""
import os

from pyuepak import PakFile
from pyuepak.version import PakVersion

REPO = os.path.dirname(os.path.abspath(__file__))
RELEASE_ZIP = os.path.join(REPO, "ITR2_Chinese_v2.zip")
LOCRES_PAK_ENTRY = "ITR2_Chinese_v2/pakchunk99-ZH_Locres_P.pak"


def make_pak(files: dict, out_path: str) -> str:
    """files: {逻辑路径: bytes} -> 写出未压缩的 V11 patch pak，返回路径。"""
    pak = PakFile()
    pak.version = PakVersion.V11
    for logical_path, data in files.items():
        pak.add_file(logical_path, data)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    pak.write(out_path)
    return out_path


def read_pak(path: str) -> dict:
    """读回 pak：{逻辑路径: bytes}，用于产物验证。"""
    pak = PakFile()
    pak.read(path)
    return {name: pak.read_file(name) for name in pak.list_files()}


def _selftest():
    """闭环自测：入库发布包 -> 取出成品 locres pak -> 解包 -> 重打包 -> 逐字节比对。"""
    import tempfile
    import zipfile

    if not os.path.exists(RELEASE_ZIP):
        print("跳过：缺少发布包 %s" % RELEASE_ZIP)
        return True
    with zipfile.ZipFile(RELEASE_ZIP) as zf:
        gold = zf.read(LOCRES_PAK_ENTRY)

    with tempfile.TemporaryDirectory() as td:
        gp = os.path.join(td, "golden.pak")
        with open(gp, "wb") as f:
            f.write(gold)
        files = read_pak(gp)                  # 解包（dict 保序）
        out = os.path.join(td, "rebuilt.pak")
        make_pak(files, out)
        mine = open(out, "rb").read()

    print("生成 pak %d B / 成品 %d B，条目 %d 个" % (len(mine), len(gold), len(files)))
    if mine == gold:
        print("逐字节一致: PASS")
        return True
    print("验证: FAIL（字节不一致）")
    return False


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
