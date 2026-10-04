#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SK-16 重建：三值判定不用标量阈值，改用**域向量 ＋ GRADE 式合成**。

## 为什么推翻原设计

原 SK-16 把三值分界写成「边权 `w` **足够强**」，即一个标量阈值 `f`。
外部依据（GRADE，见 sources/external_evidence/external_evidence_registry.json EXT-01）明确否定这种结构：

  "concerns about domains for rating down may not equate in a one-to-one
   relationship to the overall certainty. For example, limitations pertaining
   to the risk of bias ... and indirectness domains are identified, but these
   limitations are not serious enough for moving down each of the domains,
   the overall evidence type may be downgraded by one level when limitations
   for both domains are considered together"

即：**单个弱信号不足以把「无冲突」推成「信息不足」，但多个弱信号合并可以。**
标量阈值表达不了这一点 —— 它假定「足够强」是一个可数的量。

## 本模块的取舍（必须显式）

GRADE 给了**域的清单**与**非线性的合成方向**，但**没给刻度**：
「域有多严重」「几个域合并算降几级」在 GRADE 中交给临床判断。

因此本实现：
  · 域的**存在与方向** —— 外部依据支持（5 降级域 / 3 升级标准的结构被借用，
    但按本项目的机制层重命名，下表给出映射与理由）
  · 域的**严重度刻度** —— **自建**，三档（无／轻／重）
  · 合成规则 —— **自建**，但形式取自 GRADE 的「累积降级 + 合并降级」

⚠️ 三个刻度参数（DOMAIN_SCALE / COMBINE 权重）**不是材料结论**。
   本模块把它们集中在 `SELF_BUILT` 段，便于替换成有依据的版本。
   换掉它们就能把本技能从「自建为主」升级到「有外部依据」——
   前提是找到给出刻度的文献。
