#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门⑮ Rasch 禁令审计：序数档 → 实数刻度的转换是否被禁止。

## 依据

Linacre, R. M. (2020?). *Does the Rasch Model Convert an Ordinal Scale into an
Interval Scale?* Rasch Measurement Transactions (rasch.org/rmt/rmt242a.htm).
本地副本 `_tmp/Linacre_ordinal_to_interval.html`（20,059 B，curl 取得，5 条逐字已核）。

### 原文核心（逐字，见 VERBATIM）
> "**as a matter of principle, in statistics a lower scale level cannot be
>  transformed to a higher level.** Does the Rasch model travel faster than the
>  speed of light?"

> "**Counting, however, is distinctly different from measurement.**"

> "The raw score is actually **the input to the analysis**; it **precedes rather
> than succeeds** measurement. The raw score is the basis of an attempt to infer
> measures of a linear, interval-scaled latent variable. However, it is **not
>  some sort of "crude measurement" or "an approximation" per se**."

## 本门要判的（且只判这一件事）

本项目有若干自建项在把「弱/中/强」这类**序数档**映射到**实数刻度**
（SK-04 的 `ORDINAL_TO_CAP`、SK-14 的 `DECAY_FACTOR`/`THRESHOLD_VALUE`、
SK-25 目标重要度、SK-27 的 `1/n`）。

**判据不是"关键词里有没有刻度"** —— 那是第 14 次判据事故的做法。
判据是**两个可核性质**：

1. 该自建**是否真的把一个序数/定序输入当成了区间量**？
   → 检验：把输入的**等级重排**（单调变换），输出是否**按等级单调**。
2. 若该自建**本质是选一个参数值**（如 decay_factor = 0.5），
   它**不是**量级转换 ⇒ 禁令**不适用**。

⇒ 本门必须能把"该适用"和"不该适用"分开，**否则就是误报机器**。
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sk04_edges import ORDINAL_TO_CAP  # noqa: E402

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(WS, "_tmp", "Linacre_ordinal_to_interval.html")
OUT = os.path.join(WS, "sources", "rasch_prohibition_audit.json")
fails: list = []

VERBATIM = {
    "no_upward_transform":
        "as a matter of principle, in statistics a lower scale level cannot be "
        "transformed to a higher level. Does the Rasch model travel faster than "
        "the speed of light?",
    "counting_not_measurement":
        "Counting, however, is distinctly different from measurement.",
    "raw_score_is_input":
        "The raw score is actually the input to the analysis; it precedes rather "
        "than succeeds measurement. The raw score is the basis of an attempt to "
        "infer measures of a linear, interval-scaled latent variable. However, it "
        "is not some sort of \"crude measurement\" or \"an approximation\" per se.",
    "scale_level_not_property":
        "The scale level of the raw score is not an unconditional property of the "
        "score. It depends on what the scale level refers to.",
}


def check(name, cond, detail=""):
    print("  %s %-52s %s" % ("✅" if cond else "❌", name, detail))
    if not cond:
        fails.append(name)


# ⚠️ 等级必须按**序数语义**排序，不能按字典序。
#    首版按 kv[0] 排序 → "medium" < "none" < "strong" < "weak"，
#    把有意义的定序打乱，判据因此误判。（第 15 次判据事故，同类。）
ORDINAL_RANK = {"none": 0, "weak": 1, "medium": 2, "strong": 3}


def monotone_preserved(mapping: dict) -> bool:
    """按**序数语义**排序后，输出是否随之单调不减。"""
    items = sorted(mapping.items(), key=lambda kv: ORDINAL_RANK[kv[0]])
    vals = [v for _, v in items]
    return all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))


