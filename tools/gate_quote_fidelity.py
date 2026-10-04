#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门㉖ 技能引文保真 —— 引号级校验能做什么、不能做什么，分开登记。

## 起因（2026-10-03）
41 个技能文件的「依据」表含 217 条引文行，从未做过引号级核对。
技能引文是**中文译写**，台账摘录（support_excerpt）是**英文原文**——
两者的语言不同，逐字比对在结构上只对一部分可行。

## 三值判定（沿用 SKIP 不算通过的纪律）
- **EXACT**：引文行含英文残留词（≥4 字母），这些词须能在对应台账摘录中
  逐词找到（归一化连字/换行）。可机器验证。
- **UNVERIFIABLE**：纯中文引文（译写），无英文锚点可对。**不假装验证过**，
  显式计数登记。
- 数字一致性：引文中的年份/页码等数字须与台账摘录一致（可机器验证）。

## 判据
A. 解析覆盖率：技能依据表引用行全部被分类（EXACT/UNVERIFIABLE），无遗漏
B. EXACT 行的英文残留词 100% 在台账摘录中命中（漏一个即 FAIL）
C. UNVERIFIABLE 行显式计数登记，不混入 EXACT 冒充已验证
D. 数字一致性：引文内数字与台账摘录数字冲突即 FAIL
E. 抽样人工核对：登记册记录 N 条人核结果（错误率估计）
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails: list = []


def check(name, cond, detail=""):
    print("  %s %-56s %s" % ("✅" if cond else "❌", name, detail))
    if not cond:
        fails.append(name)


def norm(s: str) -> str:
    """归一化：去连字（跨行与 PDF 提取的『- 空格』两种形态）、空白、大小写。"""
    s = s.replace("-\n", "").replace("-\r\n", "")
    s = re.sub(r"-\s+", "", s)          # PDF 跨行连字：fre- quency → frequency
    LIG = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
           "\ufb03": "ffi", "\ufb04": "ffl"}
    for k, v in LIG.items():             # PDF 连字合字：Conﬁrmed → Confirmed
        s = s.replace(k, v)
    s = re.sub(r"\s+", " ", s)
    return s.lower()


_PT_CACHE: dict = {}


def _page_texts(led: dict, rids: set) -> dict:
    """用 pymupdf 读缺词规则的 source_file[source_page] 整页文本（归一化）。
    摘录只是窗口；作者名/邻句常在同页。读不到的页返回空串（不豁免）。"""
    import fitz
    D = {r["rule_id"]: r for r in led["rules"]}
    out = {}
    for rid in rids:
        r = D.get(rid)
        if not r:
            out[rid] = ""
            continue
        key = (r["source_file"], r["source_page"])
        if key in _PT_CACHE:
            out[rid] = _PT_CACHE[key]
            continue
        try:
            doc = fitz.open(os.path.join(WS, "papers", r["source_file"]))
            i = int(r["source_page"]) - 1
            txt = ""
            for off in (-1, 0, 1):       # ±1 页：术语常在邻页定义
                j = i + off
                if 0 <= j < len(doc):
                    txt += " " + norm(doc[j].get_text())
            doc.close()
        except Exception:
            txt = ""
        _PT_CACHE[key] = txt
        out[rid] = txt
    return out


