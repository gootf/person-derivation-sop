#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门⑭ SK-27 稀释 —— 验证 ACT-R base-level 形式 + 脚注 6 的三因素结构。

## 两个判据

### 判据 A：ACT-R 公式形式正确（可硬判）
手册 PDF 物理页 263 给：
    B = β + ln( Σ 1/(d·t_j) )      (:ol = nil，完整式)
    B = β + ln( n / (d·(L−d)) )    (:ol = t，近似式)
⇒ 单调性、正值性、对 d 的反向关系都必须成立。

### 判据 B：★ 不能退化成"只看集合大小"
GST-2002 PDF 物理页 7 脚注 6 逐字：
> "**Uniqueness of association is only one among several determinants** of
>  association-strength. Another determinant is **repeated pairing** ...
>  A mental representation ... could derive also from pronouncements of a
>  trusted **"epistemic authority"**"

⇒ 构造「集合同样大、但重复配对/权威不同」的两系统，
   **强度必须不同**。若相同 ⇒ 脚注 6 被忽略，模型错。

### 边界纪律
⚠️ `1/n` 形式是**自建**（ACT-R 无集合维度公式，GST-2002 的函数在不可读的
   Figures 4/5 里）。门⑭ 只验证它**满足原文方向**、且**不吞掉脚注 6**。
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sk27_dilution import (  # noqa: E402
    base_level, GoalSystem, UPSTREAM, VERBATIM, SELF_BUILT,
)

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(WS, "sources", "sk27_dilution_verification.json")
fails: list = []


def check(name, cond, detail=""):
    print("  %s %-48s %s" % ("✅" if cond else "❌", name, detail))
    if not cond:
        fails.append(name)


