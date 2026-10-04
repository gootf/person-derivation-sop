#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SK-14 再修正：激活传播**默认不衰减**，流出按 degree **均分**。

## 🔴 这是第四次结构证伪，且直接推翻本文件的上一版

上一版（本文件历史）依据 EXT-07（de Groot 1983）确认"衰减存在"，
于是给传播加了 `decay_factor = 0.5`（借用 ACT-R 的推荐值）。**那是错的。**

## 依据：Vitevitch, Ercal & Adagarla (2011)
*Simulating retrieval from a highly clustered network: Implications for spoken
word recognition.* Frontiers in Psychology, 2, 369（开放获取，10 页，
**10/10 页有文本层**）。`spreadr` R 包实现的就是这个算法
（Siew 2019, *Behavior Research Methods* 51, 910-929）。

### 原文逐字（PDF 物理页 5）—— ★ 关键
> "In the present simulation, activation is defined as a limited cognitive
>  resource, which **spreads unimpeded between connected nodes, and does not
>  decay over time**."

> "...**activation in the present simulation does not diminish as it spreads
>  between two connected nodes**."

> "We recognize that the assumptions we employ regarding activation and its
>  spread in the current simulation **are simple and may differ from other
>  cognitive models** that employ 'spreading activation.'"

> "**we see no reason to include additional assumptions simply because other
>  models include those assumptions.** In the present simulation we invoke the
>  **principle of parsimony**."

⚠️ 最后两条是对我这类错误的**直接点名**：
我加 `decay_factor` 的唯一理由是"ACT-R 和 de Groot 里有"。
原文明确说**不能因为别的模型有就加进来**。

### 算法（PDF 物理页 6 逐字）
> "at time step 1 the target node, n, was given an activation of **100 units**.
>  A proportion of that activation stayed in the target node, according to Eq. 2,
>  and the remaining amount of activation was spread equally to all the neighbors
>  of node n, according to Eq. 3.
>
>  **reservoir(t,n) = r × inflow(t,n)**                            (2)
>  **outflow(t,n) = (1 − r) × inflow(t,n) / degree(n)**            (3)
>
>  ... **r is the proportion of the activation (ranging from 0.1 to 0.9 in
>  increments of 0.1) retained at node n**"

其它设定（逐字）：初始激活 **100**（p.6）；跑 **10 个离散时间步**（p.5）；
主结果用 **r = 0.3** 与 **r = 0.7**（p.7）；**明确不采用阈值**（p.5）。

## 与 EXT-07（de Groot）的关系：不是推翻，是**分维度**

- de Groot 1983 的 decay 指**时间上**的衰减（隔一会儿再测，效应变小）
- Vitevitch 2011 的 r 指**空间上**沿网络传播时的保留比例

⇒ 上一版把二者混为一谈，用**一个** `decay_factor` 顶了两件事。**已修正。**

## ⚠️ 残留自建
- `r` 的取值：原文当**扫描参数**（0.1–0.9），未指定唯一正确值。
  本实现默认 0.3（其主结果之一），**必须报告对 r 的敏感性**。
- **阈值**：Vitevitch 2011 明确不采用，且反对"别的模型有就加"的推理。
  本项目保留阈值是为 SK-16 的三值判定，属**独立的自建选择**，
  **不得引 Vitevitch 为据**。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional, Set

SOURCE = {
    "citation": "Vitevitch, M. S., Ercal, G., & Adagarla, B. (2011). Simulating "
                "retrieval from a highly clustered network: Implications for "
                "spoken word recognition. Frontiers in Psychology, 2, 369.",
    "doi": "10.3389/fpsyg.2011.00369",
    "local": "_tmp/Vitevitch2011.pdf",
    "pages": 10, "pages_with_text_layer": 10,
    "implemented_by": "spreadr R package (Siew 2019, Behavior Research Methods "
                      "51, 910-929)",
    "authoritative_param_doc": {
        "title": "spreadr: An R package to simulate spreading activation in a network",
        "url": "https://cran.r-project.org/web/packages/spreadr/spreadr.pdf",
        "local": "_tmp/spreadr_cran_manual.pdf",
        "version": "0.3.0", "date": "2026-05-30",
        "why": "PMC 版（PMC6478646）被挡取（55 字符 HTML 错误页）；CRAN 官方手册逐字给出参数定义，"
               "比论文更精确，作为参数默认值的第一依据。",
    },
}
SPREADR_DEFAULTS = {"retention": 0.5, "time": 10, "decay": 0, "suppress": 0}
SPREADR_ORDER = ["spread activation from node to node",
                 "decay the activation at each node by the proportion specified by decay",
                 "set the activation at nodes with activation less than suppress to 0"]
