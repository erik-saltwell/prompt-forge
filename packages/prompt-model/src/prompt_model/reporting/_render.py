from __future__ import annotations

import html
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class _Stats:
    runs: int = 0
    rounds: int = 0
    total_candidates: int = 0
    feedback_actions: int = 0
    structural_actions: int = 0
    actions_applied: int = 0
    actions_skipped_apply: int = 0
    skip_reasons: Counter[str] = field(default_factory=Counter)
    metric_results_by_name: Counter[str] = field(default_factory=Counter)
    metric_validation_errors: int = 0
    transport_errors: int = 0
    iterations_run: int = 0
    best_score: float = 0.0
    duration_ms: int = 0
    runs_meta: list[dict[str, object]] = field(default_factory=list)
    failures: list[dict[str, object]] = field(default_factory=list)
    failures_by_event: Counter[str] = field(default_factory=Counter)
    applied_by_action_type: Counter[str] = field(default_factory=Counter)
    skipped_by_action_type: Counter[str] = field(default_factory=Counter)


def _record_failure(stats: _Stats, ev: dict[str, object], event_name: str) -> None:
    error_type: object = ev.get("error_type")
    if not isinstance(error_type, str) or not error_type:
        return
    stats.failures_by_event[event_name] += 1
    stats.failures.append(
        {
            "event": event_name,
            "run_id": ev.get("run_id"),
            "round": ev.get("round"),
            "error_type": error_type,
            "error_message": ev.get("error_message"),
        }
    )


def _read_events(jsonl_path: Path) -> Iterable[dict[str, object]]:
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _aggregate(events: Iterable[dict[str, object]]) -> _Stats:
    stats: _Stats = _Stats()
    candidates: set[str] = set()
    for ev in events:
        name: object = ev.get("event")
        match name:
            case "optimize_run.start":
                stats.runs += 1
                stats.runs_meta.append(
                    {
                        "run_id": ev.get("run_id"),
                        "n_iterations": ev.get("n_iterations"),
                        "n_eval_cases": ev.get("n_eval_cases"),
                        "metric_names": ev.get("metric_names"),
                    }
                )
            case "optimize_run":
                iters: object = ev.get("iterations_run")
                if isinstance(iters, int):
                    stats.iterations_run += iters
                best: object = ev.get("best_score")
                if isinstance(best, (int, float)) and float(best) > stats.best_score:
                    stats.best_score = float(best)
                dur: object = ev.get("duration_ms")
                if isinstance(dur, int):
                    stats.duration_ms += dur
                _record_failure(stats, ev, "optimize_run")
            case "round.start":
                stats.rounds += 1
            case "actor_run":
                children: object = ev.get("children_produced")
                if isinstance(children, int):
                    stats.total_candidates += children
                _record_failure(stats, ev, "actor_run")
            case "action":
                kind: object = ev.get("actor_kind")
                if kind == "feedback":
                    stats.feedback_actions += 1
                elif kind == "structural":
                    stats.structural_actions += 1
                applied: object = ev.get("applied")
                action_type: object = ev.get("action_type")
                if applied is True:
                    stats.actions_applied += 1
                    if isinstance(action_type, str):
                        stats.applied_by_action_type[action_type] += 1
                elif applied is False:
                    stats.actions_skipped_apply += 1
                    if isinstance(action_type, str):
                        stats.skipped_by_action_type[action_type] += 1
                    reason: object = ev.get("skip_reason")
                    if isinstance(reason, str):
                        stats.skip_reasons[reason] += 1
            case "metric_evaluation":
                metric_name: object = ev.get("metric_name")
                outcome: object = ev.get("outcome")
                if isinstance(metric_name, str) and outcome == "success":
                    stats.metric_results_by_name[metric_name] += 1
                error_type: object = ev.get("error_type")
                if isinstance(error_type, str):
                    if "Validation" in error_type:
                        stats.metric_validation_errors += 1
                    else:
                        stats.transport_errors += 1
            case "critic_evaluation":
                cand: object = ev.get("candidate_id")
                if isinstance(cand, str):
                    candidates.add(cand)
                error_type = ev.get("error_type")
                if isinstance(error_type, str) and "Validation" not in error_type:
                    stats.transport_errors += 1

    # Seed candidate is implicit; total_candidates already counts revise-produced children
    # plus the seed candidates observed in critic_evaluation events.
    stats.total_candidates = max(stats.total_candidates, len(candidates))
    return stats


