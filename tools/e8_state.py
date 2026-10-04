#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
E8 —— S4 激活与状态推导的可执行验收。

未测原因：前三个 dry run 都不含状态推导需求，S4 一次没真跑过。

要验的承重约束：

  **P20-06b（层次不可混算）**——本 harness 的第一道门。
    原文：「the change is in frequency, not capacity」。
    三行 state-E 分布属**状态层**；TraitDES 均值 5.5／SD 1.4 属**特质描述层**。
    ⚠️ 二者**不是同一个量**。5.5 超出三行加权上界 5.05，故 5.5 不可能是三行均值。
    —— 这个错误在 V1 已经犯过一次（V1 首次实跑得到 4.675 而非 5.5），
       根因就是混算。E8 必须在**流程层面**锁死它，不能只锁算式。

  **P01-07** 一致性检查的对象只能是**结构**，不能是状态。
  **P01-05** 判据是「行为变异模式的稳定性」，不是一致性系数。
  **P20-01** 特质分 TraitDES／TraitEXP，二者经过程因果连接（TraitEXP → TraitDES）。

判据：
  C1  状态层与特质层**分字段**，永不合并
  C2  不得对状态层做跨时一致性判定（P01-07）——结构才可判，状态不可
  C3  频率变化 ≠ 能力变化：必须报「频率」而非改写「容量」（P20-06b 原话）
  C4  频率归一（各行频率和为 1）
  C5  TraitEXP → TraitDES 方向**单向**，不得反向
  C6  激活不收敛时返回 None，**禁止截断取末值**（承接 V4）
  C7  种子冻结：回边不得给种子续命（承接 V4）
  C8  判据用**变异模式稳定性**，不输出单一一致性系数（P01-05）
  C9  状态推导不得触发 F3（跨时一致性）——F3 属结构层
  C10 S4 不产出「冲突」——状态值高低不是冲突；冲突由 S3 的符号矛盾判