UPSTREAM = {
    "named_by_material": "P20 (WTT 2025) PDF 物理页 7 点名 Collins & Loftus (1975)",
    "primary_1975": {
        "citation": "Collins & Loftus (1975). JVLVA 14(6), 468-485.",
        "retrieved": False,
        "reason_not_retrieved": "付费墙 —— 按项目纪律不绕过",
    },
    "time_dimension": {
        "source": "de Groot (1983), EXT-07",
        "note": "decay 指**时间**衰减；本文件处理的是**空间**传播。",
    },
    "space_dimension": {"source": "Vitevitch et al. (2011), 本文件依据"},
}
VERBATIM = {
    "no_decay": (5, "In the present simulation, activation is defined as a limited "
                    "cognitive resource, which spreads unimpeded between connected "
                    "nodes, and does not decay over time."),
    "no_diminish": (5, "activation in the present simulation does not diminish as "
                        "it spreads between two connected nodes"),
    "parsimony": (5, "we see no reason to include additional assumptions simply "
                      "because other models include those assumptions. In the present "
                      "simulation we invoke the principle of parsimony."),
    "may_differ": (5, "We recognize that the assumptions we employ regarding "
                       "activation and its spread in the current simulation are simple "
                       "and may differ from other cognitive models that employ "
                       "'spreading activation.'"),
    "init_100": (6, "at time step 1 the target node, n, was given an activation of "
                     "100 units."),
    "eq2_eq3": (6, "reservoir(t, n) = r x inflow(t, n)   outflow(t, n) = (1 - r) x "
                    "inflow(t, n) / degree(n)   r is the proportion of the activation "
                    "(ranging from 0.1 to 0.9 in increments of 0.1) retained at node n"),
    "ten_steps": (5, "resulting in activation spreading back and forth between the "
                      "target, the one-hop neighbors, and the two-hop neighbors over "
                      "10 discrete time steps."),
    "r_values": (7, "The top panel shows the results of the simulation when (the "
                     "proportion of activation retained at a node) r = 0.3, and the "
                     "bottom panel shows the results when r = 0.7."),
    "time_decay_distinct": (13, "Due to decay of activation (Collins & Loftus, 1975), "
                              "this effect may be smaller than the approximately 30 "
                              "millisecond facilitation that was obtained for directly "
                              "related targets"),
    "minimum_to_spread": (16, "the absence of facilitation of a word indirectly "
                               "related to the prime may simply indicate that a "
                               "minimum amount of activation is required in a memory "
                               "location if it is to spread further"),
}

SELF_BUILT = {
    "R_DEFAULT": 0.5,
    "INIT_ACTIVATION": 100.0,
    "TIME_STEPS": 10,
    "_why_r": "Vitevitch 2011 把 r 当**扫描参数**（0.1–0.9），未指定唯一正确值；"
              "0.3/0.7 是其主结果（p.7）。**spreadr 包的官方默认是 0.5**（CRAN 手册 0.3.0）。"
              "本实现默认 0.5 以对齐包默认。",
    "_sensitivity_required": "r 直接决定传播范围。使用方**必须**报告对 r 的敏感性。",
    "_threshold_caveat": "⚠️ Vitevitch 2011 明确**不采用阈值**，且明确反对"
                         "「因为别的模型有就加上」的推理。本项目保留阈值是为 SK-16 "
                         "的三值判定，属**独立的自建选择**，**不得引 Vitevitch 为据**。",
    "_no_decay_default": "默认 decay = 0（**不衰减**），这是 Vitevitch 2011 与 spreadr 包的共同设定；"
                         "如需衰减须显式声明理由，且不得以「别的模型有」为由。",
}


