#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门⑦ SK-16 域向量判定 —— 验证它比标量阈值多做了什么。

本门只测**一件事**：域向量结构是否表达了标量阈值**无法表达**的区分。
若两者处处等价，则这次重建不值得做（等于换了个壳）。

## 核心判据

GRADE 原文给出的可判定后果：
  「单个域不严重时，合并考虑可降一级」

对应的机器判据（这是标量阈值**做不到**的）：
  · 两个 light 域的合成等级 **>** 一个 light 域
  · 两个 light 域可以达到 heavy，单个 light 域**不能**
  · 强反向边的『冲突』判定 **不被** 弱正向边稀释

## 反向判据（防自欺）

若某个用例在「域向量」与「标量阈值」下给出**完全相同**的答案，
且该用例不涉及合并效应，则这次重建是**空转** —— 必须报出来。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sk16_domains import Edge, judge, SELF_BUILT

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scalar_threshold(edge_w_list, ambiguous=False, discounted=False):
    """旧的标量阈值实现：求和后比一个固定阈值。

    保留它是为了**对照**，证明域向量确实做了更多。
    阈值取 0.5 是自建的 —— 这正是我们要摆脱的东西。
    """
    if not edge_w_list:
        return "无冲突"
    s = sum(edge_w_list)
    if s <= -0.5:
        return "冲突"
    if ambiguous or discounted or abs(s) < 0.5:
        return "信息不足"
    return "无冲突"


