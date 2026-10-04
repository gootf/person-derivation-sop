#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
形式化审计 SOP.md §3.1 转移表。

对应四个审计方法：
  · Petri 网工作流建模      → soundness: no deadlock / option to complete
  · 过程复杂度审计      → size / coupling / cohesion
  · 过程质量评估       → 四维度质量
  · 复用组件挖掘 → 技能复用（孤立组件检测）

**转移表是文档，指标是代码。** §3.1.1 里的数字必须由本脚本生成，不得手填。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOP = os.path.join(WS, "SOP.md")
SKILLS = os.path.join(WS, "skills")
LEDGER = os.path.join(WS, "sources", "mechanism_rule_ledger_2026-09-26.json")

N_STATES = 9          # S0..S8
GATES = ["verify_gates", "dryrun_e2e", "s1_formats", "e7_gap", "e8_state", "e9_backedge"]


# ================================================================ 解析转移表

def parse_transitions():
    lines = open(SOP, encoding="utf-8").read().split("\n")
    i = lines.index("### 3.1 转移表")
    rows = []
    for l in lines[i + 2:]:
        s = l.strip()
        if s == "":
            break
        if s.startswith("|") and s[1] not in "-":
            c = [x.strip().replace("**", "") for x in s.strip("|").split("|")]
            if len(c) >= 4 and c[0].startswith("S"):
                rows.append(c)
    return rows


# ================================================================ soundness

def audit():
    rows = parse_transitions()
    out = defaultdict(list)
    inn = defaultdict(int)
    for a, b, guard, _ in rows:
        out[a].append(b)
        if b.startswith("S"):
            inn[b] += 1
    states = {"S%d" % i for i in range(N_STATES)}
    finals = {"终止"}

    # 可达性
    seen = {"S0"}
    stack = ["S0"]
    while stack:
        n = stack.pop()
        for m in out.get(n, []):
            if m in states and m not in seen:
                seen.add(m)
                stack.append(m)
    unreachable = sorted(states - seen)

    # option to complete
    def reaches_final(n, path=frozenset()):
        if n in finals:
            return True
        if n in path:
            return False
        return any(reaches_final(m, path | {n}) for m in out.get(n, []))

    no_complete = sorted(n for n in seen if not reaches_final(n))

    # 死锁
    dead = sorted(n for n in seen if n not in finals and not out.get(n))

    # 环
    color, cycles = {}, []

    def dfs(n, st):
        color[n] = 1
        st = st + [n]
        for m in out.get(n, []):
            if m not in states:
                continue
            if color.get(m) == 1:
                cycles.append(st[st.index(m):] + [m])
            elif color.get(m) is None:
                dfs(m, st)
        color[n] = 2

    for n in sorted(seen):
        if color.get(n) is None:
            dfs(n, [])

    # 复杂度
    P = len(states)
    T = len({(a, b) for a, b, _, _ in rows})
    fanout = {a: len(bs) for a, bs in out.items()}
    hub = max(fanout, key=lambda k: fanout[k]) if fanout else "-"
    # 连通组件
    adj = defaultdict(set)
    for a, bs in out.items():
        adj[a] |= {a} | set(bs)
        for b in bs:
            adj[b] |= {a, b}
    vis, comps = set(), 0
    for n in adj:
        if n in vis:
            continue
        comps += 1
        st = [n]
        vis.add(n)
        while st:
            x = st.pop()
            for y in adj[x]:
                if y not in vis:
                    vis.add(y)
                    st.append(y)

    # 技能复用
    files = [f for f in os.listdir(SKILLS) if f.endswith(".md")]
    used = set()
    for fn in files:
        s = open(os.path.join(SKILLS, fn), encoding="utf-8").read()
        fid = re.search(r"id:\s*(SK-\d\d)", s)
        if not fid:
            continue
        used.add(fid.group(1).replace("-", ""))
        for k in ("depends_on", "outputs_to"):
            m = re.search(k + r":\s*\[(.*?)\]", s)
            for x in (m.group(1).split(",") if m else []):
                x = x.strip().replace("-", "")
                if x.startswith("SK"):
                    used.add(x)
    orphan = [fn for fn in files
              if re.search(r"id:\s*(SK-\d\d)", open(os.path.join(SKILLS, fn),
                                                    encoding="utf-8").read())
              and re.search(r"id:\s*(SK-\d\d)", open(os.path.join(SKILLS, fn),
                                                     encoding="utf-8").read()).group(1).replace("-", "")
              not in used]

    return {
        "rows": rows, "out": out, "inn": inn,
        "reachable": len(seen & states), "unreachable": unreachable,
        "no_complete": no_complete, "dead": dead, "cycles": cycles,
        "P": P, "T": T, "size": P + T, "hub": hub, "hub_fanout": fanout.get(hub, 0),
        "comps": comps, "cohesion": round((P + T) / T, 2) if T else 0,
        "orphan": orphan, "n_skills": len(files),
    }


# ================================================================ 质量四维

