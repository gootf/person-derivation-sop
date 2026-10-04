#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""摘录-页码核验（程序化抽取后的正确形态）。

摘录由 build_anchored_excerpts.py 从原文窗口切出，因此核验标准是
「摘录必须逐字出现在声明页上」。比较前只做空白折叠（消除 PDF 抽取的换行），
不做任何语义归一化 —— 归一化会掩盖真实的转写错误。

verdict:
  exact           摘录整体逐字命中
  boundary_shift  摘录内容命中但首尾被裁短（窗口边界），非转写错误
  split_pages     摘录跨页，两半分别命中声明页与相邻页
  MISSING         未命中，必须人工复核
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 发行版不含研究材料：papers/ 不在时显式 SKIP（三值纪律：材料缺失≠失败≠通过）
if not os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "papers")):
    print("SKIP · verify_mechanism_excerpts")
    print("原因：papers/ 研究材料不在（不随仓库分发），摘录-页码核验需原文")
    sys.exit(0)
import pymupdf
from build_anchored_excerpts import page_text, PAPERS, WS, LEDGER

_cache = {}


def npages(fname):
    if fname.lower().endswith(".pdf"):
        if fname not in _cache:
            _cache[fname] = pymupdf.open(os.path.join(PAPERS, fname)).page_count
        return _cache[fname]
    return 1


def flat_of(fname, pg):
    raw, _ = page_text(fname, pg)
    return re.sub(r"\s+", " ", raw or "")


def longest_prefix(ex, flat):
    lo, hi = 0, len(ex)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if ex[:mid] in flat:
            lo = mid
        else:
            hi = mid - 1
    return lo


def main():
    led = json.load(open(LEDGER, encoding="utf-8"))
    rows = []
    for r in led["rules"]:
        fn, pg = r["source_file"], r["source_page"]
        ex = re.sub(r"\s+", " ", r.get("support_excerpt", "")).strip()
        if not ex:
            rows.append((r["rule_id"], "NO_EXCERPT", 0.0, f"{fn} p.{pg}")); continue
        flat = flat_of(fn, pg)
        if not flat.strip():
            rows.append((r["rule_id"], "NO_PAGE_TEXT", 0.0, f"{fn} p.{pg}")); continue
        if ex in flat:
            rows.append((r["rule_id"], "exact", 1.0, f"{fn} p.{pg}")); continue

        pgi = int(pg) if str(pg).isdigit() else None
        if pgi:
            half = len(ex) // 2
            a, b = ex[:half + 40].rstrip(), ex[half - 40:].lstrip()
            for p2 in (pgi - 1, pgi + 1):
                if not (1 <= p2 <= npages(fn)):
                    continue
                f2 = flat_of(fn, p2)
                if a in f2 and b in f2:
                    rows.append((r["rule_id"], "split_pages", 1.0, f"{fn} p.{pg}~{p2}"))
                    break
            else:
                lo = longest_prefix(ex, flat)
                v = "boundary_shift" if lo >= 0.9 * len(ex) else "MISSING"
                rows.append((r["rule_id"], v, round(lo / len(ex), 3), f"{fn} p.{pg}"))
        else:
            lo = longest_prefix(ex, flat)
            v = "boundary_shift" if lo >= 0.9 * len(ex) else "MISSING"
            rows.append((r["rule_id"], v, round(lo / len(ex), 3), f"{fn} p.{pg}"))

    tally = {}
    for x in rows:
        tally[x[1]] = tally.get(x[1], 0) + 1
    bad = [x for x in rows if x[1] in ("MISSING", "NO_EXCERPT", "NO_PAGE_TEXT")]

    print(f"total={len(rows)}  " + "  ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    for label, group in (("MISSING", bad),
                         ("boundary_shift（窗口裁短，非转写错误）",
                          [x for x in rows if x[1] == "boundary_shift"])):
        if group:
            print(f"\n--- {label} ---")
            for x in group:
                print(f"  {x[0]:10s} {x[1]:14s} score={x[2]:.2f}  {x[3]}")

    out = {"ledger": os.path.basename(LEDGER), "total": len(rows), "tally": tally,
           "rows": [{"rule_id": a, "verdict": b, "score": c, "where": d} for a, b, c, d in rows]}
    p = os.path.join(WS, "sources", "mechanism_ledger_excerpt_verification.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nsaved:", p)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
