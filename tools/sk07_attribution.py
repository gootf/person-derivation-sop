#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SK-07 重建：归因折扣**不是单调衰减函数**。

## 外部依据

Gilbert & Malone (1996), *The Correspondence Bias*, Psychological Bulletin 120(3),
392-416（MIT 公开 PDF，有文本层，18 页）。本文件逐字引文均取自该 PDF，
PDF 物理页 1-based。

## 为什么推翻原设计

原 SK-07 把归因折扣建成「**折扣的函数形式**」——
隐含假设：情境理由越多，归因强度越低，**单调递减**。

Gilbert & Malone 明确指出折扣原则有**三种失效情形**，
其中两种会让"折扣"**方向反转或完全失效**：

  PDF 物理页 13-14（逐字）：
  "These are the cases of **self-induced constraint**,
   **omnipresent constraint**, and **superfluous constraint**."

  自生约束（self-induced）：情境是**人物自己选择进入**的
  → "individuals appear to **gravitate actively toward social situations that will
     foster and encourage the behavioral expression of their own characteristic
     dispositions**"
  ⇒ 此时"情境理由"本身就是** dispositions 的表达**，不是外生干扰。
  ⇒ 继续折扣会**抹掉真实特质**。

  弥散约束（omnipresent）：情境**持久**时不是"暂时波动"而是"**创造**倾向"
  → "when situations are temporary, they encourage temporary fluctuations in
     overt behavior ... But when situations are **enduring, they may foster
     enduring behavioral tendencies**, and one says that **the actor has been
     changed by the situation**."
  → "observers who attempt to use the discounting principle to subtract out the
     effects of disposition-generating situations (e.g., 'The battered child isn't
     dispositionally fearful, she's just been in a scary situation for 10 years')
     will end up with an **erroneous inference**."

  多余约束（superfluous）：情境约束**实际未起作用**时，
  按它折扣同样是错的。

**结论**：折扣不是 `f(情境理由数)` 的单调函数，而是
**「情境理由是否外生于人物倾向」这一判断的函数**。
本项目台账 P23-11 **自己已经写了**「有些时候折扣效应不像理论所提示的那么强」，
但台账把它压成了「双向方向明确，无函数形式」——**方向对了，缺的不是数值，是判断维度**。

## 本实现的三种约束类型

| 类型 | 判定 | 折扣处理 | 依据 |
|---|---|---|---|
| `imposing` 外加 | 情境独立于人物，行为被情境要求 | **正常折扣** | Kelley 1967 discounting principle（台账 P23-11） |
| `self_induced` 自生 | 人物主动选择/被倾向吸引进入 | **不折扣**，且须记为「倾向的证据」 | Gilbert & Malone PDF P13 |
| `omnipresent` 弥散 | 情境持久且**塑造**倾向 | **不折扣**，且反向记为「倾向已被塑造」 | Gilbert & Malone PDF P14 |
| `superfluous` 多余 | 约束存在但实际未起作用 | **不折扣** | Gilbert & Malone PDF P14 |
| `unknown` 未知 | 无法判定是否外生 | **不得默认折扣** —— 默认折扣等于默认抹除特质 | 本实现的保守默认（自建，须显式） |

## 仍然自建的部分

⚠️ `unknown` 的默认处理是**自建的保守选择**，不是文献结论。
   文献只说"当情境与倾向因果相关时折扣原则不是有效逻辑工具"，
   没有说"无法判断时该怎么办"。本实现选「不折扣」是因为
   折扣会**不可逆地抹除**特质证据，而不折扣最坏只是过度归因
   （而过度归因可被三值判定的「信息不足」接住）。

   这与 SK-16 的 `MANUAL` 约定一致：不确定时降级为人工，不做默认动作。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# 外部依据登记