def _h(s: object) -> str:
    return html.escape(str(s))


def _action_funnel(stats: _Stats) -> str:
    feedback_total: int = stats.feedback_actions
    structural_total: int = stats.structural_actions
    total_emitted: int = feedback_total + structural_total
    applied: int = stats.actions_applied
    skipped: int = stats.actions_skipped_apply
    return (
        f"emitted {total_emitted} (feedback {feedback_total} / structural {structural_total})"
        f" &rarr; applied {applied} &rarr; skipped {skipped}"
    )


def _skip_reason_rows(stats: _Stats) -> str:
    if not stats.skip_reasons:
        return "<tr><td colspan='2'><em>none</em></td></tr>"
    rows: list[str] = []
    for reason, count in stats.skip_reasons.most_common():
        rows.append(f"<tr><td>{_h(reason)}</td><td class='num'>{count}</td></tr>")
    return "".join(rows)


def _metric_rows(stats: _Stats) -> str:
    if not stats.metric_results_by_name:
        return "<tr><td colspan='2'><em>none</em></td></tr>"
    rows: list[str] = []
    for name, count in sorted(stats.metric_results_by_name.items()):
        rows.append(f"<tr><td>{_h(name)}</td><td class='num'>{count}</td></tr>")
    return "".join(rows)


def _action_type_rows(stats: _Stats) -> str:
    types: set[str] = set(stats.applied_by_action_type) | set(stats.skipped_by_action_type)
    if not types:
        return "<tr><td colspan='4'><em>none</em></td></tr>"
    rows: list[str] = []
    for t in sorted(types):
        applied: int = stats.applied_by_action_type.get(t, 0)
        skipped: int = stats.skipped_by_action_type.get(t, 0)
        total: int = applied + skipped
        rate: str = f"{(skipped / total) * 100:.0f}%" if total else "-"
        rows.append(f"<tr><td>{_h(t)}</td><td class='num'>{applied}</td><td class='num'>{skipped}</td><td class='num'>{rate}</td></tr>")
    return "".join(rows)


def _failure_rows(stats: _Stats) -> str:
    if not stats.failures:
        return "<tr><td colspan='5'><em>none</em></td></tr>"
    rows: list[str] = []
    for f in stats.failures:
        rows.append(
            "<tr>"
            f"<td>{_h(f.get('event'))}</td>"
            f"<td>{_h(f.get('run_id'))}</td>"
            f"<td class='num'>{_h(f.get('round'))}</td>"
            f"<td>{_h(f.get('error_type'))}</td>"
            f"<td>{_h(f.get('error_message'))}</td>"
            "</tr>"
        )
    return "".join(rows)


def _runs_table(stats: _Stats) -> str:
    if not stats.runs_meta:
        return "<tr><td colspan='4'><em>none</em></td></tr>"
    rows: list[str] = []
    for meta in stats.runs_meta:
        rows.append(
            "<tr>"
            f"<td>{_h(meta.get('run_id'))}</td>"
            f"<td class='num'>{_h(meta.get('n_iterations'))}</td>"
            f"<td class='num'>{_h(meta.get('n_eval_cases'))}</td>"
            f"<td>{_h(meta.get('metric_names'))}</td>"
            "</tr>"
        )
    return "".join(rows)


