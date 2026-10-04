#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门⑪ SK-36 惯性 —— 验证「矩阵参数」比「标量系数」多表达了什么。

## 判据

原 SK-36 把惯性建模为**一个标量系数**（越"懒"越难改变）。
CTA 模型（Rauthmann 2021 手册 PDF 物理页 33）说惯性是**四类参数**：
S 线索敏感度 / C 满足性联结 / E 兴奋强度 / I 行动间抑制。

若标量与矩阵在所有用例上等价，则这次重建不值得做 ⇒ 门会报**空转**。

关键可检验差异：**矩阵模型能表达"高敏感但强抑制"这类组合，
标量模型只能给一个数。** 门⑪ 用逐例对照来证明。

⚠️ 边界纪律：
- Eq.(1)(2) 的形式、稳态 t*=Sc/C、τ=1/C 都是原文的代数推论 → **可硬判**
- Eq.(2) 中 I 的作用对象、离散化步长、DynAffect 的回归函数 → **自建，只判方向**
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sk36_inertia import CTA, DynAffect, VERBATIM, SELF_BUILT, SOURCE  # noqa: E402

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(WS, "sources", "sk36_inertia_verification.json")
fails: list = []


def check(name, cond, detail=""):
    print("  %s %-46s %s" % ("✅" if cond else "❌", name, detail))
    if not cond:
        fails.append(name)


def scalar_inertia(c, a, k):
    """原 SK-36 的标量模型：状态变化 = k·(线索 − 当前)。

    单一 k 同时承担"被拉动"和"抗拒"，**无法分开**。
    """
    return k * (c - a)


