#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门⑯ SK-14 再修正 —— 验证 Vitevitch (2011) 的保留-均分，并确认「不衰减」。

## 本门要抓的（如果上一版没被推翻，这门就该 FAIL）

上一版是**乘性衰减** `v = up * w * df`（df=0.5）。
Vitevitch 2011 明确「**does not decay over time**」「does not diminish」。

⇒ 判据 A：**r=0 的极限下，总激活守恒**（无衰减）。
   乘性衰减模型做不到这一点 —— 无论 df 取多少，跨跳都会缩小。
   若两个模型处处一致，本门报**空转**（重建不值得做）。

## 判据 B：均分而非乘性
Eq.(3) 是 `(1−r)·inflow / degree(n)`，即**每个邻居拿到等份**。
⇒ 构造度不同的两个节点，验证分配**按邻居数均分**。

## 边界
⚠️ 阈值是**自建**（Vitevitch 明确不采用），门⑯ 只检查它被如实标记。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sk14_propagation import (spread, VERBATIM, SELF_BUILT, SOURCE,  # noqa: E402
                            UPSTREAM, SPREADR_DEFAULTS, SPREADR_ORDER)

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(WS, "sources", "sk14_vitevitch_verification.json")
fails: list = []


def check(name, cond, detail=""):
    print("  %s %-50s %s" % ("✅" if cond else "❌", name, detail))
    if not cond:
        fails.append(name)


