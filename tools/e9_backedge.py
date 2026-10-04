#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
E9 —— S8 回边与终止条件的可执行验收。

要验的约束（SOP.md §5.4「终止条件」）：

    S8 → S1 是**唯一回边**，但它**不是无界的**。
      · 补充轮上限 3；第 3 轮后仍信息不足 → **停止**，输出「当前输入不足以判定」+ 缺什么
      · 不得以降级判定标准代替补充信息
      · 自应用深度上限 2（S1 三档重判、S4 种子冻结各一次）；再错即升级
      · 回边失败（收不到补充）不是静默失败：走**升级路径**，不原地重试

被测对象不是「回边能不能走通」，而是**回边能不能停下来**。
一个不会停的 SOP 只会烧 token 或卡死，这条门是元 SOP Stage 4 的强制义务。

判据：
  A1  正常补充后可推进，轮数 1
  A2  连续补充 3 轮仍不足 → 第 3 轮**停**（不产生第 4 次回边请求）
  A3  终止时输出**缺什么**（可列的清单），不是空泛的「信息不足」
  A4  终止时**不输出任何三值判定**（不得在证据不足时硬判）
  A5  第 3 轮终止 ≠ 降级标准：轮 1／2 仍走 S5 判定，轮 3 才停
  A6  回边失败（无补充可收）→ 升级，**不原地重试**
  A7  自应用深度 > 2 → 升级，**不无限递归**
  A8  轮计数只增不减，**不因新输入而重置**（防「重置即绕过上限」）
  A9  S7 永不重试：输出阶段失败即终止
  A10 终止必须是**可观测信号**（exit_kind），不是静默返回
