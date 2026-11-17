"""Collect capstone evidence using the unmodified final reference solutions.

Run in the supplied Python 3.13 environment. No third-party runner dependencies.
The default run calls the live API for systems 1, 2 and 4. --offline is a partial
check only; it never substitutes invented API evidence for systems 1 and 2.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET


SOLUTION_PATHS = {
    1: "Build a Claims Intake Agent with a stop_reason-Driven Loop/exercises/03-dynamic-decomposition/solution",
    2: "Engineer a Long-Conversation Context Strategy for a Retail Support Copilot/04-assemble-and-locate/solution",
    3: "Configure Claude Code for a Multi-Surface Monorepo Team/04-plan-mode-and-explore-decision-doc/solution",
    4: "Build a Multi-Shift Quality Monitoring System with Claude Orchestration/04-fork-scratchpad/solution",
}
FOLDERS = {1: "system-1-agentic-loop", 2: "system-2-context-strategy",
           3: "system-3-claude-config", 4: "system-4-orchestration"}
EXPECTED_TESTS = {1: 30, 2: 30, 3: 35, 4: 33}
CAPSTONE = "Project-Harness Engineering with Claude and Claude Code"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def execute(cwd: Path, log: Path, *args: str) -> None:
    command = [sys.executable, *args]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    with log.open("w", encoding="utf-8") as handle:
        handle.write(f"Working directory: {cwd}\nCommand: {shlex.join(command)}\n\n")
        handle.flush()
        # stdout and stderr share a log, so failures and the pytest system path
        # stay together. Credential values are never printed by this runner.
        with subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                              errors="replace") as process:
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                handle.write(line)
                handle.flush()
            returncode = process.wait()
        handle.write(f"\nExit code: {returncode}\n")
    if returncode:
        raise RuntimeError(f"Command failed (exit {returncode}); see {log}")


def test_suite(system: int, cwd: Path, dest: Path, *, initial: bool = False) -> dict:
    stem = "tests-before-run" if initial else "tests"
    xml_path = dest / f"{stem}.xml"
    execute(cwd, dest / f"{stem}.log", "-m", "pytest", "tests/", "-v", "--color=no",
            f"--junitxml={xml_path}", f"--basetemp={dest / (stem + '-tmp')}")
    cases = list(ET.parse(xml_path).getroot().iter("testcase"))
    counts = {
        "collected": len(cases),
        "skipped": sum(c.find("skipped") is not None for c in cases),
        "failed": sum(c.find("failure") is not None or c.find("error") is not None for c in cases),
    }
    counts["passed"] = counts["collected"] - counts["skipped"] - counts["failed"]
    write_json(dest / f"{stem}-counts.json", counts)
    if counts["collected"] != EXPECTED_TESTS[system] or counts["failed"]:
        raise RuntimeError(f"Unexpected test results for system {system}: {counts}")
    if counts["skipped"] and not (initial and system == 2 and counts["skipped"] == 2):
        raise RuntimeError(f"Final evidence cannot contain skipped tests: {counts}")
    return counts


def collect_new_run(cwd: Path, dest: Path, module: str, extra: list[str] | None = None) -> Path:
    runs = cwd / "runs"
    before = set(runs.iterdir()) if runs.exists() else set()
    try:
        execute(cwd, dest / "run.log", "-m", module, "--all", *(extra or []))
    finally:
        after = set(runs.iterdir()) if runs.exists() else set()
        new = sorted(p for p in after - before if p.is_dir())
        for path in new:
            shutil.copytree(path, dest / "runs" / path.name)
    if len(new) != 1:
        raise RuntimeError(f"Expected one new run directory; found {len(new)}. See {dest}")
    return dest / "runs" / new[0].name


def claims_evidence(cwd: Path, dest: Path) -> dict:
    run = collect_new_run(cwd, dest, "claims_intake.run")
    expected = {json.loads(p.read_text(encoding="utf-8"))["claim_id"]
                for p in (cwd / "fixtures" / "claims").glob("claim_*.json")}
    decisions = []
    for path in list((run / "queues").glob("*.jsonl")) + [run / "escalations.jsonl"]:
        if path.exists():
            decisions.extend(read_jsonl(path))
    ids = [row["claim_id"] for row in decisions]
    if set(ids) != expected or len(ids) != len(expected):
        raise RuntimeError("Each fixture must have exactly one persisted routing or escalation decision")
    sequences = {p.stem: [row["stop_reason"] for row in read_jsonl(p)]
                 for p in (run / "traces").glob("*.jsonl")}
    if set(sequences) != expected or not all(s and s[-1] == "end_turn" for s in sequences.values()):
        raise RuntimeError("Missing trace or claim that did not finish on end_turn")
    if not any("tool_use" in s for s in sequences.values()):
        raise RuntimeError("No tool_use sequence captured")
    if not (run / "summary.md").exists():
        raise RuntimeError("Claims summary is missing")
    return {"run_id": run.name, "fixtures": len(expected), "terminal_decisions": len(ids),
            "stop_reason_sequences": sequences}


def context_evidence(cwd: Path, dest: Path) -> dict:
    run = collect_new_run(cwd, dest, "retail_context.run")
    budget = json.loads((run / "budget.json").read_text(encoding="utf-8"))
    full, control = read_jsonl(run / "eval.jsonl"), read_jsonl(run / "eval_control.jsonl")
    full_by_id = {row["question_id"]: row["passed"] for row in full}
    regressions = [row["question_id"] for row in control
                   if full_by_id.get(row["question_id"]) and not row["passed"]]
    metrics = {"run_id": run.name, "baseline_tokens": budget["baseline_tokens"],
               "assembled_tokens": budget["assembled_tokens"], "reduction_pct": budget["reduction_pct"],
               "evaluation_passes": sum(row["passed"] for row in full),
               "evaluation_total": len(full), "regressed_questions": regressions}
    write_json(dest / "context-metrics.json", metrics)
    if (budget["baseline_tokens"] <= 0 or
            budget["assembled_tokens"] > budget["baseline_tokens"] / 2 or
            len(full) != 6 or metrics["evaluation_passes"] < 5 or not regressions):
        raise RuntimeError(f"Context run did not meet every rubric threshold: {metrics}")
    return metrics


SHIFT_SETUP = '''
import json, sys
from pathlib import Path
from shift_monitor.warm import WarmStore
from shift_monitor.pipeline import build_rich_prompt, gather_new_defects
from shift_monitor.state import HotState
from shift_monitor.client import AnthropicClaudeClient
dest, since = Path(sys.argv[1]), sys.argv[2]
warm = WarmStore(dest / 'warm.sqlite')
warm.initialize()
warm.insert_many(json.loads(Path('fixtures/defects.json').read_text()))
hot = HotState(recent_defect_hashes=[], current_shift_summary='(no prior shift)',
               active_alerts=[], threshold_statuses={})
hot.write_atomic(dest / 'hot_state.json')
rows = gather_new_defects(warm, since, limit=50)
metrics = {'since': since, 'warm_total': warm.count(), 'sql_slice_count': len(rows),
           'configured_live_model': AnthropicClaudeClient().model,
           'query': 'SELECT * FROM defects WHERE ts > ? ORDER BY ts DESC LIMIT ?',
           'parameters': [since, 50], 'query_plan': warm.explain_defects_since(since, limit=50),
           'timestamp_index_present': warm.has_index_on('defects', ('ts',)),
           'returned_ids': [r['id'] for r in rows]}
(dest / 'sql-evidence.json').write_text(json.dumps(metrics, indent=2) + '\\n')
(dest / 'prompt.md').write_text(build_rich_prompt('quality engineer', hot, rows))
print(json.dumps(metrics, indent=2))
assert 0 < len(rows) < warm.count(), 'SQL query must select a nonempty proper subset'
assert metrics['timestamp_index_present'], 'Timestamp index is missing'
'''


SHIFT_ISOLATION = '''
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
from shift_monitor.fork import fork_for_hypothesis
from shift_monitor.scratchpad import Scratchpad, ScratchpadEntry
from shift_monitor.state import HotState, HOT_STATE_BYTE_BUDGET
dest = Path(sys.argv[1])
base = dest / 'hot_state.json'
before = base.read_bytes()
main_before = (dest / 'shift_scratchpad.jsonl').read_bytes()
paths = []
for label in ('maya-lot-check', 'arjun-station-check'):
    folder = fork_for_hypothesis(base, label, dest / 'forks')
    path = folder / 'shift_scratchpad.jsonl'
    Scratchpad(path).append(ScratchpadEntry(
        hypothesis_id=label, evidence='Deterministic fork-isolation demonstration.',
        conclusion='Investigation pending; this marker is not a model or causal finding.',
        ts=datetime.now(timezone.utc)))
    HotState.from_path(folder / 'hot_state.json').model_copy(
        update={'current_shift_summary': label}).write_atomic(folder / 'hot_state.json')
    paths.append(path)
assert base.read_bytes() == before
assert (dest / 'shift_scratchpad.jsonl').read_bytes() == main_before
assert all(len(Scratchpad(p).read()) == 1 for p in paths)
assert len({Scratchpad(p).read()[0].hypothesis_id for p in paths}) == 2
metrics = {'hot_state_bytes': len(before), 'budget_bytes': HOT_STATE_BYTE_BUDGET,
           'base_sha256_before': hashlib.sha256(before).hexdigest(),
           'base_sha256_after': hashlib.sha256(base.read_bytes()).hexdigest(),
           'main_scratchpad_unchanged': True, 'fork_scratchpads_isolated': True,
           'note': 'Maya and Arjun are demonstration labels, not real reviewers. No model investigations run.'}
(dest / 'state-and-isolation.json').write_text(json.dumps(metrics, indent=2) + '\\n')
print(json.dumps(metrics, indent=2))
assert len(before) <= HOT_STATE_BYTE_BUDGET
'''


def shift_evidence(cwd: Path, dest: Path, *, offline: bool, since: str) -> dict:
    execute(cwd, dest / "sql.log", "-c", SHIFT_SETUP, str(dest), since)
    args = ["-m", "shift_monitor", "run-shift", "--shift", "C", "--since", since,
            "--warm-db", str(dest / "warm.sqlite"), "--hot-state", str(dest / "hot_state.json"),
            "--scratchpad", str(dest / "shift_scratchpad.jsonl")]
    if offline:
        args += ["--recorded-response", "fixtures/recorded_responses/shift_C_2026-04-30.json"]
        shutil.copy2(cwd / args[-1], dest / "recorded-response.json")
    execute(cwd, dest / "run.log", *args)
    execute(cwd, dest / "isolation.log", "-c", SHIFT_ISOLATION, str(dest))
    return {"mode": "recorded response" if offline else "live API",
            **json.loads((dest / "sql-evidence.json").read_text()),
            **json.loads((dest / "state-and-isolation.json").read_text())}


def source_evidence(system: int, cwd: Path, dest: Path) -> None:
    # Small source snapshots let brief citations travel with the evidence.
    package = {1: "claims_intake", 2: "retail_context", 3: "ecommerce_team_config", 4: "shift_monitor"}[system]
    shutil.copytree(cwd / package, dest / "source" / package,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if system == 3:
        shutil.copy2(cwd / "CLAUDE.md", dest / "source" / "CLAUDE.md")
        shutil.copytree(cwd / ".claude", dest / "source" / ".claude")
        shutil.copytree(cwd / "docs", dest / "source" / "docs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="New evidence directory; must not already exist")
    parser.add_argument("--systems", nargs="+", type=int, choices=range(1, 5), default=[1, 2, 3, 4])
    parser.add_argument("--offline", action="store_true", help="Partial check: skip live runs 1/2, replay 4")
    parser.add_argument("--allow-other-python", action="store_true", help="Local checks only; VM needs 3.13")
    parser.add_argument("--since", default="2026-04-01T00:00:00Z", help="Fixed cutoff for historical fixture replay")
    args = parser.parse_args()
    repo = args.repo.resolve()
    systems = list(dict.fromkeys(args.systems))
    if sys.version_info[:2] != (3, 13) and not args.allow_other_python:
        parser.error("Activate /voc/data/py313-venv/bin/activate first (expected Python 3.13)")
    for system in systems:
        if not (repo / SOLUTION_PATHS[system]).is_dir():
            parser.error(f"Solution not found: {repo / SOLUTION_PATHS[system]}")
    if not args.offline and any(s in systems for s in (1, 2, 4)):
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            parser.error("ANTHROPIC_API_KEY is missing. Run on the provided VM, or use --offline for partial checks")
        if key.startswith("voc-") and not os.environ.get("ANTHROPIC_BASE_URL"):
            parser.error("Vocareum credentials require the VM-provided ANTHROPIC_BASE_URL")
    dependencies = {"pytest", "pydantic", "typing_extensions"}
    if 1 in systems or 2 in systems or (4 in systems and not args.offline):
        dependencies.add("anthropic")
    if 3 in systems:
        dependencies.update(("pathspec", "yaml"))
    missing = sorted(m for m in dependencies if importlib.util.find_spec(m) is None)
    if missing:
        parser.error(f"Missing dependencies: {', '.join(missing)}. Use the supplied VM environment; no pip installs needed there")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    output = (args.output or repo / "capstone-output" / stamp).resolve()
    output.mkdir(parents=True, exist_ok=False)
    summary = {"started_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
               "platform": platform.platform(), "api_key_present": bool(os.environ.get("ANTHROPIC_API_KEY")),
               "base_url_present": bool(os.environ.get("ANTHROPIC_BASE_URL")),
               "offline": args.offline, "systems": {}, "errors": []}
    shutil.copy2(repo / CAPSTONE / "reflection-brief-template.md", output / "reflection-brief-template.md")
    for system in systems:
        dest = output / FOLDERS[system]
        dest.mkdir()
        cwd = repo / SOLUTION_PATHS[system]
        print(f"\n--- System {system}: {cwd} ---", flush=True)
        try:
            source_evidence(system, cwd, dest)
            counts = test_suite(system, cwd, dest, initial=(system == 2))
            if system in (1, 2) and args.offline:
                result = {"status": "INCOMPLETE: live API run not performed", "tests": counts}
            else:
                if system == 1:
                    metrics = claims_evidence(cwd, dest)
                elif system == 2:
                    # Final tests read the newly generated context and budget.
                    try:
                        metrics = context_evidence(cwd, dest)
                    finally:
                        counts = test_suite(system, cwd, dest)
                elif system == 3:
                    execute(cwd, dest / "validator.log", "-m", "ecommerce_team_config", ".")
                    if "OK" not in (dest / "validator.log").read_text().splitlines():
                        raise RuntimeError("Validator did not print OK")
                    metrics = {"validator": "OK", "exit_code": 0}
                else:
                    metrics = shift_evidence(cwd, dest, offline=args.offline, since=args.since)
                result = {"status": "evidence checks passed", "tests": counts, "metrics": metrics}
            summary["systems"][str(system)] = result
        except Exception as exc:
            message = f"System {system}: {type(exc).__name__}: {exc}"
            print(message, file=sys.stderr, flush=True)
            summary["errors"].append(message)
            summary["systems"][str(system)] = {"status": "FAILED", "error": str(exc)}
        write_json(output / "verification-summary.json", summary)
    complete = not summary["errors"] and not args.offline and set(systems) == {1, 2, 3, 4}
    summary["all_required_evidence_checks_passed"] = complete
    summary["reflection_status"] = "NOT COMPLETED: fill all 20 answers using these artifacts"
    write_json(output / "verification-summary.json", summary)
    (output / "READ-FIRST.md").write_text(
        "# Capstone evidence\n\n"
        f"Evidence checks: {'all four systems passed' if complete else 'PARTIAL OR FAILED - inspect verification-summary.json'}.\n\n"
        "The reflection template is still blank. This folder is not a finished submission until all 20 answers cite real artifacts.\n\n"
        "System 4 uses a historical fixture cutoff, not the current date. Any recorded response is explicitly labelled; "
        "it demonstrates orchestration mechanics and is not a fresh model analysis of the SQL slice. "
        "The two fork scratchpads are deterministic isolation demonstrations, not model investigations.\n",
        encoding="utf-8")
    archive = shutil.make_archive(str(output) + "-evidence", "zip", root_dir=output.parent, base_dir=output.name)
    print(f"\nEvidence folder: {output}\nEvidence archive: {archive}")
    print("Next: complete the 20-answer reflection from actual results, then create the final submission ZIP.")
    return 0 if complete else (1 if summary["errors"] else 2)


if __name__ == "__main__":
    raise SystemExit(main())
