#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SK-36 重建：惯性不是"一个系数"，而是**状态变化率方程的矩阵参数**。

## 外部依据（本项目材料 Rauthmann 2021 手册自身载有）

Rauthmann (ed.) 2021, *Handbook of Personality Dynamics and Processes*,
PDF 物理页 33（该书已在本项目 `papers/`，**无需外部检索**）。

### 原文逐字（PDF 物理页 33）
CTA 模型（Revelle, 1986），"just two equations"：

    dt ¼ Sc  Ca            (1)      ← `¼` 是 PDF 的等号，`\x03` 是负号
    da ¼ Et  Ia            (2)

> "This is a simple control theory model with individual differences in
>  personality represented as the values of the **matrices (S, C, E, and I)**
>  thought to affect the linkage between the vectors of external cues (c),
>  latent tendencies (t) and observed actions (a)."

> "Four classes of individual differences are hypothesized: **cue sensitivities,
>  (S)**, the **excitatory strength** between tendencies and actions **(E)**,
>  and the **consummatory linkage (C)** of actions reducing action tendencies.
>  **Choice between actions was an automatic function of actions inhibiting
>  other actions (I)**."

> "**traits were seen as parameters of the CTA model and thus as influencing
>  the rates of change of states.** States were the dynamic consequences of
>  traits affecting **rates of excitation and inhibition**."

### 这解决了什么

原 SK-36 的自建项「动机／情感惯性的系数 —— 无函数」把惯性当**一个标量系数**。
原文明确：**惯性是四类个体差异参数（S, C, E, I），进入两条微分方程。**

⇒ 结构性修正：**不是"缺一个系数值"，而是"系数应是矩阵参数而非标量"**。

### 但仍未解决的部分（诚实记录）

⚠️ 原文**只给方程形式，没给参数的取值方法**。
  - 手册说 CTA 已被实现为 R 的 psych 包 `CTA` 函数（Revelle, 2019），
    **取值的具体算法在那个包里，本项目未获取**。
  - DynAffect / PersDyn（Sosnowska et al., 2019）另给三参数：
    `home base / variability / attractor strength`，
    其中 **attractor strength = rate of return to home base**（PDF 物理页 35）
    —— 这给出了**回归速度**的可辨识含义，但仍无取值方法。

⇒ 自建项从「系数无函数」缩为「**参数取值方法未给**」。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


# ════════════════════════════════════════════════════════════════
# 外部依据（逐字，PDF 物理页）
# ════════════════════════════════════════════════════════════════
SOURCE = {
    "book": "Rauthmann, J. F. (Ed.) (2021). Handbook of Personality "
            "Dynamics and Processes. Oxford University Press.",
    "local": "papers/Rauthmann_2021_Ed_Book_Handbook_of_Personality_Dynamics_and_Processes.pdf",
    "external_retrieval_needed": False,
    "note": "本依据来自项目**已有材料**自身载有的二手综述，非新检索。",
}
VERBATIM = {
    "eqs": (33, "dt ¼ Sc  Ca (1)   da ¼ Et  Ia (2)"),
    "matrices": (33, "individual differences in personality represented as the "
                    "values of the matrices (S, C, E, and I) thought to affect the "
                    "linkage between the vectors of external cues (c), latent "
                    "tendencies (t) and observed actions (a)."),
    "four_classes": (33, "Four classes of individual differences are hypothesized: "
                         "cue sensitivities, (S), the excitatory strength between "
                         "tendencies and actions (E), and the consummatory linkage "
                         "(C) of actions reducing action tendencies. Choice between "
                         "actions was an automatic function of actions inhibiting "
                         "other actions (I)."),
    "traits_as_params": (33, "traits were seen as parameters of the CTA model and "
                             "thus as influencing the rates of change of states. "
                             "States were the dynamic consequences of traits "
                             "affecting rates of excitation and inhibition."),
    "attractor": (35, "Person parameters are the home base, variation around home "
                      "base, and strength of the attractor (rate of return to home base)."),
}

