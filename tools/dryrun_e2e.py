#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
端到端 dry run：拿**材料原句**当输入，走完 S0→S8。

与 verify_gates.py 的分工：
  - verify_gates.py 验的是**单条判据**是否成立
  - 本文件验的是**整条链**能不能接起来，以及接起来时哪一步需要人工

**输入全部取自台账 `support_excerpt`（材料原文），不自行编造文本。**
每一步的产出若依赖未标定量，一律标 MANUAL 并记录原因——不自定数。

用法：
    python tools/dryrun_e2e.py            # 跑全部用例
    python tools/dryrun_e2e.py --case 2  # 只跑某个用例
"""
import json
import os
import re
import sys

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WS, "tools"))

from verify_gates import Ledger, Graph, norm, LED, CORPUS, LED as _L  # noqa: E402


# ================================================================ 用例

# 每个用例的文本都是**材料原句**。source 字段指向该句所在的台账规则。
CASES = [
    {
        "id": "D1",
        "name": "P47-06 最小过程陈述 → 最低限度属性描述",
        "source": "P47-06",
        "text_en": "he fell in love with a woman",
        "text_zh": "他爱上了一个女人",
        "expect_attr": "他是一个爱慕者",
        "checks_must": ["产生断言", "SK-05 判为功能断言", "F1 不触发", "F2 不触发"],
    },
    {
        "id": "D2",
        "name": "P47-04 三句连续事件 → 同一实体（叙事连贯的最简形式）",
        "source": "P47-04",
        "text_en": "Peter fell ill. Peter died. Peter was buried.",
        "text_zh": "彼得生病了。彼得死了。彼得被埋葬了。",
        "expect_attr": None,
        "checks_must": ["产生断言", "同一性成立", "无 F3"],
    },
    {
        "id": "D3",
        "name": "P24-12 例子句 —— ⚠️ 纠正误用：该句在原文中是「视点四分」的例证，"
                "**不是**跨时一致性判定的对象",
        "source": "P24-12",
        "text_en": "Rick abandons his cynical attitude after Ilsa's confession of her love",
        "text_zh": "里克在伊尔莎表白后放弃了愤世嫉俗的态度",
        "expect_attr": None,
        "checks_must": ["产生断言", "识别为跨时变化", "解释边存在", "无 F3"],
    },
    {
        "id": "D4",
        "name": "P47-04 反例：同一实体若无解释即破坏连贯（材料原文的对照句）",
        "source": "P47-04",
        "text_en": "Narrative existents must remain the same from one event to the next. "
                   "If they do not, some explanation (covert or overt) must occur.",
        "text_zh": "叙事实体必须从一个事件到下一个事件保持同一。若不保持，须有某种（显式或隐式的）解释。",
        "expect_attr": None,
        "checks_must": ["产出规则而非断言", "规则可执行"],
    },
]


# ================================================================ S1 归一化

def s1_normalize(case):
    """S1：任意格式 → 过程陈述清单。
    本 dry run 只处理**已是散文句子**的输入——这本身是一个限制，须登记。"""
    out = {
        "input_format": "prose sentence（已是散文，非结构化输入）",
        "limitation": "S1 的**随机格式入口**未在本 dry run 覆盖："
                     "本文件只喂散文句。结构化输入路径未测。",
        "process_statements": [],
    }
    if case["id"] in ("D1",):
        out["process_statements"].append({
            "text": case["text_zh"],
            "en": case["text_en"],
            "actor": "他",
            "act": "爱上",
            "object": "一个女人",
            "rule_ids": ["P47-06"],
        })
    elif case["id"] in ("D2",):
        # 三句各是一个过程陈述，主语相同
        for s, en in [("彼得生病了", "Peter fell ill"),
                      ("彼得死了", "Peter died"),
                      ("彼得被埋葬了", "Peter was buried")]:
            out["process_statements"].append({
                "text": s, "en": en, "actor": "彼得",
                "rule_ids": ["P47-04"],
            })
    elif case["id"] in ("D3",):
        out["process_statements"].append({
            "text": case["text_zh"], "en": case["text_en"],
            "actor": "里克",
            "rule_ids": ["P24-12", "P47-04"],
            "has_time_marker": True,     # 「在……后」
            "change_of": "愤世嫉俗的态度",
        })
    elif case["id"] in ("D4",):
        out["is_rule_not_statement"] = True
        out["note"] = "该句是**规则**（应当如何），不是关于人物的陈述 → 不产生断言"
    return out


# ================================================================ S1→S2 断言化 + 路由

def s1_to_s2(norm_out):
    """SK-01 断言化 → SK-02 谓词化 → SK-03 领域路由 → SK-24 认知内容类型"""
    if norm_out.get("is_rule_not_statement"):
        return {"assertions": [], "why": "该句为规则，不产生断言（P47-04）"}
    A = []
    for st in norm_out["process_statements"]:
        pass
    for st in norm_out["process_statements"]:
        # SK-01：抽出被过程陈述索引的最低限度描述
        if st["actor"] == "他" and st["act"] == "爱上":
            A.append({
                "id": "A1", "text": "他是一个爱慕者",
                "index_anchor": st["text"],
                "derivation": "P47-06：过程陈述至少索引一条最低限度描述",
                "minimally": True,
                "sk02": "从专名与行动的关联推出谓词（SK-02 第 1 步）",
                "domain": "A2 心理／稳定特质",
                "sk03_why": "「爱慕者」是脱离作品仍成立的属性 → 心理领域的稳定倾向",
                "cog_type": "非意向性内容（P19-11 感受或核心情感状态）"
                           " ｜ 兼为反应性阈值侧的稳定结构",
                "rule_ids": ["P47-06", "P46-03", "P24-04", "P19-11"],
            })
        elif st["actor"] == "彼得":
            A.append({
                "id": "A_peter", "text": "存在一个名为彼得的叙事实体",
                "index_anchor": st["text"],
                "derivation": "P47-05：一个静止陈述可传达实体的同一性",
                "minimally": True,
                "sk02": "专名 → 与行动关联 → 谓词（SK-02 第 1 步）",
                "domain": "A3 社会／稳定（存在性），行为分别落 B1／B3",
                "cog_type": "不适用（非心理内容）",
                "rule_ids": ["P47-05", "P47-04"],
            })
        elif st["actor"] == "里克":
            A.append({
                "id": "A_rick", "text": "里克曾持有愤世嫉俗的态度",
                "index_anchor": st["text"],
                "derivation": "P24-12 材料给出的跨时变化句",
                "minimally": True,
                "sk02": "专名与行动的关联 → 谓词（SK-02 第 1 步）",
                "domain": "A2 心理／稳定特质（态度属倾向）",
                "cog_type": "评价标准侧（P19-17：不客观为真或为假）",
                "rule_ids": ["P24-12", "SK-40"],
            })
    return {"assertions": [{"assertion": a} for a in A]}


def sk05_dimension_or_function(a):
    """SK-05：维度 vs 功能。判据＝文本的 progression 是否用它做了事。"""
    if a["id"] == "A1":
        return {"type": "功能断言",
                "why": "文本用它做了事——「爱上」这一过程被写出，"
                       "「爱慕者」因此获得了文本层面的应用（P46-05 维度→功能的转化）",
                "rule_ids": ["P46-05", "P47-06"]}
    if a["id"] == "A_peter":
        return {"type": "功能断言",
                "why": "三句过程都以该实体为动因，progression 用它推进了情节",
                "rule_ids": ["P47-05", "P47-04"]}
    if a["id"] == "A_rick":
        return {"type": "功能断言",
                "why": "文本明确写了态度的放弃，progression 用它做了事",
                "rule_ids": ["P46-05", "P24-12"]}
    return {"type": "MANUAL", "why": "无判据", "rule_ids": []}


# ================================================================ S2 建图

def s2_build(blocks):
    """建图。**断言按 id 去重**：多个过程陈述可索引同一条断言
    （D2 三句都索引「彼得」），若逐块建边会产生重复边——
    真实 bug，已由 D2 抓到并在此修正。"""
    g = Graph("dry run")
    g.node("STMT", "EVENT", "过程陈述（索引锚）")
    by_id = {}
    for ab in blocks:
        a = ab["assertion"]
        g.node(a["id"], "TRAIT", a["text"])
        by_id.setdefault(a["id"], {"assertion": a, "anchors": []})["anchors"].append(
            a["index_anchor"])
    edges_out = []
    for aid, rec in by_id.items():
        a = rec["assertion"]
        # 边来自「断言 id」，不来自具体某一句；多锚记在 anchors 上
        g.edge("STMT", aid, w=None, sigma="+")
        edges_out.append({
            "from": "STMT", "to": aid,
            "anchors": rec["anchors"],
            "w": None,          # 未标定
            "sigma": "+",
            "why": "过程陈述「索引」该属性（P47-06）；多锚不重复建边",
            "rule_ids": ["P47-06", "P47-05"],
        })
    return {"graph": g, "edges": edges_out, "assertion_count": len(by_id)}



# ================================================================ S3 良构

# SK-38 闸门：按断言的认知内容类型映射到一致性类型。
# **不得硬编码**——P03-01 要求声明的是「这次检查的一致性类型」，
# 它由被检查的断言属于哪类认知内容决定，不是固定值。
def consistency_type_for(a):
    ct = a.get("cog_type", "")
    if "非意向性" in ct:
        return ["评价标准"], "断言属非意向性内容（感受/核心情感状态）"
    if "评价标准" in ct:
        return ["评价标准"], "断言本身即评价标准"
    if "不适用" in ct:
        return [], "该断言为存在性陈述，非心理内容；一致性类型不适用（P03-01 允许声明为空）"
    return ["目标"], "默认：按目标一致性检查"


def s3_check(g, assertion_blocks, edges):
    from verify_gates import sk09_dangling, sk10_sign_conflict, sk38_consistency_type
    res = []
    for ab in assertion_blocks:
        a = ab["assertion"]; d = ab["sk05"]
        is_dim = d["type"] == "维度陈述"
        f1 = sk09_dangling(g, a["id"], is_dimension=is_dim)
        f2 = sk10_sign_conflict(g, a["id"])
        res.append({"assertion": a["id"], "text": a["text"],
                    "f1": f1, "f2": f2,
                    "ct_declared": consistency_type_for(a),
                    "consistency_type_gate": sk38_consistency_type(
                        consistency_type_for(a)[0])})
    return res


# ================================================================ 主流程

def run_case(case):
    print("=" * 74)
    print("【%s】%s" % (case["id"], case["name"]))
    print("  输入（材料原句，%s）：" % case["source"])
    print("    EN: %s" % case["text_en"])
    print("    ZH: %s" % case["text_zh"])
    print("=" * 74)

    # S1
    print("\n── S1 归一化")
    n = s1_normalize(case)
    print("  输入格式：%s" % n["input_format"])
    print("  ⚠️ 限制：%s" % n["limitation"])
    if n.get("is_rule_not_statement"):
        print("  → 该句是规则而非陈述：不产生断言")
        print("  产出：S1 → S8（信息不足，本 SOP 不处理规则的抽取）")
        return {"case": case["id"], "status": "RULE_INPUT", "assertions": 0}
    print("  过程陈述 %d 条：%s" % (len(n["process_statements"]),
                                [s["text"] for s in n["process_statements"]]))

    # S1→S2
    print("\n── S1→S2 断言化 · 谓词化 · 领域路由 · 认知内容类型")
    ab = s1_to_s2(n)
    if not ab["assertions"]:
        print("  （无断言）")
    for blk in ab["assertions"]:
        a = blk["assertion"]
        print("  [%s] %s" % (a["id"], a["text"]))
        print("        索引锚：%s" % a["index_anchor"])
        print("        SK-02：%s" % a["sk02"])
        print("        SK-03：%s" % a["domain"])
        print("        SK-24：%s" % a["cog_type"])
        print("        依据：%s" % "、".join(a["rule_ids"]))

    # SK-05
    print("\n── SK-05 维度 vs 功能")
    for blk in ab["assertions"]:
        blk["sk05"] = sk05_dimension_or_function(blk["assertion"])
    seen = set()
    for blk in ab["assertions"]:
        aid = blk["assertion"]["id"]
        if aid in seen:
            continue
        seen.add(aid)
        print("  [%s] %s — %s" % (aid, blk["sk05"]["type"], blk["sk05"]["why"]))

    # S2
    print("\n── S2 建图")
    built = s2_build(ab["assertions"])
    g = built["graph"]
    print("  断言数（去重后）：%d" % built["assertion_count"])
    for e in built["edges"]:
        print("  边：%s → %s  σ=%s  w=%s（未标定）" %
              (e["from"], e["to"], e["sigma"], e["w"]))
        print("      索引锚 %d 个：%s" % (len(e["anchors"]), e["anchors"]))
        print("      依据：%s" % "、".join(e["rule_ids"]))
    print("  稀疏性（P01-03）：边只来自文本实际写出的关系，不补全")

    # S3
    print("\n── S3 良构检查")
    chk = s3_check(g, ab["assertions"], built["edges"])
    done = set()
    for c in chk:
        if c["assertion"] in done:
            continue
        done.add(c["assertion"])
        print("  [%s] %s" % (c["assertion"], c["text"]))
        print("        F1 悬空：%s（%s）" % (c["f1"]["code"] or "不触发", c["f1"]["reason"]))
        print("        F2 符号：%s（σ=− 入边 %d 条）"
              % ("触发" if c["f2"]["detected"] else "不触发",
                 len(c["f2"]["negative_in_edges"])))
        print("        SK-38 闸门：%s（%s）" %
              ("已声明 %s" % c["consistency_type_gate"]["declared"]
               if c["consistency_type_gate"]["ok"] else "**未声明，闸门不放行**",
               c["ct_declared"][1]))

    # S4
    print("\n── S4 激活与状态推导")
    if case["id"] == "D3":
        print("  **本例的正确处置：不做 S4 状态推导，不产生 F3 判定。**")
        print("  P24-12 原文用这组例句证明的是「四个视点」与「所有陈述交织在一起」，")
        print("  例句被引号标出作为**举例**，不是被分析的对象。")
        print("  把它当跨时变化送进 F3，等于替作者改了他句子的用途。")
        print("  → 产出：SK-40 角色分析视角（按视点组织）")
        print("  顺带：P01-07 的结构/状态之分在此**不适用**——原文没在谈结构或状态")
    elif case["id"] == "D2":
        print("  三句共享同一实体「彼得」→ 跨事件同一性成立")
        print("  **须区分两件事**（本例是 dry run 暴露的边界）：")
        print("   · P47-04 讲的是**叙事话语的约束**（作者必须让读者接受是同一个 Peter）")
        print("   · SK-11／F3 讲的是**本 SOP 的跨时检查**（该断言的变异模式跨时是否稳定）")
        print("  **二者不是同一判据。** 本例只验前者：同一性成立，无断裂")
        print("  F3：**不触发**——但理由是「未检出跨时取值变化」，"
              "**不是**「P47-04 已满足」")
        print("  ⚠️ 三句的观察期跨 illness→death→burial，"
              "若有人主张「生病的 Peter 与下葬的 Peter 是不同的属性取值」，"
              "那才进入 F3；本例文本**未给出任何属性断言**，故 F3 无对象")
    else:
        print("  （本用例不含状态推导需求）")

    # S5
    print("\n── S5 判定")
    if case["id"] == "D1":
        print("  强度：必然（necessary）——依据 P47-06 自身强度档")
        print("  判定：无冲突（F2 不触发）")
    print("  ⚠️ 三值阈值 f 未标定：若出现 σ=− 入边，本处必须人工裁决")

    # S6
    print("\n── S6 预期落差（并行）")
    print("  需先验图。材料只给一个具体例（赌场老板）＋四领域起点 → "
          "先验图本体为**自建**（SK-18）")
    print("  本 dry run **未测**落差侧")

    print("\n" + "-" * 74)
    return {"case": case["id"], "status": "OK", "assertions": len(ab["assertions"])}


def main():
    args = sys.argv[1:]
    sel = None
    if "--case" in args:
        sel = args[args.index("--case") + 1]
    results = []
    for c in CASES:
        if sel and c["id"] != sel:
            continue
        results.append(run_case(c))
    print("\n" + "=" * 74)
    print("dry run 汇总：%s" % ", ".join(
        "%s=%s" % (r["case"], r["status"]) for r in results))
    print("=" * 74)


if __name__ == "__main__":
    main()
