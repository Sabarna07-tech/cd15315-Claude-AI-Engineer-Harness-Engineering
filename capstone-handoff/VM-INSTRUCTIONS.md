# Harness Engineering capstone: run and submission guide

This is the four-system Python capstone in `cd15315-Claude-AI-Engineer-Harness-Engineering`.
The capstone instructions say to run the **completed final `solution/` directories**.
Do not implement the starter TODOs or modify the reference solutions.

Your work is to run the systems, collect real evidence, and explain their designs
in the supplied reflection template. Local API credentials are not needed to
prepare this handoff. Run the API-dependent work on the provided VM.

## What to submit

Submit the **completed reflection brief and four evidence folders**. A ZIP is a
convenient way to keep these together; the supplied instructions do not mandate
a particular upload format, so follow any format restriction shown by the classroom.

| Submission item | Required contents and success criteria |
| --- | --- |
| `reflection-brief-template.md` | Fill all 20 answers, plus name, date, model, OS/Python, and approximate API spend. Each answer needs a real artifact citation. Generally write 3–6 sentences per answer. Synthesis answers must connect at least two systems. |
| `system-1-agentic-loop/` | **30 passing tests**; the eight-claim run's `summary.md`, routing/escalation records, and traces. Every claim must end routed or escalated. Include a trace with `tool_use` turns followed by `end_turn`. |
| `system-2-context-strategy/` | **30 passing tests after the run**; `context.md`, `budget.json`, `eval.jsonl`, and `eval_control.jsonl`. Assembled tokens must be at most half the baseline, at least 5/6 full-context questions must pass, and at least one previously passing question must fail in the control. |
| `system-3-claude-config/` | **35 passing tests**; validator output `OK` with exit code 0; root `CLAUDE.md`, imported standards, path-scoped rules with YAML globs, `/review` command, and the skill with `context: fork` and read-only tools. Keep the `.claude` folder included. |
| `system-4-orchestration/` | **33 passing tests**; shift output; SQL query evidence showing the selected defects versus the warm-tier total; `hot_state.json` and its measured byte size; shift scratchpad. The implementation enforces a 5,120-byte hot-state limit. Include fork isolation evidence if available. |

The four final test logs should show **128 passed in total: 30 + 30 + 35 + 33**.
Each log must identify its system. Test logs alone are insufficient: include
the actual run artifacts and the completed brief.

The rubric does not ask you to submit the entire course repository. Source
snapshots relevant to the brief are included by the runner for convenient review.

## Run on the VM

1. Upload the `capstone-handoff` folder into the VM directory containing all four
   course projects and `Project-Harness Engineering with Claude and Claude Code`.
   According to the classroom instructions, that directory is
   `/voc/work/py3.13-exercises-and-project`.
2. Open the VM terminal and run these commands:

```bash
source /voc/data/py313-venv/bin/activate
python --version

SYSTEMS="/voc/work/py3.13-exercises-and-project"
cd "$SYSTEMS"

# Confirm credentials are present without displaying their values.
python -c "import os; print('key set:', bool(os.getenv('ANTHROPIC_API_KEY'))); print('base URL set:', bool(os.getenv('ANTHROPIC_BASE_URL')))"

# Collect the evidence. The default makes live API calls for systems 1, 2 and 4.
python capstone-handoff/run_capstone_vm.py --repo "$SYSTEMS"
```

Expected Python version: **3.13.x**. The VM already supplies dependencies,
`ANTHROPIC_API_KEY`, and `ANTHROPIC_BASE_URL`. Do not create a new environment,
install packages, or paste credentials into the project. The course estimates
roughly $1–$5 for a full run; actual usage varies.

If the VM uses a different directory, set `SYSTEMS` to the directory that
actually contains the four project folders. The runner checks all paths before
running and accepts `--repo` so it does not depend on its own upload location.

If a specific model is required or the environment default is unavailable,
set `CLAUDE_MODEL` to a model supported by the VM account before running.
Otherwise the reference solutions honor the VM's existing model configuration.

## What the runner does

- Uses each final solution as its working directory and captures stdout/stderr
  and exit codes. It does not edit reference source or fixtures.
- Runs all four test suites. System 2 may initially show 28 passed and 2 skipped;
  it runs that suite again after producing context artifacts and requires 30 passed.
- Runs systems 1 and 2 and copies each newly created run directory, including
  all traces, token budgets, and full/control evaluations.
- Runs the configuration validator and includes its config files, including `.claude`.
- Seeds a fresh SQLite store inside the evidence folder and runs system 4 against
  a **historical fixture window**, using the fixed cutoff `2026-04-01T00:00:00Z`.
  This avoids an empty query caused by the default "last eight hours" against
  older fixtures. It captures the actual query plan, selected IDs, warm-tier
  total, prompt, hot-state size, and scratchpad.
- Demonstrates fork isolation with independent state copies and scratchpads
  labelled `maya-lot-check` and `arjun-station-check`. These are demonstration
  labels, not claims that real people reviewed the system. The demonstration
  runs no model investigations and asserts no causal findings.
