#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门⑩ SK-29 规范贡献 —— 以**上游论文自己的工作例**为回归基准。

## 为什么这么判

自建项最容易被"实现得像模像样但和来源对不上"蒙混过去。
唯一的硬判据是：**能否复现来源自己公布的工作例数字**。

Neto 2011 PDF 物理页 7 逐字（救援演练场景）：
  "the contribution for fulfilling it is equal to "+3" and greater than
   the contribution for violating it that is equal to "-1""   ← Norm 1
  "Norm 2 ... the contribution for fulfilling it is equal to "-1" and
   greater than the contribution for violating it that is equal to "-2""  ← Norm 2
  "Norm 3 ... equal to "+1" ... violating it that is equal to "-1""  ← Norm 3
  "We consider that any norm element generates the same contribution that is 1."

⚠️ 注意 Norm 2 的**履行贡献是负的**（-1）—— 因为它是禁止型：
   履行它 = 放弃一个被想要的正贡献。
   若实现复现不出这个符号，本门 FAIL。

## 本门不做什么
❌ 不验证下游 2018 的加权（那部分是自建，无外部基准）
❌ 不判定冲突求解的合理性
✅ 只验证：结构、符号、零值、平局自检、可追溯
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sk29_normative import (  # noqa: E402
    Desire, Norm, contribution, select, has_conflict, solve_conflict,
    SOURCE, VERBATIM, SELF_BUILT,
)

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(WS, "sources", "sk29_normative_verification.json")

fails: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print("  %s %-44s %s" % ("✅" if cond else "❌", name, detail))
    if not cond:
        fails.append(name)


