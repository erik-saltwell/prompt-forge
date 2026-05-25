# Benchmarking Against SCULPT

## Overview

A phased empirical comparison between prompt-forge and the SCULPT reference implementation, run on a subset of SCULPT's published benchmarks. The goal is design validation: confirm prompt-forge produces results in the neighborhood of SCULPT's published numbers, then measure whether prompt-forge's distinctive design choices (per-bucket fan-out, structural cleanup pass, annotation-first action vocabulary) lift those numbers further. Not for external publication — internal confidence-building.

## Key Concepts

**Reference system.** The SCULPT paper and its public repo at `Sshanu/SCULPT`. Source of the benchmark data, initial prompts, eval parsers, and published headline numbers.

**Task.** A single benchmark with its own data splits, initial prompt, metric, and reported SCULPT score. The two tasks in scope: **Causal Judgement (CJ)** from BBH (binary classification, SCULPT reports 75.9 on GPT-4o, initial prompt 71.1) and **GoEmotions (GoE)** (multi-label macro-F1, 28 classes, SCULPT reports 30.6, initial 7.8). CJ first; GoE deferred until phase 3.

**Hybrid run.** SCULPT runs in its own repo to produce a final optimized prompt as a markdown string. Prompt-forge runs in its own harness to produce its own final prompt. Both final prompts are then evaluated by a single shared evaluator (prompt-forge's) on the same test split using the same parser. The optimizers differ; the judge does not.

**Phase 1 config (prompt-forge).** Prompt-forge defaults *except* the three cheap switches that already exist as named alternates: structural cleanup off (`never_cleanup_structure`), JSON prompt rendering, "keep everything" redaction. This nudges prompt-forge toward SCULPT's shape without a week of mirroring work. Everything else stays at prompt-forge defaults — the design under test.

**Pass criteria (phase 1, CJ).** Floor: beat the initial prompt's 71.1 by at least +3 points. Goal: land within 2 points of SCULPT's published 75.9. Below the floor signals a bug; between floor and goal triggers phase 2 tuning; at or above goal skips phase 2.

**Convergence.** Optimization stops when no improvement on the validation set for 3 consecutive iterations, hard cap at 16 iterations.

## Flows

### Phase 1 — CJ smoke test

1. Pull SCULPT's CJ data splits and initial prompt verbatim from `Sshanu/SCULPT/data/causal_judgement/` and `Sshanu/SCULPT/prompts/`. Locate and replicate SCULPT's eval parser for CJ.
2. Build the CJ accuracy metric in prompt-forge (`metrics/` is empty; CJ is the simplest case — binary string match using SCULPT's parser logic).
3. Configure prompt-forge with the phase-1 config (three switches flipped, otherwise defaults). Use GPT-4o for target, critic, and actor; temperature 0 on eval, 0.5 on optimization steps.
4. Run prompt-forge to convergence. Sample 25% of train/val cases per optimization step. Evaluate the final prompt on the full test set for a number directly comparable to SCULPT's published 75.9.
5. Single trial. Compare against pass criteria.

### Phase 2 — Tune (conditional)

Runs only if phase 1 lands between floor (74.1) and goal (73.9). Flip the three phase-1 switches back to prompt-forge's real defaults one at a time, observe lift, settle on a winning config.

### Phase 3 — GoEmotions, prompt-forge only

1. Build the GoEmotions multi-label macro-F1 metric using SCULPT's output parser.
2. Run prompt-forge with the phase-2 config on GoEmotions to convergence.
3. Compare the result against SCULPT's published 30.6. No SCULPT rerun.

## Behaviors & Rules

- **Held fixed across both systems:** initial prompt, target LLM (GPT-4o), critic and actor LLMs (GPT-4o on both sides — matching model strength is non-negotiable), train/val/test splits, eval metric, eval parser, stopping rule.
- **Varied (the experiment):** optimizer architecture and all prompt-forge defaults the user does not explicitly flip.
- **The eval parser is part of "configured similarly."** Loose-vs-strict output matching can shift CJ scores by 2–5 points on identical prompts. Use SCULPT's parser logic exactly.
- **One trial per cell in phase 1.** Not for publication — the variance budget that 3 trials buys isn't worth the cost at the smoke-test stage. If phase 2 surfaces a result close to a decision boundary, re-run that specific cell 3× for confidence.
- **25% sampling applies to optimization-time validation only.** Final reported scores always use the full test split, or the comparison to SCULPT's number is meaningless.
- **No re-implementation of SCULPT inside prompt-forge.** Phase 1 mirrors SCULPT only via the three named switches; deeper mirroring is out of scope.
- **No published headlines.** Internal-only.

## Open Questions

None — all design decisions were resolved during the brainstorm.