"""
from __future__ import annotations

import sys
import os
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ════════════════════════════════════════════════════════════════
# 外部依据（GRADE 结构）
# ════════════════════════════════════════════════════════════════
# GRADE 5 个降级域：risk of bias / inconsistency / indirectness /
#                  imprecision / publication bias
# GRADE 3 个升级标准：strength of association / dose-response /
#                  opposing plausible residual confounding
#
# 本项目的机制层没有「发表偏倚」这一层（本项目不做文献检索的偏倚校正），
# 也没有「剂量-反应」的实验设计。但**有**两个 GRADE 没有的域：
#   · 行为唯一性不足   ← P22-05「普遍被期望的行为不携带独特性信息」
#   · 行为意向性未确认 ← P22-02「只有当行为后果被认为是该人有意造成时，才可归因」
# 两者都是 P22 系列的 necessary 规则，**比 GRADE 的对应项更贴近本项目**。
GRADE_5_DOWN = ["risk_of_bias", "inconsistency", "indirectness",
                "imprecision", "publication_bias"]
GRADE_3_UP = ["strength_of_association", "dose_response",
              "opposing_residual_confounding"]

DOMAIN_MAP = {
    # 本项目域 ← 依据
    "source_weak":      ("GRADE.risk_of_bias",
        "断言所依据的来源本身弱（单一处、含混）→ 对应 GRADE risk_of_bias"),
    "ambiguous":         ("GRADE.inconsistency",
        "来源文本含糊 → GRADE inconsistency 的本项目对应物（P44-08）"),
    "discounted":        ("GRADE.indirectness",
        "被情境折扣 → 间接性（P23-11 折扣原则）"),
    "non_unique":        ("（本项目专有，对应 GRADE 的无直接对应）",
        "普遍被期望的行为不携带独特性信息（P22-05）"),
    "intention_unclear": ("（本项目专有，对应 GRADE 的无直接对应）",
        "行为意向性未确认时不可归因到倾向（P22-02）"),
}

# ════════════════════════════════════════════════════════════════
# ⚠️ 以下全部是【自建】。不是材料结论，也不是 GRADE 结论。
# ════════════════════════════════════════════════════════════════
SELF_BUILT = {
    "DOMAIN_SCALE": {
        "none": 0, "light": 1, "heavy": 2,
        "_why": "GRADE 只说『不严重/严重』，未给刻度。三档是可执行的最简划分；"
                "改成二档会让『两个 light 域』与『一个 heavy 域』无法区分，"
                "而 GRADE 恰恰强调合并效应。",
    },
    "COMBINE": {
        # 合成规则：各域严重度求和 → 映射到最终档
        # GRADE 原文：单个域不严重时，合并考虑可降一级 ⇒ 线性求和 ＋ 阶梯
        "thresholds": [(0, "none"), (1, "light"), (3, "heavy"),
                       (5, "very_heavy")],
        "_why": "阶梯取 GRADE「累积降级」的定性形状。具体数字无外部依据。",
    },
    "CONFLICT_OVERRIDE": True,
    "_conflict_why": "强反向边（heavy 源 + 未折扣）直接判『冲突』，"
                     "不进入域合成 —— 否则弱正向证据会稀释强反向证据。",
}


# ════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════
@dataclass
class Edge:
    src: str
    sigma: int            # +1 支持 / -1 相反
    w: Optional[float]    # None = 未标定
    discounted: bool = False   # 被情境折扣（P23-11）
    source_quality: str = "none"   # none/light/heavy（P22-01 对应度）
    intention: str = "none"        # none/light/heavy（P22-02 意向性）
    uniqueness: str = "none"       # none/light/heavy（P22-05 独特性）


@dataclass
class Verdict:
    value: str                    # 冲突 / 信息不足 / 无冲突
    reason: str
    domains: dict = field(default_factory=dict)   # 域 → 严重度
    total: int = 0
    confidence: str = "exact"     # exact / manual
    notes: list = field(default_factory=list)


# ════════════════════════════════════════════════════════════════
# 核心：三值判定
# ════════════════════════════════════════════════════════════════
def judge(assertion: str, in_edges: list, ambiguous: str = "none") -> Verdict:
    """对一条功能断言做三值判定。

    与原版的**根本差别**：不比较标量阈值，只统计**域**，
    再按 GRADE 的非线性规则合成。
    """
    SC = SELF_BUILT["DOMAIN_SCALE"]
    if not in_edges:
        # 无入边：不是「信息不足」，是「无冲突」（维度陈述）——
        # 这是原契约已有的区分，保留。
        return Verdict("无冲突", "入边集为空，且已确认为维度陈述",
                       {}, 0, "exact")

    neg = [e for e in in_edges if e.sigma < 0]
    pos = [e for e in in_edges if e.sigma > 0]

    # ── 强反向边 → 冲突（覆盖，不进合成） ──
    if SELF_BUILT["CONFLICT_OVERRIDE"]:
        for e in neg:
            if (e.source_quality == "heavy" and not e.discounted
                    and e.w is not None):
                return Verdict(
                    "冲突",
                    "存在未折扣且来源强度为重的反向边（%s）" % e.src,
                    {"_override": e.src}, 0, "exact",
                    ["强反向边直接判冲突，不被弱正向证据稀释"])

    # ── 弱反向边 → 不判冲突，进入域合成 ──
    domains = {}
    for e in in_edges:
        if e.source_quality != "none":
            domains["source_weak"] = max(domains.get("source_weak", 0),
                                         SC[e.source_quality])
        if e.discounted:
            domains["discounted"] = max(domains.get("discounted", 0), SC["light"])
        if e.intention != "none":
            domains["intention_unclear"] = max(
                domains.get("intention_unclear", 0), SC[e.intention])
        if e.uniqueness != "none":
            domains["non_unique"] = max(domains.get("non_unique", 0),
                                        SC[e.uniqueness])
    if ambiguous != "none":
        domains["ambiguous"] = max(domains.get("ambiguous", 0), SC[ambiguous])

    total = sum(domains.values())
    label = "none"
    for th, lab in SELF_BUILT["COMBINE"]["thresholds"]:
        if total >= th:
            label = lab
    combined = {"none": "无冲突", "light": "无冲突",
                "heavy": "信息不足", "very_heavy": "信息不足"}[label]

    # 有反向边但合成只到 light → 仍是无冲突，但**必须留痕**
    notes = []
    if neg and combined == "无冲突":
        notes.append("存在 %d 条反向边但均未达 heavy（%s）→ 按契约"
                     "『证据不足与证据相反是两件事』判无冲突"
                     % (len(neg), ",".join(e.src for e in neg)))
    return Verdict(combined,
                   "域向量 %s 合成 total=%d → %s" % (domains, total, label),
                   domains, total, "exact", notes)


# ════════════════════════════════════════════════════════════════
# 与旧接口的兼容层
# ════════════════════════════════════════════════════════════════
def judge_legacy_w(w, ambiguous=False, discounted=False):
    """旧的「标量阈值」调用方式。

    ⚠️ 保留它是为了**让既有 harness 继续跑**，不代表这个接口是推荐用法。
    它把 w 强行映射到域，映射规则是自建的。
    """
    e = Edge(src="legacy", sigma=(-1 if (w or 0) < 0 else 1), w=w,
             discounted=discounted,
             source_quality="heavy" if w is not None and abs(w) >= 0.5 else "light")
    return judge("legacy", [e], ambiguous="light" if ambiguous else "none")
