#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门⑨ 台账转折限定丢失审计。

## 假设

SK-16 与 SK-07 的重建暴露了同一个模式：
**台账规则里的「转折限定」在下游技能中被丢掉了**，
导致把"方向性警告"误读成"缺个刻度"，进而做出结构错误的实现。

若这个模式普遍，则剩下 3 个承重自建项（SK-29／SK-04／SK-36）
很可能也在犯同样的错 —— 且能在动手前就预警。

## 判据（本门最重要的一节）

⚠️ **关键词命中 ≠ 丢限定。**
   看过 SK-07 的人都知道：按词搜索会捞出一堆无关的东西。
   所以本门**不用关键词判长短**，而用可核的代理指标：

   P0 结构完整性 —— 机制文本里转折词**之后**必须有实质内容。
              转折词在句尾（"…但是。"）就是**空转折**，不是限定。
   P1 下游引用   —— 该 rule_id 被哪些技能引用。
   P2 限定是否被引 —— 技能引用它时，**是否提到了转折后的那个限定**。
              这是关键判据：引用了但只取前半句 = 丢限定。

   ⚠️ **P2 的实测局限（2026-09-27 已确认）**：
      本门取的是「含 rule_id 的那一行」，但技能引用规则有**三种方式**：
        ① 依据表整行引用（该行通常含完整摘录）→ 本门能判
        ② 正文散句引用（如「这正是…（P30-11）的一个具体实例」）
           → 限定在**上一段**，本门取不到
        ③ 多文件引用同一 rule_id → 本门只取第一处
      实测 6 条候选**全部是这三种情况造成的误报**，
      逐条人工核后确认**真丢限定 0 条**。
      故本门**只能用作初筛**，不可作为「丢限定」的结论。
      下次改法：取 rule_id 所在**段落**（到空行为止）而非单行。

## 本门不做什么

❌ 不判定"哪条规则错了"——那是逐条读原文的活。
❌ 不自动改任何技能或台账。
✅ 只**报告**候选清单，供人工逐条核。
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(WS, "sources", "mechanism_rule_ledger_2026-09-26.json")
SKILLS = os.path.join(WS, "skills")
OUT = os.path.join(WS, "sources", "turn_qualifier_audit.json")

# 转折词 → (该词后应出现的限定类型, 判定用的特征词)
TURN = {
    "但是":   ("转折限定", ["不像", "并非", "不是", "过于", "过强", "更复杂", "太"]),
    "但经验": ("经验修正", ["不像", "并非", "更复杂", "趋势", "弱"]),
    "然而":   ("转折限定", ["但", "却", "不", "仅", "并非", "有限", "需要注意"]),
    "只是":   ("程度限定", ["而非", "不是", "不意味", "仅", "只", "有限"]),
    "有时":   ("存在性限定", ["不总是", "并非总是", "有些", "在某些"]),
    "似乎":   ("不确定性限定", ["可能", "并不", "未必", "不意味"]),
    "仅在":   ("条件限定", ["时", "条件", "情况"]),
    "局限":   ("适用范围", ["仅适用", "不适用", "限于", "范围"]),
    "除非":   ("条件限定", ["否则", "才"]),
    "不过":   ("转折限定", ["但", "却", "不"]),
    "不能直接": ("禁止性限定", ["必须", "不能", "需"]),
}


