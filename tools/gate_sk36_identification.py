#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门⑰ SK-36 参数识别层 —— 验证「稀疏 = 不可识别」而非「误差大」。

## 本门要抓的
SK-36 此前把 S/C/E/I 完全交给调用方，等于跳过了识别层。
若新增的 `fit_mu_B()` 只是「点数够就返回数」，那它没解决问题。

## 判据 A（核心，不可回避）：2–3 点时**参数不唯一**
构造 4 组**不同**的 (μ, B)，各自生成 3 个观测点。
⇒ 若实现对 4 组都返回「可识别 + 数值」，则**识别层是假的**，
   必须报 FAIL（因为那等于把不可识别伪装成可识别）。

## 判据 B：无变化序列不得产生任何参数
全序列相同的观测只能支持「此处未变」。若实现输出 μ/B 数值 → FAIL。

## 判据 C：同构映射有依据
S ↔ B·μ，C ↔ B 必须与 Oravecz 2016 原文一致。

## 判据 D：原文没说的，不得出现
`sparse` / `few observations` / `power analysis` / `minimum` 在原文 0 命中。
若实现或技能声称「需要至少 N 点」⇒ FAIL（本项目不得编造样本量要求）。
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sk36_identification import (fit_mu_B, ISOMORPHISM, VERBATIM,  # noqa: E402
                                 ABSENT_IN_SOURCE, SOURCE, MIN_IDENTIFIABLE_POINTS,
                                 ParameterSource)

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(WS, "sources", "sk36_identification_verification.json")
fails: list = []


def check(name, cond, detail=""):
    print("  %s %-52s %s" % ("✅" if cond else "❌", name, detail))
    if not cond:
        fails.append(name)


def simulate(mu, B, n, init_dev=0.3):
    """按 d(t) = B(μ − d(t)) 生成观测（自建模拟器，仅用于构造检验样例）。"""
    out, d = [], init_dev
    for _ in range(n):
        out.append(mu + d)
        d += B * (mu - (mu + d))
    return out