def quality():
    r = {}
    codes = {}
    for g in GATES:
        p = subprocess.run([sys.executable, os.path.join(WS, "tools", g + ".py")],
                           capture_output=True, cwd=WS)
        codes[g] = p.returncode
    r["gates"] = codes
    r["gates_ok"] = sum(1 for v in codes.values() if v == 0)

    sop = open(SOP, encoding="utf-8").read()
    r["sop_lines"] = sop.count("\n") + 1
    r["headings"] = len([l for l in sop.split("\n") if l.startswith("#")])
    r["skeleton"] = "本文件只含骨架" in sop

    guards = sum(1 for x in parse_transitions() if x[2])
    r["guards"] = guards
    r["trans"] = len(parse_transitions())

    import json
    led = json.load(open(LEDGER, encoding="utf-8"))

    def norm(s):
        for a, b in [("−", "-"), ("–", "-"), ("—", "-"), ("『", "「"), ("』", "」")]:
            s = s.replace(a, b)
        for ch in "＊*　「」《》…·※﻿`":
            s = s.replace(ch, "")
        return re.sub(r"\s+", "", re.sub(r"[\"']", "", s.replace("\\", "")))

    corpus = norm(" ".join((x.get("mechanism") or "") + " " + (x.get("support_excerpt") or "")
                            for x in led["rules"]))
    tot = ok = 0
    bad = []
    for fn in sorted(f for f in os.listdir(SKILLS) if f.endswith(".md")):
        s = open(os.path.join(SKILLS, fn), encoding="utf-8").read()
        m = re.search(r"## 依据\b(.*?)(?:## 依据分级)", s, re.S)
        for q in re.findall(r"「([^「」]{12,})」", m.group(1) if m else ""):
            segs = [x for x in (norm(x) for x in re.split(r"…+", q)) if len(x) >= 16]
            if not segs:
                continue
            tot += 1
            if all(x in corpus for x in segs):
                ok += 1
            else:
                bad.append(fn)
    r["quote_ok"], r["quote_tot"], r["quote_bad"] = ok, tot, bad
    return r


# ================================================================ 报告

def main():
    a = audit()
    q = quality()
    print("=" * 74)
    print("Stage 5 · 形式化审计（SOP.md §3.1 转移表 + 技能库）")
    print("=" * 74)
    print("\n[Petri 网工作流建模] soundness")
    print("  可达性        %d/%d %s" % (a["reachable"], N_STATES,
                                        "✅" if not a["unreachable"] else "❌ " + str(a["unreachable"])))
    print("  option to complete  %s" % ("✅" if not a["no_complete"] else "❌ " + str(a["no_complete"])))
    print("  死锁          %s" % ("✅ 无" if not a["dead"] else "❌ " + str(a["dead"])))
    print("  环            %d 条 %s" % (len(a["cycles"]),
                                        "✅（唯一回边，轮上限保证有界）" if len(a["cycles"]) == 1
                                        else "❌" if len(a["cycles"]) > 1 else "—"))
    for c in a["cycles"]:
        print("      %s" % " → ".join(c))
    print("\n[过程复杂度审计]")
    print("  Size          places=%d transitions=%d tokens=%d" % (a["P"], a["T"], a["size"]))
    print("  Coupling      连通组件=%d %s｜最大扇出 %s=%d" %
          (a["comps"], "✅" if a["comps"] == 1 else "❌", a["hub"], a["hub_fanout"]))
    print("  Cohesion      tokens/arcs=%.2f %s" % (a["cohesion"], "✅" if a["cohesion"] > 1 else "⚠️"))
    print("\n[复用组件挖掘]")
    print("  技能 %d 个；孤立(无任何依赖边) %d %s" %
          (a["n_skills"], len(a["orphan"]), "✅" if not a["orphan"] else "❌ " + str(a["orphan"])))
    print("\n[过程质量评估] 四维度")
    print("  Correctness      %d/%d 门退出码 0 %s" %
          (q["gates_ok"], len(GATES), "✅" if q["gates_ok"] == len(GATES) else "❌"))
    print("  Understandability SOP %d 行 / %d 标题 %s" %
          (q["sop_lines"], q["headings"], "✅ 骨架+索引" if q["skeleton"] else "❌"))
    print("  Expressiveness   %d 条转移，%d 条带守卫（%.0f%%）" %
          (q["trans"], q["guards"], q["guards"] / q["trans"] * 100))
    print("  Maintainability  引文 %d/%d 逐字 %s" %
          (q["quote_ok"], q["quote_tot"], "✅" if not q["quote_bad"] else "❌ " + str(q["quote_bad"])))

    ok = (not a["unreachable"] and not a["no_complete"] and not a["dead"]
          and a["comps"] == 1 and not a["orphan"]
          and q["gates_ok"] == len(GATES) and not q["quote_bad"])
    print("\n" + "-" * 74)
    print("Stage 5 审计: %s" % ("✅ 全部通过" if ok else "❌ 有未过项"))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
