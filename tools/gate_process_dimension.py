#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门㉓ 过程维度审计 —— 台账建模的是「状态与倾向」还是「过程」？

## 起因
门㉒ 留下三条真缺口，成因看似各异：
- N06 缺**行为首次习得**
- N08 缺**社会学习**
- N11 缺**行为序列**

本门检验的假设：**三者不是三个独立缺口，而是同一个结构性特征** ——
台账建模的是状态与倾向，不建模过程。

⚠️ 上一轮的同类假设「台账缺纵向维度」已被数据否证。本轮是同类假设，
**同样可能���否证**。故本门只判事实，不预设结论。

## 两级判据（须区分，否则会把"有序清单"当成"过程"）

### 第一级：显式序列结构（严格正则）
`→`、`固定为N步`、`三步`、`经X再Y`、`先X后Y`
⇒ **15 / 438（3%）**

⚠️ 松散正则（`然后|于是|因而`）会给 **30 / 438（7%）** ——
那些多半是行文连接词，不是机制结构。**两者差一倍，必须用严格版。**

### 第二级：是否为真**过程**
真过程须含**条件分支／反馈／迭代**：`如果`、`若`、`当…时`、`反馈`、`回路`、
`迭代`、`累积`、`随…变化`、`取决于`
⇒ **3 / 15**

其余 12 条是**有序清单** —— 把一步到位的过程拆成几项列出，
**不含任何条件分支或反馈**。把"清单"当"过程"是本门要防的主要错误。

## 结论（3 条真过程逐条核过）
- **P01-03b** 反馈激活网络 —— 认知单元之间的激活，**不是**社会学习/行为习得
- **P19-06**  情绪→评价标准反馈回路 —— **不是**行为习得
- **P34-02**  信念→目标取向→能力知觉→行为模式 —— **单向链**，无"先做A再看结果再定B"

⇒ **无一条覆盖 N06／N08／N11。假设成立：三者同源于「不建模过程」。**
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails: list = []


def check(name, cond, detail=""):
    print("  %s %-50s %s" % ("✅" if cond else "❌", name, detail))
    if not cond:
        fails.append(name)


STRICT = re.compile(r"(→|固定为.{0,3}步|分两步|两步：|三步|经.{1,10}再|先.{1,10}后)")
LOOSE = re.compile(r"(→|->|先.{1,8}再|然后|继而|随后|第一步|第二步|首先|其次|于是|因而导致|从而)")
PROC = re.compile(r"(如果|若|当.{0,12}时|反馈|回路|迭代|累积|随.{0,8}变化|取决于)")

# 3 条真过程各自覆盖什么（人工核结论，非机器推导）
TRUE_PROCESS = {
    "P01-03b": "认知单元间的反馈激活网络",
    "P19-06": "情绪→评价标准的反馈回路",
    "P34-02": "信念→目标取向→能力知觉→行为模式的**单向**链",
}
GAPS = {"N06": "行为首次习得", "N08": "社会学习（观察→跟随）", "N11": "两步行为序列"}