def main():
    print("=" * 76)
    print("门⑨ 台账转折限定丢失审计")
    print("=" * 76)
    with open(LEDGER, encoding="utf-8") as f:
        rules = json.load(f)["rules"]
    R = {r["rule_id"]: r for r in rules}

    # ── 技能正文：rule_id → 出现它的技能名与上下文 ──
    ctx = defaultdict(list)
    for fn in sorted(os.listdir(SKILLS)):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(SKILLS, fn), encoding="utf-8") as f:
            s = f.read()
        for m in re.finditer(r"\b((?:P\d+|BOTT|GST)-?\d+[a-z]?)\b", s):
            rid = m.group(1)
            if rid in R:
                # 取该 rule_id 所在整行作为上下文
                ls = s.rfind("\n", 0, m.start()) + 1
                le = s.find("\n", m.end())
                ctx[rid].append((fn, s[ls:le if le > 0 else len(s)]))

    # ── P0 结构完整性：转折词后是否有实质内容 ──
    print("\n" + "-" * 76)
    print("【P0】转折词后的限定是否非空")
    print("-" * 76)
    cands = []
    for r in rules:
        t = r["mechanism"]
        for kw, (kind, feats) in TURN.items():
            i = t.find(kw)
            if i < 0:
                continue
            after = t[i + len(kw):].strip()
            # 去掉句末标点后还剩多少实质字符
            body = re.sub(r"[。，；、）\s]+$", "", after)
            has_content = len(body) >= 6
            has_feature = any(x in body for x in feats)
            cands.append(dict(rid=r["rule_id"], kw=kw, kind=kind,
                              strength=r["derivation_strength"],
                              after=body[:120], has_content=has_content,
                              has_feature=has_feature))
            break
    print("  候选 %d 条" % len(cands))
    empty = [c for c in cands if not c["has_content"]]
    print("  空转折（词后无实质内容）%d 条" % len(empty))
    for c in empty[:8]:
        print("    ⚠️ %s 「%s」后为：%r" % (c["rid"], c["kw"], c["after"][:40]))

    # ── P2 限定是否被下游引用 ──
    print("\n" + "-" * 76)
    print("【P2】被引用的限定是否在技能正文中体现（关键判据）")
    print("-" * 76)
    lost, kept, unreferenced = [], [], []
    for c in cands:
        rid = c["rid"]
        hits = ctx.get(rid, [])
        if not hits:
            unreferenced.append(c)
            continue
        # 技能提到该 rule_id 时，同一行是否含限定特征词
        feat_ok = any(
            any(x in line for x in TURN[c["kw"]][1])
            or any(x in line for x in ["限定", "不总是", "并非", "只在", "仅适用",
                                        "经验修正", "不能直接", "不得"])
            for _fn, line in hits
        )
        (kept if feat_ok else lost).append((c, hits))

    print("  被技能引用且**体现了限定**   %2d 条" % len(kept))
    print("  被技能引用但**可能丢了限定** %2d 条  ← 需人工核" % len(lost))
    print("  未被任何技能引用            %2d 条" % len(unreferenced))

    print("\n  ── 「可能丢了限定」清单（须人工逐条核）──")
    for c, hits in lost:
        print("  %-10s [%s] 转折词「%s」 (%s)" % (c["rid"], c["strength"][:4],
                                                c["kw"], c["kind"]))
        print("      机制转折后：%s" % c["after"][:88])
        print("      引用处：%s" % "; ".join(f for f, _ in hits[:2])[:70])
        print("      引用行：%s" % hits[0][1].strip()[:88])

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "n_candidates": len(cands),
            "n_empty_turn": len(empty),
            "n_kept": len(kept), "n_lost": len(lost),
            "n_unreferenced": len(unreferenced),
            "lost": [{"rule_id": c["rid"], "turn": c["kw"], "kind": c["kind"],
                      "strength": c["strength"], "after": c["after"],
                      "cited_in": [fn for fn, _ in hits],
                      "cite_line": hits[0][1].strip()}
                     for c, hits in lost],
        }, f, ensure_ascii=False, indent=1)
    print("\n  落盘 %s" % OUT)

    print("\n" + "=" * 76)
    print("【判据】")
    fails = []
    if len(lost) == 0:
        fails.append("零条「可能丢了限定」—— 要么真无问题，要么判据太松（关键词匹配）")
        print("  ❌ 零条候选：判据可能太松，须人工确认")
    else:
        print("  ✅ 找到 %d 条候选（**关键词只是初筛，须人工逐条核**）" % len(lost))
    print()
    print("  ══ 人工逐条核结论（2026-09-27）══")
    print("  6 条候选**全部为误报**，真丢限定 **0 条**：")
    for rid, why in [
        ("P04-04", "依据表整行已含「(d) 有时对情绪情势做范畴化」—— 限定在内"),
        ("P33-09", "SK-06 正文写「可与**任何情境分类体系**结合」—— 限定在内"),
        ("P30-11", "SK-29 正文散句引用「相同环境下改变内部特征即可改变行为」—— 限定在内"),
        ("P46-03", "SK-02/40/41 三处均含「有时必须从专名关联推断」—— 限定在内"),
        ("P45-02", "SK-36 依据表含「然而在所有情形下…具有持续时间与进程」—— 限定在内"),
        ("P24-02", "SK-10 引的是前半句（动态系统），但该规则用于**模型结构**非限定，"
                   "「有时观众…」是举例不是限定"),
    ]:
        print("    %-9s %s" % (rid, why))
    print()
    print("  ⚠️ 结论：**台账的转折限定没有在下游丢失**。")
    print("     SK-16/SK-07 的两次结构证伪**不是这个模式** ——")
    print("     那两次是【自建项】把限定读窄了，与台账→技能的传递无关。")
    print("     这个假设**被证伪**，且证伪过程本身值得保留。")
    if empty:
        print("  ⚠️ %d 条转折词后为空 —— 这是结构问题，应先修" % len(empty))
    else:
        print("  ✅ 无空转折（词后均有实质内容）")
    print()
    print("  ⚠️ 本门**不判定任何规则对错**，只报告候选。")
    print("     关键词会误报 —— 这是本项目已翻了 12 次的坑。")
    print()
    if fails:
        for f in fails:
            print("  ❌ %s" % f)
        return 1
    print("PASS  门⑨ 审计完成（候选 %d 条待人工核）" % len(lost))
    return 0


if __name__ == "__main__":
    sys.exit(main())
