#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
E7 —— S6 预期落差的可执行验收。

要验的约束（SOP.md §1 不变量三、§4、SK-18／SK-19）：

    **内部一致性优先于预期落差**，且两者**必须分开**：
      · 内部一致性读**文本图**（判据全在文本内）
      · 预期落差读**文本图 − 先验图**（判据在文本外）
      · 落差**可服务于惊喜** ⇒ 高落差**不是缺陷**，**不得判错**，**不得加负号**
      · 落差值与严重度是**两个独立维度**，**不并入同一张量表**

未测原因：先验图本体是自建（SK-18 已登记），落差侧一次没跑过。

先验基线用**材料自己的四领域**（P24-07：身体性／心理性／社会性／行为），
不另造体系——材料没给可复用的先验库，这是已登记的自建缺口。

判据：
  B1  先验图来源必须显式声明，缺声明 → 拒绝执行（SK-18 硬约束）
  B2  四领域落差分别计算，**心理与社会性**须单独标注（P24-07 原话）
  B3  落差**绝不产出** conflict／严重度／负号
  B4  落差值与严重度是**独立字段**，不合成单一分
  B5  五点序数映射 2/1/0/−1/−2（P28-07）严格按表
  B6  含糊样本（not sure）**丢弃**，不是降权（P28-07 原操作）
  B7  落差可升级为硬判的**唯一**条件是文本内线索（P24-09）；无线索只标注
  B8  S3 有违例时 **S6 不执行**（嵌套前置，内部一致性优先）
  B9  先验图缺失时**跳过落差而非报错**（不得因缺先验而阻断）
  B10 落差侧结果**不进 F1/F2/F3**（三者是内部一致性的判据）
