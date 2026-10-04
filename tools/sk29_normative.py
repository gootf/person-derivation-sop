#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SK-29 重建：规范贡献**有外部依据**，不再是纯自建。

## 依据链（本项目台账自己指向上游）

台账 P30-04（`necessary`，P30_Alves_Viana_Lucena_2018 p.6）明写：
「该概念**扩展自 Neto (2011)**，本文加入目标权重与人格特质权重」

⇒ 上游即 **Neto & Santos (2011), NBDI: An Architecture for Goal-Oriented
Normative Agents**（SCITEPRESS 公开 PDF，10 页，有文本层）。
**本项目此前只引了下游 2018，漏掉了它自己指明的上游。**

## 上游给了什么（本文件的全部依据）

Neto 2011, PDF 物理页 5-9：

| 出处 | 逐字要点 | 对应台账 |
|---|---|---|
| p.5 | 义务：若规范所述状态 == 某欲望/意向所述状态 ⇒ 贡献为**正**，由 `g(n.DeonticConcept, n.State)` **按该欲望的优先级**定量 | P30-04 |
| p.5 | 禁止：同上情形但贡献为**负**（`g` 取**绝对值**，符号由 deontic 概念定） | P30-04 |
| p.5 | 其余情形贡献为**零**（不干扰欲望达成） | P30-04 |
| p.5 | 奖励**永不产生负面影响**，总是正向或中性；`r(n.Rewards)` 返回**受益欲望优先级之和** | P30-08 |
| p.5-6 | 惩罚同理计入 | P30-08 |
| p.6 | **「我们考虑任何规范元素产生相同的贡献，即 1」** ← **刻度依据** | §5.1 原缺口 |
| p.7 | 若履行贡献 **≥** 违反贡献 ⇒ 选履行；否则选违反 | P30-06 |
| p.7 | 冲突 = 两个规范**针对同一状态**、一个义务一个禁止、且**都想履行或都想违反** | P30-06 |
| p.7 | 冲突时取**贡献更高**者 | P30-06 |
| p.9 | 人格特质通过 `p.annotatePriority(±1)` 影响**计划优先级** | P30-07 第二位置 |

## 因此本实现的"自建"只剩一处

下游 2018 论文声称加入「目标权重与人格特质权重」，但**未给出合成函数**
（这正是 §5.1 登记的自建项）。本实现的处置：

  contribution(n) = g(±) · w_goal · w_trait  ... ⚠️ **乘法权重是自建**

**为什么不能用加法**？乘法与加法都符合"权重"这个词，
但乘法有一个可检验后果：权重为 0 时贡献为 0（与"不计入"等价）。
加法下权重为 0 **不**归零。因此**必须选一种**，而这不是形式推导能定的。

**本实现的选法与理由**：用**加法**做目标权重（重要度是"多少"的量纲，
与贡献同量纲相加），**乘法**做人格特质权重（人格特质是"倾向强度"，
更像调节系数而非可加项）。**这两个选择是自建的**，已集中在 `SELF_BUILT`。

⚠️ 换掉它们需要找到明确给出合成式的文献。找不到就一直是自建。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal

