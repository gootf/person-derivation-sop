#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""台账数字的唯一真源。文档中的统计数字必须由本脚本实测，不得手填。

用法：
    python tools/ledger_numbers.py          # 打印全部
    python tools/ledger_numbers.py --check   # 校验文档中的数字是否与实测一致
"""
import json, os, re, sys
from collections import Counter

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(WS, "sources", "mechanism_rule_ledger_2026-09-26.json")


def load():
    with open(LEDGER, encoding="utf-8") as f:
        return json.load(f)


def numbers():
    led = load()
    rules = led["rules"]
    c = Counter(x["derivation_strength"] for x in rules)
    D = os.path.join(WS, "skills")
    refs = set()
    for fn in os.listdir(D):
        if fn.endswith(".md"):
            with open(os.path.join(D, fn), encoding="utf-8") as f:
                refs |= set(re.findall(r"\b(?:P\d+[a-z]?|BOTT|GST)-\d+[a-z]?\b", f.read()))
    with open(os.path.join(WS, "SOP.md"), encoding="utf-8") as f:
        sop = f.read()
    # ⚠️ §5.5 缺口表里的 rule_id 是**「提及」不是「引用」**——
    #    计入会让缺口自证为已覆盖（同 §5.5 口径声明）。故排除该节。
    sop_body = re.split(r"^## 5\.5 ", sop, flags=re.M)[0]
    sop_gap = "## 5.5 " + sop.split("## 5.5 ", 1)[1] if "## 5.5 " in sop else ""
    soprefs = set(re.findall(r"\b(?:P\d+[a-z]?|BOTT|GST)-\d+[a-z]?\b", sop_body))
    ids = {x["rule_id"] for x in rules}
    sk = refs & ids
    spec = json.load(open(os.path.join(WS, "sources", "mechanism_spec_level_map.json"),
                          encoding="utf-8"))
    L3 = set()
    for r, v in spec.items():
        if r != "_meta":
            L3 |= set(v.get("L3", []))
    L3 &= ids
    # 自建项：按「量」计（SK-14 一项含四个量 → 计 4）
    skills = os.path.join(WS, "skills")
    sb_skills, sb_items = 0, 0
    for fn in sorted(os.listdir(skills)):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(skills, fn), encoding="utf-8") as f:
            s = f.read()
        # 2026-10-03 审计后：读全部【自建】行（不只第一行）；
        # 『无』/『无。』开头 = 无自建项（注记），跳过不计数
        file_has = False
        for m in re.finditer(r"\*\*【自建】\*\*\s*\|([^\n]*)", s):
            v = m.group(1).strip().rstrip("|").strip()
            if not v or v.startswith("无"):
                continue
            file_has = True
            sb_items += len(re.findall(r"[；;]", v)) + 1
        if file_has:
            sb_skills += 1

    return {
        "total": len(rules),
        "selfbuilt_skills": sb_skills,
        "selfbuilt_items": sb_items,
        "necessary": c["necessary"], "strong": c["strong"],
        "contextual": c["contextual"], "possible": c["possible"],
        "conflict": c["conflict"],
        "skill_refs": len(sk), "sop_only": len((soprefs & ids) - sk),
        "gap_table_mentions": len(set(re.findall(
            r"\b(?:P\d+[a-z]?|BOTT|GST)-\d+[a-z]?\b", sop_gap)) & ids),
        "L3_total": len(L3), "L3_unref_strict": len(L3 - sk),
    }


def check():
    n = numbers()
    D = os.path.join(WS, "skills")
    pat = re.compile(
        r"necessary\s*(\d+)[^\n]{0,40}strong\s*(\d+)[^\n]{0,40}"
        r"contextual\s*(\d+)[^\n]{0,40}possible\s*(\d+)[^\n]{0,40}conflict\s*(\d+)")
    want = (str(n["necessary"]), str(n["strong"]), str(n["contextual"]),
            str(n["possible"]), str(n["conflict"]))
    bad = []
    for fn in sorted(os.listdir(D)):
        if not fn.endswith(".md"):
            continue
        p = os.path.join(D, fn)
        with open(p, encoding="utf-8") as f:
            for m in pat.finditer(f.read()):
                if m.groups() != want:
                    bad.append((fn, m.groups(), want))
    if bad:
        for fn, got, w in bad:
            print("STALE %s: %s  应为 %s" % (fn, got, w))
        return False
    print("OK 分布数字全部与台账一致: %s" % ("／".join(want)))
    # 校验 SOP 中的自建项计数
    sop_path = os.path.join(WS, "SOP.md")
    with open(sop_path, encoding="utf-8") as f:
        sop = f.read()
    m = re.search(r"自建项清单（(\d+) 处", sop)
    if m and int(m.group(1)) != n["selfbuilt_items"]:
        print("STALE SOP.md 自建项计数 %s，应为 %d（%d 个技能）"
              % (m.group(1), n["selfbuilt_items"], n["selfbuilt_skills"]))
        return False
    print("OK 自建项计数一致: %d 处 / %d 个技能"
          % (n["selfbuilt_items"], n["selfbuilt_skills"]))

    # ⚠️ SOP.md **自己**的 §5.5 覆盖率数字此前无人校验 ——
    #    §5.5 写着「被技能引用 213（48.6%）」，实测已是 219（50.0%），
    #    漂了很久没被抓。check_sync_docs 原本不覆盖 SOP 自身。补上。
    m2 = re.search(r"被技能引用.*?\*\*(\d+)\*\*（([\d.]+)%）", sop)
    if m2:
        got_n, got_p = int(m2.group(1)), float(m2.group(2))
        want_p = round(n["skill_refs"] / n["total"] * 100, 1)
        if got_n != n["skill_refs"] or abs(got_p - want_p) > 0.05:
            print("STALE SOP.md §5.5 技能引用 写 %d（%s%%），应为 %d（%s%%）"
                  % (got_n, got_p, n["skill_refs"], want_p))
            return False
        print("OK SOP §5.5 技能引用一致: %d（%s%%）" % (n["skill_refs"], want_p))
    # ⚠️ 判据自身翻车一次：原正则 `L3 缺口）\s*\|\s*\*\*(\d+)\*\*`
    #    匹配到了**宽松口径**那行的 12（"宽松口径：…的 L3 缺口"），
    #    而严口径是 14。同一节里两个"L3 缺口"，正则抓错了行。
    #    正解：锚定"其中仍未被引用（严口径）"这一行。
    m3 = re.search(r"其中仍未被引用\*\*（严口径）\s*\|\s*\*\*(\d+)\*\*", sop)
    if m3 and int(m3.group(1)) != n["L3_unref_strict"]:
        print("STALE SOP.md §5.5 严格 L3 缺口 %s，应为 %d"
              % (m3.group(1), n["L3_unref_strict"]))
        return False
    if m3:
        print("OK SOP §5.5 严格 L3 缺口一致: %d" % n["L3_unref_strict"])

    if not check_sync_docs(n):
        return False
    return True


def check_sync_docs(n):
    """校验同步文档里的统计数字是否与实测一致。

    对象：交付文档中的统计数字。
    历史漂移：437/438、360/361；2026-09-28 复查又抓到一批未被覆盖的类别
    （SOP 版本/行数、工具计数、映射统计、依赖边数、门数）——
    当时本函数只显示不校验其中一部分 ⇒ **覆盖范围窄于自称**。
    教训：显示的数字 ≥ 校验的数字时，OK 行就是假绿。现已扩面。

    原则：只在**该数字确实以字面量出现**时才判；不出现不报。
    """
    # —— 结构性数字全部实测，避免手填 ——
    skills = len([f for f in os.listdir(os.path.join(WS, "skills"))
                  if f.endswith(".md")])
    scripts = len([f for f in os.listdir(os.path.join(WS, "tools"))
                   if f.endswith(".py")])
    with open(os.path.join(WS, "SOP.md"), encoding="utf-8") as f:
        sop = f.read()
    sop_lines = len(sop.splitlines())
    m = re.search(r"版本\s*v(\d+\.\d+)", sop)
    sop_ver = float(m.group(1)) if m else None
    # 依赖图边数 = SOP 中含 SK 节点的 --> 行（跳过 S0–S8 流程图：其中无 SK 节点）
    edges = sum(1 for l in sop.splitlines() if "-->" in l and re.search(r"SK-?\d+", l))
    # 套件门数 = run_all_gates.sh 的 run 行数
    with open(os.path.join(WS, "tools", "run_all_gates.sh"), encoding="utf-8") as f:
        n_gates = len(re.findall(r"(?m)^run ", f.read()))
    # 映射统计 = mechanism_map.json 的 map（对 stats 块的双重核对）
    # 发行版不含该映射数据文件：源在才校验，不在则显式 SKIP 该组。
    _mmp = os.path.join(WS, "sources", "mechanism_map.json")
    _mmp_skip = not os.path.exists(_mmp)
    if not _mmp_skip:
        with open(_mmp, encoding="utf-8") as f:
            mm = json.load(f)["map"]
    else:
        mm = []
    mm_direct = sum(1 for e in mm if e["kind"] == "DIRECT")
    mm_bridge = sum(1 for e in mm if e["kind"] == "BRIDGE")
    mm_none = sum(1 for e in mm if e["kind"] == "NONE")
    mm_rules = len({e["rule_id"] for e in mm if e.get("rule_id")})
    mm_pct = (round(mm_bridge / (mm_direct + mm_bridge) * 100, 1)
               if (mm_direct + mm_bridge) else 0.0)

    # (正则, 实测值元组, 说明)  —— 数字统一转 float 比较；版本 x.y 亦以 float 计
    pats = [
        (r"台账\s*\*\*(\d+)\s*条", (n["total"],), "台账条数"),
        (r"necessary\s*\*\*(\d+)\*\*", (n["necessary"],), "necessary"),
        (r"技能引用\s*\*\*(\d+)", (n["skill_refs"],), "技能引用"),
        (r"自建\s*\*\*(\d+)\s*处\s*/\s*(\d+)\s*个技能",
         (n["selfbuilt_items"], n["selfbuilt_skills"]), "自建处数/技能数"),
        (r"自建\s*\*\*(\d+)\s*处", (n["selfbuilt_items"],), "自建处数(宽)"),
        (r"\*\*(\d+)\s*个技能\*\*", (skills,), "技能数"),
        (r"\*\*(\d+)\s*个技能", (skills,), "技能数(宽松)"),
        (r"未引用 L3\s*\*\*(\d+)\*\*", (n["L3_unref_strict"],), "未引用L3"),
        # —— 2026-09-28 扩面：曾漂移的类别 ——
        (r"`SOP\.md`\s*\*\*v(\d+\.\d+)\*\*（(\d+) 行）",
         (sop_ver, sop_lines), "SOP版本/行数"),
        (r"骨架，(\d+) 行 v(\d+\.\d+)", (sop_lines, sop_ver), "SOP行数/版本"),
        (r"\|\s*v(\d+\.\d+)\s*/\s*(\d+)\s*行\s*\|",
         (sop_ver, sop_lines), "SOP版本/行数(表)"),
        (r"\|\s*(\d+)\s*行\s*/\s*v(\d+\.\d+)\s*\|",
         (sop_lines, sop_ver), "SOP行数/版本(表)"),
        (r"(\d+)\s*个工具脚本", (scripts,), "工具脚本数"),
        (r"(\d+)\s*个 Python 脚本", (scripts,), "Python脚本数"),
        (r"\|\s*`tools/`\s*\|\s*(\d+)\s*个脚本", (scripts,), "工具脚本数(表)"),
        (r"直接\s*\*{0,2}(\d+)\s*／\s*桥接\s*\*{0,2}(\d+)\s*／\s*无机制\s*\*{0,2}(\d+)",
         (mm_direct, mm_bridge, mm_none), "映射三分类"),
        (r"触及台账\s*(\d+)\s*条规则", (mm_rules,), "触及规则数"),
        (r"桥接(?:只)?占\s*(\d+\.\d+)%", (mm_pct,), "桥接占比"),
        (r"(\d+)\s*条明标无机制", (mm_none,), "无机制条数"),
        (r"(\d+)\s*(?:条)?依赖边", (edges,), "依赖边数"),
        (r"全部门（\*\*(\d+) 项\*\*）", (n_gates,), "门数"),
    ]

    def _norm(g):
        out = []
        for x in g:
            try:
                out.append(float(x))
            except (TypeError, ValueError):
                out.append(x)
        return out

    def _eq(got, want):
        if len(got) != len(want):
            return False
        for a, b in zip(got, want):
            if isinstance(b, float):
                if not isinstance(a, float) or abs(a - b) > 0.06:
                    return False
            elif a != b:
                return False
        return True

    bad = False
    for fn in ("SOP.md",):
        p = os.path.join(WS, fn)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            s = f.read()
        for pat, want, label in pats:
            if _mmp_skip and any(w in ("mm_direct", "mm_bridge", "mm_none",
                                       "mm_rules", "mm_pct") for w in ()):
                continue
            if _mmp_skip and label.startswith(("映射", "触及", "桥接", "无机制")):
                print("（未校验）映射数据源不在发行版，跳过 %s" % label)
                continue
            for mo in re.finditer(pat, s):
                got = _norm(mo.groups())
                if not _eq(got, list(want)):
                    print("STALE %s: %s 写 %s，应为 %s"
                          % (fn, label, mo.group(0).strip()[:60], want))
                    bad = True
    if bad:
        return False
    print("OK 同步文档数字一致 (台账 %d / necessary %d / 技能 %d / 脚本 %d / "
          "SOP v%s·%d 行 / 映射 %d·%d·%d / 依赖边 %d / 自建 %d·%d)"
          % (n["total"], n["necessary"], skills, scripts,
             sop_ver, sop_lines, mm_direct, mm_bridge, mm_none, edges,
             n["selfbuilt_items"], n["selfbuilt_skills"]))
    return True

if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(0 if check() else 1)
    n = numbers()
    for k, v in n.items():
        print("%-16s %s" % (k, v))