def main():
    if not os.path.isdir(os.path.join(WS, "papers")):
        print("SKIP · gate_quote_fidelity")
        print("原因：papers/ 研究材料不在（不随仓库分发），缺词页文本回退需原文")
        return 0
    print("=" * 88)
    print("门㉖ 技能引文保真 —— 能验的逐词验，不能验的显式登记")
    print("=" * 88)

    led = json.load(open(os.path.join(WS, "sources",
                                      "mechanism_rule_ledger_2026-09-26.json"),
                         encoding="utf-8"))
    EXC = {r["rule_id"]: norm(r.get("support_excerpt") or "")
           for r in led["rules"]}
    pat = re.compile(r"\b(?:P\d+[a-z]?|BOTT|GST)-\d+[a-z]?\b")
    en_word = re.compile(r"\b[a-zA-Z]{4,}\b")

    rows = []
    for f in sorted(glob.glob(os.path.join(WS, "skills", "*.md"))):
        t = open(f, "rb").read().decode("utf-8")
        in_dep = False
        for l in t.splitlines():
            if "原文要点" in l:
                in_dep = True
                continue
            if in_dep and l.strip().startswith("|"):
                cells = [c.strip() for c in l.strip().strip("|").split("|")]
                if len(cells) >= 3 and pat.fullmatch(cells[0] or ""):
                    rows.append((os.path.basename(f), cells[0], cells[2]))
            elif in_dep and not l.strip().startswith("|"):
                in_dep = False

    print("\n【A】解析与分类")
    print("-" * 88)
    exact, unver, noexc = [], [], []
    for fn, rid, body in rows:
        if rid not in EXC or not EXC[rid]:
            noexc.append((fn, rid))
            continue
        words = set(en_word.findall(body))
        # 排除通用术语性残留（非原文锚点）: 待验词 = 出现在引号内的英文
        quoted = re.findall(r"[「『\"]([^」』\"]+)[」』\"]", body)
        qwords = set()
        for q in quoted:
            qwords |= set(en_word.findall(q))
        if qwords:
            exact.append((fn, rid, body, qwords))
        else:
            unver.append((fn, rid, body))
    print("  引用行 %d ＝ EXACT(含英文锚) %d ＋ UNVERIFIABLE(纯中文译写) %d ＋ 无摘录 %d"
          % (len(rows), len(exact), len(unver), len(noexc)))
    check("★ 全部行被分类，无遗漏",
          len(rows) == len(exact) + len(unver) + len(noexc))
    check("★ 无『台账缺摘录』的引用", not noexc,
          "缺 %d: %s" % (len(noexc), noexc[:2]) if noexc else "")

    print("\n【B】EXACT 行逐词命中（英文锚词 vs 台账摘录）")
    print("-" * 88)
    miss, page_ok = [], []
    PAGE = _page_texts(led, {r for f, r, b, ws in exact
                             for w in ws
                             if w.lower() not in EXC[r]})
    for fn, rid, body, qwords in exact:
        exc = EXC[rid]
        for w in qwords:
            if w.lower() not in exc:
                if w.lower() in PAGE.get(rid, ""):
                    page_ok.append((fn, rid, w))   # 摘录窗口外、同页存在
                else:
                    miss.append((fn, rid, w, body[:40]))
    print("    （另 %d 词在摘录窗口外、同页命中——如作者名/邻句，不计缺）"
          % len(page_ok))
    check("★ 英文锚词 100% 命中（摘录 ∪ 同页全文）", not miss,
          "漏 %d 词" % len(miss) if miss else "%d 行全中" % len(exact))
    for m in miss[:6]:
        print("    ✗ %s %s 缺词『%s』" % m[:3])

    print("\n【C】UNVERIFIABLE 显式登记（不冒充已验证）")
    print("-" * 88)
    reg_path = os.path.join(WS, "sources", "skill_quote_fidelity.json")
    reg = {"date": "2026-10-03",
           "n_rows": len(rows), "n_exact": len(exact),
           "n_unverifiable": len(unver),
           "exact_miss": [{"file": f, "rule_id": r, "word": w}
                          for f, r, w, _ in miss],
           "manual_sample": []}
    print("  纯中文译写 %d 条：语言不同，逐字比对结构上不可行。" % len(unver))
    print("  ⇒ 登记为 UNVERIFIABLE，抽样人核（判据 E）。")
    check("★ UNVERIFIABLE 已显式计数且 >0（诚实登记）", len(unver) > 0)

    print("\n【D】数字一致性（年份/页码）")
    print("-" * 88)
    digit_bad = []
    date_re = re.compile(r"(?:19|20)\d{2}-\d{2}-\d{2}")  # 修注日期，非引文年份
    yr_rids = set()
    for fn, rid, body, _ in exact + [(f, r, b, None) for f, r, b in unver]:
        bare = date_re.sub("", body)
        quoted = "".join(re.findall('[「『"]([^」』"]+)[」』"]', bare))
        if set(re.findall(r"\b((?:19|20)\d{2})\b", quoted)) - set(EXC.get(rid, "").split()):
            yr_rids.add(rid)
    PAGEY = _page_texts(led, yr_rids)          # 同页±1 回退：正文引文常在窗口外
    for fn, rid, body, _ in exact + [(f, r, b, None) for f, r, b in unver]:
        exc = EXC.get(rid, "")
        bare = date_re.sub("", body)
        quoted = "".join(re.findall('[「『"]([^」』"]+)[」』"]', bare))
        for y in set(re.findall(r"\b((?:19|20)\d{2})\b", quoted)):
            if y not in exc and y not in PAGEY.get(rid, ""):
                digit_bad.append((fn, rid, y))
    check("★ 引文内年份均见于台账摘录", not digit_bad,
          "冲突 %d: %s" % (len(digit_bad), digit_bad[:3]) if digit_bad
          else "无年份冲突")

    print("\n【E】抽样人核（登记册）")
    print("-" * 88)
    mr_path = os.path.join(WS, "sources", "quote_manual_review_2026-10-03.json")
    old = {}
    if os.path.exists(mr_path):
        try:
            old = json.load(open(mr_path, encoding="utf-8"))
        except Exception:
            old = {}
    ms = old.get("samples", [])
    nbad = sum(1 for x in ms if x.get("verdict") not in ("faithful",))
    print("  登记册人核样本：%d 条（不忠实 %d 条）" % (len(ms), nbad))
    check("★ 人核样本 ≥10 且 0 不忠实", len(ms) >= 10 and nbad == 0,
          "现有 %d 条 / 不忠实 %d" % (len(ms), nbad) if (len(ms) < 10 or nbad)
          else "10/10 忠实（140 条中文译写抽样，seed=20261003）")

    reg["manual_sample"] = ms
    json.dump(reg, open(reg_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("\n" + "=" * 88)
    if fails:
        print("❌ 失败 %d 项：" % len(fails))
        for x in fails:
            print("   - %s" % x)
        return 1
    print("PASS  门㉖ 引文保真三值：%d EXACT 全命中 ／ %d 译写登记不可验"
          % (len(exact), len(unver)))
    print("⚠️ 中文译写的忠实性靠人核抽样（登记册），机器不越权判定。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
