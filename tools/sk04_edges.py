#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SK-04 重建：边权 `w` 的语义、取值域、聚合函数**全部有原文**。

## 外部依据（本项目**已有材料**自身载有，非新检索）

Mischel, W., & Shoda, Y. (1995). A Cognitive-Affective System Theory of
Personality: Reconceptualizing Situations, Dispositions, Dynamics, and
Invariance in Personality Structure. Psychological Review, 102(2), 246-268.
本项目 `papers/Mischel_Shoda_1995_CAP_S.pdf`。

### 原文逐字（PDF 物理页 22，Appendix: Details of the Simulation）

> "**Positive (excitatory)** sensitivity and connection weight were assumed to
>  **increase the activation value of the recipient unit by the amount
>  corresponding to the weight** when the source unit was activated.
>  **Negative (inhibitory)** connection weight was assumed to **decrease** the
>  activation of the recipient unit when the source unit was activated.
>  **A connection weight of 0 was equivalent to having no connection.**"

> "We assumed that **all the positive and negative inputs into a mediating unit
>  were simply summed**, and the resultant activation value was **1 if the total
>  activation was positive, and 0 if it was negative.**
>  (Different summing and threshold functions produced essentially the same
>  overall results.)"

> "It is activated by mediating units 1 through 4, with a set of activating
>  weights characteristic for each person. **For Person 1, they were .2, -.56,
>  1.07, and .55**, respectively."  ← Table A1 的真实数值

Table A1（PDF 物理页 22）给出的 situation feature → mediating unit 权重矩阵：
unit1: -0.29 -0.06  0.31 -0.05 -0.42  0.03
unit2:  0.06 -0.62 -0.38 -0.10  1.28  0.29
unit3: -0.56 -0.02  0.20  0.77  0.10 -0.12
unit4:  0.24 -0.14  0.21  1.19 -0.15  1.06

## 这解决了什么

原 SK-04 的自建项「边权 `w` 的取值」缺三样东西，现在**三样都有原文**：
1. **语义**：正=兴奋（按权重大小提高接受单元激活值）、负=抑制、**0 = 无连接**
2. **聚合**：所有正负输入**直接求和**
3. **阈值**：求和结果 **>0 → 1，<0 → 0**（二值化）

⚠️ 原文明确「不同的求和与阈值函数产生基本相同的结果」——
**这说明阈值函数的选择是稳健的，不是承重的**。故门⑫ 会对多种阈值做对照，
证明本实现不依赖某个特定阈值。

## 仍然自建的部分

⚠️ **权重从文本到数值的估计方法**。CAP 只给「个体差异体现在权重上」，
   并提供了一张示例表，**未给如何由自然语言推得具体权重**。
   本项目的 S1 归一化只能产出「弱/中/强」等序数档，
   **映射到 CAP 的实数刻度是自建的**——见 SELF_BUILT。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Optional

# ════════════════════════════════════════════════════════════════
# 外部依据
# ════════════════════════════════════════════════════════════════
SOURCE = {
    "citation": "Mischel, W., & Shoda, Y. (1995). A Cognitive-Affective "
                "System Theory of Personality. Psychological Review, 102(2), 246-268.",
    "local": "papers/Mischel_Shoda_1995_CAP_S.pdf",
    "page": 22,   # Appendix: Details of the Simulation
    "external_retrieval_needed": False,
}
VERBATIM = {
    "weight_semantics": (22,
        "Positive (excitatory) sensitivity and connection weight were assumed to "
        "increase the activation value of the recipient unit by the amount "
        "corresponding to the weight when the source unit was activated. Negative "
        "(inhibitory) connection weight was assumed to decrease the activation of "
        "the recipient unit when the source unit was activated. A connection weight "
        "of 0 was equivalent to having no connection."),
    "aggregation": (22,
        "We assumed that all the positive and negative inputs into a mediating unit "
        "were simply summed, and the resultant activation value was 1 if the total "
        "activation was positive, and 0 if it was negative. (Different summing and "
        "threshold functions produced essentially the same overall results.)"),
    "person1_weights": (22,
        "It is activated by mediating units 1 through 4, with a set of activating "
        "weights characteristic for each person. For Person 1, they were .2, -.56, "
        "1.07, and .55, respectively."),
    "table_a1": (22,
        "unit1: -0.29 -0.06 0.31 -0.05 -0.42 0.03 / "
        "unit2: 0.06 -0.62 -0.38 -0.10 1.28 0.29 / "
        "unit3: -0.56 -0.02 0.20 0.77 0.10 -0.12 / "
        "unit4: 0.24 -0.14 0.21 1.19 -0.15 1.06"),
}

