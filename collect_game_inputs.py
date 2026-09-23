# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""在装有游戏的机器上收集构建/验证所需的**游戏侧输入文件**。

为什么要这个脚本
----------------
游戏的 IoStore 容器（`pakchunk0-Windows.ucas`）有十几 GB，不可能整体搬运；
而构建与验证真正需要的只有其中三个 `.uasset`。本脚本在装游戏的机器上就地提取它们，
加上那个只有几十 MB 的传统 `.pak`（内含 `Game.locres` / `Game.locmeta`，本机用 pyuepak 解），
把结果汇总到一个可以整体拷走的小目录。

设计约束
--------
* **零第三方依赖**：只用标准库 + `ctypes` 调游戏自带的 Oodle 运行库（`oo2core*.dll`）。
* **只读**：绝不写入或修改游戏目录，只读容器、只往输出目录写。
* **可核对**：每个产出文件都记录大小与 SHA256，并做格式合理性检查（uasset 魔数等）。

用法
----
    python collect_game_inputs.py                    # 自动定位游戏目录
    python collect_game_inputs.py --game-dir "D:\\path\\to\\IntoTheRadius2"
    python collect_game_inputs.py --out D:\\game_inputs
    python collect_game_inputs.py --dry-run          # 只列出会取哪些文件，不写盘

    # 离线/自检模式：不碰游戏目录，直接用指定的容器
    python collect_game_inputs.py --paks <容器所在目录> --container <容器名>