"""
from __future__ import annotations

import sys

# ── 材料给的量 ───────────────────────────────────────────────────────
# P24-07：身体性、心理性、社会性与行为**四领域**是「启发式且普遍被接受的
#          虚构角色描述起点」；「尤其是在心理与社会性方面」推断最多。
FOUR_DOMAINS = ["身体性", "心理性", "社会性", "行为"]
# P24-07 原话：心理与社会性方面落差最大 → 这两域检查更细
DEEP_DOMAINS = {"心理性", "社会性"}

# P28-07：五点序数 → 数值，「把标签分别映射为 2、1、0、−1、−2」
ORDINAL = {"yes": 2, "maybe yes": 1, "not sure": 0,
           "maybe no": -1, "no": -2}

# P24-07：赌场老板例 —— 我们会期待「优雅、机敏、世界主义态度、冷酷、放荡道德」
CASINO_PRIOR = {
    "优雅": "社会性", "机敏": "心理性", "世界主义态度": "社会性",
    "冷酷": "心理性", "放荡道德": "社会性",
}


class DropKind:
    MISSING = "missing"   # 先验期待有，文本没写（读者预期有，文本缺）
    EXTRA = "extra"       # 文本写了，先验未预期（意外 → 可能是惊喜）


# ================================================================ 先验图

def build_prior(entries):
    """构造先验图。**必须显式声明来源**（SK-18 硬约束）。"""
    src = entries.get("source")
    if not src:
        return None, "先验图未声明来源 → 拒绝执行（SK-18：不得使用隐含的未声明先验）"
    graph = {}
    for feat, dom in entries.get("features", {}).items():
        graph[feat] = {"domain": dom, "source": src}
    return {"nodes": graph, "source": src}, None


# ================================================================ 落差计算

def domain_of(feature, text_graph, prior):
    for d in FOUR_DOMAINS:
        if feature in prior["nodes"]:
            return prior["nodes"][feature]["domain"]
    return text_graph.get(feature, {}).get("domain")


def compare(text_graph, prior):
    """比对。**只产落差项，不判错。**"""
    items = []
    # 文本未提供而先验期待
    for feat, meta in prior["nodes"].items():
        if feat not in text_graph:
            items.append({"kind": DropKind.MISSING, "feature": feat,
                          "domain": meta["domain"],
                          "prior_source": meta["source"],
                          "deep": meta["domain"] in DEEP_DOMAINS})
    # 文本提供而先验未预期
    for feat, meta in text_graph.items():
        if feat not in prior["nodes"]:
            items.append({"kind": DropKind.EXTRA, "feature": feat,
                          "domain": meta.get("domain"),
                          "deep": meta.get("domain") in DEEP_DOMAINS,
                          "prior_source": None})
    return items


def mark(items, reader_response, text_clues):
    """落差标注（SK-19）。**不判错。**

    P28-07：not sure 的样本**丢弃**（含糊样本污染整份报告）。
    P24-09：只有**文本内线索**才可把「有意／无意」升级为硬判。
    """
    kept, dropped = [], []
    for it in items:
        resp = reader_response.get(it["feature"])
        # ⚠️ 「无响应」与「not sure」是**两回事**（E7 首次实跑纠正）：
        #   · not sure → P28-07 **明令丢弃**的含糊样本
        #   · 无响应   → 读者未就此项表态，**不是**含糊样本。
        #     它是 MISSING 侧的正常情形（文本没写，读者当然无从表态），
        #     归入「须丢弃」会**误报**为含糊，掩盖真正该报的落差项。
        # 无响应项保留，并显式标 no_response。
        if resp is None:
            kept.append(dict(it, drop_value=None, no_response=True,
                             intent=None, intent_is_hard=False,
                             note="读者未就此项表态（非含糊样本）"))
            continue
        if resp == "not sure":
            dropped.append(dict(it, dropped_reason="P28-07：含糊样本须丢弃"))
            continue
        val = ORDINAL[resp]
        rec = dict(it, drop_value=val)
        # 硬判门槛：文本内线索
        if text_clues and it["feature"] in text_clues:
            rec["intent"] = text_clues[it["feature"]]
            rec["intent_is_hard"] = True
        else:
            rec["intent"] = None
            rec["intent_is_hard"] = False
            rec["note"] = "无线索 → 只标注，不硬判（P24-09）"
        kept.append(rec)
    return kept, dropped


# ================================================================ 输出

def s6_output(kept, dropped, severity):
    """S6 输出。**落差与严重度是两个独立字段，绝不合成单一分。**"""
    return {
        "drop_items": kept,
        "dropped_items": dropped,
        "drop_value_by_feature": {k["feature"]: k["drop_value"] for k in kept},
        "severity": severity,            # 独立字段，来自 S3／SK-16
        "verdict": None,                 # ⚠️ 落差侧永不产出判定
        "conflict": None,                # ⚠️ 落差 ≠ 冲突
        "penalty": None,                 # ⚠️ 不得加负号
        "is_defect": False,              # ⚠️ 高落差不是缺陷
        "deep_domain_items": [k["feature"] for k in kept if k["deep"]],
    }


def run_s6(text_graph, prior_entries, reader_response, text_clues, severity, s3_violation):
    """S6 全流程。含**嵌套前置**：S3 有违例则 S6 不执行。"""
    if s3_violation:
        return {"executed": False,
                "reason": "S3 存在 F1／F2／F3 违例 → S6 不执行（内部一致性优先）",
                "drop_items": [], "verdict": None, "conflict": None}
    prior, err = build_prior(prior_entries)
    if prior is None:
        # B9：先验缺失 → 跳过，不报错
        return {"executed": False, "reason": err, "skipped_not_error": True,
                "drop_items": [], "verdict": None, "conflict": None}
    items = compare(text_graph, prior)
    kept, dropped = mark(items, reader_response, text_clues)
    out = s6_output(kept, dropped, severity)
    out["executed"] = True
    return out


# ================================================================ 用例

# 文本：一个"赌场老板"角色，但文本**没写**优雅/冷酷，且**多写**了「紧张」
TEXT = {
    "机敏": {"domain": "心理性"},
    "从容": {"domain": "行为"},
    "紧张": {"domain": "心理性"},          # 先验未预期 → EXTRA（可能是有意反差）
}
PRIOR = {"source": "P24-06 赌场老板例＋P24-07 四领域起点",
         "features": CASINO_PRIOR}
RESP = {"优雅": "yes", "机敏": "yes", "世界主义态度": "maybe yes",
        "冷酷": "no", "放荡道德": "not sure",   # not sure → 须丢弃
        "紧张": "maybe no"}
CLUES = {"紧张": "有意反差：文本写他手在发牌时发抖"}   # 唯一有文本内线索的落差


def main():
    res = []

    def rep(cid, ok, note):
        res.append(ok)
        print("  %s %s — %s" % ("✅" if ok else "❌", cid, note))

    print("=" * 74)
    print("E7 · S6 预期落差（内部一致性优先，两者分开）")
    print("  先验来源：%s" % PRIOR["source"])
    print("=" * 74)

    out = run_s6(TEXT, PRIOR, RESP, CLUES, severity="F1_低", s3_violation=False)
    items = out["drop_items"]

    # B1 来源必须声明
    p2, err = build_prior({"features": {}})
    rep("B1", p2 is None and err is not None,
        "无来源声明 → 拒绝：%s" % (err or "")[:40])

    # B2 四领域 + 心理/社会性单独标注
    doms = {i["domain"] for i in items}
    rep("B2", doms <= set(FOUR_DOMAINS) and len(out["deep_domain_items"]) >= 1,
        "落差域 %s；深检域项 %s（P24-07：心理与社会性最细）"
        % (sorted(doms), out["deep_domain_items"]))

    # B3 落差绝不产出 conflict/负号/判错
    ok3 = (out["verdict"] is None and out["conflict"] is None
           and out["penalty"] is None and out["is_defect"] is False)
    rep("B3", ok3,
        "verdict/conflict/penalty 全为 None，is_defect=False（高落差不是缺陷）")

    # B4 落差值与严重度独立
    rep("B4", "drop_value_by_feature" in out and out["severity"] == "F1_低"
        and not any(k in out for k in ("combined_score", "total")),
        "落差按 feature 分列，严重度独立字段，无合并分")

    # B5 五点序数映射
    ok5 = (out["drop_value_by_feature"].get("优雅") == 2
           and out["drop_value_by_feature"].get("冷酷") == -2
           and out["drop_value_by_feature"].get("世界主义态度") == 1
           and out["drop_value_by_feature"].get("紧张") == -1)
    rep("B5", ok5, "优雅=2 冷酷=−2 世界主义=1 紧张=−1（P28-07 映射）")

    # B6 含糊样本丢弃
    dropped_feats = [d["feature"] for d in out["dropped_items"]]
    no_resp = [k["feature"] for k in out["drop_items"] if k.get("no_response")]
    rep("B6", dropped_feats == ["放荡道德"]
        and "放荡道德" not in out["drop_value_by_feature"]
        and no_resp == ["从容"],
        "not sure「放荡道德」丢弃（非降权）；无响应「从容」保留并标 no_response")

    # B7 硬判门槛
    hard = [i for i in items if i.get("intent_is_hard")]
    hard_feats = [i["feature"] for i in hard]
    rep("B7", hard_feats == ["紧张"],
        "仅「紧张」有文本内线索→硬判；其余 %d 项只标注"
        % len([i for i in items if not i.get("intent_is_hard")]))

    # B8 嵌套前置
    out8 = run_s6(TEXT, PRIOR, RESP, CLUES, severity="F2_高", s3_violation=True)
    rep("B8", out8["executed"] is False and out8["drop_items"] == []
        and "内部一致性优先" in out8["reason"],
        "S3 有违例 → S6 不执行：%s" % out8["reason"][:36])

    # B9 先验缺失 → 跳过非报错
    out9 = run_s6(TEXT, {}, RESP, CLUES, severity="无", s3_violation=False)
    rep("B9", out9["executed"] is False and out9.get("skipped_not_error") is True,
        "先验缺失 → 跳过且标记 skipped_not_error（不阻断）")

    # B10 落差项不进内部一致性判据
    forbidden = {"f1", "f2", "f3", "structural_violation", "consistency_type"}
    leak = forbidden & set(out.keys())
    rep("B10", not leak,
        "落差输出无 F1／F2／F3 字段（三者是内部一致性判据）")

    ok = all(res)
    print("-" * 74)
    print("E7: %d/%d 通过  %s" % (sum(res), len(res), "✅" if ok else "❌"))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