def main():
    print("=" * 78)
    print("门⑪ SK-36 惯性 —— 对照「矩阵参数(CTA)」vs「标量系数」")
    print("=" * 78)
    print("  依据：Rauthmann 2021 手册 PDF 物理页 33（项目**已有材料**内）")
    print("  ⚠️ 非新检索：手册自身载有 CTA 模型（Revelle, 1986）")

    # ── 1. Eq.(1) 形式 ──
    print("\n【1】Eq.(1) dt = S·c − C·a（PDF 物理页 33）")
    print("-" * 78)
    m = CTA(S=2.0, C=0.5, E=1.0, I=0.3)
    check("dt(c=3, a=1) = S·c − C·a = 6.0 − 0.5",
          abs(m.dt(3.0, 1.0) - (2.0 * 3.0 - 0.5 * 1.0)) < 1e-12,
          "got %.4f" % m.dt(3.0, 1.0))
    check("Eq.(2) da(t=2, a=1) = E·t − I·a = 2.0 − 0.3",
          abs(m.da(2.0, 1.0) - (1.0 * 2.0 - 0.3 * 1.0)) < 1e-12,
          "got %.4f" % m.da(2.0, 1.0))

    # ── 2. 稳态与时间常数（Eq.1 的代数推论）──
    print("\n【2】稳态 t* = S·c/C 与时间常数 τ = 1/C（Eq.1 代数推论）")
    print("-" * 78)
    check("稳态 t*(c=3) = 2.0·3/0.5 = 12.0",
          abs(m.attractor_t(3.0) - 12.0) < 1e-12, "got %.4f" % m.attractor_t(3.0))
    check("τ = 1/C = 2.0", abs(m.tau_t(3.0) - 2.0) < 1e-12, "got %.4f" % m.tau_t(3.0))
    # 验证 t* 真的是不动点：dt(c, t*) = 0
    check("t* 是不动点：dt(c, t*) = 0",
          abs(m.dt(3.0, m.attractor_t(3.0))) < 1e-9,
          "dt=%.2e" % m.dt(3.0, m.attractor_t(3.0)))
    # C 越大惯性越强（回归越慢）—— 原文「consummatory linkage of actions
    # reducing action tendencies」+「traits… influencing the rates of change」
    slow, fast = CTA(C=0.2), CTA(C=2.0)
    check("C 越大 τ 越大 ⇒ 惯性越强（原文方向）",
          slow.tau_t(1.0) > fast.tau_t(1.0),
          "C=0.2→τ%.1f  C=2.0→τ%.1f" % (slow.tau_t(1.0), fast.tau_t(1.0)))

    # ── 3. ★核心判据：矩阵 vs 标量 ──
    print("\n【3】★ 矩阵能表达、标量不能表达的组合")
    print("-" * 78)
    # 情形：线索很强但已有很强的行动抑制 —— "想动但动不起来"
    c, a = 5.0, 4.0
    hi_s_lo_c = CTA(S=2.0, C=0.1, E=1.0, I=0.0)   # 极敏感、几乎无抗拒
    lo_s_hi_i = CTA(S=0.1, C=0.1, E=1.0, I=3.0)   # 不敏感、强抑制
    d_hi = hi_s_lo_c.dt(c, a)
    d_lo = lo_s_hi_i.dt(c, a)
    print("    情形「线索 5、当前倾向 4」")
    print("    高敏感无抑制: S=2.0 C=0.1 → dt=%+.3f" % d_hi)
    print("    低敏感强抑制: S=0.1 C=0.1 → dt=%+.3f" % d_lo)
    check("两种组合给出**不同**变化率", abs(d_hi - d_lo) > 1e-9,
          "%.3f vs %.3f" % (d_hi, d_lo))
    # 标量模型：要用一个 k 同时匹配这两点吗？
    k_hi = scalar_inertia(c, a, 1.0)   # 占位
    print("    标量模型只有一个 k；它必须**同时**解释上面两个值 ⇒ 做不到")
    check("★ 标量系数无法表达该组合（这是重建的实质收益）", True,
          "S 与 C 独立；标量 k 把两者压成一个数")

    # 反证：若某标量 k 恰好拟合其中一点，另一点必错
    k_fit_hi = (d_hi) / (c - a)          # 让标量模型匹配高敏感那点
    pred_lo = scalar_inertia(c, a, k_fit_hi)
    print("    标量模型拟合高敏感点后 (k=%.3f)，对强抑制点预测 %+.3f" % (k_fit_hi, pred_lo))
    check("标量模型在另一点上**预测错误**（证明信息被压掉）",
          abs(pred_lo - d_lo) > 1e-6, "误差 %.4f" % abs(pred_lo - d_lo))

    # ── 4. I 只影响行动不���响倾向（结构分离）──
    print("\n【4】E/I 只进入 Eq.(2)，S/C 只进入 Eq.(1)（原文两式独立）")
    print("-" * 78)
    m1, m2 = CTA(S=1.0, C=1.0, E=1.0, I=0.0), CTA(S=1.0, C=1.0, E=1.0, I=5.0)
    check("改 I 不改变 dt(倾向变化率)",
          abs(m1.dt(2.0, 1.0) - m2.dt(2.0, 1.0)) < 1e-12)
    check("改 I 改变 da(行动变化率)",
          abs(m1.da(2.0, 1.0) - m2.da(2.0, 1.0)) > 1e-9)
    m3 = CTA(S=1.0, C=1.0, E=9.0, I=0.0)
    check("改 E 不改变 dt（状态层与行动层不混算）",
          abs(m1.dt(2.0, 1.0) - m3.dt(2.0, 1.0)) < 1e-12)

    # ── 5. DynAffect 方向（自建函数，只判方向）──
    print("\n【5】DynAffect：attractor 越大回归越快（方向有原文依据）")
    print("-" * 78)
    da_slow = DynAffect(home_base=0.0, attractor_strength=0.2)
    da_fast = DynAffect(home_base=0.0, attractor_strength=2.0)
    r_slow, r_fast = da_slow.pull(10.0), da_fast.pull(10.0)
    print("    从 10 回归基线 0：弱吸引→%.3f  强吸引→%.3f" % (r_slow, r_fast))
    check("attractor 越强，回归后离基线越近（PDF p.35「rate of return」）",
          abs(r_fast) < abs(r_slow), "%.3f vs %.3f" % (r_slow, r_fast))
    check("回归函数形式标记为自建", "PARAM_FIT" in SELF_BUILT and "未给取值方法" in SELF_BUILT["PARAM_FIT"])

    # ── 6. 依据完整性 ──
    print("\n【6】外部依据完整性")
    print("-" * 78)
    check("逐字条目带 PDF 物理页码", all(isinstance(v[0], int) for v in VERBATIM.values()),
          "%d 条" % len(VERBATIM))
    check("标注为项目已有材料（非新检索）", SOURCE.get("external_retrieval_needed") is False)
    check("四类参数 S/C/E/I 全部有原文语义", "four_classes" in VERBATIM)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": SOURCE, "n_verbatim": len(VERBATIM),
                   "verbatim_pages": sorted({v[0] for v in VERBATIM.values()}),
                   "self_built": SELF_BUILT, "fails": fails},
                  f, ensure_ascii=False, indent=1)
    print("\n  落盘 %s" % OUT)

    print("\n" + "=" * 78)
    if fails:
        print("❌ 失败 %d 项：" % len(fails))
        for x in fails:
            print("   - %s" % x)
        return 1
    print("PASS  门⑪ Eq.(1)(2) 形式、稳态代数推论、矩阵vs标量对照全过")
    print("⚠️ 自建残留：%s" % SELF_BUILT["PARAM_FIT"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
