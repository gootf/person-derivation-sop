#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SK-27 重建：稀释函数**有依据**（ACT-R base-level），但**适用性是本项目的判断**。

## 依据链（三跳，每跳都可核）

台账 GST-03（Kruglanski et al. 2002, PDF 物理页 6）**自己指明上游**：

> "the lower the number of means connected to a given goal (i.e., the smaller
>  the equifinality set) or the lower the number of goals connected to a given
>  means (i.e., the smaller the multifinality set) - the stronger the
>  cognitive association-strength between a given means and the goal.
>  This is analogous to the classic **"fan effect" discussed to by John
>  Anderson (1974, 1983)**."

⇒ 上游 = **Anderson 的 ACT-R 系列**。GST-2002 只给**方向**（越小越强），
   并说该关系画在 **Figures 4 和 5**。

⚠️ **该 PDF 全文 0 张嵌入图**（矢量绘图，文字不在文本层），
   ⇒ 稀释的**具体函数形式在 GST-2002 里不可得**。已核 95 页全部如此。

## 补上的依据：ACT-R 官方参考手册（公开，有文本层）

ACT-R 7.28 Reference Manual, CMU（542 页，**532 页有文本层**，
SHA256 `16a5e730af7ebad6…`）。

### 激活方程（PDF 物理页 262）
> "Here is the general equation for the activation (A) of a chunk i:
>  **A_i = B_i + S_i + P_i + ε_i**
>  B_i: This is the **base-level activation** and reflects the recency and
>       frequency of use of the chunk.
>  S_i: This is the **spreading activation** value..."

### base-level 的衰减公式（PDF 物理页 263）
```
B_i = β_i + ln( Σ_{j=1..n} 1 / (d · t_j) )          (:ol 为 nil，完整式)
B_i = β_i + ln( n / (d · (L − d)) )                  (:ol 为 t，近似式)
```
> "**d: The decay parameter** which is set using the :bll parameter."

### 推荐值（PDF 物理页 269）—— ★ 这就是刻度
> "The value nil means do not use base-level learning and is the default value,
>  a number means that base-level is enabled and the given value is the decay
>  parameter. **The recommended value for :bll is .5**, and it is one of the few
>  parameters which have a strong recommended value."

## ⚠️ 必须说清的适用性边界（本项目的判断，非文献结论）

1. ACT-R 的 base-level 是**频次/近因**驱动，**不是集合大小**驱动。
   ⇒ 「equifinality 集越大 ⇒ 联结越弱」**在 ACT-R 里不是同一条公式**。
   本实现用 `1/n` 表示集合稀释，是**把方向映射为形式**，属**自建**。
2. GST-2002 p.7 脚注 6 明确：**独特性只是关联强度的决定因素之一**，
   另有「重复配对」与「权威陈述」（Kruglanski, 1989; Ellis & Kruglanski, 1992）。
   ⇒ **不可把强度完全归因于集合大小**。已实现 `repeated_pairing` 项。
3. GST-2002 p.7：链接是"cognitive railroad tracks"，**激活只是流动的属性之一**。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# ════════════════════════════════════════════════════════════════
# 外部依据
# ════════════════════════════════════════════════════════════════
UPSTREAM = {
    "named_by_material": "GST-03 (Kruglanski et al. 2002) PDF 物理页 6 原文点名 "
                         "Anderson (1974, 1983) 的 classic \"fan effect\"",
    "material_figures_unavailable": {
        "note": "GST-2002 说该关系见 Figures 4 and 5，但**全文 95 页 0 张嵌入图**，"
                "图形文字不在文本层 ⇒ 稀释函数形式在 GST-2002 内不可得。",
        "verified": "逐页统计 get_images() 全为 0",
    },
    "surrogate": {
        "title": "ACT-R 7.28 Reference Manual",
        "publisher": "Carnegie Mellon University, Department of Psychology",
        "local": "_tmp/ACTR7_reference_manual.pdf",
        "pages": 542, "pages_with_text_layer": 532,
        "sha256_prefix": "16a5e730af7ebad6",
    },
}
VERBATIM = {
    "activation_eq": (262, "Here is the general equation for the activation (A) of a "
                         "chunk i: A = B + S + P + ...  B: This is the base-level "
                         "activation and reflects the recency and frequency of use "
                         "of the chunk. S: This is the spreading activation value"),
    "base_level": (263, "B = b + ln( SUM 1 / (d * t_j) )   d: The decay parameter "
                         "which is set using the :bll parameter."),
    "recommended_d": (269, "The value nil means do not use base-level learning and is "
                            "the default value, a number means that base-level is "
                            "enabled and the given value is the decay parameter. The "
                            "recommended value for :bll is .5, and it is one of the "
                            "few parameters which have a strong recommended value."),
    "not_only_uniqueness": (7, "Uniqueness of association is only one among several "
                               "determinants of association-strength. Another "
                               "determinant is repeated pairing of elements with one "
                               "another ... A mental representation of an association "
                               "could derive also from pronouncements of a trusted "
                               "\"epistemic authority\" (Kruglanski, 1989; Elis & "
                               "Kruglanski, 1992)."),
    "fan_effect": (6, "This is analogous to the classic \"fan effect\" discussed to by "
                      "John Anderson (1974, 1983) wherein the greater the number of "
                      "specific facts linked to a general mental construct, the less "
                      "likely it is that any particular fact will be retrieved or "
                      "recalled upon the presentation of the construct."),
}