@dataclass
class SpreadResult:
    activation: Dict[str, float]
    steps: int
    r: float
    decay: float = 0.0
    threshold: Optional[float] = None
    fired: Set[str] = field(default_factory=set)
    stalled: Set[str] = field(default_factory=set)

    def reached(self) -> Set[str]:
        return {k for k, v in self.activation.items() if v > 1e-9}

    def downstream_absent(self) -> str:
        """可区分诊断（de Groot p.16）：停滞 ≠ 未激活 ≠ 反号。"""
        if self.stalled:
            return "STALLED(有激活但低于门槛，非反号)"
        return "UNVISITED(未激活)" if not self.reached() else "OK"


def spread(start: str, edges: Mapping[str, Iterable[tuple]],
           *, r: Optional[float] = None,
           steps: Optional[int] = None,
           init: Optional[float] = None,
           threshold: Optional[float] = None,
           decay: Optional[float] = None,
           suppress: float = 0.0) -> SpreadResult:
    """Vitevitch et al. (2011) Eq.(2)(3) + spreadr 包的参数语义。

    ⚠️ 与本文件历史版本的两处关键差别：
       ① 流出从**乘性衰减**改为 `(1-r) * inflow / degree`（**均分**）
       ② 衰减从「混进权重」改为**独立参数 `decay`（时间维度），默认 0（关闭）**

    参数语义取自 spreadr CRAN 手册（0.3.0）逐字：
      retention = "the proportion of activation that remains in the node
                   (not spread) at each time step"
      decay     = "the proportion of activation that is lost at each time step"
      suppress  = "the maximum amount of activation in a node for it to be
                   set to 0, at each time step"

    每步迭代顺序（CRAN 手册逐字）：
      spread → decay → suppress → 加入 start_run → 保存 → 查终止条件
    """
    rr = SELF_BUILT["R_DEFAULT"] if r is None else r
    T = SELF_BUILT["TIME_STEPS"] if steps is None else steps
    a0 = SELF_BUILT["INIT_ACTIVATION"] if init is None else init

    neighbors: Dict[str, list] = {n: list(es) for n, es in edges.items()}
    for ns in list(edges.values()):
        for d, _ in ns:
            neighbors.setdefault(d, [])

    act: Dict[str, float] = {start: a0}
    fired: Set[str] = set()
    stalled: Set[str] = set()
    if threshold is not None:
        for n, v in act.items():
            (fired if v >= threshold else stalled).add(n)

    dec = 0.0 if decay is None else decay   # spreadr 默认 decay = 0（关闭）

    for _t in range(T):
        # ── ① spread（Vitevitch Eq.2/Eq.3）──
        inflow: Dict[str, float] = {}
        for n, v in list(act.items()):
            ns = neighbors.get(n, [])
            if not ns:
                continue
            act[n] = rr * v                                   # Eq.(2) 保留 r
            out = (1.0 - rr) * v / len(ns)                    # Eq.(3) 按 degree 均分
            for d, w in ns:
                inflow[d] = inflow.get(d, 0.0) + out * w
        for d, v in inflow.items():
            act[d] = act.get(d, 0.0) + v
        # ── ② decay（时间维度，spreadr 独立参数，默认 0）──
        if dec > 0.0:
            for n in list(act):
                act[n] *= (1.0 - dec)
        # ── ③ suppress（每步把 ≤ suppress 的置 0）──
        if suppress > 0.0:
            for n in list(act):
                if act[n] < suppress:
                    act[n] = 0.0
        if threshold is not None:
            fired, stalled = set(), set()
            for n, v in act.items():
                (fired if v >= threshold else stalled).add(n)

    return SpreadResult(act, T, rr, dec, threshold, fired, stalled)
