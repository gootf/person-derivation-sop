# Person Derivation SOP — make "would this character do X?" an answer you can audit

**English** | [简体中文](README.zh-CN.md)

![License](https://img.shields.io/github/license/gootf/person-derivation-sop.svg)
![Release](https://img.shields.io/github/v/release/gootf/person-derivation-sop.svg)
![Stars](https://img.shields.io/github/stars/gootf/person-derivation-sop.svg)

**Ask an LLM "would this character do X?" and you get a fluent paragraph. It reads like reasoning, but it cannot be checked: no citation, no strength rating, no way to compare it against the same question asked tomorrow. When information is missing, the answer does not get weaker — it just gets quieter about its weakness.**

This repository ships a different instrument. Feed it character material in any format — prose, trait lists, archetype labels, fragments — and you get **a traceable evidence path** instead of a plausible-sounding explanation:

> **input assertion → mechanism rule (`rule_id`) → graph path → derivation strength (five tiers) → character conclusion**

Underneath sit **438 mechanism rules, every one bound to traceable evidence** — each carrying a verbatim excerpt and a five-tier derivation strength, extracted from 44 full-text-verified sources (personality psychology alongside narrative planning).

> **"Undecidable" is a legal answer.**
>
> This SOP is not in the business of making answers bolder. Its job is to make uncertainty visible: when the evidence runs out, it stops — listing what is missing and what to supply — instead of dressing a guess up as a conclusion.

## What goes wrong without it

| The failure | Without it | With it |
|---|---|---|
| One act decides a trait — one returned wallet, one snapped retort | "This shows who he really is" | Attribution-discount ladder (SK-07/SK-08, P22): what one behavior can and cannot establish about a disposition |
| A trait applied as law — "introverts don't go to parties" | One label, absolute behavior | Frequency quantification (SK-06): trait–behavior distributions overlap; almost no behavior is exclusive to a trait |
| Two scenes contradict | Smoothed into one "coherent" story | Contradiction is a first-class finding, reported as-is |
| Information is missing | A confident guess | S8 asks the input side for more — the state machine's only back edge; the standard never drops to fit the data |
| "She would never do that" | An untraceable assertion | Judgment = `rule_id` + graph path + strength tier, walking back to the source text |

## What you get, in 30 seconds

(Example constructed to the SK-20 output contract to show the shape of the output; every `rule_id` cited exists in the ledger — look them up yourself.)

```text
Material (from a draft — prose, any format works):
  After the meeting, Marcus finds a wallet in the parking garage —
  ID intact, $340 in cash. He tracks down the owner that evening
  and returns it untouched. The draft never shows him handling
  money again.

Question: is Marcus honest?
```

**The conclusion (first glance):**

> **One honest act is established — deliberate, at personal cost. The *trait* "honest" is not: a single observation, with no cross-situational covariation, licenses at most "possible" — not "highly probable". The upgrade path is named: show him meeting temptation in varied situations.**

**Expand the audit view (SK-20 quadruple):**

```text
  Assertion : Marcus is honest (a stable trait)
  Verdict   : not established — insufficient evidence (not a conflict
              finding; nothing contradicts it)
  Strength  : possible only (weak evidence, cannot exclude)
  Basis     : P22-01  correspondence is a scalar: behaviors vary in
              how much they inform a disposition
              P22-02  intentionality holds (a deliberate return at
              cost), so some correspondent inference is licensed
              SK-08   single-observation rule: one situation, one
              time point, no covariation → no trait-level attribution
  Path      : [returns wallet, deliberately, at cost]
              ─supports→ [honest act: this instance]
              ⇢ requires covariation ⇢ [trait: honest]
  Missing   : cross-situational observations — supply: money or
              temptation scenes in varied contexts
```

**The same question, answered by a plain LLM:**

```text
"Returning the wallet shows Marcus is fundamentally honest — his
core value system drives him to do the right thing even when
nobody is watching."

Audit questions: what mechanism takes ONE act to a "fundamental"
trait? Where in the text is the "core value system"? What strength
is the claim? Delete the wallet scene — what is left of "honest"?
```

Note what the SOP refused to do here: it did **not** answer "no". Absence of evidence is not evidence of absence — the verdict is "not established", with a named upgrade path, not a character assassination. Every audit question above has a landing spot in the output: each intermediate judgment carries its anchor, rule, path, and strength — **no evidence, no upgrade**.

## Who this is for

Core user: **anyone who needs an LLM to derive character behavior from character material reliably.** The scenarios below share that one need:

| You are | Your situation | What this gives you |
|---|---|---|
| **Fiction author / editor** | Keeping a character consistent across a long manuscript | Conflict-check reads; contradictions surface as structured findings with evidence, not vibes |
| **LLM persona / role-play builder** | Agents that drift, blend characters, or break persona | Anchored-assertion discipline: a claim without an anchor never enters the graph, so contamination cannot propagate |
| **Character-AI product / narrative-game team** | Settings where being wrong has measurable cost (character-consistency QC) | Auditable judgment output: every conclusion walks back to evidence; re-runnable, archivable |
| **Narrative-generation researcher** | Character models that must cite their sources | A 438-rule ledger: verbatim excerpts, five-tier strength, a 44-entry verified bibliography |
| **Anyone auditing AI character judgments** | "Why did the model say that?" | Every judgment walks back: conclusion → graph path → rule → excerpt → source |

## Why this SOP (verifiable, not trust-demanding)

You don't need to believe anything on this page — the repository ships the mechanism to check it yourself:

1. **Every rule has a source.** All 438 rules carry `rule_id → verbatim excerpt → publication`; ledger excerpts verified verbatim 438/438.
2. **Every derivation has a path.** Conclusion → graph path → rule → input assertion; a judgment without `rule_id` and path may not be output at all (SK-20).
3. **The repository itself is tested, and numbers are measured.** A 23-gate verification suite re-runs with one command (current baseline 19 OK / 4 SKIP / 0 FAIL); every statistic in the docs is recomputed from the ledger by `tools/ledger_numbers.py --check` — a stale number fails the gate instead of shipping.

## How it works

One graph, three reads — not three pipelines:

```text
arbitrary-format input
        │ S1 normalize
        ▼
indexed, anchored assertion set
        │ S2 build
        ▼
one weighted directed symbol graph
        │
        ├── reachability ───▶ completion          (what else is established?)
        ├── activation ─────▶ behavioral tendency (what is she likely to do?)
        └── well-formedness ▶ conflict check       (do the pieces cohere?)
```

Main flow S0–S8: ingest → normalize → build graph → well-formedness check → activation & state derivation → verdict → expectation gap → output → insufficient information (the single back edge S8→S1: **ask the input side for more; never lower the standard**).

And the chain stops exactly where automation honestly stops:

```text
mechanism rule (rule_id) ──machine──▶ behavioral tendency ──human──▶ character conclusion
```

The machine's job is to work out precisely which rules support which behavior; the human's job is to decide whether those rules suffice for a character-level conclusion. "Undecidable" appears not only when input runs short — it is also the mechanism boundary where this system refuses to pass a behavioral tendency off as a character conclusion. This repository does not dress that gap up as automation — it is a product boundary, not an unfinished feature.

### How to use it: a judgment on your own material

1. **Read** `SOP.md` §2–§4: input classification (narrative text / pure attributes / trope priors) and graph-building rules.
2. **Normalize** (S0–S3): turn your material into an indexed, anchored assertion set and build the graph — executed by a human; the shape is shown by the seven input formats in `tools/s1_formats.py`.
3. **Machine part**: reachability / activation propagation / in-degree (skills like SK-14 supply the parameter basis; script example: `tools/dryrun_e2e.py`).
4. **Human two hops**: rule → behavioral tendency, behavioral tendency → character conclusion (§5.6.12h: not automatable).
5. **Three-valued output**: confirmed / excluded / undecidable — "undecidable" is a legal conclusion, not a failure.

## Verify it, then use it

```bash
git clone https://github.com/gootf/person-derivation-sop.git
cd person-derivation-sop

# Python 3.11+; pymupdf is only needed by material-dependent gates
pip install pymupdf

# Watch it actually run (end-to-end 4 cases + 7 input formats):
python tools/dryrun_e2e.py
python tools/s1_formats.py

# Then run the 23-gate verification suite:
bash tools/run_all_gates.sh
# current baseline: 19 OK / 4 SKIP / 0 FAIL
# (4 SKIP: those gates need research material not distributed with this repo;
#  SKIP is reported separately from FAIL and never counts as a pass)
```

`dryrun_e2e.py` is a real end-to-end execution — here is its actual output (the scripts print in Chinese; excerpt — run them for the full text):

```text
$ python tools/dryrun_e2e.py
==========================================================================
[D1] P47-06 minimal process statement → minimal attribute description
  input (source sentence, P47-06): he fell in love with a woman
==========================================================================
── S1 normalize
  process statements: 1 ["he fell in love with a woman"]
── S1→S2 assertion · predication · domain routing · content type
  [A1] he is an admirer
        index anchor : he fell in love with a woman
        SK-03 domain : A2 psychological / stable trait
        basis        : P47-06, P46-03, P24-04, P19-11
── S2 build graph
  assertions (deduplicated): 1
  edge: STMT → A1  σ=+  w=None (uncalibrated)
        basis: P47-06, P47-05
        sparsity (P01-03): edges come only from relations the text
        actually states — nothing is completed
── S3 well-formedness check
  [A1] he is an admirer
        F1 dangling : not triggered (1 incoming edge)
        F2 sign     : not triggered (0 negative-sign incoming edges)
── S5 verdict
  strength: necessary — per P47-06's own ledger tier
  verdict : no conflict (F2 not triggered)
==========================================================================
dry run summary: D1=OK, D2=OK, D3=OK, D4=RULE_INPUT
```

## What it deliberately does NOT do

- **No story generation.** Generators produce text; this SOP produces **judgments**.
- **No numeric confidence.** Edge weights and the three-valued threshold are uncalibrated (SOP §5.1) — five strength tiers only; any "87% confident" would be baseless.
- **No automating the last two hops.** Rule → behavioral tendency → character conclusion is decided by a human; this repository does not dress that gap up as automation.
- **No retrying "undecidable" until it produces an answer.** A forced verdict on insufficient evidence is worse than no verdict.

## Known boundaries

- **Process-class mechanism gap**: 3/438 rules (corpus frozen; see SOP §5.6.12l) — within-process dynamics can only be predicted directionally.
- **Skill ↔ ledger semantic consistency**: sampled 30/30 consistent (95% CI upper bound ≈ 9.6%); not a full audit.
- **Quote fidelity**: 77 anchor-word lines verified machine-EXACT; 140 Chinese-paraphrase lines verified by 10/10 sampling — the remaining paraphrase lines are not individually machine-checkable.
- **Weights uncalibrated**: hence five strength tiers, no numeric confidence.
- **A structural-judgment system, not a dynamic personality model** (P45-01).

## Structure

| Path | Contents |
|---|---|
| `SOP.md` | The protocol itself (v1.8, 1418 lines): S0–S8 state machine, judgment contract, discipline clauses |
| `skills/` | 41 mechanism skills (SK-01…SK-41), every quote tagged with its `rule_id` |
| `sources/` | The 438-rule mechanism ledger (verbatim excerpts + five-tier strength), verification registries, 44-entry bibliography |
| `tools/` | 32 Python scripts + `run_all_gates.sh` (the 23-gate suite) |

## License

MIT — see [LICENSE](LICENSE).