- Checks the rubric's measurable thresholds and writes
  `verification-summary.json`. Independent systems continue if one fails,
  so useful logs are retained.
- Copies the original blank reflection template and creates an evidence ZIP.
  **It does not fill the reflection or declare the submission finished.**

The output paths appear at the end, for example:

- Evidence directory: `capstone-output/<timestamp>-<id>/`
- Evidence archive: `capstone-output/<timestamp>-<id>-evidence.zip`

Open `verification-summary.json`. For a successful full run,
`all_required_evidence_checks_passed` must be `true`, with no errors.
Even then, the reflection must still be completed before submission.

Exit codes: `0` means all four evidence checks passed; `1` means a system failed;
`2` means a partial/offline run or a preflight argument/environment error.
Read the terminal message and summary to distinguish them. A failed or partial
run is archived for troubleshooting, not presented as a passing submission.

## Complete the reflection after the VM run

Use the copied template in the output folder. Keep the 20 questions and answer
them using the artifacts in the same folder. Use your actual name, such as
**Sabarna Saha**, and the date you completed the work.

| Questions | Evidence to consult |
| --- | --- |
| 1–4: agentic loop | `system-1-agentic-loop/runs/<run-id>/summary.md`, traces, queue/escalation files, `tests.log`, and `source/claims_intake/loop.py`, `tools.py`, `system_prompt.py` |
| 5–7: context strategy | `system-2-context-strategy/runs/<run-id>/budget.json`, `context.md`, `eval.jsonl`, `eval_control.jsonl`, and `context-metrics.json` |
| 8–10: Claude Code configuration | `system-3-claude-config/validator.log`, `tests.log`, `source/CLAUDE.md`, and `source/.claude/` |
| 11–13: orchestration | `system-4-orchestration/sql-evidence.json`, `run.log`, `hot_state.json`, `state-and-isolation.json`, and `source/shift_monitor/recovery.py` |
| 14–18: synthesis | Cite named files/artifacts from at least two systems. Use the actual context token counts and hot-state byte size. Explain one guarantee shown by tests beyond a single successful run. |
| 19–20: assessment | Real failures, checks, or limitations you observed, and one change supported by that evidence. If nothing failed, describe what you checked rather than inventing a problem. |

Write in clear, concrete language. For example, identify the particular claim,
trace sequence, question ID, or byte count before explaining its significance.
Do not replace fixture names or edit run logs to make them look more personal.
A useful optional addition is a short application to wagon damage monitoring:
how tiered state and SQL filtering could support repeated video inspections.

Approximate API cost should distinguish reported estimates from measured spend.
System 1 supplies cost estimates in its run summary; the other systems do not
necessarily provide a complete bill. Do not present a guessed total as measured.

The config validator prints a single `OK`, not a detailed scope report. For the
template's scope question, cite both that successful validator run and the scope
documentation in the captured `source/CLAUDE.md`.

After the reflection is complete, package the final folder. Replace the example
directory below with the actual output directory printed by the runner:

```bash
cd "$SYSTEMS"
EVIDENCE="capstone-output/<timestamp>-<id>"
python -c "import shutil, sys; from pathlib import Path; p=Path(sys.argv[1]).resolve(); print(shutil.make_archive(str(p)+'-submission', 'zip', root_dir=p.parent, base_dir=p.name))" "$EVIDENCE"
deactivate
```

Submit the resulting `*-submission.zip` if the classroom accepts ZIP files.
The earlier `*-evidence.zip` was created **before** you completed the reflection,
so do not accidentally submit that version.

If this conversation is being used to finish the brief, return the VM-generated
evidence ZIP. Its real numbers and traces are needed to complete the answers.

## Optional partial checks

On the VM, this runs tests and system 3 without live calls and replays system 4:

```bash
python capstone-handoff/run_capstone_vm.py --repo "$SYSTEMS" --offline
```

It skips the live runs for systems 1 and 2 and explicitly reports incomplete
evidence. It is not the final submission. The recorded system-4 response is
a supplied scenario replay; it is not a fresh model analysis of the chosen
historical SQL slice. Use the default live run for a fully evidence-grounded report.

For local checking on another Python version, `--allow-other-python` is available.
This option does not replace the classroom's requirement to run on Python 3.13.

## Differences from older README examples

- Follow the classroom's shared Python **3.13** environment instructions on the VM,
  rather than the generic local-venv installation instructions.
- The older capstone README mentions 29 claims tests; the final solution/rubric
  require **30**. The runner checks 30.
- Report the token counts in your own `budget.json`. README baseline estimates
  differ and are not evidence of your run.
- System 4's valid CLI is `python -m shift_monitor run-shift --shift C ...`.
  Do not add a positional `.` after `run-shift`.
- Keep the explicit historical date filter when running fixed defect fixtures.

An optional second-model comparison or deeper model-driven fork investigation
can strengthen the submission, but neither replaces the required evidence.
