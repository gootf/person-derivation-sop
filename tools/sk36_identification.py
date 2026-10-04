#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SK-36 再修正：S/C/E/I 缺的不是「另一个方程」，而是**参数识别层（parameter identification）**。

## 依据：Oravecz, Tuerlinckx & Vandekerckhove (2016)
*Bayesian Data Analysis with the Bivariate Hierarchical Ornstein–Uhlenbeck
Process Model.* Multivariate Behavioral Research, 51(1), 106-119.
DOI 10.1080/00273171.2015.1110512（KU Leuven 机构库公开全文，**15/15 页有文本层**，
72,677 字符）。

## 核心发现：CTA 的 S/C 与 OU 的 B/μ 是**同构**的

CTA（Rauthmann 手册 PDF 物理页 33，本项目已有）：
    dt = S·c − C·a
即「线索驱动 + 自我抑制」的两项线性结构。

OU 状态方程（同文 PDF 物理页 4 逐字）：
    > "d⃗(t) = B(μ − d⃗(t))dt + σdW(t)   (1)"
  其中 μ = baseline（基线），B = "the 2 × 2 regulatory force (or drift or
  dampening) matrix"（调节力／漂移／阻尼矩阵）。

展开 (1)：  dd⃗ = −B·d⃗·dt + B·μ·dt + σdW(t)
            dd⃗ ≈ (B·μ)·dt − B·d⃗·dt

        「外部输入项」  「自我抑制项」
             ↓                ↓
CTA:      S · c          −  C · a
OU:       B · μ          −  B · d⃗

⇒ **结构同构**：S ↔ B·μ（外部驱动），C ↔ B（自我抑制的速率）。

## 由此可得的、**有依据**的三件事

### ① 稀疏数据不是「误差大」，是**结构性不可识别**
位置方程（同文 PDF 物理页 5 逐字）：
    > "d⃗(t+m) | d⃗(t) ~ N₂( μ + e^(−Bm)(d⃗(t) − μ),
                              Σ − e^(−Bm)Σe^(−BTm) )   (2)"

⇒ 一次观测给出的是**一个分布**，其参数（B、μ、Σ）不能由 2–3 个点定出。
这与「样本少导致估计方差大」是**两件事**，必须分开报告。

### ② 估计路径：不是解方程，是**从观测分布反推参数**
位置方程已把「位置」写成分布。给定观测序列可用其矩匹配 B、μ、Σ。
本实现 `fit_mu_B()` 即此矩匹配，**自建**（原文未给算法）。

### ③ 先验的作用随数据量变化（同文 PDF 物理页 7 逐字）
    > "The BHOUM toolbox follows this philosophy: all priors are set to be vague.
       In addition, the more data one acquires, the less influential the prior
       becomes on the posterior as its shape is overwhelmed by the tighter shape
       of the likelihood."

⇒ 明确了 `ParameterSource` 分级：**数据越多，先验权重越低**。
这不是本项目的发明，是原文陈述的性质。

## ⛔ 原文**未**给出的（不得编造）
全文检索 `sparse` / `few observations` / `power analysis` / `minimum`
—— **全部 0 命中**。

⚠️ 因此：
- ❌ **不能**说「需要至少 N 个观测点」—— Oravecz 2016 没给这个数
- ❌ **不能**引用任何具体样本量要求（那需另找 Driver & Voelkle 的参数恢复研究）
- ✅ 原文只报告了自己的数据：**79 人**（PDF p.9 逐字）
- ✅ 原文只说先验是 vague（弥散），**未**说何种数据量下换何种先验

## 自建清单（如实标注）
- `fit_mu_B()` 矩匹配算法 —— 原文未给算法，只给了方程
- 稀疏度阈值 `MIN_IDENTIFIABLE_POINTS` —— **纯自建启发式，无文献支撑**
- `ParameterSource` 六级枚举 —— 分级思路来自 EXT 检索，**枚举本身是自建**
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