"""
from __future__ import annotations

import os
import sys

# ── 元 SOP Stage 4 给的量（不是本 SOP 自创） ──────────────────────────
MAX_SUPPLEMENT_ROUNDS = 3     # 补充轮上限
MAX_SELF_APPLY_DEPTH = 2      # 自应用深度上限


# ================================================================ 状态

class ExitKind:
    OK = "OK"                    # 判定完整，正常到 S7
    INSUFFICIENT = "INSUFFICIENT"  # 轮上限耗尽，停止
    ESCALATED = "ESCALATED"      # 回边失败／自应用超限，升级
    OUTPUT_FAILED = "OUTPUT_FAILED"  # S7 失败，不重试


class Run:
    """一次 S5→S8→S1 回边循环的执行记录。"""

    def __init__(self):
        self.rounds = 0            # 已请求的补充轮数（只增不减）
        self.trace = []            # 逐轮记录
        self.escalated = False
        self.exit_kind = None
        self.final = None          # 终止时的输出

    def request(self, kind, detail):
        self.trace.append({"round": self.rounds, "kind": kind, "detail": detail})
        return self.trace[-1]


# ================================================================ 缺失清单

def missing_of(assertions):
    """S8 要「缺什么」——必须可列，不接受空泛的『信息不足』。

    依据 SOP.md §5.4：终止时须输出缺什么。
    """
    miss = []
    for a in assertions:
        if a.get("anchor") in (None, "", "internal_unanchored"):
            miss.append({
                "what": "断言缺索引锚",
                "which": a.get("id"),
                "ask": "请补一句能索引到该属性的行为或状态描述",
            })
        if not a.get("rule_ids"):
            miss.append({
                "what": "断言无上游规则",
                "which": a.get("id"),
                "ask": "请说明该属性的判定依据，或改用属性清单格式直接告知",
            })
    if not miss:
        miss.append({"what": "路径过弱", "which": "-", "ask": "请补充更直接的情境或行为片段"})
    return miss


# ================================================================ 回边

def s5_to_s8_decision(assertions, edges, f_annotated):
    """S5 的信息不足判定。返回 (need_supplement, reasons)。

    对齐 SOP.md §3.1：`S5 → S8 | 路径弱 或 输入含糊`。
    `f_annotated` 为三值阈值 f 是否已标定；未标定 → 必须交人工（不得自动判定）。
    """
    if not f_annotated:
        # 元 SOP §5.4 跨边界：MANUAL 不得由脚本自动裁决
        return False, [{"why": "三值阈值 f 未标定", "manual": True}]
    reasons = []
    if not assertions:
        reasons.append({"why": "断言集为空", "manual": False})
        return True, reasons
    # 收敛判据（E9 第二次实跑纠正）：**不是「所有断言都补齐」**。
    # S8 补充的是**新描述**，不是修补**旧断言**——用户改口描述一条新行为，
    # 不会回头去把先前那句「他很害羞」补上索引锚。要求全集补全 ⇒ 回边永不收敛。
    #
    # 正确判据：**存在至少一条完整可判定的断言**（有 anchor 且有 rule_ids）即可推进；
    # 残缺的断言不阻断推进，但要**带入 S7 的受限标注**（不能被当成已确立）。
    # 两条都缺时才是真的信息不足。
    complete = [a for a in assertions
                if a.get("anchor") not in (None, "", "internal_unanchored")
                and a.get("rule_ids")]
    if complete:
        return False, [{"why": "已有 %d 条完整可判定断言" % len(complete),
                        "manual": False,
                        "restricted": [a.get("id") for a in assertions
                                       if a not in complete]}]
    else:
        # ⚠️ 判据边界（E9 首次实跑纠正）：**`w is None` 不得作为回边触发条件**。
        # `w` 未标定是**全局未标定量**（SOP §5.3 已登记），不是「本轮缺什么」——
        # 用户补充描述补不出权重。若拿它当触发条件，回边**永远不收敛**：
        # 补充多少轮都还是 w=None。第 1 轮就 ESCALATED 正是这个 bug。
        # `w` 属 SK-16 的强度分档，不是 S5→S8 的信息不足判据。
        unanch = [a for a in assertions
                  if a.get("anchor") in (None, "", "internal_unanchored")]
        if unanch:
            reasons.append({"why": "存在缺索引锚的断言（%d 条）" % len(unanch),
                            "manual": False,
                            "detail": [a.get("id") for a in unanch]})
        norule = [a for a in assertions if not a.get("rule_ids")]
        if norule:
            reasons.append({"why": "存在无上游规则的断言（%d 条）" % len(norule),
                            "manual": False, "detail": [a.get("id") for a in norule]})
    return bool(reasons), reasons


def run_loop(case):
    """跑完整回边循环，直到 (a) 判定完整 (b) 轮上限 (c) 升级。"""
    run = Run()
    self_apply = 0

    for rnd in range(1, MAX_SUPPLEMENT_ROUNDS + 1):
        run.rounds = rnd
        supp = case["supplements"].get(rnd)          # 本轮收到的补充
        assertions = case["assertions"].copy()

        if supp is None:
            # ── A6 回边失败：收不到补充 ──────────────────────────
            run.request("S8_no_reply", "第 %d 轮未收到补充" % rnd)
            run.escalated = True
            run.exit_kind = ExitKind.ESCALATED
            run.final = {
                "rounds": rnd,
                "verdict": "回边失败：未收到补充描述。",
                "missing": missing_of(assertions),
                "escalate_to": "用户（须明确补充，或改用属性清单／三元组格式）",
            }
            return run

        assertions += supp                          # 补充并入

        # ── A7 自应用深度：S1 三档重判（§5.4 说仅一次） ─────────
        if supp and supp[0].get("is_mixed_anchor") and self_apply >= MAX_SELF_APPLY_DEPTH:
            run.request("self_apply_exceeded", "第 %d 轮" % rnd)
            run.escalated = True
            run.exit_kind = ExitKind.ESCALATED
            run.final = {
                "rounds": rnd,
                "verdict": "自应用深度超过上限 %d，交人工裁定同义／归属。" % MAX_SELF_APPLY_DEPTH,
                "missing": missing_of(assertions),
                "escalate_to": "用户（需裁定该断言的 anchor 归属档位）",
            }
            return run
        if supp and supp[0].get("is_mixed_anchor"):
            self_apply += 1

        need, reasons = s5_to_s8_decision(assertions, case["edges"], case["f_annotated"])
        rest = []
        for rr in reasons:
            rest += rr.get("restricted", [])
        case["_restricted"] = rest
        run.request("judged", {"need_supplement": need, "reasons": reasons,
                               "restricted": rest})

        if not need:
            # ── A1 正常推进 ────────────────────────────────────
            run.exit_kind = ExitKind.OK
            run.final = {"rounds": rnd, "verdict": "判定完整，可进 S7。",
                         "missing": [], "reasons": reasons,
                         "restricted": case.get("_restricted", [])}
            return run

        if rnd == MAX_SUPPLEMENT_ROUNDS:
            # ── A2 第 3 轮仍不足 → 停 ─────────────────────────
            run.request("rounds_exhausted", "第 %d 轮（上限 %d）仍不足"
                        % (rnd, MAX_SUPPLEMENT_ROUNDS))
            run.exit_kind = ExitKind.INSUFFICIENT
            run.final = {
                "rounds": rnd,
                "verdict": "当前输入不足以判定：补充轮已达上限 %d，停止回边。"
                           % MAX_SUPPLEMENT_ROUNDS,
                "missing": missing_of(assertions),
                "escalate_to": None,
            }
            return run
        # 轮 1／2：继续回边（A5 —— 不得此时就停）
        run.request("supplement_asked", "请求第 %d 轮补充" % (rnd + 1))

    # 不可达
    run.exit_kind = ExitKind.ESCALATED
    return run


# ================================================================ S7

def s7_output(run, fail=False):
    """S7 永不重试（A9）。"""
    if fail:
        return {"exit_kind": ExitKind.OUTPUT_FAILED,
                "note": "输出阶段失败：直接终止，不重试。"}
    return {"exit_kind": run.exit_kind, "payload": run.final}


# ================================================================ 用例

def mk(assertions, edges, supplements, f_annotated=True):
    return {"assertions": assertions, "edges": edges, "supplements": supplements,
            "f_annotated": f_annotated}


# A1：初始只有「他很害羞」这类缺锚属性 → S5 要信息；第 1 轮补充给出可索引的行为句
#     → 判定完整。注意补充**不能**用来补权重（w 恒 None），只补描述。
A1 = mk([{"id": "a1", "text": "他很害羞", "anchor": None, "rule_ids": []}],
        [{"from": "他", "to": "回避", "w": None, "sigma": "+", "rule_ids": []}],
        {1: [{"id": "a2", "text": "他在宴会上避开陌生人的目光",
              "anchor": "avoided strangers' gaze", "rule_ids": ["P47-06"]}]})

A2 = mk([{"id": "a1", "text": "他很害羞", "anchor": None, "rule_ids": []}],
        [{"from": "他", "to": "回避", "w": None, "sigma": "+", "rule_ids": []}],
        {1: [{"id": "b1", "text": "他很内向", "anchor": None, "rule_ids": []}],
         2: [{"id": "c1", "text": "他比较拘谨", "anchor": None, "rule_ids": []}],
         3: [{"id": "d1", "text": "他不太主动", "anchor": None, "rule_ids": []}]})

A3 = mk([{"id": "a1", "text": "他很害羞", "anchor": None, "rule_ids": []}],
        [{"from": "他", "to": "回避", "w": None, "sigma": "+", "rule_ids": []}],
        {1: [{"id": "b1", "text": "他很内向", "anchor": None, "rule_ids": []}],
         2: [{"id": "c1", "text": "他比较拘谨", "anchor": None, "rule_ids": []}],
         3: [{"id": "d1", "text": "他不太主动", "anchor": None, "rule_ids": []}]})

A4 = mk([{"id": "a1", "text": "他很害羞", "anchor": None, "rule_ids": []}],
        [{"from": "他", "to": "回避", "w": None, "sigma": "+", "rule_ids": []}],
        {1: [{"id": "b1", "text": "他很内向", "anchor": None, "rule_ids": []}],
         2: [{"id": "c1", "text": "他比较拘谨", "anchor": None, "rule_ids": []}],
         3: [{"id": "d1", "text": "他不太主动", "anchor": None, "rule_ids": []}]})

A5 = mk([{"id": "a1", "text": "他很害羞", "anchor": None, "rule_ids": []}],
        [{"from": "他", "to": "回避", "w": None, "sigma": "+", "rule_ids": []}],
        {1: [{"id": "b1", "text": "他很内向", "anchor": None, "rule_ids": []}],
         2: [{"id": "c1", "text": "他比较拘谨", "anchor": None, "rule_ids": []}],
         3: [{"id": "d1", "text": "他不太主动", "anchor": None, "rule_ids": []}]})

A6 = mk([{"id": "a1", "text": "他很害羞", "anchor": None, "rule_ids": []}],
        [{"from": "他", "to": "回避", "w": None, "sigma": "+", "rule_ids": []}],
        {})   # 一轮补充也收不到

A7 = mk([{"id": "a1", "text": "他很害羞", "anchor": None, "rule_ids": []}],
        [{"from": "他", "to": "回避", "w": None, "sigma": "+", "rule_ids": []}],
        {1: [{"id": "b1", "text": "他很内向", "anchor": None, "rule_ids": [],
              "is_mixed_anchor": True}],
         2: [{"id": "c1", "text": "他比较拘谨", "anchor": None, "rule_ids": [],
              "is_mixed_anchor": True}],
         3: [{"id": "d1", "text": "他不太主动", "anchor": None, "rule_ids": [],
              "is_mixed_anchor": True}]})

A8 = mk([{"id": "a1", "text": "他很害羞", "anchor": None, "rule_ids": []}],
        [{"from": "他", "to": "回避", "w": None, "sigma": "+", "rule_ids": []}],
        {1: [{"id": "b1", "text": "他很内向", "anchor": None, "rule_ids": []}],
         2: [{"id": "c1", "text": "他比较拘谨", "anchor": None, "rule_ids": []}],
         3: [{"id": "d1", "text": "他不太主动", "anchor": None, "rule_ids": []}]})

CASES = [
    ("A1", "正常补充后推进", A1),
    ("A2", "连续 3 轮仍不足 → 第 3 轮停", A2),
    ("A3", "终止时必须列缺失清单", A3),
    ("A4", "终止时不得硬判三值", A4),
    ("A5", "轮 1／2 仍走 S5，不得提前停", A5),
    ("A6", "回边失败 → 升级，不原地重试", A6),
    ("A7", "自应用深度 > 2 → 升级", A7),
    ("A8", "轮计数不因新输入重置", A8),
    ("A9", "S7 永不重试", None),
    ("A10", "终止是可观测信号", None),
    ("A11", "残缺断言不得静默丢弃", None),
]


# ================================================================ 断言

def run_all(verbose=True):
    results = []

    def rep(cid, ok, note):
        results.append((cid, ok, note))
        if verbose:
            print("  %s %s — %s" % ("✅" if ok else "❌", cid, note))

    if verbose:
        print("=" * 74)
        print("E9 · S8 回边与终止条件")
        print("  上限：补充轮 %d ／ 自应用深度 %d" %
              (MAX_SUPPLEMENT_ROUNDS, MAX_SELF_APPLY_DEPTH))
        print("=" * 74)

    # A1
    r = run_loop(A1)
    rep("A1", r.exit_kind == ExitKind.OK and r.rounds == 1,
        "第 1 轮补充后判定完整，rounds=%d exit=%s" % (r.rounds, r.exit_kind))

    # A2 轮上限
    r = run_loop(A2)
    asked = [t for t in r.trace if t["kind"] == "supplement_asked"]
    rep("A2", r.exit_kind == ExitKind.INSUFFICIENT and r.rounds == MAX_SUPPLEMENT_ROUNDS
        and len(asked) == MAX_SUPPLEMENT_ROUNDS - 1,
        "第 %d 轮停，请求次数=%d（应为 %d）" %
        (r.rounds, len(asked), MAX_SUPPLEMENT_ROUNDS - 1))

    # A3 缺失清单可列
    rep("A3", isinstance(r.final.get("missing"), list) and len(r.final["missing"]) >= 1
        and all("what" in m and "ask" in m for m in r.final["missing"]),
        "终止输出 %d 项缺失，每项含 what/ask" % len(r.final.get("missing", [])))

    # A4 终止时不得硬判三值
    f = s7_output(r)
    no_verdict = "verdict" in r.final and not any(
        k in r.final for k in ("three_valued", "conflict", "no_conflict"))
    rep("A4", no_verdict and f["exit_kind"] == ExitKind.INSUFFICIENT,
        "终止输出含 verdict 文案但无三值字段（三值键全缺）")

    # A5 轮 1／2 不得提前停
    r5 = run_loop(A5)
    early = [t for t in r5.trace
             if t["kind"] == "rounds_exhausted" and t["round"] < MAX_SUPPLEMENT_ROUNDS]
    rep("A5", not early and r5.exit_kind == ExitKind.INSUFFICIENT,
        "rounds_exhausted 只在第 %d 轮出现（未提前停）" % MAX_SUPPLEMENT_ROUNDS)

    # A6 回边失败 → 升级
    r6 = run_loop(A6)
    rep("A6", r6.exit_kind == ExitKind.ESCALATED and r6.escalated,
        "无补充可收 → ESCALATED，升级到 %s" % r6.final.get("escalate_to"))

    # A7 自应用超限 → 升级
    r7 = run_loop(A7)
    rep("A7", r7.exit_kind == ExitKind.ESCALATED,
        "自应用深度 %d 命中上限 %d → ESCALATED" %
        (MAX_SELF_APPLY_DEPTH, MAX_SELF_APPLY_DEPTH))

    # A8 轮计数不被重置
    r8 = run_loop(A8)
    rounds_seen = [t["round"] for t in r8.trace]
    rep("A8", rounds_seen == sorted(rounds_seen) and rounds_seen[0] == 1
        and r8.rounds == MAX_SUPPLEMENT_ROUNDS,
        "轮序列 %s 单调且不重置，终值 %d" % (rounds_seen, r8.rounds))

    # A9 S7 永不重试
    f9 = s7_output(r8, fail=True)
    rep("A9", f9["exit_kind"] == ExitKind.OUTPUT_FAILED and "retry" not in str(f9).lower(),
        "S7 失败 → OUTPUT_FAILED，无重试入口")

    # A10 终止是可观测信号
    known = {ExitKind.OK, ExitKind.INSUFFICIENT, ExitKind.ESCALATED, ExitKind.OUTPUT_FAILED}
    rep("A10", r8.exit_kind in known and r8.final is not None,
        "exit_kind=%s 属四值枚举，final 非空" % r8.exit_kind)

    # A11 残缺断言不得静默丢弃 —— E9 实跑发现的洞，必须锁住
    r1 = run_loop(A1)
    rest = r1.final.get("restricted")
    all_ids = {a["id"] for a in A1["assertions"]} | {
        s["id"] for lst in A1["supplements"].values() for s in lst}
    ok11 = isinstance(rest, list) and set(rest) == (all_ids - {"a2"}) and "a2" not in rest
    rep("A11", ok11,
        "残缺断言 a1 进入受限标注 %s，完整断言 a2 不在内" % rest)

    ok = all(x[1] for x in results)
    if verbose:
        print("-" * 74)
        print("E9: %d/%d 通过  %s" %
              (sum(1 for x in results if x[1]), len(results),
               "✅" if ok else "❌"))
    return ok


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