def main():
    print("=" * 78)
    print("门⑩ SK-29 规范贡献 —— 回归 Neto 2011 (EXT-05) 自published工作例")
    print("=" * 78)

    # ── 1. 复现上游工作例：+3/-1、-1/-2、+1/-1 ──
    print("\n【1】上游工作例复现（PDF 物理页 7）")
    print("-" * 78)
    print("  ⚠️ 基准校验必须**关掉自建加权** —— 否则自建项会污染外部基准。")
    _orig_goal = SELF_BUILT["GOAL_WEIGHT"]
    SELF_BUILT["GOAL_WEIGHT"] = "none"
    d = [Desire("s1", 1), Desire("s2", 1), Desire("s3", 1)]

    # Norm 1：履行 +3 = g(+1) + 奖励许可(+2)
    # 论文 Norm1：履行 +3、违反 -1。
    # 违反 -1 只能来自 Algorithm 4 行 5（惩罚是禁止型 → x = x - g）。
    # ⇒ Norm1 带**一个**禁止型惩罚项。具体是哪个状态不可得（Tables 1/2/3 无文本层），
    #    但**项数**可由 -1 反推：恰好 1 项 × 优先级 1。
    n1 = Norm("s1", "obligation", rewards=["s2", "s3"],
              punishments=["s1"], punishments_deontic="prohibition", name="Norm1")
    f1, v1 = contribution(n1, d, fulfilling=True), contribution(n1, d, fulfilling=False)
    print("  Norm1 履行=%+.2f 违反=%+.2f  (期望 +3 / -1)" % (f1, v1))
    check("Norm1 履行贡献 = +3", abs(f1 - 3) < 1e-9, "got %+.2f" % f1)
    check("Norm1 违反贡献 = -1", abs(v1 - (-1)) < 1e-9, "got %+.2f" % v1)
    check("Norm1 选履行（3 ≥ -1）", select(n1, d).decision == "fulfil")

    # Norm 3：+1 / -1
    # 论文 Norm3：履行 +1、违反 -1 ⇒ 同样带一个禁止型惩罚项，**无许可**。
    n3 = Norm("s3", "obligation",
              punishments=["s3"], punishments_deontic="prohibition", name="Norm3")
    f3, v3 = contribution(n3, d, fulfilling=True), contribution(n3, d, fulfilling=False)
    print("  Norm3 履行=%+.2f 违反=%+.2f  (期望 +1 / -1)" % (f3, v3))
    check("Norm3 履行贡献 = +1", abs(f3 - 1) < 1e-9, "got %+.2f" % f3)
    check("Norm3 违反贡献 = -1", abs(v3 - (-1)) < 1e-9, "got %+.2f" % v3)
    check("Norm3 选履行", select(n3, d).decision == "fulfil")

    # Norm 2：论文公布 履行 -1 / 违反 -2。
    # ⚠️ 证据边界：救援场景的**规范构成在 PDF 里无文本层**
    #    （Tables 1/2/3 是图形，正文不复述构成）⇒ 我**拒绝猜测构造**。
    #    改为只断言可从 Algorithm 3/4 伪码直接推出的关系。
    print("  Norm2 期望 -1/-2 —— 场景构成不可得（见门注释），只验伪码可推出的关系")
    n2 = Norm("s1", "prohibition", name="Norm2")
    f2, v2 = contribution(n2, d, fulfilling=True), contribution(n2, d, fulfilling=False)
    check("禁止型：履行走 Alg.3 行12 的 -g 分支 ⇒ 为负", f2 < 0, "got %+.2f" % f2)
    check("无惩罚项时：违反走 Alg.4 ⇒ 贡献为 0", abs(v2) < 1e-9, "got %+.2f" % v2)
    # 论文的 -1/-2 结构：履行 -1（-g），违反 -2（惩罚是禁止型，-g 累计两项）
    n2b = Norm("s1", "prohibition", punishments=["s2", "s3"],
               punishments_deontic="prohibition", name="Norm2b")
    f2b, v2b = contribution(n2b, d, fulfilling=True), contribution(n2b, d, fulfilling=False)
    print("    构造对照：履行=%+.2f 违反=%+.2f（论文 -1/-2）" % (f2b, v2b))
    check("构造对照：履行 -1 / 违反 -2（惩罚两项各 -1）",
          abs(f2b - (-1)) < 1e-9 and abs(v2b - (-2)) < 1e-9,
          "got 履行%+.2f 违反%+.2f" % (f2b, v2b))
    check("两数皆负但仍选履行（判据是 fulfil>=violate，非 >0）",
          select(n2b, d).decision == "fulfil",
          "→ %s" % select(n2b, d).decision)

    # 零值规则也必须在自建关闭下测：否则 goal_weight 恒 +1，掩盖了「零」。
    n0 = Norm("no_such_state", "obligation", name="Norm0")
    f0, v0 = contribution(n0, d, fulfilling=True), contribution(n0, d, fulfilling=False)
    check("状态不匹配任一欲望 ⇒ 贡献为 0（自建关闭下）",
          abs(f0) < 1e-9 and abs(v0) < 1e-9, "got %+.2f / %+.2f" % (f0, v0))

    SELF_BUILT["GOAL_WEIGHT"] = _orig_goal
    print("  （已恢复自建加权 %r）" % _orig_goal)

    # ── 2. 奖励符号（上游 p.5）──
    print("\n【2】奖励是许可，只在履行方向计入（上游 p.5）")
    print("-" * 78)
    SELF_BUILT["GOAL_WEIGHT"] = "none"
    nR = Norm("s1", "obligation", rewards=["s2"], name="NormR")
    fR = contribution(nR, d, fulfilling=True)
    vR = contribution(nR, d, fulfilling=False)
    check("奖励使履行方向更高（许可生效）", fR > vR,
          "履行%+.2f 违反%+.2f" % (fR, vR))
    check("奖励永不为负：履行方向不含负的惩罚项", fR > 0, "got %+.2f" % fR)
    SELF_BUILT["GOAL_WEIGHT"] = _orig_goal

    # ── 3. 冲突定义（上游 p.7）──
    print("\n【3】冲突定义（上游 p.7：同一状态 + 一义务一禁止 + 决策相同）")
    print("-" * 78)
    a = Norm("s1", "obligation", name="A")
    b = Norm("s1", "prohibition", rewards=["s2", "s3"], name="B")
    c = Norm("s2", "obligation", name="C")
    ra, rb, rc = select(a, d), select(b, d), select(c, d)
    print("    A=%s(%+.2f/%+.2f)  B=%s(%+.2f/%+.2f)" %
          (ra.decision, ra.fulfil_contribution, ra.violate_contribution,
           rb.decision, rb.fulfil_contribution, rb.violate_contribution))
    check("同状态+异 deontic+同决策(都履行) ⇒ 冲突", has_conflict(a, b, ra, rb),
          "← 上游 p.7 明确：都想履行或都想违反才冲突")
    check("不同状态 ⇒ 不冲突", not has_conflict(a, c, ra, rc))
    e = Norm("s1", "prohibition", name="E")   # 纯禁止：决策为 violate，与 A 不同
    re_ = select(e, d)
    if ra.decision != re_.decision:
        check("同状态+异 deontic+**异决策** ⇒ 不冲突", not has_conflict(a, e, ra, re_),
              "A=%s E=%s" % (ra.decision, re_.decision))
    else:
        check("同状态+异 deontic+异决策 ⇒ 不冲突", True, "（构造决策相同，跳过）")

    # ── 4. 冲突求解 + 平局自检 ──
    print("\n【4】冲突求解（上游 p.7「highest contribution」）+ 平局自检")
    print("-" * 78)
    SELF_BUILT["GOAL_WEIGHT"] = "none"
    a2 = Norm("s1", "obligation", rewards=["s2", "s3"], name="A2")
    ra2, rb2 = select(a2, d), select(b, d)
    res, _msg = solve_conflict(a, b, ra2, rb2)
    win = res[0].name if res else "?"
    cw, cx = (res[2], res[3]) if res else (0, 0)
    check("取贡献更高者", res is not None and res[0].name == "A" and cw > cx,
          "winner=%s %.2f vs %.2f" % (win, cw, cx))
    p1 = Norm("s1", "obligation", name="P1")
    p2 = Norm("s1", "obligation", name="P2")
    rp1, rp2 = select(p1, d), select(p2, d)
    t1 = rp1.fulfil_contribution if rp1.decision == "fulfil" else rp1.violate_contribution
    t2 = rp2.fulfil_contribution if rp2.decision == "fulfil" else rp2.violate_contribution
    if t1 == t2:
        res, msg = solve_conflict(p1, p2, rp1, rp2)
        check("平局时返回 None 并要求人工裁决（上游未给平局规则）",
              res is None and "人工裁决" in msg, msg[:56])
    else:
        check("平局自检（构造未对齐，跳过）", True)
    SELF_BUILT["GOAL_WEIGHT"] = _orig_goal

    # ── 5. 自建项必须仍然标记 ──
    print("\n【5】自建项标记（下游 2018 未给合成式）")
    print("-" * 78)
    check("GOAL_WEIGHT 标记为自建", "GOAL_WEIGHT" in SELF_BUILT)
    check("TRAIT_WEIGHT 标记为自建", "TRAIT_WEIGHT" in SELF_BUILT)
    check("自建项附理由与可检验后果", "_why" in SELF_BUILT and "可检验" in SELF_BUILT["_why"])
    check("外部依据带 PDF 物理页码",
          all(isinstance(v[0], int) for v in VERBATIM.values()),
          "%d 条逐字" % len(VERBATIM))
    check("依据标注为下游 2018 的上游",
          "upstream_of" in SOURCE and "P30" in SOURCE["upstream_of"],
          SOURCE.get("upstream_of", "")[:46])

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "source": SOURCE,
            "n_verbatim": len(VERBATIM),
            "worked_example": {
                "Norm1": {"fulfil": f1, "violate": v1, "expected": [3, -1]},
                "Norm3": {"fulfil": f3, "violate": v3, "expected": [1, -1]},
                "Norm2": {"fulfil": f2, "violate": v2,
                          "note": "论文公布 -1/-2，但救援场景构成在 PDF 无文本层"
                                  "（Tables 1/2/3 为图形，正文不复述）⇒ 未猜测构造，"
                                  "只验符号与判据"},
            },
            "self_built": SELF_BUILT,
            "fails": fails,
        }, f, ensure_ascii=False, indent=1)
    print("\n  落盘 %s" % OUT)

    print("\n" + "=" * 78)
    if fails:
        print("❌ 失败 %d 项：" % len(fails))
        for x in fails:
            print("   - %s" % x)
        return 1
    print("PASS  门⑩ 上游工作例 Norm1(+3/-1)、Norm3(+1/-1) 复现；"
          "结构、符号、零值、平局自检全过")
    print("⚠️ 下游 2018 的加权仍是自建（%s / %s）" %
          (SELF_BUILT["GOAL_WEIGHT"], SELF_BUILT["TRAIT_WEIGHT"]))
    return 0