# ════════════════════════════════════════════════════════════════
# 自建：把「集合大小 → 强度」映射为函数
# ════════════════════════════════════════════════════════════════
SELF_BUILT = {
    "SET_DILUTION_FORM": "1/n（n 为 equifinality 集或 multifinality 集大小）",
    "DECAY_D": 0.5,
    "_why_D": "d=0.5 取自 ACT-R 手册**推荐值**（PDF p.269），但 ACT-R 的衰减是"
              "**时间/频次**维度，本项目把它借用到集合维度 ⇒ **借用是自建的**。",
    "_why_form": "ACT-R **没有**「集合越大越弱」的公式（base-level 由频次/近因驱动）。"
                 "GST-2002 只给方向且函数在不可读的 Figures 4/5 里。1/n 是本项目选的映射。",
    "_foot6_must_model": "GST-2002 p.7 脚注 6：独特性只是**之一**；"
                         "另有重复配对与权威陈述。⇒ 强度不可只由集合大小决定。",
}


def base_level(n_uses: int, times: Optional[list] = None, lifetime: Optional[float] = None,
               d: Optional[float] = None, beta: float = 0.0) -> float:
    """ACT-R base-level（PDF 物理页 263）。

    :ol = nil 的完整式：  B = β + ln( Σ 1/(d·t_j) )
    :ol = t  的近似式：  B = β + ln( n / (d·(L − d)) )
    """
    dd = SELF_BUILT["DECAY_D"] if d is None else d
    if n_uses <= 0:
        return beta
    if times:
        s = sum(1.0 / (dd * max(t, 1e-9)) for t in times)
    elif lifetime is not None:
        s = n_uses / (dd * max(lifetime - dd, 1e-9))
    else:
        # 无时间信息时退化为「全部发生在现在」
        s = n_uses / dd
    return beta + math.log(s)


@dataclass
class GoalSystem:
    """一个目标-手段系统（Kruglanski et al. 2002 的结构）。"""
    equifinality: list = None    # 达成同一目标的所有手段
    multifinality: list = None   # 同一手段服务的所有目标
    repeated_pairing: float = 0.0  # 重复配对强度（脚注 6 的第二因素）
    authority: float = 0.0         # 权威陈述建立的联结（脚注 6 的第三因素）
    d: Optional[float] = None

    def association_strength(self, means: str = None, goals: str = None) -> dict:
        """手段-目标联结强度。

        ✅ 方向有 GST-2002 原文依据（p.6）：集合越小越强。
        ✅ d 有 ACT-R 推荐值依据。
        ⚠️ **1/n 的形式是自建**（见 SELF_BUILT["_why_form"]）。
        ✅ 脚注 6 的另外两个因素已建模，不是只由集合大小决定。
        """
        eq = len(self.equifinality or [])
        mf = len(self.multifinality or [])
        # 手段-目标对在两个集合中的"独特性"：乘性（两者都小才强）
        uniq = 1.0 / (eq or 1) * 1.0 / (mf or 1)
        # 脚注 6：重复配对与权威陈述是**独立**加成
        extra = self.repeated_pairing + self.authority
        # ACT-R 风格的 ln 压缩，避免线性放大
        dd = SELF_BUILT["DECAY_D"] if self.d is None else self.d
        val = uniq + extra
        return {
            "uniqueness": uniq,
            "repeated_pairing": self.repeated_pairing,
            "authority": self.authority,
            "d": dd,
            "strength": (math.log(1.0 / (dd * max(1.0 / val, 1e-9))) if val > 0 else float("-inf")),
            "components_note": "GST-2002 p.7 脚注 6：uniqueness 只是三因素之一",
        }