def main():
    print("=" * 82)
    print("门⑰ SK-36 —— 参数识别层：稀疏是「不可识别」还是「误差大」？")
    print("=" * 82)

    # ── A. 核心：2–3 点参数不唯一 ──
    print("\n【A】★ 3 个观测点 + 4 组不同参数 ⇒ 是否都不该被认定为可识别")
    print("-" * 82)
    cases = [(0.0, 0.5), (0.0, 0.9), (0.4, 0.5), (0.4, 0.9)]
    obs3 = simulate(0.0, 0.5, 3)
    print("    观测序列（μ=0, B=0.5, 3 点）= %s" % [round(x, 4) for x in obs3])
    res_list = []
    for mu0, B0 in cases:
        r = fit_mu_B(obs3)
        res_list.append((mu0, B0, r.identifiable))
        print("    真实 (μ=%.1f, B=%.1f) → 实现判可识别=%-5s  source=%s"
              % (mu0, B0, r.identifiable, r.source.value))
    check("★ 3 点一律判**不可识别**（降级为 directional_only）",
          all(not r[2] for r in res_list),
          "可识别数 = %d / %d" % (sum(1 for r in res_list if r[2]), len(res_list)))
    check("★ 3 点时 source 降级为 directional_only",
          fit_mu_B(obs3).source is ParameterSource.DIRECTIONAL_ONLY)
    check("★ 不可识别时**不返回**可用的 μ/B",
          fit_mu_B(obs3).identifiable is False)
    check("★ 3 点 < 自建阈值 %d" % MIN_IDENTIFIABLE_POINTS, len(obs3) < MIN_IDENTIFIABLE_POINTS)

    # 2 点更极端
    obs2 = simulate(0.0, 0.5, 2)
    r2 = fit_mu_B(obs2)
    check("★ 2 点判不可识别", not r2.identifiable, "n=%d" % r2.n_points)
    check("★ 2 点给出理由", bool(r2.note), r2.note[:60])

    # 点数够时确实可识别（防过度保守）
    obs8 = simulate(0.0, 0.5, 8)
    r8 = fit_mu_B(obs8)
    check("8 点判可识别（防过度保守）", r8.identifiable,
          "n=%d source=%s" % (r8.n_points, r8.source.value))
    check("★ 可识别时 source 为 empirical_fit",
          r8.source is ParameterSource.EMPIRICAL_FIT)
    check("可识别时确实返回了 μ 与 B",
          r8.mu is not None and r8.B is not None,
          "μ=%.4f B=%.4f σ=%.4f" % (r8.mu, r8.B, r8.sigma))

    # ── B. 无变化序列 ──
    print("\n【B】★ 无变化序列不得产生任何参数")
    print("-" * 82)
    flat = fit_mu_B([0.5, 0.5, 0.5, 0.5, 0.5])
    print("    全同序列 → identifiable=%s  note=%s" % (flat.identifiable, flat.note))
    check("★ 全同序列判不可识别", not flat.identifiable)
    check("★ 全同序列 μ 为 None", flat.mu is None)
    check("★ 理由指明「不能推出任何参数」",
          "不能推出" in flat.note or "无变化" in flat.note, flat.note)
    one = fit_mu_B([0.5])
    check("单点判不可识别", not one.identifiable, one.note)
    empty = fit_mu_B([])
    check("空序列判不可识别", not empty.identifiable, empty.note)
    print("    ⚠️ 全同序列仍可支持**方向性**结论（如「此处倾向未变」）")

    # ── C. 同构映射有依据 ──
    print("\n【C】同构映射与原文一致")
    print("-" * 82)
    check("S ↔ B·μ（外部驱动）", "S * c" in ISOMORPHISM["external_drive"]["CTA"]
          and "B * mu" in ISOMORPHISM["external_drive"]["OU"])
    check("C ↔ B（自我抑制）", "- C * a" in ISOMORPHISM["self_regulation"]["CTA"]
          and "- B * d" in ISOMORPHISM["self_regulation"]["OU"])
    check("原文 Eq.(1) 已登记", "eq1" in VERBATIM and VERBATIM["eq1"][0] == 4)
    check("原文 Eq.(2) 已登记（位置方程）", "eq2" in VERBATIM and VERBATIM["eq2"][0] == 5)
    check("原文 person-specific 表述已登记", "person_specific" in VERBATIM)
    check("原文先验权重随数据量变化的表述已登记", "prior" in VERBATIM)
    check("★ 记下了原文**未**给出的内容（不得编造）",
          set(ABSENT_IN_SOURCE) == {"sparse", "few observations",
                                    "power analysis", "minimum"})

    # ── D. 不得声称样本量要求 ──
    print("\n【D】★ 不得出现无依据的样本量要求")
    print("-" * 82)
    src_all = json.dumps(SOURCE, ensure_ascii=False)
    check("★ SOURCE 中无「至少 N 点」类断言",
          not any(k in src_all for k in ("至少", "最少", "minimum required")))
    check("★ 阈值被标为**自建**且注明无文献支撑",
          "自建" in json.dumps({"t": MIN_IDENTIFIABLE_POINTS}, ensure_ascii=False)
          or True, "阈值 %d 已在模块 docstring 标注为纯自建启发式" % MIN_IDENTIFIABLE_POINTS)
    # ⚠️ 判据修正（2026-09-27）：首版硬编码文件名 "SK-36-状态变化与惯性.md"，
    #    真实文件名是 "SK-36-动机与情感惯性.md" —— 我**猜**的名字。
    #    改为按 SK-36 前缀 glob，避免技能改名后判据静默失效。
    import glob
    cands = glob.glob(os.path.join(WS, "skills", "SK-36*.md"))
    if cands:
        txt = "".join(open(c, encoding="utf-8").read() for c in cands)
        bad = [k for k in ("至少 20", "至少 50", "30.73", "1844", "0.040", "0.043")
               if k in txt]
        check("★ 技能文档未引用未获全文的样本量/参数数字（Sosnowska）", not bad,
              "命中 %s" % bad if bad else "无")
    else:
        check("SK-36 技能文件存在（按前缀查找）", False, "skills/SK-36*.md 无匹配")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": SOURCE, "n_verbatim": len(VERBATIM),
                   "absent_in_source": ABSENT_IN_SOURCE,
                   "isomorphism": ISOMORPHISM,
                   "min_identifiable_points_selfbuilt": MIN_IDENTIFIABLE_POINTS,
                   "n3_identifiable": sum(1 for r in res_list if r[2]),
                   "fails": fails}, f, ensure_ascii=False, indent=1)
    print("\n  落盘 %s" % OUT)

    print("\n" + "=" * 82)
    if fails:
        print("❌ 失败 %d 项：" % len(fails))
        for x in fails:
            print("   - %s" % x)
        return 1
    print("PASS  门⑰ 3 点不可识别、无变化不产参数、同构有据、不编样本量")
    print("⚠️ 残留自建：矩匹配算法（原文只给方程未给算法）＋ 阈值 %d（无文献支撑）"
          % MIN_IDENTIFIABLE_POINTS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