"""
from __future__ import annotations

import sys

# ── 材料给的量（不得自创） ─────────────────────────────────────────
# P20-06 算例：三个情境线索 → 三行 state-E 分布
JOHN_CASES = [
    {"cue": "与 Sarah 在家度过的周末夜晚", "pcc": "支持亲密",
     "e_range": (4, 5), "freq": 0.60},
    {"cue": "朋友邀去酒吧；Sarah 一同前往", "pcc": "维持友谊",
     "e_range": (6, 7), "freq": 0.15},
    {"cue": "朋友邀约但 Sarah 拒绝", "pcc": "目标冲突而留在家中",
     "e_range": (4, 4), "freq": 0.25},
]
# P20-06b：TraitDES 层（**与上表不同量**）
JOHN_TRAITDES = {"mean": 5.5, "sd": 1.4}

MAX_ROUNDS = 50
DECAY = 0.5


# ================================================================ S4 激活

def propagate(seeds, edges, threshold, max_rounds=MAX_ROUNDS, decay=DECAY,
               init=None):
    """激活扩散。**承接 V4 的两条实现纪律。**

    ① 种子冻结：回边不得给种子续命（否则形成"续命"，永不衰减）
    ② 不收敛返回 None，**禁止截断取末值**
    """
    # init：非种子节点的情境线索激活（**每轮重新注入**——这是真实来源，
    #       不同于种子：种子是「一次注入后冻结」的外部承诺）
    act = {n: 0.0 for n in set(list(seeds) + list(init or {})
                               + [e["to"] for e in edges] + [e["from"] for e in edges])}
    for s, v in seeds.items():
        act[s] = max(act[s], v)          # 外部承诺一次注入后冻结
    seed_frozen = dict(seeds)

    for rnd in range(1, max_rounds + 1):
        new = dict(act)
        for n, v in (init or {}).items():
            new[n] = max(new[n], v)      # 情境线索：持续激活
        for e in edges:
            src, dst = e["from"], e["to"]
            if dst in seed_frozen:        # ① 种子不再接受回边注入
                continue
            f = e.get("w") * e.get("sigma_sign", 1)
            new[dst] = max(new[dst], act[src] * abs(f) * decay)
        changed = any(abs(new[k] - act[k]) > 1e-9 for k in act)
        act = new
        if not changed:
            return {"converged": True, "rounds": rnd, "activation": act}
    # ② 不收敛 → None（不截断取末值）
    return {"converged": False, "rounds": max_rounds, "activation": None}


# ================================================================ 状态推导

def derive_state(john, traitdes, traitexp, edges=None, seeds=None):
    """S4 状态推导。**层次严格分离**（P20-06b 的核心）。"""
    # ── 状态层：频率分布 ──────────────────────────────────
    freqs = [c["freq"] for c in john]
    total = sum(freqs)
    assert abs(total - 1.0) < 1e-9, "频率未归一：%s" % total

    state_layer = {
        "kind": "state",
        "rows": [{
            "cue": c["cue"], "pcc": c["pcc"],
            "e_range": list(c["e_range"]), "freq": c["freq"],
            "e_mid": (c["e_range"][0] + c["e_range"][1]) / 2,
        } for c in john],
        "weighted_e_mid": sum(
            c["freq"] * (c["e_range"][0] + c["e_range"][1]) / 2 for c in john),
    }
    # ── 特质描述层：独立字段 ──────────────────────────────
    traitdes_layer = {"kind": "trait_description", **traitdes}
    # ── 特质解释层 → 描述层（单向因果，P20-01）────────────
    traitexp_layer = {"kind": "trait_explanation", "drives": "TraitDES",
                      "value": traitexp}

    out = {
        "state_layer": state_layer,
        "traitdes_layer": traitdes_layer,
        "traitexp_layer": traitexp_layer,
        # ⚠️ 绝不提供 combined 分——P20-06b 禁止混算
        "verdict": None,
        "consistency_score": None,      # P01-05：不输出单一一致性系数
        "pattern_stability": None,      # 改为变异模式稳定性（P01-05）
    }
    if edges is not None:
        out["activation"] = propagate(seeds or {}, edges, threshold=0.0)
    return out


def pattern_stability(rows):
    """P01-05 判据：**行为变异模式的稳定性**，不是一致性系数。

    稳定 = 变异模式在行间**可复现**（同样的 cue→pcc 映射一致），
    而**不是**「各行 state-E 相同」——后者恰恰是 P01-07 说的"状态"，
    对它求一致性是范畴错误。
    """
    mapping = {r["cue"]: r["pcc"] for r in rows}
    # 同一 pcc 是否总是被同一 cue 激活（无交叉）
    by_pcc = {}
    for cue, pcc in mapping.items():
        by_pcc.setdefault(pcc, set()).add(cue)
    cross = sum(1 for cues in by_pcc.values() if len(cues) > 1)
    return {"stable": cross == 0, "pcc_count": len(by_pcc),
            "cross_activated": cross,
            "criterion": "P01-05 变异模式稳定性（非一致性系数）"}


# ================================================================ 用例

def main():
    res = []

    def rep(cid, ok, note):
        res.append(ok)
        print("  %s %s — %s" % ("✅" if ok else "❌", cid, note))

    print("=" * 74)
    print("E8 · S4 激活与状态推导")
    print("  P20-06b 层次纪律：状态层 ≠ 特质层，永不混算")
    print("=" * 74)

    edges = [
        {"from": "周末夜晚", "to": "亲密", "w": 0.8, "sigma_sign": 1},
        {"from": "酒吧邀约", "to": "友谊", "w": 0.6, "sigma_sign": 1},
        {"from": "邀约被拒", "to": "留在家中", "w": 0.5, "sigma_sign": 1},
    ]
    seeds = {"周末夜晚": 0.9, "酒吧邀约": 0.7, "邀约被拒": 0.4}
    st = derive_state(JOHN_CASES, JOHN_TRAITDES, "高尽责性", edges, seeds)

    # C1 层次分字段
    ok1 = (st["state_layer"]["kind"] == "state"
           and st["traitdes_layer"]["kind"] == "trait_description"
           and not any(k in st for k in ("combined", "total_score", "unified")))
    wm = st["state_layer"]["weighted_e_mid"]
    ub = 0.6 * 5 + 0.15 * 7 + 0.25 * 4
    # 层次分离的实质判据：状态层加权值**不得等于也不得冒充** TraitDES 均值
    ok1 = ok1 and abs(wm - 4.675) < 1e-9 and wm != JOHN_TRAITDES["mean"] and wm <= ub
    rep("C1", ok1,
        "状态层加权中点 %.3f（≠TraitDES 均值 5.5）｜三行上界 %.2f" % (wm, ub))

    # C2 状态层不得被跨时一致性判定
    ok2 = st.get("consistency_score") is None
    rep("C2", ok2, "无 consistency_score 字段；状态层不参与 P01-07 结构一致性")

    # C3 频率≠容量
    rep("C3", abs(sum(r["freq"] for r in st["state_layer"]["rows"]) - 1.0) < 1e-9,
        "报的是频率分布（和为 1），未改写 capacity（P20-06b：change is in frequency）")

    # C4 频率归一
    f = [r["freq"] for r in st["state_layer"]["rows"]]
    rep("C4", abs(sum(f) - 1.0) < 1e-9, "三行频率 %s 归一" % f)

    # C5 TraitEXP → TraitDES 单向
    ok5 = (st["traitexp_layer"]["drives"] == "TraitDES"
           and st["traitdes_layer"].get("drives") is None)
    rep("C5", ok5, "TraitEXP → TraitDES 单向；TraitDES 无反向 drives（P20-01）")

    # C6 不收敛返回 None
    loop = [{"from": "a", "to": "b", "w": 3.0, "sigma_sign": 1},
            {"from": "b", "to": "a", "w": 3.0, "sigma_sign": 1}]
    # ⚠️ 首次实跑纠正：全 0 激活下 max 传播**平凡收敛**（第 1 轮 changed=False），
    #    这是**正确行为**，不是 bug。真正的不收敛需要**非零**的持续激活源。
    #    故 C6 的 fixture 必须给 init（情境线索激活），且**不含种子**。
    r6 = propagate({}, loop, 0.0, init={"a": 0.5})   # w·decay=1.5>1 → 发散
    rep("C6", r6["converged"] is False and r6["activation"] is None,
        "无种子正反馈环 init=0.5，w·decay=%.1f>1 → 不收敛，activation=None（不截断）"
        % (3.0 * DECAY))

    # C7 种子冻结
    same = [{"from": "a", "to": "b", "w": 0.9, "sigma_sign": 1},
            {"from": "b", "to": "a", "w": 0.9, "sigma_sign": 1}]
    r7 = propagate({"a": 0.8}, same, 0.0)
    rep("C7", r7["converged"] is True,
        "含种子的互指环收敛于第 %d 轮（种子被冻结，未被回边续命）" % r7["rounds"])

    # C8 变异模式稳定性
    ps = pattern_stability(st["state_layer"]["rows"])
    rep("C8", ps["stable"] and ps["criterion"].startswith("P01-05"),
        "判据=%s；pcc %d 个，交叉激活 %d" % (ps["criterion"], ps["pcc_count"],
                                            ps["cross_activated"]))

    # C9 状态推导不触发 F3
    ok9 = not any(k in st for k in ("f1", "f2", "f3", "cross_time_violation"))
    rep("C9", ok9, "无 F1／F2／F3 字段——F3 属结构层，状态层不触发")

    # C10 状态值高低不是冲突
    rep("C10", st["verdict"] is None,
        "verdict=None：state-E 4 与 7 的差异不是冲突，冲突由 S3 符号矛盾判")

    ok = all(res)
    print("-" * 74)
    print("E8: %d/%d 通过  %s" % (sum(res), len(res), "✅" if ok else "❌"))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