def main():
    print("=" * 78)
    print("门⑭ SK-27 稀释 —— ACT-R base-level（EXT-08）+ GST-2002 脚注 6 三因素")
    print("=" * 78)

    # ── A. ACT-R 公式 ──
    print("\n【A】ACT-R base-level 公式（手册 PDF 物理页 263）")
    print("-" * 78)
    b_now = base_level(1, times=[0.5])
    b_old = base_level(1, times=[20.0])
    print("    n=1, t=0.5  → B=%.4f" % b_now)
    print("    n=1, t=20.0 → B=%.4f" % b_old)
    check("近因 > 远因（recency 方向）", b_now > b_old,
          "%.4f > %.4f" % (b_now, b_old))
    # ⚠️ 判据修正（2026-09-27）：首版写 `base_level(3, times=[0.5])`，
    #    但手册完整式是 B = β + ln( Σ_{j=1..n} 1/(d·t_j) ) ——
    #    **求和项数由 times 的长度决定**，不是由 n_uses 参数决定。
    #    混用两者导致 n=3 与 n=1 同值。实现无误，判据错。
    b3 = base_level(3, times=[0.5, 0.5, 0.5])
    check("频次 > 单次（frequency 方向，times 长度=3）", b3 > b_now,
          "n=3→%.4f  n=1→%.4f" % (b3, b_now))
    # 防混用：n_uses 与 len(times) 不一致时，实现应按 times 求和
    mixed = base_level(3, times=[0.5])
    check("★ 实现按 len(times) 求和而非 n_uses（防混用）",
          abs(mixed - b_now) < 1e-12,
          "n_uses=3 但只有 1 个时间点 → 与 n=1 相同，证明按 times 走")
    d_fast = base_level(1, times=[1.0], d=0.1)
    d_slow = base_level(1, times=[1.0], d=1.0)
    check("d 越大衰减越强 ⇒ B 越低", d_slow < d_fast,
          "d=1.0→%.4f  d=0.1→%.4f" % (d_slow, d_fast))
    # 完整式与近似式应同量级
    full = base_level(4, times=[1.0, 2.0, 3.0, 4.0])
    approx = base_level(4, lifetime=4.0)
    print("    完整式=%.4f  近似式=%.4f" % (full, approx))
    check("完整式与近似式同量级（手册称 :ol=t 是近似）",
          abs(full - approx) < 1.0, "差 %.4f" % abs(full - approx))
    check("n=0 时退化为 β", abs(base_level(0, times=[1.0]) - 0.0) < 1e-12)

    # ── B. ★ 脚注 6 三因素 ──
    print("\n【B】★ 脚注 6：uniqueness 只是三因素之一")
    print("-" * 78)
    # 同集合大小，不同重复配对
    plain = GoalSystem(equifinality=["a", "b", "c", "d"], multifinality=["g"]).association_strength()
    rep = GoalSystem(equifinality=["a", "b", "c", "d"], multifinality=["g"],
                     repeated_pairing=0.5).association_strength()
    auth = GoalSystem(equifinality=["a", "b", "c", "d"], multifinality=["g"],
                      authority=0.8).association_strength()
    print("    同集合(4手段×1目标)：")
    print("      无额外      strength=%.4f" % plain["strength"])
    print("      重复配对0.5  strength=%.4f" % rep["strength"])
    print("      权威0.8      strength=%.4f" % auth["strength"])
    check("★ 重复配对能改变强度（脚注6 第二因素生效）",
          abs(rep["strength"] - plain["strength"]) > 1e-9)
    check("★ 权威陈述能改变强度（脚注6 第三因素生效）",
          abs(auth["strength"] - plain["strength"]) > 1e-9)
    check("★ 强重复配对可补偿大集合的稀释",
          rep["strength"] > plain["strength"])
    # 方向：集合越大越弱
    small = GoalSystem(equifinality=["a"], multifinality=["g"]).association_strength()
    large = GoalSystem(equifinality=list("abcdefgh"), multifinality=["g"]).association_strength()
    print("    1 手段→strength=%.4f ；8 手段→strength=%.4f"
          % (small["strength"], large["strength"]))
    check("★ equifinality 集越大 ⇒ 联结越弱（GST-2002 p.6 原文方向）",
          large["strength"] < small["strength"])
    m1 = GoalSystem(equifinality=["a"], multifinality=["g"]).association_strength()
    m8 = GoalSystem(equifinality=["a"], multifinality=list("abcdefgh")).association_strength()
    check("★ multifinality 集越大 ⇒ 联结越弱（同上）",
          m8["strength"] < m1["strength"])

    # ── C. 依据链完整性 ──
    print("\n【C】依据链与边界")
    print("-" * 78)
    check("记录了 GST-2002 的 Figures 4/5 不可得",
          UPSTREAM["material_figures_unavailable"]["verified"].startswith("逐页统计"))
    check("记录了 ACT-R 手册文本层覆盖率",
          UPSTREAM["surrogate"]["pages_with_text_layer"] == 532)
    check("逐字条目带 PDF 物理页码",
          all(isinstance(v[0], int) for v in VERBATIM.values()), "%d 条" % len(VERBATIM))
    check("自建项标明 1/n 形式是自建", "1/n" in SELF_BUILT["SET_DILUTION_FORM"])
    check("说明 d=0.5 的借用是自建", "借用是自建的" in SELF_BUILT["_why_D"])
    check("脚注 6 要求已记录", "_foot6_must_model" in SELF_BUILT)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"upstream": UPSTREAM, "n_verbatim": len(VERBATIM),
                   "base_level_samples": {"n1_t0.5": b_now, "n1_t20": b_old,
                                          "n3_t0.5": b3, "full": full, "approx": approx},
                   "self_built": SELF_BUILT, "fails": fails},
                  f, ensure_ascii=False, indent=1)
    print("\n  落盘 %s" % OUT)

    print("\n" + "=" * 78)
    if fails:
        print("❌ 失败 %d 项：" % len(fails))
        for x in fails:
            print("   - %s" % x)
        return 1
    print("PASS  门⑭ base-level 公式方向正确；脚注 6 三因素均生效")
    print("⚠️ 残留自建：%s；d=0.5（借用）" % SELF_BUILT["SET_DILUTION_FORM"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