SOURCE = {
    "citation": "Oravecz, Z., Tuerlinckx, F., & Vandekerckhove, J. (2016). Bayesian "
                "Data Analysis with the Bivariate Hierarchical Ornstein-Uhlenbeck "
                "Process Model. Multivariate Behavioral Research, 51(1), 106-119.",
    "doi": "10.1080/00273171.2015.1110512",
    "local": "_tmp/Oravecz2016.pdf",
    "pages": 15, "pages_with_text_layer": 15, "chars": 72677,
    "data_reported": "79 人（PDF 物理页 9 逐字：\"we model pleasantness and activation "
                     "levels of 79 people from the described experience-sampling study\"）",
}
VERBATIM = {
    "eq1": (4, "d(t) = B(mu - d(t))dt + sigmadW(t) (1)"),
    "eq1_desc": (4, "The level of self-regulation is expressed through the 2 x 2 "
                    "regulatory force (or drift or dampening) matrix, B."),
    "eq2": (5, "d(t + m) | d(t) ~ N2(mu + e-Bm(d(t) - mu), "
               "Sigma - e-BmSigmae-BTm), (2)"),
    "eq3": (5, "Equation (3) demonstrates that the scale of the diffusion process "
               "can be partitioned into a dampening contribution of the mean-reversion "
               "process (governed by the regulatory force matrix B) and the stationary "
               "covariance."),
    "prior": (7, "The BHOUM toolbox follows this philosophy: all priors are set to be "
                 "vague. In addition, the more data one acquires, the less influential "
                 "the prior becomes on the posterior as its shape is overwhelmed by the "
                 "tighter shape of the likelihood."),
    "person_specific": (2, "To characterize changes within an individual, repeated "
                           "measures over time are modeled in terms of three person-specific "
                           "parameters: a baseline level, intraindividual variation around "
                           "the baseline, and regulatory mechanisms adjusting toward baseline."),
    "n79": (9, "we model pleasantness and activation levels of 79 people from the "
                "described experience-sampling study"),
}
# 全文检索为 0 的词 —— 记录「原文没说什么」比记录「说了什么」同样重要
ABSENT_IN_SOURCE = ["sparse", "few observations", "power analysis", "minimum"]

# ── 结构同构映射（依据见上）──
ISOMORPHISM = {
    "external_drive": {"CTA": "S * c", "OU": "B * mu", "meaning": "外部输入驱动力"},
    "self_regulation": {"CTA": "- C * a", "OU": "- B * d", "meaning": "偏离基线的自我抑制"},
    "shared_structure": "两者均为「外部驱动 − 自我抑制」的二项线性结构；"
                        "S ↔ B·μ，C ↔ B。",
}

MIN_IDENTIFIABLE_POINTS = 4   # ⚠️ 纯自建启发式，Oravecz 2016 全文 0 命中相关表述


class ParameterSource(Enum):
    """参数来源分级。⚠️ 枚举本身为自建；分级的**思想**来自 EXT 检索与
    Oravecz 2016 关于先验权重随数据量变化的陈述。"""
    EMPIRICAL_FIT = "empirical_fit"            # 由纵向数据矩匹配
    LITERATURE_DEFAULT = "literature_default"  # 文献推荐值
    CALIBRATED_EXAMPLE = "calibrated_example"  # 从模型工作例反推
    USER_SPECIFIED = "user_specified"          # 调用方显式给出
    DIRECTIONAL_ONLY = "directional_only"      # 不足以定量，只做方向判断


@dataclass
class FitResult:
    mu: Optional[float]
    B: Optional[float]
    sigma: Optional[float]
    n_points: int
    identifiable: bool
    source: ParameterSource
    note: str = ""
    warnings: List[str] = field(default_factory=list)


def _is_informative(seq: Sequence[float]) -> Tuple[bool, str]:
    if len(seq) < 2:
        return False, "不足 2 点：无法定义变化率"
    if all(abs(x - seq[0]) < 1e-12 for x in seq):
        return False, "全序列无变化：只能说明「此处未变」，不能推出任何参数"
    return True, ""


def fit_mu_B(obs: Sequence[float]) -> FitResult:
    """矩匹配估计 OU 的 μ 与 B（**自建算法**，原文只给方程）。

    依据：位置方程 (2) 给出条件分布；用一阶矩与指数衰减形状匹配。
    ⚠️ 这**不是**最大似然、也不是贝叶斯后验。原文的路径是
       「vague prior + MCMC」，本函数是简化替身。
    """
    ok, why = _is_informative(obs)
    if not ok:
        return FitResult(None, None, None, len(obs), False,
                         ParameterSource.DIRECTIONAL_ONLY, why,
                         ["不可识别：不得用默认值伪装成估计值"])
    ys = list(obs)
    mu = ys[0]                                   # 起点作基线估计
    try:
        devs = [abs(y - mu) for y in ys]
        nz = [d for d in devs if d > 1e-12]
        B = 0.0 if not nz else min(2.0, -math.log(max(nz[0], 1e-9) /
                                                    max(nz[-1], 1e-9)) / max(len(nz) - 1, 1))
        sigma = float(sum(devs) / len(devs))
    except (ValueError, ZeroDivisionError, OverflowError):
        return FitResult(None, None, None, len(obs), False,
                         ParameterSource.DIRECTIONAL_ONLY, "数值不稳定",
                         ["不可识别"])
    if len(ys) < MIN_IDENTIFIABLE_POINTS:
        return FitResult(mu, B, sigma, len(ys), False,
                         ParameterSource.DIRECTIONAL_ONLY,
                         "点数 %d < 自建阈值 %d" % (len(ys), MIN_IDENTIFIABLE_POINTS),
                         ["**不可识别**：任何 (S,C,E,I) 都可复现这 %d 点 ⇒ 不得输出数值"
                          % len(ys)])
    return FitResult(mu, B, sigma, len(ys), True, ParameterSource.EMPIRICAL_FIT,
                     "矩匹配（自建算法，非 MLE/贝叶斯）",
                     ["自建：矩匹配非原文算法；自建：可识别性阈值无文献支撑"])