# Table A1 原文数值（用于回归验证）
TABLE_A1 = {
    1: [-0.29, -0.06, 0.31, -0.05, -0.42, 0.03],
    2: [0.06, -0.62, -0.38, -0.10, 1.28, 0.29],
    3: [-0.56, -0.02, 0.20, 0.77, 0.10, -0.12],
    4: [0.24, -0.14, 0.21, 1.19, -0.15, 1.06],
}
PERSON1_BEHAVIOR_WEIGHTS = [.2, -.56, 1.07, .55]

# ════════════════════════════════════════════════════════════════
# 残留自建
# ════════════════════════════════════════════════════════════════
SELF_BUILT = {
    "TEXT_TO_WEIGHT": "未实现 —— 序数档 → CAP 实数刻度的映射",
    "_why": "CAP 给出权重的语义/聚合/阈值与一张示例表，但**未给如何由自然语言"
            "推得具体权重**。本项目 S1 只能产出「弱/中/强」序数档。",
    "_consequence": "序数→实数的映射若要使用，必须声明映射表并标为自建；"
                    "不得声称权重由材料推得。",
}

# 序数档 → CAP 刻度的示例映射（⚠️ 自建，仅示范接口形状）
ORDINAL_TO_CAP = {"none": 0.0, "weak": 0.2, "medium": 0.6, "strong": 1.07}
# ↑ 0.2 与 1.07 取自 CAP Table A1 / Person1 的真实权重，
#   0.6 与 0.0 是插值/端点 —— **映射本身仍是自建**。


@dataclass(frozen=True)
class Edge:
    """一条带权有向边。符号与大小遵循 CAP 原文语义。"""
    src: str
    dst: str
    w: float                      # >0 兴奋；<0 抑制；==0 无连接
    ordinal: Optional[str] = None  # 来源序数档（若由 S1 产出）

    @property
    def excitatory(self) -> bool: return self.w > 0
    @property
    def inhibitory(self) -> bool: return self.w < 0
    @property
    def absent(self) -> bool: return self.w == 0


def activate(incoming: Iterable[float], threshold: str = "sign") -> int:
    """CAP 原文的聚合 + 阈值（PDF 物理页 22）。

    先"simply summed"，再 **1 if positive, 0 if negative**。
    ⚠️ 原文补充「不同的求和与阈值函数产生基本相同的结果」，
       故 threshold 参数仅供稳健性对照，**默认即原文判据**。
    """
    total = sum(incoming)
    if threshold == "sign":
        return 1 if total > 0 else 0
    if threshold == "strict":
        return 1 if total >= 0 else 0     # 变体：把 0 算作激活
    if threshold == "magnitude":
        return total                      # 变体：不二值化
    raise ValueError("unknown threshold: %r" % threshold)


def unit_activation(feature_weights: Iterable[float]) -> int:
    """单个中介单元的激活 = 其来自各情境特征的权重求和后二值化。"""
    return activate(feature_weights)


def behavior_activation(unit_weights: Iterable[float], unit_active: Iterable[int]) -> int:
    """行为脚本单元的激活：四个中介单元各以 Person1 式权重激活。"""
    return activate(w * a for w, a in zip(unit_weights, unit_active))


def from_ordinal(ordinal: str) -> float:
    """序数档 → CAP 刻度。⚠️ **映射表是自建**，见 SELF_BUILT。"""
    try:
        return ORDINAL_TO_CAP[ordinal]
    except KeyError:
        raise ValueError("unknown ordinal: %r" % ordinal)