# ════════════════════════════════════════════════════════════════
# 自建项：参数取值方法（原文只给形式）
# ════════════════════════════════════════════════════════════════
SELF_BUILT = {
    "PARAM_FIT": "未实现 —— 原文只给方程形式，未给取值方法",
    "_why": "Rauthmann 手册称 CTA 已实现为 R psych 包的 CTA 函数（Revelle, 2019），"
            "取值算法在包内，本项目未获取。DynAffect/PersDyn 的三参数"
            "（home base / variability / attractor strength）给了**含义**，"
            "但同样无取值方法。",
    "_consequence": "本实现中的 S/C/E/I 只能由**调用方显式给定**，"
                    "不得声称从材料自动推得。这是本技能当前最大限制。",
}


@dataclass
class CTA:
    """CTA 模型（Revelle 1986；载于 Rauthmann 2021 手册 PDF 物理页 33）。

    状态：t = 潜在行动倾向，a = 已观测行动
    输入：c = 外部线索向量
    参数：S 线索敏感度 / C 满足性联结（行动降低倾向）
          E 倾向→行动的兴奋强度 / I 行动间相互抑制
    """

    S: float = 1.0   # cue sensitivity
    C: float = 1.0   # consummatory linkage
    E: float = 1.0   # excitatory strength
    I: float = 0.0   # inhibition between actions

    def dt(self, c: float, a: float) -> float:
        """Eq.(1): dt = S·c − C·a"""
        return self.S * c - self.C * a

    def da(self, t: float, a: float) -> float:
        """Eq.(2): da = E·t − I·a

        ⚠️ 上游 Eq.(2) 字面为 `da ¼ Et  Ia`（第二项无矩阵前缀），
        Rauthmann 手册未标明 I 的作用对象。**本实现假定 I·a**
        （与 Eq.1 同型：自我抑制），这是**自建**——见 SELF_BUILT。
        """
        return self.E * t - self.I * a

    def step(self, t: float, a: float, c: float, dt: float = 1.0) -> tuple:
        """显式欧拉一步。⚠️ 步长形式是自建（原文给微分方程，未给离散化）。"""
        nt = t + self.dt(c, a) * dt
        na = a + self.da(t, a) * dt
        return nt, na

    def run(self, t0: float, a0: float, cues: Sequence[float],
            dt: float = 1.0) -> list:
        t, a = t0, a0
        out = [(t, a)]
        for c in cues:
            t, a = self.step(t, a, c, dt)
            out.append((t, a))
        return out

    def attractor_t(self, c: float) -> float:
        """线索持续为 c 时的**倾向稳态**：令 dt=0 ⇒ t* = S·c / C。

        ✅ 这是 Eq.(1) 的**代数推论**，非自建。
        ⇒ 惯性 = C 越大，回到稳态越快。
        """
        return (self.S * c / self.C) if self.C else float("inf")

    def tau_t(self, c: float) -> float:
        """时间常数 τ = 1 / C。✅ Eq.(1) 的线性系统解，非自建。"""
        return (1.0 / self.C) if self.C else float("inf")


# ════════════════════════════════════════════════════════════════
# DynAffect / PersDyn 三参数（Rauthmann 2021 手册 PDF 物理页 35）
# ════════════════════════════════════════════════════════════════
@dataclass
class DynAffect:
    """affect 的 home base / variability / attractor strength。

    ✅ 参数**含义**有原文依据（PDF 物理页 35）；
    ⚠️ 方程形式与取值方法原文未给 ⇒ 见 SELF_BUILT。
    """
    home_base: float = 0.0
    variability: float = 1.0
    attractor_strength: float = 1.0   # = rate of return to home base
    tau: float = 1.0                  # ⚠️ 自建：attractor→τ 的换算未给

    def target(self, current: float) -> float:
        """回归方向：偏离基线越远，拉回越强（原文「attractor」语义）。"""
        return self.home_base

    def pull(self, current: float, dt: float = 1.0) -> float:
        """⚠️ **纯自建**：线性回归 `x += k(home − x)·dt` 的形式原文未给。

        原文只说「attractor strength = rate of return to home base」，
        即**越大回归越快**，未给具体函数。此处用最简线性形式，
        门⑪ 会验证"增大 attractor_strength ⇒ 回归更快"这一**方向**
        来自原文，而**函数形式**标记为自建。
        """
        k = 1.0 - math.exp(-self.attractor_strength * dt)
        return current + (self.home_base - current) * k
