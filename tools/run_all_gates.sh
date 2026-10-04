#!/usr/bin/env bash
# 全部门的一次性运行入口。
#
# ⚠️ 解释器必须显式指定。踩过的坑：
#    shell 里的 `python` 指向另一套运行时解释器（**没有 pymupdf**），
#    而 verify_mechanism_excerpts 依赖 pymupdf。同一台机器上两个 `python`
#    指向不同环境 —— 用错解释器会让摘录门假失败（ModuleNotFoundError）。
#    本脚本锁定带 pymupdf 的那个，避免"在 bash 里能过、在别处失败"。
#
# ⚠️ 三值判定（2026-09-27 加入）。初版只有 OK／FAIL 两值且丢弃 stdout，
#    导致两个真实缺陷：
#      1. 外部输入被移动时，门抛 FileNotFoundError → 显示 FAIL，
#         看起来像程序坏了，实际只是输入不在；
#      2. SKIP 与 OK 混为一谈 → 谎报覆盖率。
#    现在按门输出判定：
#      OK    退出码 0，且输出不含 SKIP 标记
#      SKIP  退出码 0，且输出含 "SKIP · <gate>"
#      FAIL  退出码非 0
#    SKIP 不计入失败，但**必须显式显示**。

set -u
cd "$(dirname "$0")/.." || exit 2

PY="${PYTHON:-$(command -v python3 || command -v py || command -v python)}"
[ -x "$PY" ] || PY="${PYTHON:-$(command -v python3 || command -v py || command -v python)}"

# pymupdf 仅 3 个材料门需要；缺失时这些门按 SKIP 处理，其余门照常运行。
PYMU_GATES=" tools/verify_mechanism_excerpts.py tools/gate_quote_fidelity.py tools/gate_sk07_attribution.py "
if "$PY" -c "import pymupdf" 2>/dev/null; then
  PYMU_OK=1
else
  PYMU_OK=0
  echo "注意：解释器缺 pymupdf → $PY"
  echo "      依赖 pymupdf 的 3 个材料门将按 SKIP 处理，其余门不受影响。"
fi

TMP="${TMPDIR:-/tmp}/gate_$$"
mkdir -p "$TMP" || exit 2
trap 'rm -rf "$TMP"' EXIT

fail=0
skip=0
ok=0

run() {
  local name="$1"; shift
  local script="$1"
  if [ "$PYMU_OK" = "0" ] && [[ "$PYMU_GATES" == *" $script "* ]]; then
    printf "  %-24s SKIP  原因：解释器缺 pymupdf（材料门需要）\n" "$name"
    skip=$((skip+1))
    return
  fi
  local out="$TMP/$name.out"
  "$PY" "$@" >"$out" 2>&1
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    printf "  %-24s FAIL(EXIT=%s)\n" "$name" "$rc"
    fail=$((fail+1))
  elif grep -q "^SKIP · " "$out" 2>/dev/null; then
    # 门自己声明跳过：输入不可用。不是失败，但也不能算通过。
    local why
    why=$(grep -A2 "^SKIP · " "$out" | grep "原因：" | head -1 | sed 's/^ *//')
    printf "  %-24s SKIP  %s\n" "$name" "$why"
    skip=$((skip+1))
  else
    printf "  %-24s OK\n" "$name"
    ok=$((ok+1))
  fi
}

echo "解释器: $PY"
echo "======================================================================"
echo "全部门运行"
echo "======================================================================"

run "verify_gates"          tools/verify_gates.py
run "dryrun_e2e"            tools/dryrun_e2e.py
run "s1_formats"            tools/s1_formats.py
run "e7_gap"                tools/e7_gap.py
run "e8_state"              tools/e8_state.py
run "e9_backedge"           tools/e9_backedge.py
run "audit_formal"          tools/audit_formal.py
run "excerpts"              tools/verify_mechanism_excerpts.py
run "ledger_numbers"        tools/ledger_numbers.py --check
run "gate_sk16_domains"     tools/gate_sk16_domains.py
run "gate_sk07_attribution"  tools/gate_sk07_attribution.py
run "gate_turn_qualifier"   tools/gate_turn_qualifier.py
run "gate_sk29_normative"   tools/gate_sk29_normative.py
run "gate_sk36_identification" tools/gate_sk36_identification.py
run "gate_sk36_inertia"     tools/gate_sk36_inertia.py
run "gate_sk04_edges"       tools/gate_sk04_edges.py
run "gate_sk14_vitevitch"    tools/gate_sk14_vitevitch.py
run "gate_sk27_dilution"     tools/gate_sk27_dilution.py
run "gate_strength_validity"  tools/gate_strength_validity.py
run "gate_process_dimension"  tools/gate_process_dimension.py
run "gate_selfbuilt_audit"  tools/gate_selfbuilt_audit.py
run "gate_quote_fidelity"   tools/gate_quote_fidelity.py
run "gate_rasch_prohibition" tools/gate_rasch_prohibition.py

echo "======================================================================"
echo "OK $ok ｜ SKIP $skip ｜ FAIL $fail"
if [ "$fail" -gt 0 ]; then
  echo "→ $fail 项失败。SKIP 表示输入不可用，恢复输入后重跑即可。"
  exit 1
fi
if [ "$skip" -gt 0 ]; then
  echo "→ 无失败，但 $skip 项因输入不可用被跳过 —— **不等于全部通过**。"
  exit 0
fi
echo "全部通过"
exit 0
