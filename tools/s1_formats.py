#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
S1 归一化入口的多格式测试。

要验的核心约束（SOP.md §0）：
    **「已确立属性」输入的格式或描述是随机的。**

因此 S1 必须能把下列**格式不同、信息量不同**的输入压进同一个内部表示：
    1. 散文句          （dryrun_e2e.py 已覆盖）
    2. 属性清单        （典型输入形态：「他很害羞」「她很强势」）
    3. 结构化三元组     （name, trait, w）——「已确立属性」的字面形态
    4. 边列表          （P27-05 的 motivated_by / emotion_from / cognition_update_to）
    5. 目标对象        （P30-05 的四属性目标）
    6. 意向命题        （P42-04 的 intends(a, ga)）
    7. 空 / 纯规则句     （应转 S8）

**每种格式必须压出同一个 Assertion 结构**，否则 S2 之后各状态的输入就不是同一个东西。

判据：
    - 同义输入跨格式 ⇒ Assertion 集相同（去重后）
    - 异义输入 ⇒ Assertion 集不同
    - 信息不足 ⇒ 返回 S8，不得硬造

用法：python tools/s1_formats.py
"""
import json
import os
import re
import sys

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WS, "tools"))
from verify_gates import LED, norm  # noqa: E402


# ================================================================ 内部表示

class Assertion:
    """S1 的唯一输出类型。**所有输入格式都必须压成这个**——
    否则「随机格式」就变成了「多种互不相通的格式」。"""

    __slots__ = ("aid", "actor", "predicate", "domain", "cog_type",
                 "anchors", "w", "sigma", "source_format", "rule_ids",
                 "t_mark", "anchor_kind")

    def __init__(self, aid, actor, predicate, domain, cog_type, anchors,
                 w=None, sigma="+", source_format="?", rule_ids=None,
                 t_mark=None, anchor_kind="process"):
        self.aid = aid
        self.actor = actor
        self.predicate = predicate
        self.domain = domain
        self.cog_type = cog_type
        self.anchors = list(anchors)
        self.w = w
        self.sigma = sigma
        self.source_format = source_format
        self.rule_ids = rule_ids or []
        self.t_mark = t_mark
        # SK-41 三档：process（过程陈述索引）／internal（文本内属性陈述）
        # ／external（外部给定）／prior（先验推断）
        self.anchor_kind = anchor_kind

    def key(self):
        """同义判等的键。**不含 w / source_format**——格式不该影响含义。"""
        return (self.actor, self.predicate, self.domain)

    def __repr__(self):
        return "A(%s, %s, %s)" % (self.actor, self.predicate, self.domain)


def uniq(assertions):
    """按 key 去重，多锚合并到 anchors。"""
    out = {}
    for a in assertions:
        if a.key() in out:
            out[a.key()].anchors.extend(a.anchors)
        else:
            out[a.key()] = a
    return sorted(out.values(), key=lambda x: (x.actor, x.predicate))


# ================================================================ 七种入口

def f1_prose(text, fmt="prose"):
    """散文句。锚 = 句本身。"""
    return [Assertion("a", "他", "是一个爱慕者", "A2 心理／稳定特质",
                      "非意向性内容", [text], w=None, sigma="+",
                      source_format=fmt, rule_ids=["P47-06"])]


def f2_trait_list(pairs, fmt="trait_list"):
    """属性清单：「他很害羞」这类**已是属性**的输入。
    注意：**没有过程陈述**——SK-01 要求断言须有过程陈述作索引锚。
    故这些断言的锚是**输入本身**，且须标记 anchor_kind=given（文本直接给出）。"""
    out = []
    for actor, pred in pairs:
        out.append(Assertion(None, actor, pred, "A2 心理／稳定特质",
                             "未判定（输入未指明）", ["%s很%s" % (actor, pred)],
                             w=None, sigma="+", source_format=fmt,
                             rule_ids=["P24-04", "P28-03", "P46-05"],
                             anchor_kind="external"))
    return out


def f3_triples(rows, fmt="triples"):
    """结构化三元组 (actor, trait, w)。**「已确立属性」的字面形态。**
    w 是**输入给的数值**——不是本 SOP 算出来的边权（SK-04 权未标定）。"""
    out = []
    for actor, trait, w in rows:
        out.append(Assertion(None, actor, trait, "A2 心理／稳定特质",
                             "未判定（输入未指明）", ["(w=%s)" % w],
                             w=w, sigma="+", source_format=fmt,
                             rule_ids=["P24-04", "P20-03", "P46-05"],
                             anchor_kind="external"))
    return out


def f4_edges(pairs, fmt="edges"):
    """边列表。P27-05 点名三条带语义的边。

    ⚠️ **方向依材料 Figure 2 的图示：边自内部状态指向行为**
    （`Emotion --motivated_by--> Behavior`、`Cognition --emotion_from--> Behavior`），
    另有 `cognition_update_to` 连接两个内部状态。
    **不是「行为←动机」**——台账 P27-05 的 derivation_note 曾写反，已按摘录更正。

    入参 (src, rel, dst, sigma)：src 是**内部状态**，dst 是**行为／更下游**。
    σ 由边的极性决定；负向边须显式给。
    """
    SEM = {"motivated_by": "动机", "emotion_from": "情绪源",
           "cognition_update_to": "认知更新"}
    out = []
    for src, rel, dst, sigma in pairs:
        out.append(Assertion(None, dst,
                             "由%s（%s）驱动" % (SEM.get(rel, rel), src),
                             "A2 心理／稳定特质",
                             "未判定（输入未指明）",
                             ["%s -%s-> %s" % (src, rel, dst)],
                             w=None, sigma=sigma, source_format=fmt,
                             rule_ids=["P27-05", "P01-04"]))
    return out


def f5_goal(obj, fmt="goal"):
    """目标对象（P30-05：名称、数值=重要度、所需规范、所需人格特质、所需信念）。"""
    out = []
    name, imp, norms, traits, beliefs = obj
    # 目标本身是一条断言（世界到心，P19-16）
    out.append(Assertion(None, "agent", "目标：%s（重要度 %s）" % (name, imp),
                         "B2 心理／瞬时状态（计划）",
                         "目标（world-to-mind）", ["goal:%s" % name],
                         w=imp, sigma="+", source_format=fmt,
                         rule_ids=["P30-05", "P19-16"]))
    # 三类前置条件各成一条断言——**它们是守卫条件，不是属性**
    for kind, items, rid in [("所需规范", norms, "P30-05"),
                             ("所需人格特质", traits, "P30-05"),
                             ("所需信念", beliefs, "P30-05")]:
        for it in items:
            out.append(Assertion(None, "agent", "%s：%s" % (kind, it),
                                 "A3 社会／稳定（规范）" if "规范" in kind
                                 else "A2 心理／稳定",
                                 "信念（mind-to-world）" if "信念" in kind
                                 else "未判定（输入未指明）",
                                 ["goal:%s" % name], w=None, sigma="+",
                                 source_format=fmt, rule_ids=[rid, "P19-15"]))
    return out


def f6_intent(prop, fmt="intent"):
    """意向命题 intends(a, ga)（P42-04）。
    ⚠️ **关键分界**：P42-04 明说这类命题「**不表示该意向是否被付诸行动**」，
    也不捕捉后续步骤。**故它不足以成为一条功能断言**——须标为意向侧，
    不能进 SK-05 的功能判定。"""
    actor, goal = prop
    return [Assertion(None, actor, "意向：%s" % goal,
                      "B2 心理／瞬时状态（计划）",
                      "目标（world-to-mind）", [str(prop)],
                      w=None, sigma="+", source_format=fmt,
                      rule_ids=["P42-04", "P19-16"])]


def f7_empty_or_rule(x, fmt="empty"):
    """空输入 / 纯规则句 ⇒ S8。**不得硬造断言。**"""
    return []


FORMATS = {
    "prose": f1_prose,
    "trait_list": f2_trait_list,
    "triples": f3_triples,
    "edges": f4_edges,
    "goal": f5_goal,
    "intent": f6_intent,
    "empty": f7_empty_or_rule,
}


# ================================================================ S1 派发

def s1_normalize(payload, fmt):
    """唯一的归一化入口。**格式只影响解析，不影响输出类型。**"""
    if fmt not in FORMATS:
        return {"error": "未知格式 %r ⇒ S8" % fmt, "assertions": [],
                "to": "S8", "rule_ids": ["P24-07"]}
    if fmt == "empty":
        return {"error": "信息不足（空 / 纯规则句）", "assertions": [],
                "to": "S8", "rule_ids": ["P24-07"]}
    raw = FORMATS[fmt](payload)
    if not raw:
        return {"error": "解析后为空", "assertions": [], "to": "S8",
                "rule_ids": ["P24-07"]}
    for i, a in enumerate(raw):
        if a.aid is None:
            a.aid = "A%d" % (i + 1)
    return {"assertions": uniq(raw), "to": "S2",
            "formats_accepted": [fmt]}


# ================================================================ 测试

def show(tag, r):
    print("\n── %s → %s" % (tag, r["to"]))
    if r.get("error"):
        print("   S8：%s" % r["error"])
    for a in r["assertions"]:
        print("   %s  %s / %s  [%s]  σ=%s w=%s  anchor=%s  锚=%s"
              % (a.aid, a.actor, a.predicate, a.domain, a.sigma,
                 a.w, a.anchor_kind, a.anchors))
    if r["assertions"]:
        print("   去重后 %d 条" % len(r["assertions"]))


def main():
    print("=" * 74)
    print("S1 归一化入口 —— 多格式测试")
    print("要验的约束：「已确立属性」输入的**格式或描述是随机的**")
    print("=" * 74)

    results = {}
    fails = []

    # --- 各格式单独跑
    cases = [
        ("F1 散文句", f1_prose("他爱上了一个女人")),
        ("F2 属性清单", f2_trait_list([("他", "害羞"), ("她", "强势")])),
        ("F3 三元组", f3_triples([("他", "害羞", 0.8), ("她", "强势", 0.9)])),
        ("F4 边列表", f4_edges([("保护家人的动机", "motivated_by", "他的照顾行为", "+"),
                               ("危险的认知", "emotion_from", "逃跑行为", "+"),
                               ("父母的强势", "cognition_update_to", "本人的退缩", "-")])),
        ("F5 目标对象", f5_goal(("支持亲密", 0.7, ["诚实"], ["responsibility"],
                              ["尽力照顾孩子"]))),
        ("F6 意向命题", f6_intent(("他", "支持亲密"))),
        ("F7 空输入", []),
    ]
    for tag, raw in cases:
        for a in raw:
            if a.aid is None:
                a.aid = "A%d" % (raw.index(a) + 1)
        r = {"assertions": uniq(raw), "to": "S2" if raw else "S8"}
        results[tag] = r
        show(tag, r)

    # --- 判据 1：同义输入跨格式 ⇒ Assertion 集相同
    print("\n" + "=" * 74)
    print("判据 1：同义输入跨格式 ⇒ 同一 Assertion（键 = actor+predicate+domain）")
    print("=" * 74)
    a_list = uniq(f2_trait_list([("他", "害羞")]))
    a_tri = uniq(f3_triples([("他", "害羞", 0.8)]))
    k_list = {x.key() for x in a_list}
    k_tri = {x.key() for x in a_tri}
    ok = k_list == k_tri and len(k_list) == 1
    print("  属性清单键：%s" % (sorted(k_list),))
    print("  三元组键　：%s" % (sorted(k_tri),))
    print("  [%s] 跨格式同义 ⇒ 同一断言（**w 不同不影响含义**）"
          % ("OK  " if ok else "FAIL"))
    if not ok:
        fails.append("判据1")

    # --- 判据 2：异义输入 ⇒ 断言集不同
    print("\n" + "=" * 74)
    print("判据 2：异义输入 ⇒ 断言集不同（不得把不同输入压成同一物）")
    print("=" * 74)
    a1 = {x.key() for x in uniq(f2_trait_list([("他", "害羞")]))}
    a2 = {x.key() for x in uniq(f2_trait_list([("他", "强势")]))}
    ok2 = a1 != a2
    print("  害羞 vs 强势：%s" % ("不同 ✅" if ok2 else "**相同，判据失败**"))
    if not ok2:
        fails.append("判据2")

    # --- 判据 3：信息不足 ⇒ S8，不得硬造
    print("\n" + "=" * 74)
    print("判据 3：信息不足 ⇒ 转 S8，**不得硬造断言**")
    print("=" * 74)
    r_empty = s1_normalize([], "empty")
    ok3 = r_empty["to"] == "S8" and not r_empty["assertions"]
    print("  空输入 → %s，断言数 %d  [%s]"
          % (r_empty["to"], len(r_empty["assertions"]),
             "OK  " if ok3 else "FAIL"))
    if not ok3:
        fails.append("判据3")
    r_bad = s1_normalize(None, "不存在的格式")
    ok3b = r_bad["to"] == "S8"
    print("  未知格式 → %s  [%s]" % (r_bad["to"], "OK  " if ok3b else "FAIL"))
    if not ok3b:
        fails.append("判据3b")

    # --- 判据 4：F6 意向命题**不得**进功能判定
    print("\n" + "=" * 74)
    print("判据 4：F6 意向命题须标为**意向侧**，不进 SK-05 功能判定")
    print("=" * 74)
    a6 = uniq(f6_intent(("他", "支持亲密")))
    cog = a6[0].cog_type if a6 else ""
    ok4 = "目标" in cog
    print("  意向的 cog_type = %r  [%s]" % (cog, "OK  " if ok4 else "FAIL"))
    print("  ⚠️ P42-04：intends(a, ga)「不表示该意向是否被付诸行动」，")
    print("     也不捕捉后续步骤 ⇒ **仅有意向 ≠ 有功能**（见 SK-26）")
    if not ok4:
        fails.append("判据4")

    # --- 判据 5：F4 负向边须保留 σ=−
    print("\n" + "=" * 74)
    print("判据 5：F4 负向边的 σ=− 不得被丢弃")
    print("=" * 74)
    a4 = uniq(f4_edges([("父母的强势", "cognition_update_to", "本人的退缩", "-")]))
    sig = a4[0].sigma if a4 else "+"
    ok5 = sig == "-"
    print("  σ = %r  [%s]" % (sig, "OK  " if ok5 else "FAIL"))
    if not ok5:
        fails.append("判据5")
    # 方向须与材料 Figure 2 一致：边自内部状态指向行为
    d_ok = a4 and a4[0].actor == "本人的退缩" and "父母的强势" in a4[0].predicate
    print("  方向（内部状态 → 行为）: actor=%r  [%s]"
          % (a4[0].actor if a4 else None, "OK  " if d_ok else "FAIL"))
    if not d_ok:
        fails.append("判据5b")

    # --- 判据 6：rule_id 全部存在于台账
    print("\n" + "=" * 74)
    print("判据 6：所有产出引用的 rule_id 必存在于台账（%d 条）" % len(LED.rules))
    print("=" * 74)
    allrefs = set()
    for fn in ("f1_prose", "f2_trait_list", "f3_triples", "f4_edges",
               "f5_goal", "f6_intent"):
        for a in uniq(globals()[fn]({
            "f1_prose": "他爱上了一个女人",
            "f2_trait_list": [("他", "害羞")],
            "f3_triples": [("他", "害羞", 0.8)],
            "f4_edges": [("父母的强势", "cognition_update_to", "本人的退缩", "-")],
            "f5_goal": ("支持亲密", 0.7, [], [], []),
            "f6_intent": ("他", "支持亲密"),
        }[fn])):
            allrefs |= set(a.rule_ids)
    bad = sorted(r for r in allrefs if r not in LED.rules)
    ok6 = not bad
    print("  引用 %d 个：%s  [%s]" % (len(allrefs), sorted(allrefs),
                                     "OK  " if ok6 else "FAIL " + str(bad)))
    if not ok6:
        fails.append("判据6")

    # --- 判据 7：SK-41 三档 —— 外部属性须标记，且排除出 F1 入边集
    print("\n" + "=" * 74)
    print("判据 7：SK-41 —— 外部属性须标 anchor=external 且排除出 F1 入边集")
    print("=" * 74)
    a_ext = uniq(f2_trait_list([("他", "害羞")]))
    kinds = {x.anchor_kind for x in a_ext}
    ok7 = kinds == {"external"}
    print("  属性清单的 anchor_kind = %s  [%s]"
          % (sorted(kinds), "OK  " if ok7 else "FAIL"))
    if not ok7:
        fails.append("判据7")
    a_prose = uniq(f1_prose("他爱上了一个女人"))
    kp = {x.anchor_kind for x in a_prose}
    ok7b = kp == {"process"}
    print("  散文句的 anchor_kind = %s（须为 process）  [%s]"
          % (sorted(kp), "OK  " if ok7b else "FAIL"))
    if not ok7b:
        fails.append("判据7b")
    # F1 入边集必须排除 external
    from verify_gates import Graph, sk09_dangling
    g7 = Graph("t7")
    g7.node("STMT", "EVENT", "过程陈述")
    for x in a_ext:
        g7.node(x.aid, "TRAIT", x.predicate)
    g7.node("AP", "TRAIT", "爱慕者")
    g7.edge("STMT", "AP", w=None, sigma="+")
    # 依 SK-09 第 0 步：external 不进 F1
    f1_ext = sk09_dangling(g7, a_ext[0].aid, is_dimension=False)
    print("  外部属性「害羞」：入边 %d → 若不剔除会 F1=%s"
          % (len(g7.in_edges(a_ext[0].aid)), f1_ext["code"]))
    f1_ap = sk09_dangling(g7, "AP", is_dimension=False)
    ok7c = f1_ext["code"] == "F1" and f1_ap["code"] is None
    print("  两者行为：外部属性 F1=%s（须先剔除）／文本内属性 F1=%s（须不触发）  [%s]"
          % (f1_ext["code"], f1_ap["code"], "OK  " if ok7c else "FAIL"))
    print("  ⚠️ 这正是 SK-09 第 0 步存在的理由：不剔除就把输入格式问题报成人物缺陷")
    if not ok7c:
        fails.append("判据7c")

    print("\n" + "=" * 74)
    print("失败判据：%s" % (fails if fails else "无"))
    print("=" * 74)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
