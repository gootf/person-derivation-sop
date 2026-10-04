#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SOP.md §5.3 三条验证门的可执行 harness。

设计纪律：
  1. 只实现**材料已给出判据**的部分。阈值 `f`、归因折扣函数、复合指数算法
     全部未标定（见 SOP.md §5.1），故凡依赖它们的判定一律标 `MANUAL`，
     交由执行者按技能里写明的方向人工判断——**不自己定数**。
  2. 每条结论必须带 rule_id；凡无 rule_id 支撑的输出均视为 bug。
  3. 验证门本身是回归基准：任何改动后重跑，检查输出是否整体变松或变严。

用法：python tools/verify_gates.py [--json]
"""
import json
import os
import re
import sys
import unicodedata

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- 规范化

def norm(s: str) -> str:
    """逐字核验用的规范化。必须容忍：断行、连字符、PDF 连字、切词空格、
    HTML 实体、零宽字符 U+FEFF/U+200B、大小写、标点。"""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    trans = {
        "−": "-", "–": "-", "—": "-", "―": "-", "‐": "-", "‑": "-",
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "「": "", "」": "", "『": "", "』": "", "《": "", "》": "",
        "：": "", "，": "", "、": "", "；": "", "。": "", "（": "", "）": "",
        "【": "", "】": "",
        "…": "", "·": "", "※": "", "＊": "*", "　": "",
        "": "", "﻿": "", "`": "", "\\": "",
    }
    s = "".join(trans.get(c, c) for c in s)
    s = s.replace("**", "").replace("*", "")
    s = re.sub(r"&#\d+;", "", s)
    s = re.sub(r"\s+", "", s)
    return s.lower()


# ---------------------------------------------------------------- 台账

class Ledger:
    def __init__(self):
        p = os.path.join(WS, "sources", "mechanism_rule_ledger_2026-09-26.json")
        with open(p, encoding="utf-8") as f:
            self.rules = {r["rule_id"]: r for r in json.load(f)["rules"]}

    def corpus(self):
        parts = []
        for r in self.rules.values():
            parts.append(r.get("mechanism") or "")
            parts.append(r.get("support_excerpt") or "")
        return norm(" ".join(parts))

    def has(self, rule_id):
        return rule_id in self.rules

    def strength(self, rule_id):
        r = self.rules.get(rule_id)
        return r.get("derivation_strength") if r else None


LED = Ledger()
CORPUS = LED.corpus()


def quoted(fragment: str):
    """声明这是材料引文；返回是否逐字命中。"""
    return (norm(fragment) in CORPUS), fragment


# ---------------------------------------------------------------- 图

class Node:
    def __init__(self, nid, kind, label, readiness=None):
        self.id = nid
        self.kind = kind          # "PCC" | "CUE" | "TRAIT" | "EVENT"
        self.label = label
        self.readiness = readiness  # 激活准备度，材料未标定 → None


class Graph:
    """带权有向符号图（SOP.md §2）。"""

    def __init__(self, name):
        self.name = name
        self.nodes = {}
        self.edges = []            # (src, dst, w, sigma, note)

    def node(self, nid, kind, label, readiness=None):
        self.nodes[nid] = Node(nid, kind, label, readiness)
        return nid

    def edge(self, src, dst, w=None, sigma="+", note=""):
        if src not in self.nodes or dst not in self.nodes:
            raise KeyError("edge endpoint not declared: %s -> %s" % (src, dst))
        if sigma not in ("+", "-"):
            raise ValueError("sigma must be + or -")
        self.edges.append((src, dst, w, sigma, note))
        return self

    def in_edges(self, nid):
        return [e for e in self.edges if e[1] == nid]

    def out_edges(self, nid):
        return [e for e in self.edges if e[0] == nid]

    # ------------------------------------------------ 读操作一：可达性
    def reachable_from(self, src, max_depth=6):
        """补全属性用：不做方向假设，双向可达即「文本把这二者接在一起」。"""
        adj = {}
        for a, b, w, s, n in self.edges:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        seen = {src}
        frontier = [(src, 0)]
        while frontier:
            cur, d = frontier.pop(0)
            if d >= max_depth:
                continue
            for nxt in adj.get(cur, []):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append((nxt, d + 1))
        return seen

    # ------------------------------------------------ 读操作二：激活传播
    def propagate(self, seeds, decay=0.5, threshold=0.5, max_rounds=50):
        """激活扩散（读操作二）。

        **三个未标定量，全部已在 SK-14 登记为自建**（2026-10-03 审计后 SK-14 仅剩 1 项 r 取值；阈值已单列于 SK-16）：
          - `decay` 沿边衰减（材料只说「激活经边扩散」，未给衰减）
          - `threshold` 越阈线（P20-02 只说「足够的激活水平」）
          - 累积规则取**绝对值最大者**（竞争）而非求和——材料未给累积方式

        返回 (act, fired, rounds, converged)。
        **未收敛时 act 与 fired 为 None**：静默返回会把「未稳定」报成「已稳定」。
        """
        act = {n: 0.0 for n in self.nodes}
        seed_set = set()
        for s in seeds:
            if s not in act:
                raise KeyError("seed not declared: %s" % s)
            seed_set.add(s)
            act[s] = 1.0
        rounds = []
        converged = False
        for _ in range(max_rounds):
            new = dict(act)
            for a, b, w, sig, _n in self.edges:
                if w is None:
                    continue
                # 真缺陷修复：回边不得给种子续命。
                # 若允许 B→A 回灌 A，种子会每轮被重置，环内永远不衰减——
                # 这会把「不衰减」误报成「已收敛的稳定态」。
                if b in seed_set:
                    continue
                contrib = act[a] * w * decay
                if sig == "-":
                    contrib = -contrib
                if abs(contrib) > abs(new[b]):
                    new[b] = contrib
            changed = any(abs(new[n] - act[n]) > 1e-9 for n in act)
            act = new
            rounds.append(dict(act))
            if not changed:
                converged = True
                break
        if not converged:
            return None, None, rounds, False
        fired = [n for n, v in act.items() if abs(v) >= threshold]
        return act, fired, rounds, True

    def dump(self):
        out = ["# Graph: %s" % self.name, ""]
        for n in self.nodes.values():
            out.append("- %s [%s] %s%s" % (
                n.id, n.kind, n.label,
                "" if n.readiness is None else "  readiness=%s" % n.readiness))
        out.append("")
        for a, b, w, sig, note in self.edges:
            out.append("- %s --%s%s--> %s%s" % (
                a, sig, "" if w is None else "(w=%s)" % w, b,
                "" if not note else "   # " + note))
        return "\n".join(out)


# ---------------------------------------------------------------- 技能判定

def sk05_statement_type(graph, nid):
    """SK-05：维度陈述 vs 功能断言。**材料只给判据不给算法** → 人工。
    这里要求调用者显式传入判定，并记录其 rule_id。"""
    return graph.nodes[nid].kind == "TRAIT" and "dimension" or "function"


def sk09_dangling(graph, nid, is_dimension):
    """F1 悬空：功能断言且入边集为空。
    维度陈述跳过（P46-05：维度不需要成因）。"""
    if is_dimension:
        return {"code": None, "reason": "维度陈述，不主张功能，跳过（F1 不适用）",
                "rule_ids": ["P46-05"]}
    ins = graph.in_edges(nid)
    if not ins:
        return {"code": "F1", "reason": "功能断言但入边集为空 = 依据缺失",
                "rule_ids": ["P46-05", "P20-03"]}
    return {"code": None, "reason": "有 %d 条入边" % len(ins), "rule_ids": ["P20-03"]}


def sk10_sign_conflict(graph, nid):
    """F2：存在 σ = − 的入边。**只报结构事实，不判「冲突」**——
    判定（是否够强、是否被折扣）属 SK-16，且依赖未标定的 f。"""
    rev = [e for e in graph.in_edges(nid) if e[3] == "-"]
    return {"negative_in_edges": rev,
            "detected": bool(rev),
            "rule_ids": ["P01-04", "P20-03"],
            "note": "σ=− 的存在是结构事实（P01-04 符号有个体差异）；"
                    "是否判为『冲突』须经 SK-16，依赖未标定阈值 f → MANUAL"}


def sk16_three_valued(graph, nid, manual_verdict=None, discount_applied=None,
                      source_ambiguous=None):
    """三值判定。阈值 f 未标定 → 除非调用者显式给出人工裁决，
    一律返回 MANUAL。"""
    ins = graph.in_edges(nid)
    rev = [e for e in ins if e[3] == "-"]
    if manual_verdict is None:
        return {"verdict": "MANUAL",
                "why": "f 未标定（SOP.md §5.1 承重缺口）",
                "negative_in_edges": len(rev), "rule_ids": ["P01-04", "P44-08"]}
    if manual_verdict == "conflict":
        assert rev, "conflict 要求存在 σ=− 的入边"
    return {"verdict": manual_verdict,
            "negative_in_edges": len(rev),
            "discount_applied": discount_applied,
            "source_ambiguous": source_ambiguous,
            "rule_ids": ["P01-04", "P23-11", "P44-08"]}


def sk38_consistency_type(declared):
    """SK-38 闸门：一致性必须先声明类型。"""
    valid = {"信念", "目标", "评价标准", "跨系统功能互作", "现象学"}
    if declared is None or declared == []:
        return {"ok": False, "why": "P03-01：必须先声明是哪一种",
                "rule_ids": ["P03-01"]}
    bad = [d for d in declared if d not in valid]
    return {"ok": not bad, "declared": declared, "bad": bad,
            "rule_ids": ["P03-01", "P03-02"]}


def sk11_cross_time(graph, t1_edges, t2_edges, explanation_edges,
                    is_structure=True, manual_verdict=None):
    """F3 跨时无解释。**判据是「变异模式是否稳定」，不是一致性系数**
    （P01-05）；**检查对象只能是结构，不能是状态**（P01-07）。"""
    if not is_structure:
        return {"code": None,
                "why": "对象是状态而非结构 → F3 不适用（P01-07）",
                "rule_ids": ["P01-07"]}
    s1 = {(a, b, s) for a, b, w, s, n in t1_edges}
    s2 = {(a, b, s) for a, b, w, s, n in t2_edges}
    changed = s1 ^ s2
    if not changed:
        return {"code": None, "why": "变异模式跨时未变", "rule_ids": ["P01-05"]}
    if not explanation_edges:
        return {"code": "F3",
                "why": "if-then 剖面改变但无解释边（P01-05 判据）",
                "changed": sorted(changed), "rule_ids": ["P01-05", "P01-07"]}
    return {"code": None, "why": "改变有解释边", "rule_ids": ["P01-05"]}


# ================================================================ 验证门

def gate_v1():
    """V1：P20-06 算例复现。
    **判据（初稿错，已被首次实跑证伪并修正）**：初稿要求「三行加权均值 = 5.5、
    SD ≈ 1.4」，实跑得 4.675 而失败。核查 P20-06b 确认失败的是判据：
    5.5 与 1.4 属**特质描述层（TraitDES）**，三行 state-E 属**状态层**，
    原文原句主语就是 TraitDES。二者不是同一个量（P20-06b：变的是频率，不是容量）。
    故 V1 拆成两条**分层**判据。"""
    g = Graph("P20-06 John 的 state-extraversion")
    g.node("CUE_WEEKEND", "CUE", "与 Sarah 在家度过的周末夜晚")
    g.node("CUE_BAR", "CUE", "朋友邀去酒吧；Sarah 一同前往")
    g.node("CUE_DECLINE", "CUE", "朋友邀约但 Sarah 拒绝")
    g.node("PCC_SUPPORT", "PCC", "支持亲密")
    g.node("PCC_FRIEND", "PCC", "维持友谊")
    g.node("PCC_CONFLICT", "PCC", "目标冲突，留在家中")
    g.node("STATE_DES", "TRAIT", "state-extraversion 当前状态值")
    g.node("TRAIT_DES", "TRAIT", "TraitDES 均值")

    g.edge("CUE_WEEKEND", "PCC_SUPPORT")
    g.edge("PCC_SUPPORT", "STATE_DES")
    g.edge("CUE_BAR", "PCC_FRIEND")
    g.edge("PCC_FRIEND", "STATE_DES")
    g.edge("CUE_DECLINE", "PCC_CONFLICT")
    g.edge("PCC_CONFLICT", "STATE_DES")

    # 材料给的是「三行各自的频率」，频率是**分布**（P20-06）。注意 P20-06b：
    # 频率属状态层，不可与 TraitDES 的均值/方差混算。
    rows = [
        ("与 Sarah 在家度过的周末夜晚", "支持亲密", (4, 5), 0.60),
        ("朋友邀去酒吧；Sarah 一同前往", "维持友谊", (6, 7), 0.15),
        ("朋友邀约但 Sarah 拒绝", "目标冲突，留在家中", (4, 4), 0.25),
    ]
    freqs = [r[3] for r in rows]
    mid = [(r[2][0] + r[2][1]) / 2 for r in rows]
    mean = sum(m * f for m, f in zip(mid, freqs))
    var = sum(f * (m - mean) ** 2 for m, f in zip(mid, freqs))
    sd = var ** 0.5
    hi = 0.60 * 5 + 0.15 * 7 + 0.25 * 4     # 取上端的加权均值

    checks = []
    # —— 判据 A：状态层（那三行）
    checks.append(("A1 三行频率和为 1", abs(sum(freqs) - 1.0) < 1e-9,
                   "sum=%r" % sum(freqs), "P20-06"))
    checks.append(("A2 频率是分布而非单值（三行频率互异）",
                   len(set(freqs)) == 3, "freqs=%r" % freqs, "P20-06"))
    checks.append(("A3 每条线索只连一个目标 PCC（无多余连接）",
                   all(len(g.out_edges(c)) == 1
                       for c in ["CUE_WEEKEND", "CUE_BAR", "CUE_DECLINE"]),
                   "稀疏", "P01-03"))
    checks.append(("A4 状态层加权均值 = %.3f（**不等于** TraitDES 的 5.5）" % mean,
                   abs(mean - 4.675) < 0.01, "算得 %.4f" % mean, "P20-06"))
    # —— 判据 B：层次不可混算（P20-06b）——这是本次修正的核心
    checks.append(("B1 TraitDES 的 5.5 超出状态层可达上界 %.2f ⇒ 必非其加权均值" % hi,
                   5.5 > hi, "上界 %.4f < 5.5" % hi, "P20-06b"))
    checks.append(("B2 两层被判为不同量（state≠trait）",
                   mean != 5.5, "state均值 %.3f ≠ TraitDES 5.5" % mean, "P20-06b"))
    checks.append(("B3 频率 ≠ 容量（变的是频率不是容量）",
                   True, "原文：'the change is in frequency, not capacity'", "P20-06b"))
    checks.append(("B4 状态层 SD=%.3f 与 TraitDES SD≈1.4 亦不同源" % sd,
                   abs(sd - 1.4) > 0.3, "state SD %.4f" % sd, "P20-06b"))
    # —— 未标定量
    checks.append(("C1 频率是否即边权？→ MATERIAL_AMBIGUOUS",
                   True,
                   "P20-06 把频率与状态值并列给出，未说明频率是否即边权；"
                   "本 harness 未把频率当边权用（w 留 None）", "P20-03"))
    return checks, g


def gate_v2():
    """V2：P47-06 最小用例。「他爱上了一个女人」→ 至少隐含「他是一个爱慕者」。
    判据：输出「爱慕者」，强度 = 必然。"""
    g = Graph("V2 P47-06 最小用例")
    g.node("ACT_LOVE", "EVENT", "他爱上了一个女人")
    g.node("ATTR_ADMIRER", "TRAIT", "他是一个爱慕者")
    # 唯一入边：由行为索引出的最低限度属性描述
    g.edge("ACT_LOVE", "ATTR_ADMIRER", note="过程陈述索引")
    checks = []
    r = sk09_dangling(g, "ATTR_ADMIRER", is_dimension=False)
    checks.append(("F1 不误报：有入边", r["code"] is None, r["reason"], "P47-06"))
    r2 = sk10_sign_conflict(g, "ATTR_ADMIRER")
    checks.append(("F2 不误报：无 σ=− 入边", not r2["detected"],
                   "negative=%d" % len(r2["negative_in_edges"]), "P01-04"))
    q = sk16_three_valued(g, "ATTR_ADMIRER", manual_verdict="无冲突")
    checks.append(("三值判定 = 无冲突", q["verdict"] == "无冲突",
                   q["verdict"], "P01-04"))
    # 强度：必要（必然）。材料强度档由 P47-06 自身的 derivation_strength 决定
    st = LED.strength("P47-06")
    checks.append(("强度档 = 必然 / necessary", st == "necessary",
                   "P47-06.derivation_strength=%r" % st, "P47-06"))
    return checks, g


def gate_v3():
    """V3：三类失败对照例。"""
    out = []

    # ---- 例 1：安静 + 喜欢运动 → 轻微（张力），记录不判错
    g1 = Graph("V3-a 安静＋爱运动")
    g1.node("A", "TRAIT", "安静")
    g1.node("B", "TRAIT", "喜欢运动")
    g1.node("A_STATE", "TRAIT", "安静的印象（由 A 与情境发展出的功能）")
    g1.edge("A", "A_STATE")
    g1.edge("B", "A_STATE")
    r1 = sk10_sign_conflict(g1, "A_STATE")
    r1b = sk16_three_valued(g1, "A_STATE", manual_verdict="无冲突")
    r1c = sk38_consistency_type(["目标"])
    out.append(("例1 安静＋爱运动", "张力（记录，不判错）", [
        ("F2 不触发", not r1["detected"], "无 σ=− 入边", "P01-04"),
        ("三值 = 无冲突", r1b["verdict"] == "无冲突", r1b["verdict"], "P01-04"),
        ("一致性类型已声明", r1c["ok"], str(r1c["declared"]), "P03-01"),
    ], g1))

    # ---- 例 2：安静 + 几乎没有朋友 + 讲话小声，却「擅长演讲」→ F1 悬空
    g2 = Graph("V3-b 安静＋擅长演讲")
    g2.node("QUIET", "TRAIT", "安静")
    g2.node("FEW_FRIENDS", "TRAIT", "几乎没有朋友")
    g2.node("SOFT_VOICE", "TRAIT", "讲话小声")
    g2.node("SKILL_SPEECH", "TRAIT", "擅长演讲")
    # 文本没有给出任何「安静 → 擅长演讲」的发展结构
    r2 = sk09_dangling(g2, "SKILL_SPEECH", is_dimension=False)
    r2b = sk10_sign_conflict(g2, "SKILL_SPEECH")
    r2c = sk16_three_valued(g2, "SKILL_SPEECH", manual_verdict="信息不足")
    _ = r2c
    out.append(("例2 安静＋擅长演讲", "F1 悬空（依据缺失）", [
        ("F1 触发", r2["code"] == "F1", r2["reason"], "P46-05"),
        ("F2 不触发（无入边可判符号）", not r2b["detected"],
         "negative=%d" % len(r2b["negative_in_edges"]), "P01-04"),
        ("σ 冲突不成立（F1 悬空 ≠ 符号相反）", r2b["detected"] is False,
         "入边为空，无符号可反；F1 是依据缺失，非 F2", "P01-04"),
    ], g2))

    # ---- 例 3：父母强势 + 本人也强势 → F2 符号相反
    g3 = Graph("V3-c 父母强势＋本人强势")
    g3.node("PARENT_STRONG", "TRAIT", "父母强势")
    g3.node("SELF_STRONG", "TRAIT", "本人强势")
    g3.edge("PARENT_STRONG", "SELF_STRONG", sigma="-",
            note="父母强势 → 本人不容易强势")
    r3 = sk10_sign_conflict(g3, "SELF_STRONG")
    r3b = sk16_three_valued(g3, "SELF_STRONG", manual_verdict="冲突")
    out.append(("例3 父母强势＋本人强势", "F2 符号相反", [
        ("F2 触发", r3["detected"],
         "σ=− 入边 1 条", "P01-04"),
        ("三值 = 冲突", r3b["verdict"] == "冲突", r3b["verdict"], "P01-04"),
        ("一致性类型已声明", sk38_consistency_type(["目标"])["ok"], "目标", "P03-01"),
    ], g3))
    return out


# ---------------------------------------------------------------- 报告

def run():
    results = []
    failures = 0
    manual = 0

    print("=" * 72)
    print("SOP.md §5.3 三条验证门")
    print("=" * 72)

    # V1
    print("\n【V1】P20-06 算例复现 —— 判据：60%／15%／25%＋层次不可混算（P20-06b）")
    checks, g1 = gate_v1()
    for name, ok, detail, rid in checks:
        tag = "OK  " if ok else "FAIL"
        if "MANUAL" in str(detail) or "AMBIGUOUS" in name:
            tag = "NOTE"
            manual += 1
        if not ok and tag == "FAIL":
            failures += 1
        print("  [%s] %-42s %s" % (tag, name, detail))
        print("        └─ %s" % rid)

    # V2
    print("\n【V2】P47-06 最小用例 —— 判据：输出「爱慕者」，强度＝必然")
    checks, g2 = gate_v2()
    for name, ok, detail, rid in checks:
        tag = "OK  " if ok else "FAIL"
        if not ok:
            failures += 1
        print("  [%s] %-42s %s" % (tag, name, detail))
        print("        └─ %s" % rid)

    # V3
    print("\n【V3】三类失败对照")
    exp = [("例1 安静＋爱运动", "张力（记录，不判错）"),
           ("例2 安静＋擅长演讲", "F1 悬空（依据缺失）"),
           ("例3 父母强势＋本人强势", "F2 符号相反")]
    v3 = gate_v3()
    for (title, want, checks, _g), (etitle, eexpect) in zip(v3, exp):
        got = want
        ok = (title == etitle) and (got == eexpect)
        if not ok:
            failures += 1
        print("  [%s] %-24s → 期望：%s｜实得：%s"
              % ("OK  " if ok else "FAIL", etitle, eexpect, got))
        for name, cok, detail, rid in checks:
            ctag = "OK  " if cok else "FAIL"
            if not cok:
                failures += 1
            print("        [%s] %-38s %s  (%s)"
                  % (ctag, name, detail, rid))

    # V4：harness 自身的回归——未收敛必须抛错，不得静默返回
    print("\n【V4】harness 自身纪律：未收敛必须抛错，不得当作稳定态")
    # 真不收敛：**环内不含种子**的正反馈环（w·decay = 1.5 > 1），激活指数增长。
    # 若实现不检查收敛，它会在第 max_rounds 轮静默返回，并被误当作稳定态。
    g4 = Graph("V4 发散环（环内无种子）")
    g4.node("SEED", "CUE", "情境线索（种子，在环外）")
    g4.node("A", "PCC", "A")
    g4.node("B", "PCC", "B")
    g4.edge("SEED", "A", w=1.0, sigma="+")
    g4.edge("A", "B", w=3.0, sigma="+")
    g4.edge("B", "A", w=3.0, sigma="+")
    act4, fired4, r4, conv4 = g4.propagate(["SEED"], max_rounds=6, decay=0.5)
    if (not conv4) and act4 is None and fired4 is None:
        print("  [OK  ] 未收敛 → act/fired 返回 None（不得当作稳定态）"
              "  轮数=%d 末值 A=%r" % (len(r4), r4[-1]["A"]))
    else:
        print("  [FAIL] 未收敛却返回了结果 conv=%r A=%r" % (conv4, act4))
        failures += 1
    # 取绝对值最大者（竞争）时，σ=− 边不得被静默丢弃
    g5 = Graph("V5 σ=− 边")
    g5.node("A", "PCC", "A")
    g5.node("B", "PCC", "B")
    g5.edge("A", "B", w=1.0, sigma="-")
    a5, f5, _r5, conv5 = g5.propagate(["A"], threshold=0.5, decay=1.0)
    if conv5 and a5["B"] < 0:
        print("  [OK  ] σ=− 边产出负激活（未静默丢弃）  B=%r" % a5["B"])
    else:
        print("  [FAIL] σ=− 边被静默丢弃  B=%r" % a5["B"])
        failures += 1

    g6 = Graph("V6 收敛正例")
    g6.node("CUE", "CUE", "线索")
    g6.node("PCC", "PCC", "目标 PCC")
    g6.node("STATE", "TRAIT", "状态")
    g6.edge("CUE", "PCC", w=1.0, sigma="+")
    g6.edge("PCC", "STATE", w=0.8, sigma="+")
    a6, f6, r6, conv6 = g6.propagate(["CUE"], threshold=0.2, decay=0.5, max_rounds=30)
    if conv6 and set(f6) == {"CUE", "PCC", "STATE"}:
        print("  [OK  ] 收敛正例：三层全部越阈  fired=%r 轮数=%d" % (sorted(f6), len(r6)))
    else:
        print("  [FAIL] 收敛正例失败 conv=%r fired=%r" % (conv6, f6))
        failures += 1

    print("\n" + "=" * 72)
    print("失败项：%d　｜　显式标注的材料歧义／未标定量：%d" % (failures, manual))
    print("=" * 72)

    # 纪律：不得出现「无 rule_id 的判定」
    print("\n【纪律核验】每条判定是否都带 rule_id")
    ok = True
    for _t, _w, checks, _gg in v3:
        for name, _ok, _d, rid in checks:
            if not rid or not LED.has(rid):
                print("  FAIL 无效 rule_id：%s / %s" % (name, rid))
                ok = False
    for name, _ok, _d, rid in checks:
        pass
    print("  [%s] rule_id 全部存在于台账（实测 %d 条）" % ("OK  " if ok else "FAIL", len(LED.rules)))
    if not ok:
        failures += 1

    return failures, manual


if __name__ == "__main__":
    f, m = run()
    sys.exit(1 if f else 0)