# ════════════════════════════════════════════════════════════════
# 外部依据
# ════════════════════════════════════════════════════════════════
SOURCE = {
    "id": "EXT-05",
    "citation": "Neto, N., & Santos, F. (2011). NBDI: An Architecture for "
                "Goal-Oriented Normative Agents. ICAART 2011, pp. 621-628.",
    "url": "https://www.scitepress.org/PublishedPapers/2011/31798/31798.pdf",
    "has_text_layer": True, "pages": 10,
    "upstream_of": "P30 (Alves, Viana & Lucena 2018) —— 下游台账自己指明",
}
VERBATIM = {
    "obligation_positive": (5, "In case of obligations, it checks if the state "
        "described in the norm is equal to one of the states that the agent has "
        "desire (or intention) to achieve. In affirmative cases, the contribution "
        "is positive and the function g(n.DeonticConcept, n.State) returns a value "
        "indicating the level of norm's contribution that is calculated according "
        "to the priority of the desire that is similar to the state described by norm."),
    "prohibition_negative": (5, "In case of prohibitions ... In affirmative cases, "
        "the contribution is negative since it disturbs the achievement of the "
        "agent's desires or intentions and the function g(n.DeonticConcept, "
        "n.State) calculates the absolute value of the contribution."),
    "otherwise_zero": (5, "In any other case, the contribution is zero since it "
        "does not disturb the achievement of the agent's desires or intentions."),
    "rewards_never_negative": (5, "We consider that rewards can never influence the "
        "agent negatively but always positively or neutrally since they give "
        "permissions to achieve a set of states."),
    "unit_contribution": (7, "We consider that any norm element generates the same "
        "contribution that is 1."),
    "fulfil_threshold": (7, "If the contribution for fulfilling the norm is greater "
        "than or equal to the contribution for violating the norm, the norm is "
        "selected to be fulfilled"),
    "conflict_definition": (7, "If two different norms (one being an obligation and "
        "the other one a prohibition) specify the same state, it is important to "
        "check their status ... if the agent intends to fulfil both norms or to "
        "violate both norms, they are in conflict and it must be solved."),
    "conflict_pick_higher": (7, "in case of conflicts between two norms that the "
        "agent intends to fulfil or violate, the one with highest contribution to "
        "the achievement of"),
}

# ════════════════════════════════════════════════════════════════
# ⚠️ 以下是全部剩余自建（下游 2018 未给合成式）
# ════════════════════════════════════════════════════════════════
SELF_BUILT = {
    "GOAL_WEIGHT": "additive",
    "TRAIT_WEIGHT": "multiplicative",
    "_why": "2018 论文声称「加入目标权重与人格特质权重」但未给合成式。"
            "重要度与贡献同量纲 → 加法；人格特质是调节强度 → 乘法。"
            "两者均可换：若找到明确给出合成式的文献，改这里即可。"
            "**注意两种选择可检验后果不同**：乘法权重为 0 时贡献归零，"
            "加法下不为零 —— 这不是形式推导能定的。",
}


# ════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════
Deontic = Literal["obligation", "prohibition"]


@dataclass
class Desire:
    state: str
    priority: int = 1      # 上游 p.7「任何规范元素产生相同的贡献，即 1」为默认刻度


@dataclass
class Norm:
    state: str
    deontic: Deontic
    rewards: list = field(default_factory=list)    # 许可达成的状态（Algorithm 3 用）
    punishments: list = field(default_factory=list)  # 惩罚的状态（Algorithm 4 用）
    # 上游 Algorithm 4 读的是 n.punishments.DeonticConcept —— 惩罚项**自己**的
    # deontic 类型，不是主规范取反。缺省为 prohibition（惩罚通常是禁止）。
    punishments_deontic: Deontic = "prohibition"
    goal_weight: int = 1      # 目标权重（下游加入）
    trait_weight: float = 1.0  # 人格特质权重（下游加入）
    name: str = ""


@dataclass
class Resolution:
    decision: str          # fulfil / violate
    fulfil_contribution: float
    violate_contribution: float
    reason: str
    trace: list = field(default_factory=list)


# ════════════════════════════════════════════════════════════════
# 核心
# ════════════════════════════════════════════════════════════════
def _g(deontic: Deontic, desire_priority: int) -> int:
    """上游 g(n.DeonticConcept, n.State)（PDF 物理页 5）—— 返回**绝对值**。

    上游伪码中 g 始终取正值，符号由调用处的 `+`/`-` 决定
    （Algorithm 3 行 5 / 行 12，Algorithm 4 行 5 / 行 12）。
    """
    return abs(desire_priority)