_CSS: str = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2em auto; max-width: 900px; color: #222; }
h1 { border-bottom: 2px solid #333; padding-bottom: .3em; }
h2 { margin-top: 2em; color: #444; }
table { border-collapse: collapse; margin: .5em 0 1em 0; min-width: 320px; }
th, td { border: 1px solid #ddd; padding: 6px 12px; text-align: left; }
th { background: #f4f4f4; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.summary { background: #f9f9f9; padding: 1em 1.5em; border-left: 4px solid #4a90e2; margin-bottom: 1.5em; }
.summary div { margin: .25em 0; }
.label { display: inline-block; min-width: 14em; color: #666; }
.funnel { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; padding: .5em .75em; background: #f4f4f4; border-radius: 4px; }
"""


def render_report(jsonl_path: Path) -> str:
    """Read a JSON-lines event log and produce a self-contained HTML report."""
    stats: _Stats = _aggregate(_read_events(jsonl_path))

    summary_block: str = (
        f"<div><span class='label'>Optimize runs</span> <strong>{stats.runs}</strong></div>"
        f"<div><span class='label'>Rounds</span> <strong>{stats.rounds}</strong></div>"
        f"<div><span class='label'>Iterations completed</span> <strong>{stats.iterations_run}</strong></div>"
        f"<div><span class='label'>Total candidates</span> <strong>{stats.total_candidates}</strong></div>"
        f"<div><span class='label'>Best score</span> <strong>{stats.best_score:.4f}</strong></div>"
        f"<div><span class='label'>Total duration (ms)</span> <strong>{stats.duration_ms}</strong></div>"
    )

    failed_optimize_runs: int = stats.failures_by_event.get("optimize_run", 0)
    failed_actor_runs: int = stats.failures_by_event.get("actor_run", 0)
    error_block: str = (
        f"<div><span class='label'>LLM transport errors</span> <strong>{stats.transport_errors}</strong></div>"
        f"<div><span class='label'>Metric validation errors</span> <strong>{stats.metric_validation_errors}</strong></div>"
        f"<div><span class='label'>Failed optimize runs</span> <strong>{failed_optimize_runs}</strong></div>"
        f"<div><span class='label'>Failed actor runs</span> <strong>{failed_actor_runs}</strong></div>"
    )

    actions_block: str = (
        f"<div><span class='label'>Feedback actor actions</span> <strong>{stats.feedback_actions}</strong></div>"
        f"<div><span class='label'>Structural actor actions</span> <strong>{stats.structural_actions}</strong></div>"
        f"<div><span class='label'>Actions applied</span> <strong>{stats.actions_applied}</strong></div>"
        f"<div><span class='label'>Actions failed to apply</span> <strong>{stats.actions_skipped_apply}</strong></div>"
    )

    funnel: str = _action_funnel(stats)
    metric_rows: str = _metric_rows(stats)
    skip_rows: str = _skip_reason_rows(stats)
    runs_rows: str = _runs_table(stats)
    failure_rows: str = _failure_rows(stats)
    action_type_rows: str = _action_type_rows(stats)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>prompt-model report</title>
<style>{_CSS}</style>
</head>
<body>
<h1>prompt-model optimization report</h1>

<h2>Summary</h2>
<div class="summary">{summary_block}</div>

<h2>Errors</h2>
<div class="summary">{error_block}</div>

<h3>Run / actor failures</h3>
<table>
<thead><tr><th>Event</th><th>run_id</th><th>Round</th><th>Error type</th><th>Message</th></tr></thead>
<tbody>{failure_rows}</tbody>
</table>

<h2>Actions</h2>
<div class="summary">{actions_block}</div>

<h3>Action funnel</h3>
<div class="funnel">{funnel}</div>

<h3>Apply rate by action type</h3>
<table>
<thead><tr><th>action_type</th><th>Applied</th><th>Skipped</th><th>Skip rate</th></tr></thead>
<tbody>{action_type_rows}</tbody>
</table>

<h3>Skip reasons (apply phase)</h3>
<table>
<thead><tr><th>Reason</th><th>Count</th></tr></thead>
<tbody>{skip_rows}</tbody>
</table>

<h2>Metric results returned</h2>
<table>
<thead><tr><th>Metric</th><th>Results returned</th></tr></thead>
<tbody>{metric_rows}</tbody>
</table>

<h2>Runs observed</h2>
<table>
<thead><tr><th>run_id</th><th>Iterations</th><th>Eval cases</th><th>Metrics</th></tr></thead>
<tbody>{runs_rows}</tbody>
</table>
</body>
</html>
"""
