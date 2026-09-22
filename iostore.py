# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""Into the Radius 2 IoStore (.utoc/.ucas) extractor.

Layout (all little-endian unless stated), verified against build 24024260:
  [0x00] 16B magic "-==--==--==--==-"
  [0x10] u32 version, headerSize, tocEntryCount, blockEntryCount, blockEntrySize,
         methodNameCount, methodNameLength, compressionBlockSize
  [0x30] u32 directoryIndexSize, u32 partitionCount, u64 containerId, 16B keyGuid, ...
  [headerSize]                     chunkIds:   12B * tocEntryCount
  [headerSize + 12N]               offsetLens: 10B * tocEntryCount   (5B BIG-endian logical
                                   offset + 5B BIG-endian logical length, in the *uncompressed*
                                   virtual stream)
  [headerSize + 22N + extra]       blocks:     12B * blockEntryCount
                                   (40-bit LE physical offset, 24-bit LE cSize,
                                    24-bit LE uSize, u8 method: 0 = stored, 1..n = methodName[n-1])
  [ ... ]                          method names: methodNameLength * methodNameCount
  [ ... ]                          directory index, then the perfect hash map
The directory index / block table are located from the mount-point string so that the
unknown `extra` field size does not matter.
"""
import ctypes, struct, os, sys, argparse, re, math

ROOT = r"D:\SteamLibrary\steamapps\common\IntoTheRadius2\IntoTheRadius2\Content\Paks"
OODLE = r"C:\Program Files (x86)\Steam\steamapps\common\Call of Duty HQ\oo2core_8_win64.dll"

_lib = ctypes.CDLL(OODLE)
_dec = _lib.OodleLZ_Decompress
_dec.restype = ctypes.c_longlong
_dec.argtypes = [ctypes.c_char_p, ctypes.c_longlong, ctypes.c_char_p, ctypes.c_longlong,
                 ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_longlong,
                 ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_longlong, ctypes.c_int]


def oodle(src, raw_len):
    buf = ctypes.create_string_buffer(raw_len + 65536)
    r = _dec(src, len(src), buf, raw_len, 1, 0, 0, None, 0, None, None, None, 0, 3)
    return buf.raw[:r] if r > 0 else None


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


class Container:
    def __init__(self, stem, verbose=True):
        self.stem = stem
        self.utoc_path = os.path.join(ROOT, stem + ".utoc")
        self.ucas_path = os.path.join(ROOT, stem + ".ucas")
        self.utoc = open(self.utoc_path, "rb").read()
        self.ucas = open(self.ucas_path, "rb") if os.path.exists(self.ucas_path) else None
        self.ucas_size = os.path.getsize(self.ucas_path) if self.ucas else 0
        d = self.utoc
        assert d[:16] == b"-==--==--==--==-", "not an IoStore toc"
        (self.version, self.header_size, self.n_entries, self.n_blocks, self.block_entry_size,
         self.n_methods, self.method_name_len, self.block_size) = struct.unpack_from("<IIIIIIII", d, 0x10)
        self.dir_size, self.n_partitions = struct.unpack_from("<II", d, 0x30)
        self._parse(verbose)

    def _parse(self, verbose=True):
        d = self.utoc
        base = self.header_size
        # ---- chunk ids ----
        self.chunk_ids = [d[base + 12 * i: base + 12 * (i + 1)] for i in range(self.n_entries)]
        # ---- logical offset/length table: 10 bytes each, two BIG-endian 5-byte fields ----
        ol = base + 12 * self.n_entries
        self.offset_lengths = []
        for i in range(self.n_entries):
            raw = d[ol + 10 * i: ol + 10 * i + 10]
            self.offset_lengths.append((int.from_bytes(raw[:5], "big"), int.from_bytes(raw[5:10], "big")))
        # ---- directory index: locate by the mount point, then derive the rest backwards ----
        search_from = ol + 10 * self.n_entries
        mount_pos = d.find(b"../../../", search_from)
        if mount_pos < 4:
            raise RuntimeError(f"{self.stem}: cannot locate directory index")
        self.dir_off = mount_pos - 4
        mlen = struct.unpack_from("<i", d, self.dir_off)[0]
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
        # ---- block table: sits right before the method-name table ----
        self.method_off = self.dir_off - self.n_methods * self.method_name_len
        self.methods = [d[self.method_off + i * self.method_name_len:
                          self.method_off + (i + 1) * self.method_name_len].split(b"\0")[0].decode("latin1")
                        for i in range(self.n_methods)]
        self.blocks_off = self.method_off - self.n_blocks * self.block_entry_size
        self.blocks = []
        for i in range(self.n_blocks):
            x = d[self.blocks_off + 12 * i: self.blocks_off + 12 * i + 12]
            self.blocks.append((int.from_bytes(x[:5], "little"), int.from_bytes(x[5:8], "little"),
                                int.from_bytes(x[8:11], "little"), x[11]))
        self.paths = self._walk()
        if verbose:
            print(f"[{self.stem}] v{self.version} entries={self.n_entries:,} blocks={self.n_blocks:,} "
                  f"methods={self.methods} mount={self.mount!r} paths={len(self.paths):,}")

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

    # ---------------- extraction ----------------
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
                if m == 0:
                    data = payload
                else:
                    data = oodle(payload, usz)
                    if data is None:
                        raise RuntimeError(f"oodle failed at block {bi} ({po:#x})")
                take = min(bs - in_block, remaining)
                out += data[in_block:in_block + take]
                remaining -= take
                in_block = 0
        return bytes(out)

    def extract(self, path):
        u = self.paths.get(path)
        if u is None and not path.startswith("../../../"):
            u = self.paths.get("../../../" + path.lstrip("/"))
        return None if u is None else self.read_chunk(u)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "extract", "info"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("-c", "--container", default="pakchunk0-Windows")
    a = ap.parse_args()
    c = Container(a.container)
    if a.cmd == "list":
        rx = re.compile(a.arg or ".*", re.I)
        for p in sorted(c.paths):
            if rx.search(p):
                print(f"  {c.paths[p]:>7}  {p}")
    elif a.cmd == "info":
        print("entries:", len(c.offset_lengths), "first 3:", c.offset_lengths[:3])
        for p in sorted(c.paths)[:10]:
            print("  ", p, c.paths[p])
    else:
        data = c.extract(a.arg)
        if data is None:
            tail = a.arg.split("/")[-1]
            print("NOT FOUND:", a.arg)
            print("similar:", [p for p in c.paths if tail in p][:8])
            sys.exit(2)
        out = a.out or os.path.basename(a.arg)
        open(out, "wb").write(data)
        print(f"wrote {out}: {len(data):,} bytes  head={data[:16].hex(' ')}")