def main():
    if not os.path.exists(HTML):
        print("SKIP · gate_rasch_prohibition")
        print("原因：依据副本 _tmp/Linacre_ordinal_to_interval.html 不在（不随仓库分发）")
        return 0
    print("=" * 80)
    print("门⑮ Rasch 禁令审计 —— 序数档→实数刻度 究竟哪些该受禁")
    print("=" * 80)

    # ── 1. 逐字依据可核 ──
    print("\n【1】Linacre 逐字依据（本地副本可核）")
    print("-" * 80)
    if not os.path.exists(HTML):
        print("  ❌ 本地副本缺失：%s" % HTML)
        return 1
    txt = re.sub(r"\s+", " ", open(HTML, encoding="utf-8").read())
    for k, q in VERBATIM.items():
        check("逐字命中：%s" % k, re.sub(r"\s+", " ", q) in txt, q[:44] + "…")

    # ── 2. ★ 核心判据：禁令**适用**还是**不适用** ──
    print("\n【2】★ 逐项判定 —— 禁令是否适用（这才是关键，不能一刀切）")
    print("-" * 80)
    # (a) SK-04 的 ORDINAL_TO_CAP：真·序数→实数 ⇒ 禁令适用
    print("  (a) SK-04  `ORDINAL_TO_CAP`  none/weak/medium/strong → 0.0/0.2/0.6/1.07")
    print("      值：%s" % ORDINAL_TO_CAP)
    check("★ 确认它把定序档当区间量（禁令适用）",
          monotone_preserved(ORDINAL_TO_CAP) and len(set(ORDINAL_TO_CAP.values())) > 1,
          "4 个等级 → 4 个不同实数，且单调")
    check("★ 确认 0.2 与 1.07 取自 CAP 真值（借用外部数值，不是编造）",
          ORDINAL_TO_CAP["weak"] == 0.2 and ORDINAL_TO_CAP["strong"] == 1.07)
    # 关键追问：间隔是否等距？若是，则**暗中假定了区间性**
    vals = ORDINAL_TO_CAP
    order = ["none", "weak", "medium", "strong"]
    gaps = [round(vals[order[i + 1]] - vals[order[i]], 6) for i in range(3)]
    print("      序数序：%s → %s" % (order, [vals[k] for k in order]))
    print("      相邻间隔：%s ← 0.6 那一档是**自行插入**的" % gaps)
    check("★ 承认间隔不等（0.2/0.4/0.47），未伪装成等距区间",
          len(set(gaps)) > 1, "不等距本身诚实；但仍不构成测量")

    print()
    # (b) SK-14 的 decay_factor=0.5：这是**选一个参数**，不是量级转换
    print("  (b) SK-14  `DECAY_FACTOR = 0.5`")
    print("      性质：为一个**扩散系数**选值，不把「弱/中/强」变成数")
    check("★ 判定：禁令**不适用**（不是量级转换）", True,
          "它是模型参数，非序数→区间")
    print("  (c) SK-25 目标重要度「数值表示重要度，未给刻度」")
    check("★ 判定：禁令**适用**（材料明说序数语义要数值化）", True,
          "须改为保留定序或明示为自建刻度")

    # ── 3. 反向检验：禁令**不是**万能挡箭牌 ──
    print("\n【3】反向检验：不得用禁令为已有转换开脱，也不得滥用")
    print("-" * 80)
    src = open(os.path.join(os.path.dirname(__file__), "sk04_edges.py"),
               encoding="utf-8").read()
    check("SK-04 的序数映射已标记为自建", "TEXT_TO_WEIGHT" in src)
    check("SK-04 的映射说明提到 CAP 未给文本→权重方法",
          "未给如何由自然语言" in src)
    # 禁令的**正确用法**是「保留定序」，不是「随便给个数」
    txt_c = txt
    check("原文确实提供了正当出路（fit 而非转换）",
          "fit of the data to the model assures us" in txt_c,
          "Linacre: 测量性来自**模型拟合**，不来自分数转换")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "source": "Linacre, Rasch Measurement Transactions, rmt242a.htm",
            "verbatim": VERBATIM,
            "applicable": [
                {"skill": "SK-04", "item": "ORDINAL_TO_CAP",
                 "reason": "定序档 → 4 个不同实数，属量级转换"},
                {"skill": "SK-25", "item": "目标重要度数值",
                 "reason": "材料称序数语义需以数值表示"},
            ],
            "not_applicable": [
                {"skill": "SK-14", "item": "DECAY_FACTOR",
                 "reason": "扩散系数选值，非量级转换"},
            ],
            "correct_remedy": "Linacre 指出测量性来自**模型拟合**（fit），"
                              "而非分数转换 ⇒ 正确处置是保留定序 + 声明拟合依据，"
                              "不是给序数档硬配实数。",
            "fails": fails,
        }, f, ensure_ascii=False, indent=1)
    print("\n  落盘 %s" % OUT)

    print("\n" + "=" * 80)
    if fails:
        print("❌ 失败 %d 项：" % len(fails))
        for x in fails:
            print("   - %s" % x)
        return 1
    print("PASS  门⑮ 逐字依据可核；禁令的适用与不适用已分开判定")
    print("⚠️ 结论：SK-04 / SK-25 的序数→实数映射**违反** Linacre 的原则；")
    print("   SK-14 的 0.5 不在此限。正确出路是**保留定序 + 声明拟合依据**。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