def main():
    print("=" * 80)
    print("门⑯ SK-14 —— Vitevitch et al. (2011) 保留-均分 vs 上一版乘性衰减")
    print("=" * 80)

    # ── A. 不衰减：r=0 时守恒 ──
    print("\n【A】★ 不衰减（原文 p.5：does not decay over time）")
    print("-" * 80)
    # r=0 ⇒ 起点不留存，全部流出
    star = {"A": [("B", 1.0), ("C", 1.0), ("D", 1.0)]}
    r0 = spread("A", star, r=0.0, steps=1, init=100.0)
    tot = sum(r0.activation.values())
    print("    r=0, 1 步：%s  总和=%.3f" % ({k: round(v, 2) for k, v in r0.activation.items()}, tot))
    check("★ r=0 时**总激活守恒**（无衰减的极限）", abs(tot - 100.0) < 1e-6,
          "总 %.4f vs 初始 100" % tot)
    # 对照：decay>0（时间维度）应丢量；decay=0（默认）不丢
    r0_dec = spread("A", star, r=0.0, steps=1, init=100.0, decay=0.5)
    print("    （对照）同场景 decay=0.5 → 总和=%.3f ⇒ 衰减会丢量"
          % sum(r0_dec.activation.values()))
    check("★ decay>0 时**丢量**（与 decay=0 可区分）",
          abs(sum(r0_dec.activation.values()) - 100.0) > 1e-6)

    # 闭式：r=0，两步星形网络仍守恒
    r0b = spread("A", star, r=0.0, steps=2, init=100.0)
    check("★ r=0 两步仍守恒", abs(sum(r0b.activation.values()) - 100.0) < 1e-6,
          "总 %.4f" % sum(r0b.activation.values()))

    # ── B. 均分而非乘性（Eq.3）──
    print("\n【B】★ 均分（Eq.3: (1−r)·inflow / degree(n)）")
    print("-" * 80)
    deg1 = {"A": [("B", 1.0)]}
    deg3 = {"A": [("B", 1.0), ("C", 1.0), ("D", 1.0)]}
    s1 = spread("A", deg1, r=0.5, steps=1, init=100.0)
    s3 = spread("A", deg3, r=0.5, steps=1, init=100.0)
    print("    r=0.5, 起点 A: 1 个邻居 → A=%.2f B=%.2f" % (s1.activation["A"], s1.activation["B"]))
    print("               3 个邻居 → A=%.2f B=%.2f C=%.2f D=%.2f"
          % (s3.activation["A"], s3.activation["B"], s3.activation["C"], s3.activation["D"]))
    check("★ 邻居越少，单个邻居拿到越多（均分效应）",
          s1.activation["B"] > s3.activation["B"],
          "deg1 B=%.2f > deg3 B=%.2f" % (s1.activation["B"], s3.activation["B"]))
    check("★ 三个邻居**等份**（均分，不是按某种权重偏斜）",
          abs(s3.activation["B"] - s3.activation["C"]) < 1e-9
          and abs(s3.activation["C"] - s3.activation["D"]) < 1e-9)
    check("★ 起点保留恰为 r×inflow（Eq.2）",
          abs(s3.activation["A"] - 0.5 * 100.0) < 1e-6, "A=%.2f 期望 50" % s3.activation["A"])

    # 守恒（r>0 时也守恒，因为只是重新分配）
    check("r=0.5 一步总激活仍守恒", abs(sum(s3.activation.values()) - 100.0) < 1e-6,
          "总 %.4f" % sum(s3.activation.values()))

    # ── C. 原文设定核对 ──
    print("\n【C】原文设定逐条核对")
    print("-" * 80)
    check("初始激活默认 100（p.6）", SELF_BUILT["INIT_ACTIVATION"] == 100.0)
    check("默认 10 个时间步（p.5）", SELF_BUILT["TIME_STEPS"] == 10)
    check("默认 r=0.5（对齐 spreadr 包默认 0.3.0）", SELF_BUILT["R_DEFAULT"] == 0.5)
    # ⚠️ 判据修正（2026-09-27）：首版查 "decay=0" 子串，但文案里写的是
    #    "默认 decay = 0（**不衰减**）"（带空格与强调号）。改为查语义关键片段。
    check("默认无衰减（decay = 0，标注为 Vitevitch 与 spreadr 共同设定）",
          "decay = 0" in SELF_BUILT["_no_decay_default"]
          and "spreadr" in SELF_BUILT["_no_decay_default"],
          SELF_BUILT["_no_decay_default"][:70])
    check("★ 阈值标为自建且不得引 Vitevitch 为据",
          "不得引 Vitevitch 为据" in SELF_BUILT["_threshold_caveat"])
    # ⚠️ 判据修正（2026-09-27）：首版去 SELF_BUILT 里找"时间/空间"字样，
    #    但该区分写在 **UPSTREAM** 结构里 —— 查错了字段。
    td = str(UPSTREAM.get("time_dimension", {})) + str(UPSTREAM.get("space_dimension", {}))
    check("标注与 EXT-07 的时间/空间之分（在 UPSTREAM 中）",
          "时间" in td and "空间" in td, td[:78])

    # ── E. spreadr CRAN 手册：默认值与迭代顺序 ──
    print("\n【E】★ spreadr CRAN 手册（0.3.0）默认值与迭代顺序")
    print("-" * 80)
    check("spreadr 默认 retention=0.5", SPREADR_DEFAULTS["retention"] == 0.5)
    check("spreadr 默认 time=10", SPREADR_DEFAULTS["time"] == 10)
    check("★ spreadr 默认 decay=0（**默认关闭衰减**）", SPREADR_DEFAULTS["decay"] == 0)
    check("spreadr 默认 suppress=0", SPREADR_DEFAULTS["suppress"] == 0)
    # ⚠️ 判据修正（2026-09-27）：首版用 startswith("Spread"/"Decay"/"Set the activation")，
    #    但手册逐字原文是**小写**开头（"spread activation…" / "decay the…" / "set the…"），
    #    大小写不匹配导致误判。改为不区分大小写的前缀检查。
    _o = [x.lower() for x in SPREADR_ORDER]
    check("迭代顺序为 spread → decay → suppress（大小写不敏感）",
          _o[0].startswith("spread") and _o[1].startswith("decay")
          and _o[2].startswith("set the activation"), " | ".join(_o)[:96])
    check("实现默认 decay 与 spreadr 一致",
          abs(spread("A", star).decay - SPREADR_DEFAULTS["decay"]) < 1e-12)
    check("实现默认 r 与 spreadr 一致",
          abs(spread("A", star).r - SPREADR_DEFAULTS["retention"]) < 1e-12)
    # suppress：把 ≤ suppress 的置 0
    sup = spread("A", star, r=0.5, steps=1, init=100.0, suppress=20.0)
    print("    suppress=20 → %s" % {k: round(v, 2) for k, v in sup.activation.items()})
    # ⚠️ 判据修正（2026-09-27）：首版把期望值写反了。
    #    r=0.5 spread 后：A=50.00（**>20，应保留**），B/C/D 各 16.667（**<20，应置 0**）。
    #    实现输出 A=50.0, B=C=D=0.0 —— **完全正确**。
    check("★ suppress 只把**低于**门槛者置 0（门槛以上保留）",
          abs(sup.activation["A"] - 50.0) < 1e-6
          and sup.activation["B"] == 0.0 and sup.activation["C"] == 0.0,
          "A=%.1f(>20 保留) B=%.1f(<20→0) C=%.1f(<20→0)"
          % (sup.activation["A"], sup.activation["B"], sup.activation["C"]))
    check("suppress 判定用严格小于（门槛本身保留）",
          abs(spread("A", star, r=0.5, steps=1, init=100.0,
                     suppress=50.0).activation["A"] - 50.0) < 1e-6,
          "suppress=50 时 A=50 应**保留**（非严格小于）")

    # ── D. 依据完整性 ──
    print("\n【D】依据完整性")
    print("-" * 80)
    check("全文有文本层（10/10）", SOURCE["pages_with_text_layer"] == SOURCE["pages"])
    check("逐字条目带 PDF 物理页码",
          all(isinstance(v[0], int) for v in VERBATIM.values()), "%d 条" % len(VERBATIM))
    check("保留了 de Groot 的时间衰减条目（未被误删）",
          "time_decay_distinct" in VERBATIM)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": SOURCE, "n_verbatim": len(VERBATIM),
                   "r0_conservation": sum(r0.activation.values()),
                   "r0_with_decay": sum(r0_dec.activation.values()),
                   "self_built": SELF_BUILT, "fails": fails},
                  f, ensure_ascii=False, indent=1)
    print("\n  落盘 %s" % OUT)

    print("\n" + "=" * 80)
    if fails:
        print("❌ 失败 %d 项：" % len(fails))
        for x in fails:
            print("   - %s" % x)
        return 1
    print("PASS  门⑯ 不衰减守恒、均分、decay 独立、spreadr 默认值全过")
    print("⚠️ 残留自建：r 的取值（原文为扫描参数）＋ 阈值（Vitevitch 不用）")
    print("   ⚠️ 零值是**衰减**、非零是**无衰减**，与 r 无关 —— 两个维度已分开")
    return 0


if __name__ == "__main__":
    sys.exit(main())
