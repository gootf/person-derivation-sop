#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门㉕ 自建项审计 —— 「材料未给 X」这个负声明本身要被审计。

## 起因
「自建」是与「无机制支撑」(NONE) 同类的**负声明**。NONE 的假阴性率
实测 40%（2/5 漏挂，门㉒）；自建此前从未审过，账面「31 处/30 技能」
依赖一个脆弱的分号计数器（只读每技能第一行、『无。』注记行被误计）。

## 2026-10-03 全量审计结论（sources/selfbuilt_audit_2026-10-03.json）
- 真实：**27 项 / 25 技能**（账面 31 = 27 − 1 漏读 SK-41 第二行
  − 1 隐藏项 SK-28 + 6 幽灵行『无。＋注记』被误计）。
- 逐条裁决 26 项：24 准确 / 1 高估已改正（SK-23「只到形式层」——
  台账实有 ought/other 全链 P40-05/06/07 + 情绪词表 P40-10/11/14）。
- 计数器已修：读全部【自建】行、『无』前缀跳过、删「四项」特判。

## 判据
A. 机器计数 == 登记册项数 == 27；技能数 == 25
B. 登记册每项有 evidence 规则号且存在于台账（防幻想引用）
C. 修复项不得回退：SK-23 单元格含「审计改正」；SK-28 已转正（不写『无。』开头）
D. 幽灵行不得被计数（『无』前缀行计入即 FAIL）
E. 注入可失败：登记册若改 verdict 为 unknown，本门必须 FAIL
"""
from __future__ import annotations

import json
import os
import re
import sys

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails: list = []


def check(name, cond, detail=""):
    print("  %s %-58s %s" % ("✅" if cond else "❌", name, detail))
    if not cond:
        fails.append(name)


def main():
    print("=" * 88)
    print("门㉕ 自建项审计 —— 负声明「材料未给 X」的账目与真相")
    print("=" * 88)

    reg = json.load(open(os.path.join(WS, "sources",
                                      "selfbuilt_audit_2026-10-03.json"),
                         encoding="utf-8"))
    led = json.load(open(os.path.join(WS, "sources",
                                      "mechanism_rule_ledger_2026-09-26.json"),
                         encoding="utf-8"))
    rules = led["rules"] if isinstance(led, dict) else led
    ids = {r["rule_id"] for r in rules}

    # ── A. 计数对账 ──
    print("\n【A】机器计数 vs 登记册")
    print("-" * 88)
    skills = os.path.join(WS, "skills")
    n_items, n_files, ghost = 0, 0, []
    per_file = {}
    for fn in sorted(os.listdir(skills)):
        if not fn.endswith(".md"):
            continue
        s = open(os.path.join(skills, fn), encoding="utf-8").read()
        rows = []
        for m in re.finditer(r"\*\*【自建】\*\*\s*\|([^\n]*)", s):
            v = m.group(1).strip().rstrip("|").strip()
            if not v:
                continue
            if v.startswith("无"):
                ghost.append(fn)
                continue
            rows.append(len(re.findall(r"[；;]", v)) + 1)
        if rows:
            n_files += 1
            n_items += sum(rows)
            per_file[fn] = sum(rows)
    reg_items = len(reg["items"])
    reg_skills = len({i["skill"].rstrip("ab") for i in reg["items"]})
    print("    机器 %d 项/%d 技能｜登记册 %d 项（%d 技能去后缀）｜幽灵行 %d"
          % (n_items, n_files, reg_items, reg_skills, len(ghost)))
    check("★ 计数 == 登记册 == 27 项", n_items == reg_items == 27,
          "机器 %d / 登记 %d" % (n_items, reg_items))
    check("★ 技能数 == 25", n_files == reg_skills == 25,
          "机器 %d / 登记 %d" % (n_files, reg_skills))

    # ── B. 证据规则号存在 ──
    print("\n【B】登记册证据引用存在性（防幻想）")
    print("-" * 88)
    missing = []
    for it in reg["items"]:
        for rid in it["evidence"]:
            if rid.startswith("EXT-"):
                continue  # EXT 登记册另有核对
            if rid not in ids:
                missing.append((it["skill"], rid))
    check("★ 证据 rule_id 全部存在于台账", not missing,
          "缺 %d: %s" % (len(missing), missing[:3]) if missing else "0 缺")

    # ── C. 修复不回退 ──
    print("\n【C】修复不回退")
    print("-" * 88)
    sk23 = open(os.path.join(WS, "skills", "SK-23-自我差异情绪.md"),
                encoding="utf-8").read()
    sk28 = open(os.path.join(W_S := WS, "skills", "SK-28-手段类型判定.md"),
                encoding="utf-8").read()
    check("★ SK-23 改正标记在册（『审计改正』/『高估缺口』）",
          "审计改正" in sk23 and "高估缺口" in sk23)
    m28 = re.search(r"\*\*【自建】\*\*\s*\|([^\n]*)", sk28)
    v28 = m28.group(1).strip() if m28 else ""
    check("★ SK-28 隐藏项已转正（行首为实质内容、非『无』）",
          not v28.startswith("无") and "损害" in v28, v28[:40])

    # ── D. 幽灵不计 ──
    print("\n【D】幽灵行处理")
    print("-" * 88)
    print("    『无』前缀行文件：%s" % (", ".join(ghost) or "（无）"))
    # 幽灵 = 『无』前缀**且带注记**（旧计数器因不在 ("无","无。") 集合而误计）；
    # 纯「无」/「无。」行从未被计数，不算幽灵。
    true_ghost = []
    for fn in sorted(os.listdir(skills)):
        if not fn.endswith(".md"):
            continue
        s = open(os.path.join(skills, fn), encoding="utf-8").read()
        for m in re.finditer(r"\*\*【自建】\*\*\s*\|([^\n]*)", s):
            v = m.group(1).strip().rstrip("|").strip()
            if v.startswith("无") and v not in ("无", "无。", "无；"):
                true_ghost.append(fn)
    print("    带注记的『无』前缀行（真幽灵）：%s" % (", ".join(true_ghost) or "（无）"))
    check("★ 真幽灵恰 5 个文件（SK-12/13/15/19/37；SK-28 已转正）",
          sorted(set(g[:5] for g in true_ghost)) ==
          ["SK-12", "SK-13", "SK-15", "SK-19", "SK-37"]
          and len(true_ghost) == 5,
          "%d 个" % len(true_ghost))

    # ── E. 判据可失败自检 ──
    print("\n【E】注入自检（本门判据非恒真）")
    print("-" * 88)
    bad = [i for i in reg["items"] if i["verdict"] not in ("accurate",)]
    check("★ 登记册 verdict 全部为 accurate（出现 unknown 即须复审）",
          not bad, "非 accurate %d 项" % len(bad))

    print("\n" + "=" * 88)
    if fails:
        print("❌ 失败 %d 项：" % len(fails))
        for x in fails:
            print("   - %s" % x)
        return 1
    print("PASS  门㉕ 自建账目一致：27 项/25 技能；24 准确 + 1 高估已改 + 2 补录；幽灵 5 不计")
    print("⚠️ SK-23 剩余三条（ideal/own、ideal/other、ought/own）如需引用须回原文补拆。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
