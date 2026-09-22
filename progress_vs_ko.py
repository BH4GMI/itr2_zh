# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
import json, csv, os, collections

ROOT = r"D:\SteamLibrary\steamapps\common\itr2_zh"
KO = os.path.join(ROOT, "ref_ko", "translations")
OUT = os.path.join(ROOT, "progress_report.md")

def load(p):
    with open(p, "rb") as f:
        raw = f.read()
    for enc in ("utf-8", "utf-8-sig", "gb18030", "cp1252"):
        try:
            return json.loads(raw.decode(enc))
        except Exception:
            continue
    raise SystemExit("cannot decode " + p)

recs = load(os.path.join(KO, "records_with_ko.json"))
unis = load(os.path.join(KO, "unique_sources_with_ko.json"))

# my current translations
csv_path = os.path.join(ROOT, "pack", "translations_zh-Hans.csv")
rows = []
with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
    rd = csv.DictReader(f)
    cols = rd.fieldnames
    for r in rd:
        rows.append(r)

# build lookup of my translations by english source
def pick(d, names):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return None

mine = {}
for r in rows:
    src = pick(r, ["english", "source", "Source", "text", "key"])
    tgt = pick(r, ["chinese", "zh", "target", "translation", "zh-Hans", "value", "text_zh"])
    if src is not None:
        mine[src] = tgt

uniq_sources = [u["source"] for u in unis]
have = [s for s in uniq_sources if s in mine and (mine[s] or "").strip()]
miss = [s for s in uniq_sources if s not in mine or not (mine[s] or "").strip()]

L = []
def w(s=""):
    L.append(str(s))

w("# ITR2 汉化包进度报告\n")
w("生成时间基准数据：refracta/itr2-ko 记录 %d 条 / 唯一英文源 %d 条；本地 pack/translations_zh-Hans.csv %d 行\n" % (len(recs), len(unis), len(rows)))
w("CSV 列：`%s`\n" % "`, `".join(cols or []))
w("## 覆盖率\n")
w("| 指标 | 数值 |")
w("| --- | ---: |")
w("| 韩方骨架唯一英文源 | %d |" % len(uniq_sources))
w("| 我已翻译（源文精确匹配） | %d |" % len(have))
w("| 尚未覆盖 | %d |" % len(miss))
w("| 覆盖率 | %.1f%% |" % (100.0 * len(have) / max(1, len(uniq_sources))))
w("")

# translatable only
tr = [u for u in unis if u.get("translatable")]
have_t = [u for u in tr if u["source"] in mine and (mine[u["source"]] or "").strip()]
w("| 其中可翻译源 | %d |" % len(tr))
w("| 可翻译且已覆盖 | %d (%.1f%%) |" % (len(have_t), 100.0 * len(have_t) / max(1, len(tr))))
w("| 可翻译未覆盖 | %d |" % (len(tr) - len(have_t)))
w("")

# char volume
tot_chars = sum(u["char_len"] for u in tr)
got_chars = sum(u["char_len"] for u in have_t)
w("| 可翻译字符总量 | %d |" % tot_chars)
w("| 已覆盖字符 | %d (%.1f%%) |" % (got_chars, 100.0 * got_chars / max(1, tot_chars)))
w("")

# breakdown by container
byc = collections.Counter()
for u in unis:
    for c in u.get("containers", []):
        byc[c] += 1
w("## 按容器（唯一源）\n")
w("| 容器 | 唯一源数 |")
w("| --- | ---: |")
for k, n in byc.most_common():
    w("| `%s` | %d |" % (k, n))
w()

# missing by bucket length
buckets = collections.Counter()
for s in miss:
    n = len(s)
    b = "1-3" if n <= 3 else "4-10" if n <= 10 else "11-30" if n <= 30 else "31-80" if n <= 80 else "81-200" if n <= 200 else "201+"
    buckets[b] += 1
w("## 未覆盖源长度分布\n")
w("| 长度 | 条数 |")
w("| --- | ---: |")
for b in ["1-3", "4-10", "11-30", "31-80", "81-200", "201+"]:
    if buckets[b]:
        w("| %s | %d |" % (b, buckets[b]))
w()

# top missing containers for uasset
miss_ids = set()
for u in unis:
    if u["source"] in mine and (mine[u["source"]] or "").strip():
        continue
    miss_ids.add(u["source_id"])
mc = collections.Counter()
for r in recs:
    if r["source_id"] in miss_ids:
        mc[r["container"]] += 1
w("## 未覆盖记录按容器\n")
w("| 容器 | 记录数 |")
w("| --- | ---: |")
for k, n in mc.most_common():
    w("| `%s` | %d |" % (k, n))
w()

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))

# also dump the missing queue for translation
q = []
for u in unis:
    if u["source"] in mine and (mine[u["source"]] or "").strip():
        continue
    q.append({
        "source_id": u["source_id"],
        "source": u["source"],
        "char_len": u["char_len"],
        "translatable": u["translatable"],
        "containers": u["containers"],
        "placeholders": u.get("placeholders", []),
        "reference_ru": u.get("reference_ru"),
        "reference_ja": u.get("reference_ja"),
    })
with open(os.path.join(ROOT, "todo_sources.json"), "w", encoding="utf-8") as f:
    json.dump(q, f, ensure_ascii=False, indent=1)

print("wrote", OUT)
print("unique=%d have=%d miss=%d coverage=%.1f%%" % (len(uniq_sources), len(have), len(miss), 100.0*len(have)/max(1,len(uniq_sources))))
print("translatable=%d have_t=%d (%.1f%%)" % (len(tr), len(have_t), 100.0*len(have_t)/max(1,len(tr))))