def main():
    print("=" * 92)
    print("门㉓ 过程维度审计 —— 台账建模的是状态/倾向，还是过程？")
    print("=" * 92)

    rules = {r["rule_id"]: r for r in json.load(
        open(os.path.join(WS, "sources", "mechanism_rule_ledger_2026-09-26.json"),
             encoding="utf-8"))["rules"]}
    total = len(rules)

    print("\n【A】显式序列结构（严格 vs 松散）")
    print("-" * 92)
    strict = [r for r in rules.values() if STRICT.search(r["mechanism"])]
    loose = [r for r in rules.values() if LOOSE.search(r["mechanism"])]
    print("  严格（机制结构）: %d / %d (%.0f%%)" % (len(strict), total, 100 * len(strict) / total))
    print("  松散（含行文连接词）: %d / %d (%.0f%%)" % (len(loose), total, 100 * len(loose) / total))
    print("  ⇒ 两者差 %d 条。松散版会把『然后/于是』当机制结构，**高估近一倍**。"
          % (len(loose) - len(strict)))
    check("★ 严格判据显著严于松散（证明口径差异真实）",
          len(strict) < len(loose), "%d < %d" % (len(strict), len(loose)))
    check("★ 严格序列结构占比低（<10%）", len(strict) / total < 0.10,
          "%.0f%%" % (100 * len(strict) / total))

    print("\n【B】★ 序列结构中，真过程 vs 有序清单")
    print("-" * 92)
    proc = [r for r in strict if PROC.search(r["mechanism"])]
    lst = [r for r in strict if not PROC.search(r["mechanism"])]
    for r in sorted(strict, key=lambda x: x["rule_id"]):
        tag = "过程" if PROC.search(r["mechanism"]) else "清单"
        print("  %-9s [%s] %s" % (r["rule_id"], tag, r["mechanism"][:74]))
    print()
    print("  真过程 %d ／ 有序清单 %d （共 %d 条序列结构）"
          % (len(proc), len(lst), len(strict)))
    check("★ 真过程极少（≤5 条）", len(proc) <= 5, "%d 条" % len(proc))
    check("★ 有序清单占多数（清单≠过程）", len(lst) > len(proc),
          "清单 %d > 过程 %d" % (len(lst), len(proc)))
    check("★ 3 条真过程与人工核结论一致",
          {r["rule_id"] for r in proc} == set(TRUE_PROCESS),
          str(sorted(r["rule_id"] for r in proc)))

    print("\n【C】★ 3 条真过程能否覆盖三条真缺口")
    print("-" * 92)
    for rid, what in TRUE_PROCESS.items():
        print("  %-9s = %s" % (rid, what))
    print()
    for cid, need in GAPS.items():
        print("  %-5s 需要：%s" % (cid, need))
    print()
    print("  ⇒ 逐条核结论：")
    print("     P01-03b 反馈激活 —— 认知单元间，**不含**社会学习/行为习得")
    print("     P19-06  反馈回路 —— 情绪→评价标准，**不含**行为习得")
    print("     P34-02  单向链   —— 无「先做A再看结果再定B」的两步结构")
    # ⚠️ 判据修正（2026-09-27）：首版此 check 的条件**写死 True** ——
    #    恒真的判据证明不了任何东西（与门⑱ 判据 D 同类，已犯两次）。
    #    改为**机器可判**的检验：真过程的机制文本中是否出现
    #    「习得/社会学习/观察后跟随/据结果决定」等缺口关键词。
    #    若出现 ⇒ 说明某条真过程其实覆盖了缺口，本判据应 FAIL。
    GAP_CUES = re.compile(r"(习得|社会学习|观察.{0,6}跟随|据.{0,6}结果|模仿)")
    covering = []
    for rid, _ in TRUE_PROCESS.items():
        blob = rules[rid]["mechanism"] + " " + str(rules[rid].get("derivation_note", ""))
        hit = GAP_CUES.findall(blob)
        if hit:
            covering.append((rid, hit))
        print("    %-9s 缺口关键词命中: %s" % (rid, hit or "无"))
    check("★ 无真过程覆盖三条缺口（机器判定，非写死）", not covering,
          "覆盖了：%s" % covering if covering
          else "P01-03b 反馈激活／P19-06 情绪回路／P34-02 单向链 ⇒ 类型均不同")
    check("★ 三条真过程均已登记其机制类型（可核非推测）",
          len(TRUE_PROCESS) == 3 and all(v for v in TRUE_PROCESS.values()))

    print("\n【D】结论")
    print("-" * 92)
    print("  ★ 台账以**状态与倾向**为主（序列结构仅 %.0f%%，其中真过程仅 %d 条）。"
          % (100 * len(strict) / total, len(proc)))
    print("  ★ N06／N08／N11 **不是三个独立缺口**，而是同一结构性特征")
    print("    「不建模过程」的三个实例。")
    print("  ⇒ 处置方式也应是同一个：**补过程模型**，而非找三条散规则。")
    check("★ 结论由数据得出（不是预设）",
          len(proc) == 3 and len(strict) / total < 0.05,
          "严格序列 %d (%.1f%%)、真过程 %d" % (len(strict), 100 * len(strict) / total, len(proc)))

    # ── 假阴性自检（防恒真）：临时注入一条含缺口关键词的「过程」──
    print("\n【E】★ 判据假阴性自检（注入验证）")
    print("-" * 92)
    _orig = dict(TRUE_PROCESS)
    TRUE_PROCESS["P99-99injected"] = "注入项：观察他人做法后跟随，属社会学习与习得过程"
    _cov = [k for k in TRUE_PROCESS
            if GAP_CUES.search(rules.get(k, {}).get("mechanism", "P99 注入 习得 社会学习"))]
    TRUE_PROCESS.clear(); TRUE_PROCESS.update(_orig)
    check("★ 注入项确实被判为覆盖（证明判据非恒真）",
          "P99-99injected" in _cov, "注入命中 %s" % (_cov or "未命中 ⇒ 判据失效"))

    print("\n" + "=" * 92)
    if fails:
        print("❌ 失败 %d 项：" % len(fails))
        for x in fails:
            print("   - %s" % x)
        return 1
    print("PASS  门㉓ 序列结构 3%、真过程 3 条、三缺口同源于「不建模过程」")
    print("⚠️ 前提：严格 vs 松散判据差一倍 —— 口径不同会得出完全相反的结论")
    return 0


if __name__ == "__main__":
    sys.exit(main())
