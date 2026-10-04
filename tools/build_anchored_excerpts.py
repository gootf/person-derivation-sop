#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从原文程序化抽取 support_excerpt，杜绝手工转写。

匹配用「无空白签名」：把原文与锚点都压成 [a-z0-9] 序列再比对，
从而免疫 PDF 抽取的断行、断字、连字符、切词空格。
找到命中位置后，回到原始文本按同样的偏移关系截取可读窗口。

anchor_terms 全部须命中同一窗口；缺任一即 anchor_missing，不写摘录。
"""
import json, os, re, sys, zipfile
import pymupdf

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS = os.path.join(WS, "papers")
LEDGER = os.path.join(WS, "sources", "mechanism_rule_ledger_2026-09-26.json")

_cache = {}


def _ocr_pages(ocr_path):
    """把带 '=== OCR PAGE n ===' 标记的 OCR 产物切成 {物理页: 该页文本}。

    OCR 产物不是 PDF，不得冒充原文件；这里只借用它的分页标记，且要求
    标记页序从 1 连续递增，否则拒绝使用（无法保证与 PDF 物理页一一对应）。
    """
    s = open(ocr_path, "r", encoding="utf-8", errors="ignore").read()
    # 两种历史标记都要认：P39 用 '=== OCR PAGE n ==='，Chatman 扫描件用 '===== [scan page n] ====='
    marks = []
    for m in re.finditer(r"=== OCR PAGE (\d+) ===|===== \[scan page (\d+)\] =====", s):
        marks.append((int(m.group(1) or m.group(2)), m.start()))
    nums = [n for n, _ in marks]
    if not marks or nums != list(range(1, len(marks) + 1)):
        return None
    out = {}
    for k, (n, st) in enumerate(marks):
        en = marks[k + 1][1] if k + 1 < len(marks) else len(s)
        out[n] = s[st:en]
    return out


OCR_DIR = os.path.join(PAPERS, "ocr")


def _find_ocr(fname):
    """按原 PDF 文件名定位同名 OCR 目录下的合并 .txt。

    OCR 目录名是 PDF 名的前缀（P39_Baldwin_1992 vs P39_Baldwin_1992_Relational_Schemas.pdf），
    中间还可能夹一层 rerun_<日期>/，所以不能只比目录名出现在 stem 里，
    要用「stem 以目录名开头」判断，再在其中找合并产物。

    同一来源常有多个 OCR 版本，质量差别很大：同名不带日期目录下的旧版可能
    整栏丢弃且左右栏文字交错（"script foran —_of"），而 rerun 目录下的
    tesseract 重跑版是干净的单栏文本。优先 tesseract 版。
    """
    stem = os.path.splitext(fname)[0]
    cands = []
    for root, _dirs, files in os.walk(OCR_DIR):
        rel = os.path.relpath(root, OCR_DIR)
        parts = rel.split(os.sep)
        # 来源目录名须是 PDF 名（去扩展名）的前缀；rerun_<日期>/ 只是中间层
        if not (parts and parts[0] and stem.startswith(parts[0])):
            continue
        for fn in files:
            if not fn.endswith(".txt"):
                continue
            if fn.startswith("page_") or fn.startswith("ocr_p"):
                continue          # 逐页碎片，不是合并产物
            if "_ocr" in fn or fn == stem + ".txt":
                cands.append((0 if "rerun" in rel else 1, os.path.join(root, fn)))
    if not cands:
        return None
    # rerun 目录下的 tesseract 重跑版优先（sort 稳定，同级保持发现顺序）
    cands.sort(key=lambda t: t[0])
    return cands[0][1]


def page_text(fname, page):
    fp = os.path.join(PAPERS, fname)
    low = fname.lower()
    if low.endswith(".pdf"):
        if fname not in _cache:
            try:
                _cache[fname] = [pg.get_text() for pg in pymupdf.open(fp)]
            except Exception:
                _cache[fname] = []
        pg = _cache[fname]
        i = int(page) - 1
        if pg and 0 <= i < len(pg) and pg[i].strip():
            return pg[i], (i + 1 if 0 <= i < len(pg) else None)
        # 原 PDF 无文本层 -> 回退到 OCR 产物（仅当页码标记齐全）
        ocr = _find_ocr(fname)
        if ocr:
            key = "ocr:" + os.path.basename(ocr)
            if key not in _cache:
                _cache[key] = _ocr_pages(ocr) or {}
            store = _cache[key]
            i = int(page)
            if i in store:
                return store[i], i
        return "", (i + 1 if 0 <= i < len(pg) else None)
    if low.endswith(".epub"):
        if fname not in _cache:
            z = zipfile.ZipFile(fp)
            _cache[fname] = {n: re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", "ignore"))
                             for n in z.namelist()}
        store = _cache[fname]
        key = str(page).replace("\\", "/").lstrip("/")
        for n in store:
            if n == key or n.endswith("/" + key) or os.path.basename(n) == os.path.basename(key):
                return store[n], n
        return "", None
    return open(fp, "r", encoding="utf-8", errors="ignore").read(), 1


def sig(s):
    """签名：压成 [a-z0-9]，顺带折叠 PDF 连字。

    学术 PDF 常把 fi/ff/fl 连字成 U+FB01/FB02/FB03，fitz 抽出来就是单个
    特殊字符，不折叠会让 "deﬁnes" 永远匹配不上 "defines" 写的锚点。
    """
    s = (s.replace("ﬁ", "fi").replace("ﬀ", "ff").replace("ﬂ", "fl")
          .replace("ﬃ", "ffi").replace("ﬄ", "ffl"))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def sig_with_map(s):
    """返回 (签名, 签名下标 -> 原文字符下标 的列表)。连字按 1 个字符计入签名。"""
    s = (s.replace("ﬁ", "fi").replace("ﬀ", "ff").replace("ﬂ", "fl")
          .replace("ﬃ", "ffi").replace("ﬄ", "ffl"))
    out, idx = [], []
    i = 0
    while i < len(s):
        c = s[i].lower()
        if ("a" <= c <= "z") or ("0" <= c <= "9"):
            out.append(c)
            idx.append(i)
        i += 1
    return "".join(out), idx


def extract(fname, page, anchor_terms, before=300, after=900):
    raw, real_page = page_text(fname, page)
    if not raw:
        return None, None, "no_text"
    flat = re.sub(r"\s+", " ", raw).strip()
    fsig, fmap = sig_with_map(flat)

    # 所有锚点的签名都要能在页内定位
    positions = []
    for term in anchor_terms:
        ts = sig(term)
        if not ts:
            return None, None, "empty_anchor"
        # 取第一个（若要求全部出现于同一窗口，见下）
        spots = []
        start = 0
        while True:
            i = fsig.find(ts, start)
            if i < 0:
                break
            spots.append(i)
            start = i + 1
            if len(spots) >= 12:
                break
        if not spots:
            return None, None, "anchor_missing:" + term[:40]
        positions.append((term, spots))

    # 选覆盖锚点数最多、且跨度最小的一处。
    # 不用固定 ±1400 窗口：它会把同一锚点词在别处的重复出现也拉进来，把 hi
    # 撑到整段之前，摘录虽然逐字通过但机制定义落在尾部。改为按当前跨度倍增
    # 聚类，同一锚点的多处出现中取与簇相邻的那一处。
    # 聚类簇未必覆盖全部锚点（定义句与引用句常分开），故按覆盖数择优而非要求全覆盖。
    best = None
    for term, spots in positions:
        for c in spots:
            lo, hi = c, c
            for _ in range(len(positions) + 1):
                reach = max(80, (hi - lo) * 2)
                grew = False
                for _t2, sp2 in positions:
                    for s in sp2:
                        if lo - reach <= s <= hi + reach:
                            if s < lo:
                                lo = s
                                grew = True
                            elif s > hi:
                                hi = s
                                grew = True
                if not grew:
                    break
            n_cov = sum(1 for _t, sp in positions
                        if any(lo <= s <= hi for s in sp))
            key = (-n_cov, hi - lo)
            if best is None or key < best[0]:
                best = (key, lo, hi, term)
    if best is None:
        return None, None, "no_common_anchor"
    _key, lo, hi, _term = best
    c = lo
    # 窗口以锚点群为中心，长度按摘录需要限制，避免把整页拉进来。
    # before/after 按锚点群跨度按比例给，而不是给固定下限：固定下限（如 120 字符）
    # 会把锚点群之前的整段话拉进窗口，摘录仍逐字通过，但机制那句被埋在段中，
    # 而「落在该页」与「对准该机制」是两件事。
    # 簇的**实际长度**是 hi - lo，不是 hi - c（c 只是簇起点那个命中）。
    # 用 hi - c 会让紧邻的多锚点簇（lo≈c）算出 span≈0，after 退到 260 下限，
    # 于是窗口在机制句中途截断——摘录仍逐字通过，但机制句只留前半。
    span = hi - lo
    before = max(30, min(before, max(40, span // 3)))
    after = max(200, min(after, max(260, span * 2)))
    s_idx = fmap[max(0, c - before)]
    e_idx = fmap[min(len(fmap) - 1, hi + after)]
    win = flat[s_idx:e_idx + 1]
    return win, {"char_offset_in_page": s_idx, "char_end": e_idx + 1, "real_page": real_page}, "ok"


def main():
    led = json.load(open(LEDGER, encoding="utf-8"))
    ANCH = os.path.join(WS, "sources", "mechanism_anchor_terms.json")
    anchors = json.load(open(ANCH, encoding="utf-8"))
    ok = miss = moved = 0
    problems = []
    for r in led["rules"]:
        terms = anchors.get(r["rule_id"])
        if not terms:
            problems.append((r["rule_id"], "no_anchor_terms")); miss += 1; continue
        win, meta, st = extract(r["source_file"], r["source_page"], terms)
        if st != "ok":
            problems.append((r["rule_id"], st)); miss += 1
            r["support_excerpt"] = ""; r["excerpt_anchor"] = None
            continue
        if meta["real_page"] is not None and str(meta["real_page"]) != str(r["source_page"]):
            moved += 1
        r["support_excerpt"] = win
        r["excerpt_anchor"] = meta
        ok += 1
    led["excerpt_provenance"] = {
        "method": "anchor-matched window extraction; signature matching ignores whitespace/ligature noise",
        "ok": ok, "missing": miss, "page_moved": moved,
        "problems": [{"rule_id": a, "status": b} for a, b in problems],
    }
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)
    print(f"ok={ok} missing={miss} page_moved={moved}")
    for a, b in problems:
        print("  PROBLEM", a, b)
    return 0 if miss == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