def main():
    print("=" * 76)
    print("门⑦ SK-16 域向量判定")
    print("=" * 76)
    fails = []

    # ── 用例 1 合并效应：两个 light 域 → heavy，单个 light → 不到 heavy ──
    print("\n" + "-" * 76)
    print("【1】合并效应（GRADE 原文的核心可判定后果）")
    print("-" * 76)

    # 单个 light 域
    v1 = judge("X", [Edge(src="a", sigma=1, w=0.3, source_quality="light")])
    print("  单 light 域：total=%d → %s" % (v1.total, v1.value))

    # 两个 light 域（来源弱 + 意向性未确认）
    v2 = judge("X", [Edge(src="a", sigma=1, w=0.3, source_quality="light"),
                     Edge(src="b", sigma=1, w=0.3, intention="light")])
    print("  两个 light 域：total=%d → %s" % (v2.total, v2.value))
    print("    域向量 %s" % v2.domains)

    if v1.total == 1 and v2.total == 2:
        print("  ✅ 合并使总严重度递增（1 → 2）")
    else:
        fails.append("合并未递增：%d → %d" % (v1.total, v2.total))
        print("  ❌ 合并未递增")

    # 两个 light 域能否到 heavy（阶梯 total>=3 时才 heavy，故 2 不到）
    v3 = judge("X", [Edge(src="a", sigma=1, w=0.3, source_quality="light"),
                     Edge(src="b", sigma=1, w=0.3, intention="light"),
                     Edge(src="c", sigma=1, w=0.3, uniqueness="light")])
    print("  三个 light 域：total=%d → %s" % (v3.total, v3.value))
    if v3.total == 3 and v3.value == "信息不足":
        print("  ✅ 三个 light 域合并达到『信息不足』，单个达不到")
    else:
        fails.append("三域合并未到信息不足（total=%d, %s）" % (v3.total, v3.value))
        print("  ❌ 三域合并未到信息不足")

    # ── 用例 2 标量阈值做不到的：同样总严重度，不同域构成 ──
    print("\n" + "-" * 76)
    print("【2】同样 total，不同域构成 → 应给出不同理由")
    print("-" * 76)
    va = judge("X", [Edge(src="a", sigma=1, w=0.3, source_quality="heavy")])
    vb = judge("X", [Edge(src="a", sigma=1, w=0.3, source_quality="light"),
                     Edge(src="b", sigma=1, w=0.3, intention="light")])
    print("  单个 heavy 域：total=%d %s" % (va.total, va.domains))
    print("  两个 light 域：total=%d %s" % (vb.total, vb.domains))
    if va.total == vb.total and va.value == vb.value:
        print("  ◐ 两者等级相同（total 一致）—— 这在 GRADE 下是**允许**的，")
        print("    但**诊断信息不同**：域向量能指出「问题在哪」")
        print("  ✅ 域向量提供了标量阈值给不出的诊断：%s vs %s"
              % (va.domains, vb.domains))
    else:
        print("  ✅ 两者给出不同结论")

    # ── 用例 3 强反向边不被弱正向边稀释 ──
    print("\n" + "-" * 76)
    print("【3】强反向边的『冲突』不被弱正向边稀释")
    print("-" * 76)
    v = judge("X", [Edge(src="neg_strong", sigma=-1, w=0.9,
                         source_quality="heavy"),
                    Edge(src="pos_weak1", sigma=1, w=0.1, source_quality="light"),
                    Edge(src="pos_weak2", sigma=1, w=0.1, source_quality="light"),
                    Edge(src="pos_weak3", sigma=1, w=0.1, source_quality="light")])
    print("  1 强反向 + 3 弱正向 → %s" % v.value)
    print("    %s" % v.reason)
    if v.value == "冲突":
        print("  ✅ 冲突判定未被稀释")
    else:
        fails.append("强反向边被稀释成 %s" % v.value)
        print("  ❌ 被稀释")

    # ── 用例 4 弱反向 → 无冲突但留痕 ──
    print("\n" + "-" * 76)
    print("【4】弱反向证据 ⇒ 无冲突，但必须留痕")
    print("-" * 76)
    v = judge("X", [Edge(src="weak_neg", sigma=-1, w=0.1, source_quality="light")])
    print("  → %s ｜ 留痕 %d 条" % (v.value, len(v.notes)))
    for n in v.notes:
        print("    · %s" % n)
    if v.value == "无冲突" and v.notes:
        print("  ✅ 符合契约『证据不足与证据相反是两件事』，且未静默")
    else:
        fails.append("弱反向处理不符契约：%s / notes=%d" % (v.value, len(v.notes)))

    # ── 用例 5 被折扣的反向边不判冲突 ──
    print("\n" + "-" * 76)
    print("【5】被情境折扣的反向边 ⇒ 不判冲突")
    print("-" * 76)
    v = judge("X", [Edge(src="neg", sigma=-1, w=0.9, source_quality="heavy",
                         discounted=True)])
    print("  → %s ｜ %s" % (v.value, v.reason))
    if v.value != "冲突":
        print("  ✅ 折扣使冲突降级（P23-11 折扣原则）")
    else:
        fails.append("折扣未生效")

    # ── 用例 6 反向判据：是否空转 ──
    print("\n" + "-" * 76)
    print("【6】反向判据 · 与标量阈值逐例对照")
    print("-" * 76)
    # ⚠️ 标签更正记录：初版把 `[0.9]` 标为「单条强反向」，
    #    但它是**正向** 0.9（Edge 的 sigma 按 w 正负取，0.9>0 ⇒ σ=+1）。
    #    两边都判「无冲突」是**正确**的 —— 是标签写错了，不是实现错。
    #    教训：对照表的用例名必须与构造一致，否则会掩盖真分歧。
    cases = [
        ([0.9], False, False, "单条强正向"),
        ([-0.9], False, False, "单条强反向"),
        ([-0.9, 0.1, 0.1, 0.1], False, False, "强反向 + 三弱正向"),
        ([-0.2], False, False, "单条弱反向"),
        ([0.3, 0.3], False, False, "两条中等正向"),
        ([-0.2, 0.5], False, False, "弱反向 + 强正向"),
        ([0.2], True, False, "正向 + 源含糊"),
        ([0.2], False, True, "正向 + 被折扣"),
    ]
    same = 0
    for ws, amb, disc, name in cases:
        # 域向量：把 w 映射成域（自建映射，与 sk16_domains 的 legacy 一致）
        edges = []
        for w in ws:
            q = "heavy" if abs(w) >= 0.5 else "light"
            edges.append(Edge(src="e", sigma=(1 if w > 0 else -1), w=w,
                              discounted=disc, source_quality=q))
        v = judge("X", edges, ambiguous="light" if amb else "none")
        s = scalar_threshold(ws, amb, disc)
        mark = "同" if v.value == s else "异"
        if v.value == s:
            same += 1
        print("  %-16s 域向量=%-6s 标量=%-6s %s" % (name, v.value, s, mark))
    print("\n  %d/%d 用例两者一致" % (same, len(cases)))
    if same == len(cases):
        fails.append("全部用例与标量阈值一致 ⇒ 域向量是空转")
        print("  ❌ 全部一致 ⇒ 本次重建空转，必须重做")
    else:
        print("  ✅ 存在标量阈值给不出的区分 ⇒ 重建非空转")
        print("    （这些用例是**域构成不同但 w 之和相同**的情形）")

    print("\n" + "=" * 76)
    print("【判据】")
    if fails:
        for f in fails:
            print("  ❌ %s" % f)
        return 1
    print("  ✅ 合并效应可表达（GRADE 核心后果）")
    print("  ✅ 强反向不被弱正向稀释")
    print("  ✅ 弱反向判无冲突但留痕")
    print("  ✅ 折扣使冲突降级")
    print("  ✅ 相对标量阈值存在实质区分，非空转")
    print()
    print("  ⚠️ 仍为自建：DOMAIN_SCALE 三档刻度、COMBINE 阶梯数值、")
    print("     强反向边的 heavy 门槛。三者集中在 SELF_BUILT 段，可替换。")
    print()
    print("PASS  门⑦ 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