EXTERNAL_SOURCE = {
    "id": "EXT-04",
    "citation": "Gilbert, D. T., & Malone, B. K. (1996). The Correspondence Bias. "
                "Psychological Bulletin, 120(3), 392-416.",
    "url": "https://web.mit.edu/curhan/www/docs/Articles/biases/"
           "117_Psychological_Bulletin_21_(Gilbert).pdf",
    "has_text_layer": True,
    "pages": 18,
}

# 三种约束失效情形（逐字，PDF 物理页）
VERBATIM = {
    "three_cases": (13, "These are the cases of self-induced constraint, "
                        "omnipresent constraint, and superfluous constraint."),
    "self_induced": (13, "individuals appear to gravitate actively toward social "
                         "situations that will foster and encourage the behavioral "
                         "expression of their own characteristic dispositions"),
    "omnipresent": (14, "when situations are temporary, they encourage temporary "
                        "fluctuations in overt behavior ... But when situations are "
                        "enduring, they may foster enduring behavioral tendencies, "
                        "and one says that the actor has been changed by the "
                        "situation."),
    "omnipresent_erroneous": (14, "observers who attempt to use the discounting "
                                   "principle to subtract out the effects of "
                                   "disposition-generating situations ... will end "
                                   "up with an erroneous inference."),
}


@dataclass
class Attribution:
    disposition_strength: float      # 0..1，倾向证据强度
    situational_reason: Optional[str]  # 情境给出的理由（若有）
    constraint_kind: str = "unknown"  # 见上表
    enduring: bool = False            # 情境是否持久
    actually_constrained: bool = True  # 约束是否真的起了作用
    self_selected: bool = False        # 是否由人物自己选择/被吸引进入
    notes: list = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []


def discount(a: Attribution) -> Attribution:
    """应用折扣原则。返回带 discount_applied 与 kind 的新对象。"""
    a.notes = list(a.notes)
    kind = a.constraint_kind

    # ── 三种已知失效情形：不得折扣 ──
    if kind == "self_induced" or a.self_selected:
        a.notes.append(
            "自生约束：情境是人物自己选择/被倾向吸引进入的，"
            "此时情境理由是**倾向的表达**而非外生干扰 → 不折扣")
        a.discount_applied = False
        a.disposition_is_evidence = True
        return a

    if kind == "omnipresent" or (a.enduring and a.situational_reason):
        a.notes.append(
            "弥散约束：情境持久且可能**创造**倾向（Gilbert & Malone PDF 物理页 14）"
            "→ 不得扣除；「受虐的孩子不是气质害怕，只是在可怕环境待了十年」"
            "是该原则被误用的经典反例")
        a.discount_applied = False
        a.disposition_is_evidence = False
        a.situation_formed_disposition = True
        return a

    if kind == "superfluous" or (a.situational_reason
                                 and not a.actually_constrained):
        a.notes.append(
            "多余约束：情境理由存在但**实际未起作用** → 不得按它折扣")
        a.discount_applied = False
        return a

    # ── 正常折扣 ──
    if kind == "imposing" and a.situational_reason:
        a.discount_applied = True
        a.notes.append("外加约束：正常应用 Kelley 1967 折扣原则（台账 P23-11）")
        return a

    # ── unknown：自建的保守默认 ──
    a.discount_applied = False
    a.notes.append(
        "⚠️ unknown：无法判定情境是否外生于人物倾向。**默认不折扣**"
        "（自建的保守选择，非文献结论）—— 折扣会不可逆地抹除倾向证据，"
        "而不折扣的最坏结果（过度归因）可被三值判定的『信息不足』接住。")
    a.needs_manual = True
    return a


if __name__ == "__main__":
    for kind, sel, end, real in [
        ("imposing", False, False, True),
        ("self_induced", True, False, True),
        ("omnipresent", False, True, True),
        ("superfluous", False, False, False),
        ("unknown", False, False, True),
    ]:
        a = Attribution(1.0, "情境提供了明显理由", kind,
                        enduring=end, actually_constrained=real,
                        self_selected=sel)
        r = discount(a)
        print("%-14s 折扣=%-5s %s" % (kind, r.discount_applied, r.notes[-1][:60]))
