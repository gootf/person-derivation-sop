#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门⑧ SK-07 归因折扣 —— 验证「非单调」这个修正确实必要。

## 本门只测一件事

原 SK-07 的隐含模型是**单调折扣**：
`强度 = 基础 × g(情境理由数)`，g 单调递减，无条件。

若这个模型在某些情形下**给出错误答案**，而新设计给出正确的，
则修正是必要的。门⑧ 逐条列出这些情形。

## 关键约束

⚠️ 不能为了让新设计"通过"而编造反例。
   每个反例必须满足：**原文逐字支持**，
   且引文页码可核（`sk07_attribution.VERBATIM` 记录了 PDF 物理页）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sk07_attribution import (Attribution, discount, VERBATIM, EXTERNAL_SOURCE)

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def monotonic_discount(base=1.0, n_reasons=1):
    """原设计：单调衰减。理由越多，折扣越狠。无条件。"""
    return base * (1.0 - 0.4 * min(n_reasons, 2))


def main():
    if not os.path.exists(os.path.join(WS, "_tmp", "GilbertMalone1996.pdf")):
        print("SKIP · gate_sk07_attribution")
        print("原因：_tmp/GilbertMalone1996.pdf 不在（不随仓库分发），术语归属核实需原文")
        return 0
    print("=" * 76)
    print("门⑧ SK-07 归因折扣 · 非单调性验证")
    print("=" * 76)
    print("  外部依据：%s (%s)" % (EXTERNAL_SOURCE["citation"],
                                  EXTERNAL_SOURCE["url"].split("/")[-1]))
    fails = []

    # ── 1 引文可核性 ──
    print("\n" + "-" * 76)
    print("【1】外部依据引文登记")
    print("-" * 76)
    for k, (pg, txt) in VERBATIM.items():
        print("  %-22s PDF 物理页 %-3d %s…" % (k, pg, txt[:66]))
    print("  ✅ 引文页码已登记，%d 条" % len(VERBATIM))

    # ── 2 单调模型会做错的三种情形 ──
    print("\n" + "-" * 76)
    print("【2】单调模型 vs 非单调设计 · 逐情形对照")
    print("-" * 76)
    print("  %-16s %-14s %-14s %s" % ("情形", "单调(原设计)", "非单调(新)", "是否修正"))
    print("  " + "-" * 62)

    cases = [
        ("外加约束", dict(constraint_kind="imposing", self_selected=False,
                          enduring=False, actually_constrained=True)),
        ("自生约束", dict(constraint_kind="self_induced", self_selected=True,
                          enduring=False, actually_constrained=True)),
        ("弥散约束", dict(constraint_kind="omnipresent", self_selected=False,
                          enduring=True, actually_constrained=True)),
        ("多余约束", dict(constraint_kind="superfluous", self_selected=False,
                          enduring=False, actually_constrained=False)),
        ("未知", dict(constraint_kind="unknown", self_selected=False,
                      enduring=False, actually_constrained=True)),
    ]
    corrected = 0
    for name, kw in cases:
        a = Attribution(1.0, "情境提供了明显理由", **kw)
        r = discount(a)
        new = r.discount_applied
        old = monotonic_discount(1.0, 1) < 1.0   # 原设计：有理由就折扣
        differs = (old != new)
        if differs:
            corrected += 1
        print("  %-16s %-14s %-14s %s"
              % (name, "折扣" if old else "不折扣",
                 "折扣" if new else "不折扣",
                 "✅ 修正" if differs else "— 同"))

    print("\n  %d/%d 情形被修正" % (corrected, len(cases)))
    if corrected == 0:
        fails.append("无情形被修正 ⇒ 重建空转")
        print("  ❌ 空转")
    else:
        print("  ✅ 单调模型在 %d 种情形下给出错误答案" % corrected)

    # ── 3 三种失效情形必须**不折扣** ──
    print("\n" + "-" * 76)
    print("【3】三种已知失效情形必须不折扣（Gilbert & Malone 的直接后果）")
    print("-" * 76)
    for name, kw in [("self_induced", dict(constraint_kind="self_induced")),
                     ("omnipresent", dict(constraint_kind="omnipresent")),
                     ("superfluous", dict(constraint_kind="superfluous"))]:
        a = Attribution(1.0, "有理由", **kw)
        r = discount(a)
        mark = "✅" if not r.discount_applied else "❌"
        print("  %s %-14s 折扣=%s" % (mark, name, r.discount_applied))
        if r.discount_applied:
            fails.append("%s 被错误折扣" % name)

    # ── 4 正常折扣仍须生效（防过度修正） ──
    print("\n" + "-" * 76)
    print("【4】外加约束下折扣**仍须生效**（防止把折扣整个废掉）")
    print("-" * 76)
    a = Attribution(1.0, "情境明确要求这样做", constraint_kind="imposing")
    r = discount(a)
    print("  折扣=%s ｜ %s" % (r.discount_applied, r.notes[-1][:70]))
    if r.discount_applied:
        print("  ✅ 未把折扣原则整个废掉")
    else:
        fails.append("外加约束未折扣 —— 过度修正")

    # ── 5 unknown 必须标记需人工（不得静默） ──
    print("\n" + "-" * 76)
    print("【5】unknown 必须显式标记人工裁决（不得静默默认）")
    print("-" * 76)
    a = Attribution(1.0, "不明", constraint_kind="unknown")
    r = discount(a)
    print("  折扣=%s ｜ needs_manual=%s" % (r.discount_applied,
                                          getattr(r, "needs_manual", False)))
    if getattr(r, "needs_manual", False):
        print("  ✅ 已标记 MANUAL，与 SK-16 约定一致")
    else:
        fails.append("unknown 未标记人工 —— 静默默认")

    # ── 6 自生约束须反向记为「倾向的证据」 ──
    print("\n" + "-" * 76)
    print("【6】自生约束 ⇒ 情境理由是**倾向的证据**")
    print("-" * 76)
    a = Attribution(1.0, "他自己选择进入的", constraint_kind="self_induced")
    r = discount(a)
    if getattr(r, "disposition_is_evidence", False):
        print("  ✅ disposition_is_evidence=True")
        print("     「主动进入支持性情境」是**倾向的正面证据**，不是干扰")
    else:
        fails.append("自生约束未反向记为倾向证据")

    # ── 7 弥散约束须标记「情境塑造了倾向」 ──
    print("\n" + "-" * 76)
    print("【7】弥散约束 ⇒ 标记 situation_formed_disposition")
    print("-" * 76)
    a = Attribution(1.0, "长期环境", constraint_kind="omnipresent")
    r = discount(a)
    if getattr(r, "situation_formed_disposition", False):
        print("  ✅ situation_formed_disposition=True")
        print("     「情境持久→倾向被塑造」是与「倾向→行为」不同的因果方向")
    else:
        fails.append("弥散约束未标记情境塑造倾向")

    # ── 8 依据归属：Gilbert 原文究竟有几类？ ──
    print("\n" + "-" * 76)
    print("【8】★ 依据归属：核实 imposing／unknown 是否真出自 Gilbert 原文")
    print("-" * 76)
    import pymupdf as _fitz
    # ⚠️ 判据修正（2026-09-27）：首版写 os.path.dirname(WS) 多退了一层，
    #    WS 本身即工作区根，应直接拼接。
    _src = os.path.join(WS, "_tmp", "GilbertMalone1996.pdf")
    if not os.path.exists(_src):
        fails.append("Gilbert 原文缺失，无法核实术语归属")
        print("  ❌ 缺 %s" % _src)
    else:
        _d = _fitz.open(_src)
        _full = " ".join(_d[i].get_text() for i in range(_d.page_count)).lower()
        counts = {t: _full.count(t) for t in
                  ("self-induced", "omnipresent", "superfluous", "imposing", "unknown")}
        for t, c in counts.items():
            print("    %-14s 全文 %2d/%d 页 命中 %-3d  %s"
                  % (t, sum(1 for i in range(_d.page_count)
                            if t in _d[i].get_text().lower()), _d.page_count,
                     c, "原文" if c > 0 else "★ 自建（0 命中）"))
        if all(counts[t] > 0 for t in ("self-induced", "omnipresent", "superfluous")):
            print("  ✅ 三类原文术语均有支撑")
        else:
            fails.append("self-induced/omnipresent/superfluous 缺原文支撑")
        # ⛔ 核心判据：若 imposing/unknown 其实在原文里，
        #    则"自建"标注有误 —— 门必须报出来，不能默认通过。
        if counts["imposing"] == 0 and counts["unknown"] == 0:
            print("  ✅ ★ imposing／unknown 确为自建（原文 0 命中），标注属实")
        else:
            fails.append("imposing/unknown 竟在原文出现（命中 imposing=%d unknown=%d）"
                         "，自建标注有误" % (counts["imposing"], counts["unknown"]))

    print("\n" + "=" * 76)
    print("【判据】")
    if fails:
        for f in fails:
            print("  ❌ %s" % f)
        return 1
    print("  ✅ 引文页码已登记")
    print("  ✅ 单调模型确在 %d 种情形下出错" % corrected)
    print("  ✅ 三种失效情形不折扣，正常折扣仍生效")
    print("  ✅ unknown 标记 MANUAL，自生/弥散各有专门标记")
    print()
    print("  ⚠️ 仍为自建：imposing／unknown **两类术语本身**（原文 0 命中）；")
    print("     unknown 的默认『不折扣』是保守选择，非文献结论。")
    print("     文献只说『当情境与倾向因果相关时折扣不是有效逻辑工具』，")
    print("     未说无法判断时该怎么办。")
    print()
    print("PASS  门⑧ 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
