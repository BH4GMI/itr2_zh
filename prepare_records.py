# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""从 ref_ko 的原始提取数据 + 本仓库的中文映射，生成构建所需的 records_with_zh.json。

输入：
  ref_ko/translations/records_with_ko.json         （外部参考项目的 5496 条位置记录）
  ref_ko/translations/unique_sources_with_ko.json  （3772 条唯一英文原文）
  zh_sources.json                                  （source_id -> 简体中文，本仓库的翻译数据）
输出：
  records_with_zh.json                             （schema 与 records_with_ko.json 相同，ko 字段换成中文）
"""
import collections
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
KO = os.path.join(ROOT, "ref_ko", "translations")
ZH = os.path.join(ROOT, "zh_sources.json")
OUT = os.path.join(ROOT, "records_with_zh.json")


def load(path):
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8", "utf-8-sig", "gb18030", "cp1252"):
        try:
            return json.loads(raw.decode(enc))
        except Exception:
            continue
    raise SystemExit("无法解码: " + path)


def main():
    if not os.path.exists(ZH):
        raise SystemExit("缺少 zh_sources.json")
    recs_path = os.path.join(KO, "records_with_ko.json")
    uni_path = os.path.join(KO, "unique_sources_with_ko.json")
    for p in (recs_path, uni_path):
        if not os.path.exists(p):
            raise SystemExit("缺少 %s\n请先执行: git clone https://github.com/refracta/itr2-ko ref_ko" % p)

    zh = load(ZH)
    recs = load(recs_path)
    uni = load(uni_path)

    missing = [u["source_id"] for u in uni if not str(zh.get(u["source_id"], "")).strip()]
    print("唯一原文 %d 条，已译 %d 条，缺失 %d 条" % (len(uni), len(uni) - len(missing), len(missing)))
    if missing:
        for sid in missing[:20]:
            print("   缺:", sid)

    untranslated = 0
    for r in recs:
        z = zh.get(r["source_id"])
        if z:
            r["ko"] = z
        else:
            untranslated += 1
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False)

    containers = collections.Counter(r["container"] for r in recs)
    print("写出 %s：%d 条记录（未译 %d）" % (OUT, len(recs), untranslated))
    print("按容器:", dict(containers))


if __name__ == "__main__":
    main()