def contribution(norm: Norm, desires: list, *, fulfilling: bool) -> float:
    """计算履行 or 违反某规范对达成欲望的贡献。

    ⚠️ 实现严格对应上游两个**独立**算法（PDF 物理页 6），不是同一函数的取反：

      Algorithm 3「Evaluating the fulfilment」：
        义务:  if n.State == d then  x = x + g(n.DeonticConcept, n.State)
        禁止:  if n.State == d then  x = x - g(n.DeonticConcept, n.State)
        最后:  x = x + r(n.Rewards)

      Algorithm 4「Evaluating the violation」：
        惩罚是禁止型:  x = x - g(n.punishments.DeonticConcept, n.punishments.State)
        惩罚是义务型:  x = x + g(n.punishments.DeonticConcept, n.punishments.State)
        **没有 r(n.Rewards) 这一行**

    ⇒ 奖励只属履行侧；违反侧只看惩罚项，且惩罚项的符号由**它自己的**
      deontic 决定（不是"主规范取反"）。
    这也是初版实现错的地方：把违反写成"主规范取反 + 也拿奖励"，
    导致禁止型规范的符号整个反过来。
    """
    total = 0.0
    trace = []

    if fulfilling:
        # ── Algorithm 3 ──
        for d in desires:
            if d.state == norm.state:
                v = d.priority if norm.deontic == "obligation" else -d.priority
                total += v
                trace.append("g(%s,%s)=%+d" % (norm.deontic, d.state, v))
        r = sum(d.priority for d in desires if d.state in norm.rewards)
        if r:
            total += r
            trace.append("r(rewards)=+%d" % r)
    else:
        # ── Algorithm 4：只算惩罚项，符号由惩罚项自己的 deontic 决定 ──
        for d in desires:
            if d.state in norm.punishments:
                sign = -1 if norm.punishments_deontic == "prohibition" else 1
                v = sign * d.priority
                total += v
                trace.append("p(%s,%s)=%+d"
                             % (norm.punishments_deontic, d.state, v))

    # 下游 2018 的加权在此叠加（自建，见 SELF_BUILT）
    if SELF_BUILT["GOAL_WEIGHT"] == "additive":
        total = total * 1.0 + norm.goal_weight
        trace.append("×1 + goal_w(%d)" % norm.goal_weight)
    if SELF_BUILT["TRAIT_WEIGHT"] == "multiplicative":
        total = total * norm.trait_weight
        trace.append("× trait_w(%.2f)" % norm.trait_weight)
    return total


def select(norm: Norm, desires: list) -> Resolution:
    """上游 Algorithm 5 + p.7：履行贡献 ≥ 违反贡献 ⇒ 选履行。"""
    f = contribution(norm, desires, fulfilling=True)
    v = contribution(norm, desires, fulfilling=False)
    dec = "fulfil" if f >= v else "violate"
    return Resolution(dec, f, v,
                       "履行 %+.2f vs 违反 %+.2f → %s（上游 p.7 判据：履行≥违反选履行）"
                       % (f, v, dec),
                       ["履行: " + (", ".join(contribution.__doc__ or "") or "")])


def has_conflict(n1: Norm, n2: Norm, r1: Resolution, r2: Resolution) -> bool:
    """上游 p.7 冲突定义：**同一状态** + 一义务一禁止 + 决策相同。"""
    if n1.state != n2.state:
        return False
    if n1.deontic == n2.deontic:
        return False
    return r1.decision == r2.decision


def solve_conflict(n1: Norm, n2: Norm, r1: Resolution, r2: Resolution):
    """上游 p.7：取贡献更高者。**相等时不得静默任选**（本项目加的自检）。"""
    key = "fulfil_contribution" if r1.decision == "fulfil" else "violate_contribution"
    c1, c2 = getattr(r1, key), getattr(r2, key)
    if c1 == c2:
        return None, ("⚠️ 贡献完全相等（%.2f）—— 上游未给平局规则。"
                      "**不得默认任选**：交人工裁决，或改上游 Step-1 的刻度。" % c1)
    return ((n1, n2, c1, c2) if c1 > c2 else (n2, n1, c2, c1)), ""