"""
import argparse
import ctypes
import hashlib
import json
import os
import platform
import struct
import sys
import time

# ---------------------------------------------------------------- 常量

GAME_SUBDIR = "IntoTheRadius2"
DEFAULT_GAME_DIR = r"D:\SteamLibrary\steamapps\common\IntoTheRadius2"
STEAM_APPID = "2307350"
EXPECTED_BUILDID = "24024260"

# 容器里要提取的条目：用「文件名 + 期望的路径片段」匹配，避免不同版本挂载点差异导致取错
IOSTORE_WANTED = [
    {
        "basename": "EnglishSource.uasset",
        "path_hint": "Localization",
        "why": "uasset 补丁的输入（FText 原文与位置）",
    },
    {
        "basename": "NotoSansSC-Regular.uasset",
        "path_hint": "Fonts",
        "why": "裁出中文字体 NotoSansSC-Regular.ttf",
    },
    {
        "basename": "NotoSansSC-Bold.uasset",
        "path_hint": "Fonts",
        "why": "裁出中文字体 NotoSansSC-Bold.ttf",
    },
]

# 传统 pak：整体拷走，本机用 pyuepak 解出 Game.locres / Game.locmeta
PAK_TO_COPY = "pakchunk0-Windows.pak"
# 目录索引只有几十 KB~几 MB，带上它可以在本机独立核对提取结果
UTOC_TO_COPY = "pakchunk0-Windows.utoc"
UTOC_COPY_LIMIT = 64 * 1024 * 1024

UASSET_MAGIC = b"\xC1\x83\x2A\x9E"   # UE 包文件魔数 0x9E2A83C1（小端）


def log(msg=""):
    print(msg, flush=True)
    if _TEE is not None:
        _TEE.write(msg + "\n")
        _TEE.flush()


_TEE = None


def start_log(path):
    """控制台输出同时落一份 UTF-8 日志，便于异地取回后按 UTF-8 精确阅读。

    不劫持/不改写 stdout 编码：子进程被重定向时，调用方（例如 Windows
    PowerShell 5.1）会按本机 ANSI 代码页解码我们的输出，强行输出 UTF-8 会变成乱码。
    """
    global _TEE
    try:
        _TEE = open(path, "w", encoding="utf-8", newline="\n")
    except OSError as e:
        print("无法创建日志文件 %s: %s" % (path, e), flush=True)
        _TEE = None


# ---------------------------------------------------------------- Oodle

class Oodle:
    """按需加载游戏自带的 Oodle 运行库；容器未压缩时根本不需要它。"""

    def __init__(self, explicit_path=None):
        self.path = None
        self._dec = None
        self.error = None
        self._explicit = explicit_path

    @staticmethod
    def _candidates(game_dir):
        out = []
        if not game_dir or not os.path.isdir(game_dir):
            return out
        # 常见位置优先，避免对整个游戏目录做深度遍历
        preferred = [
            os.path.join(game_dir, GAME_SUBDIR, "Binaries", "Win64"),
            os.path.join(game_dir, GAME_SUBDIR, "Binaries"),
            game_dir,
        ]
        for d in preferred:
            if os.path.isdir(d):
                for name in sorted(os.listdir(d)):
                    if name.lower().startswith("oo2core") and name.lower().endswith(".dll"):
                        out.append(os.path.join(d, name))
        if out:
            return out
        # 兜底：有限深度递归
        for root, dirs, files in os.walk(game_dir):
            depth = root[len(game_dir):].count(os.sep)
            if depth >= 4:
                dirs[:] = []
                continue
            for name in files:
                if name.lower().startswith("oo2core") and name.lower().endswith(".dll"):
                    out.append(os.path.join(root, name))
            if out:
                break
        return out

    @staticmethod
    def _steam_candidates(limit=3):
        """在 Steam 库里找其他游戏自带的 Oodle（本作自身不附带 oo2core）。"""
        hits = []
        for common in steam_common_dirs():
            if not os.path.isdir(common):
                continue
            for root, dirs, files in os.walk(common):
                depth = root[len(common):].count(os.sep)
                if depth >= 4:
                    dirs[:] = []
                for name in files:
                    if name.lower().startswith("oo2core") and name.lower().endswith(".dll"):
                        hits.append(os.path.join(root, name))
                        if len(hits) >= limit:
                            return hits
        return hits

    def load(self, game_dir):
        cands = (([self._explicit] if self._explicit else [])
                 + self._candidates(game_dir)
                 + self._steam_candidates())
        for p in cands:
            if not p or not os.path.exists(p):
                continue
            try:
                lib = ctypes.CDLL(p)
                dec = lib.OodleLZ_Decompress
                dec.restype = ctypes.c_longlong
                dec.argtypes = [ctypes.c_char_p, ctypes.c_longlong, ctypes.c_char_p,
                                ctypes.c_longlong, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_void_p, ctypes.c_longlong, ctypes.c_void_p,
                                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_longlong, ctypes.c_int]
                self._dec = dec
                self.path = p
                return True
            except OSError as e:
                self.error = "%s: %s" % (p, e)
        return False

    def decompress(self, src, raw_len):
        if self._dec is None:
            return None
        buf = ctypes.create_string_buffer(raw_len + 65536)
        r = self._dec(src, len(src), buf, raw_len, 1, 0, 0, None, 0, None, None, None, 0, 3)
        return buf.raw[:r] if r > 0 else None


# ---------------------------------------------------------------- IoStore 读取

def align(v, a=16):
    return (v + a - 1) // a * a


def read_fstring(b, off):
    (n,) = struct.unpack_from("<i", b, off)
    off += 4
    if n == 0:
        return "", off
    if n > 0:
        return b[off:off + n - 1].decode("utf-8", "replace"), off + n
    u = -n
    return b[off:off + (u - 1) * 2].decode("utf-16-le", "replace"), off + u * 2


class IoStoreContainer:
    """IoStore (.utoc/.ucas) 只读容器。

    字节布局与 `iostore.py` 一致（同为 Apache-2.0 的本仓库代码），
    这里把路径参数化、并去掉启动即 require Oodle 的强耦合。
    """

    def __init__(self, stem, paks_dir, oodle=None, verbose=True):
        self.stem = stem
        self.paks_dir = paks_dir
        self.oodle = oodle or Oodle()
        self.utoc_path = os.path.join(paks_dir, stem + ".utoc")
        self.ucas_path = os.path.join(paks_dir, stem + ".ucas")
        if not os.path.exists(self.utoc_path):
            raise SystemExit("找不到容器索引: %s" % self.utoc_path)
        if not os.path.exists(self.ucas_path):
            raise SystemExit("找不到容器数据: %s" % self.ucas_path)
        with open(self.utoc_path, "rb") as f:
            self.utoc = f.read()
        self.ucas_size = os.path.getsize(self.ucas_path)
        d = self.utoc
        if d[:16] != b"-==--==--==--==-":
            raise SystemExit("%s 不是 IoStore 索引（魔数不匹配）" % self.utoc_path)
        (self.version, self.header_size, self.n_entries, self.n_blocks,
         self.block_entry_size, self.n_methods, self.method_name_len,
         self.block_size) = struct.unpack_from("<IIIIIIII", d, 0x10)
        self.dir_size, self.n_partitions = struct.unpack_from("<II", d, 0x30)
        self._parse(verbose)

    def _parse(self, verbose=True):
        d = self.utoc
        base = self.header_size
        ol = base + 12 * self.n_entries
        self.offset_lengths = []
        for i in range(self.n_entries):
            raw = d[ol + 10 * i: ol + 10 * i + 10]
            self.offset_lengths.append((int.from_bytes(raw[:5], "big"),
                                        int.from_bytes(raw[5:10], "big")))
        search_from = ol + 10 * self.n_entries
        mount_pos = d.find(b"../../../", search_from)
        if mount_pos < 4:
            raise SystemExit("%s: 无法定位目录索引" % self.stem)
        self.dir_off = mount_pos - 4
        self.mount, p = read_fstring(d, self.dir_off)
        nd = struct.unpack_from("<i", d, p)[0]; p += 4
        self.dirs = [struct.unpack_from("<IIII", d, p + 16 * i) for i in range(nd)]
        p += 16 * nd
        nf = struct.unpack_from("<i", d, p)[0]; p += 4
        self.files = [struct.unpack_from("<III", d, p + 12 * i) for i in range(nf)]
        p += 12 * nf
        ns = struct.unpack_from("<i", d, p)[0]; p += 4
        self.strings = []
        for _ in range(ns):
            s, p = read_fstring(d, p)
            self.strings.append(s)
        self.method_off = self.dir_off - self.n_methods * self.method_name_len
        self.methods = [d[self.method_off + i * self.method_name_len:
                          self.method_off + (i + 1) * self.method_name_len].split(b"\0")[0].decode("latin1")
                        for i in range(self.n_methods)]
        self.blocks_off = self.method_off - self.n_blocks * self.block_entry_size
        self.blocks = []
        for i in range(self.n_blocks):
            x = d[self.blocks_off + 12 * i: self.blocks_off + 12 * i + 12]
            self.blocks.append((int.from_bytes(x[:5], "little"),
                                int.from_bytes(x[5:8], "little"),
                                int.from_bytes(x[8:11], "little"), x[11]))
        self.paths = self._walk()
        if verbose:
            log("  容器 %s: v%d 条目=%s 块=%s 方法=%s 挂载点=%r"
                % (self.stem, self.version, format(self.n_entries, ","),
                   format(self.n_blocks, ","), self.methods, self.mount))

    def _name(self, i):
        if i == 0xFFFFFFFF or i >= len(self.strings):
            return None
        return self.strings[i]

    def _walk(self):
        out = {}
        stack = [(0, "")]
        while stack:
            di, prefix = stack.pop()
            name, first_child, next_sib, first_file = self.dirs[di]
            cur = prefix if di == 0 else prefix + (self._name(name) or "") + "/"
            f = first_file
            while f != 0xFFFFFFFF and f < len(self.files):
                fn, nxt, user = self.files[f]
                nm = self._name(fn)
                if nm is not None:
                    out[cur + nm] = user
                f = nxt
            c = first_child
            while c != 0xFFFFFFFF and c < len(self.dirs):
                stack.append((c, cur))
                c = self.dirs[c][2]
        return out

    def read_chunk(self, index):
        logical_offset, logical_length = self.offset_lengths[index]
        bs = self.block_size
        first = logical_offset // bs
        last = (align(logical_offset + logical_length, bs) - 1) // bs
        in_block = logical_offset % bs
        remaining = logical_length
        out = bytearray()
        with open(self.ucas_path, "rb") as f:
            for bi in range(first, last + 1):
                po, csz, usz, m = self.blocks[bi]
                f.seek(po)
                payload = f.read(csz)
                if len(payload) != csz:
                    raise RuntimeError("块 %d 读取不足（%d/%d）" % (bi, len(payload), csz))
                if m == 0:
                    data = payload
                else:
                    if self.oodle._dec is None:
                        raise RuntimeError("块 %d 使用了压缩方法 %r，但 Oodle 运行库不可用（%s）"
                                           % (bi, self.methods[m - 1] if m - 1 < len(self.methods) else m,
                                              self.oodle.error or "未找到 oo2core*.dll"))
                    data = self.oodle.decompress(payload, usz)
                    if data is None:
                        raise RuntimeError("块 %d Oodle 解压失败（offset=%#x）" % (bi, po))
                take = min(bs - in_block, remaining)
                out += data[in_block:in_block + take]
                remaining -= take
                in_block = 0
                if remaining <= 0:
                    break
        return bytes(out)

    def extract(self, path):
        u = self.paths.get(path)
        if u is None and not path.startswith("../../../"):
            u = self.paths.get("../../../" + path.lstrip("/"))
        if u is None:
            return None
        return self.read_chunk(u)


# ---------------------------------------------------------------- 工具

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def steam_common_dirs():
    """列出所有 Steam 库的 steamapps\\common 目录（注册表 -> libraryfolders.vdf）。"""
    out = []
    try:
        import winreg
        steams = []
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    steams.append(winreg.QueryValueEx(k, "SteamPath")[0])
            except OSError:
                pass
        for steam in steams:
            vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
            if os.path.exists(vdf):
                with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('"path"'):
                            out.append(os.path.join(line.split('"')[3], "steamapps", "common"))
            out.append(os.path.join(steam, "steamapps", "common"))
    except ImportError:
        pass
    # 去重，保持顺序
    seen = set()
    uniq = []
    for d in out:
        k = d.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(d)
    return uniq


def find_game_dir(explicit=None):
    """环境变量 -> 显式参数 -> Steam 注册表扫描 -> 内置默认路径。"""
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get("ITR2_DIR"):
        cands.append(os.environ["ITR2_DIR"])
    for common in steam_common_dirs():
        cands.append(os.path.join(common, GAME_SUBDIR))
    cands.append(DEFAULT_GAME_DIR)
    for c in cands:
        if c and os.path.exists(os.path.join(c, GAME_SUBDIR, "Binaries", "Win64",
                                             "IntoTheRadius2-Win64-Shipping.exe")):
            return os.path.abspath(c)
    return None


def read_buildid(game_dir):
    """从 Steam 的 appmanifest 读 buildid，用于确认游戏版本。"""
    try:
        steamapps = os.path.dirname(os.path.dirname(game_dir))   # ...\steamapps\common\X -> ...\steamapps
        acf = os.path.join(steamapps, "appmanifest_%s.acf" % STEAM_APPID)
        if os.path.exists(acf):
            with open(acf, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    s = line.strip()
                    if s.lower().startswith('"buildid"'):
                        return s.split('"')[3]
    except Exception:
        pass
    return None


def match_wanted(container, spec):
    """按 basename 匹配容器内路径；path_hint 用于在多命中时优选。"""
    base = spec["basename"].lower()
    hits = [p for p in container.paths if p.rsplit("/", 1)[-1].lower() == base]
    if not hits and spec["basename"].startswith("NotoSansSC"):
        # 有的版本会带 .ufont 后缀变体，退化为前缀匹配
        stem = spec["basename"][:-len(".uasset")].lower()
        hits = [p for p in container.paths
                if p.rsplit("/", 1)[-1].lower().startswith(stem)
                and p.lower().endswith((".uasset", ".ufont"))]
    if not hits:
        return None, []
    hint = (spec.get("path_hint") or "").lower()
    preferred = [p for p in hits if hint and hint in p.lower()]
    pool = preferred or hits
    pool.sort(key=lambda p: (len(p), p))
    return pool[0], hits


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="收集构建 ITR2 汉化补丁所需的游戏侧输入文件")
    ap.add_argument("--game-dir", default=None, help="游戏根目录（含 IntoTheRadius2 子目录）")
    ap.add_argument("--paks", default=None, help="容器所在目录（默认 <游戏>/IntoTheRadius2/Content/Paks）")
    ap.add_argument("--container", default="pakchunk0-Windows", help="IoStore 容器名（不含扩展名）")
    ap.add_argument("--out", default=None, help="输出目录（默认脚本同级的 game_inputs）")
    ap.add_argument("--oodle", default=None, help="显式指定 oo2core*.dll")
    ap.add_argument("--dry-run", action="store_true", help="只列出将提取的条目，不写盘")
    ap.add_argument("--no-listing", action="store_true", help="不输出容器路径清单")
    args = ap.parse_args()

    # 不要强制 stdout 为 UTF-8：重定向时由调用方按本机代码页解码，
    # 只把不可编码字符替换掉，避免中文导致 UnicodeEncodeError 直接崩掉。
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    out_dir = os.path.abspath(args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                       "game_inputs"))
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not args.dry_run:
        os.makedirs(out_dir, exist_ok=True)
        start_log(os.path.join(out_dir, "collect.log"))

    log("=" * 72)
    log("ITR2 游戏侧输入收集")
    log("=" * 72)

    game_dir = None
    if args.paks:
        paks_dir = os.path.abspath(args.paks)
        log("[i] 离线模式：容器目录 %s" % paks_dir)
    else:
        game_dir = find_game_dir(args.game_dir)
        if not game_dir:
            log("[X] 没找到游戏目录。请显式指定：--game-dir \"D:\\...\\IntoTheRadius2\"")
            return 2
        paks_dir = os.path.join(game_dir, GAME_SUBDIR, "Content", "Paks")
        log("[i] 游戏目录: %s" % game_dir)

    buildid = read_buildid(game_dir) if game_dir else None
    if buildid:
        tag = "OK" if buildid == EXPECTED_BUILDID else "!! 与预期不一致"
        log("[i] Steam buildid: %s   (预期 %s)  %s" % (buildid, EXPECTED_BUILDID, tag))
    log("[i] 容器目录: %s" % paks_dir)
    log("[i] 输出目录: %s" % out_dir)

    oodle = Oodle(args.oodle)
    # 注意：显式 --oodle 必须在离线模式（game_dir 为空）下也生效，因此不能用 game_dir 短路
    if oodle.load(game_dir):
        log("[i] Oodle 运行库: %s" % oodle.path)
    else:
        log("[i] Oodle 运行库: 暂未加载（容器若未压缩则不需要；需要时会报错）%s"
            % ("  原因: " + oodle.error if oodle.error else ""))

    utoc = os.path.join(paks_dir, args.container + ".utoc")
    ucas = os.path.join(paks_dir, args.container + ".ucas")
    for p in (utoc, ucas):
        if os.path.exists(p):
            log("[i] %s  %s 字节" % (os.path.basename(p), format(os.path.getsize(p), ",")))
        else:
            log("[X] 缺少 %s" % p)
            return 2

    try:
        container = IoStoreContainer(args.container, paks_dir, oodle=oodle)
    except SystemExit as e:
        log("[X] %s" % e)
        return 2

    # ---- 匹配目标 ----
    plan = []
    log("")
    log("--- 容器内目标匹配 ---")
    for spec in IOSTORE_WANTED:
        best, all_hits = match_wanted(container, spec)
        if best:
            log("  [OK] %-30s <- %s" % (spec["basename"], best))
            if len(all_hits) > 1:
                log("       （另有 %d 个同名条目：%s）"
                    % (len(all_hits) - 1, "; ".join(p for p in all_hits if p != best)))
        else:
            log("  [!!] %-30s 未在容器中找到" % spec["basename"])
        plan.append((spec, best))

    if args.dry_run:
        log("")
        log("[i] --dry-run：未写盘。容器内共 %s 个条目。" % format(len(container.paths), ","))
        return 0

    os.makedirs(out_dir, exist_ok=True)

    # ---- 提取 ----
    manifest = {
        "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": platform.node(),
        "game_dir": game_dir,
        "paks_dir": paks_dir,
        "container": args.container,
        "container_utoc_bytes": os.path.getsize(utoc),
        "container_ucas_bytes": os.path.getsize(ucas),
        "container_entries": len(container.paths),
        "container_toc_entries": container.n_entries,
        "container_blocks": container.n_blocks,
        "container_block_size": container.block_size,
        "container_methods": container.methods,
        "container_mount": container.mount,
        "steam_buildid": buildid,
        "expected_buildid": EXPECTED_BUILDID,
        "oodle_dll": oodle.path,
        "python": platform.python_version(),
        "files": [],
    }

    log("")
    log("--- 提取 ---")
    ok = True
    for spec, best in plan:
        if not best:
            ok = False
            manifest["files"].append({"basename": spec["basename"], "status": "not_found"})
            continue
        try:
            data = container.extract(best)
        except Exception as e:
            log("  [X] %s 提取失败: %s" % (spec["basename"], e))
            manifest["files"].append({"basename": spec["basename"], "container_path": best,
                                      "status": "error", "error": str(e)})
            ok = False
            continue
        if data is None:
            log("  [X] %s 读取返回空" % spec["basename"])
            manifest["files"].append({"basename": spec["basename"], "container_path": best,
                                      "status": "empty"})
            ok = False
            continue
        dst = os.path.join(out_dir, spec["basename"])
        with open(dst, "wb") as f:
            f.write(data)
        digest = hashlib.sha256(data).hexdigest()
        entry = {
            "basename": spec["basename"],
            "container_path": best,
            "status": "ok",
            "bytes": len(data),
            "sha256": digest,
            "head16_hex": data[:16].hex(" "),
            "why": spec["why"],
        }
        # 说明：该资产的字节开头不一定是标准 UE 包魔数（0x9E2A83C1），
        # 因此这里只做记录、不做判定；真正的判定用金标准产物对照。
        entry["head_is_ue_package_magic"] = data[:4] == UASSET_MAGIC
        if spec["basename"].startswith("NotoSansSC"):
            off = data.find(b"\x00\x01\x00\x00")
            entry["embedded_ttf_at"] = off if off >= 0 else None
        log("  [OK] %-30s %10s 字节  sha256=%s" % (spec["basename"], format(len(data), ","), digest[:16]))
        manifest["files"].append(entry)

    # ---- 传统 pak / utoc：整体拷走 ----
    log("")
    log("--- 一并拷贝（本机再解析）---")
    for name in (PAK_TO_COPY, UTOC_TO_COPY):
        src = os.path.join(paks_dir, name)
        if not os.path.exists(src):
            log("  [--] %s 不存在，跳过" % name)
            continue
        size = os.path.getsize(src)
        if name == UTOC_TO_COPY and size > UTOC_COPY_LIMIT:
            log("  [--] %s 有 %s 字节，超过 %s 上限，跳过（不必要）"
                % (name, format(size, ","), format(UTOC_COPY_LIMIT, ",")))
            continue
        dst = os.path.join(out_dir, name)
        with open(src, "rb") as fi, open(dst, "wb") as fo:
            for chunk in iter(lambda: fi.read(1 << 20), b""):
                fo.write(chunk)
        digest = sha256_of(dst)
        log("  [OK] %-30s %10s 字节" % (name, format(size, ",")))
        manifest["files"].append({"basename": name, "status": "copied", "bytes": size,
                                  "sha256": digest,
                                  "why": "传统 pak：本机用 pyuepak 解出 Game.locres/Game.locmeta"
                                         if name.endswith(".pak") else "容器索引：本机独立核对提取结果"})

    # ---- 容器路径清单（便于本机核对条目位置）----
    if not args.no_listing:
        listing = os.path.join(out_dir, "iostore_paths.txt")
        items = sorted(container.paths.items())
        with open(listing, "w", encoding="utf-8") as f:
            f.write("# 容器 %s 共 %d 个条目\n" % (args.container, len(items)))
            for path, idx in items:
                off, ln = container.offset_lengths[idx]
                f.write("%10d  %s\n" % (ln, path))
        log("  [OK] %-30s %10s 字节" % ("iostore_paths.txt", format(os.path.getsize(listing), ",")))
        manifest["files"].append({"basename": "iostore_paths.txt", "status": "listing",
                                  "bytes": os.path.getsize(listing),
                                  "why": "容器条目清单，便于核对路径与大小"})

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    total = sum(e.get("bytes", 0) for e in manifest["files"])
    log("")
    log("=" * 72)
    log("完成：%d 个文件，合计 %s 字节" % (len(manifest["files"]), format(total, ",")))
    log("输出目录：%s" % out_dir)
    log("请把整个目录（game_inputs/）拷回本机，放在本仓库的同一父目录下")
    log("=" * 72)
    if buildid and buildid != EXPECTED_BUILDID:
        log("[!] 注意：buildid %s 与预期 %s 不一致，取回的输入可能对不上版本。"
            % (buildid, EXPECTED_BUILDID))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
