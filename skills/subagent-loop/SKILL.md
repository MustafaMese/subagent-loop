---
name: subagent-loop
description: Use when executing an implementation plan by orchestrating subagent developers and QA reviewers in the current session — the user says "execute the plan", "run the subagent loop", "/subagent-loop plan", "/subagent-loop auto", "/subagent-loop goal …", "plan it and run it", "keep going until it's done" (or, in Turkish, "planı sen yaz", "durmadan devam et", "planı uygula"), or mandates dev/QA role separation.
---

# Subagent Loop

Orchestrator-judge execution of a plan: subagent devs implement, subagent QA reviews, a subagent judge reads the evidence, you decide. You are the most capable model in the room precisely because you never spend yourself on implementation.

**Roles are load-bearing. The orchestrator NEVER edits project files.** Not a one-line fix, not a null check QA already wrote out verbatim, not "just this once to save a cycle." An orchestrator edit is unreviewed code written by the judge — it pollutes your context and disqualifies your verdicts. Every change, however small, is authored by a dev dispatch. The plan is no exception: in `plan`/`goal` mode it is authored by `loop-planner`, not by you. Running the project's own tools is not editing: the gate, generators, importers, menu commands and package installs are **environment operations**, and those are yours — see "Waves", wave end.

## Modes — three independent axes

Invocation: `/subagent-loop [plan] [auto] [goal "<end condition>" budget=<N dispatches>]`. Record the active modes in the ledger header.

| Axis | Default | Switch | Meaning |
|---|---|---|---|
| Plan source | existing approved plan | `plan` | `loop-planner` (Fable) writes the plan as a wave table; interview + user approval before execution |
| Phase gate | hard user gate between phases | `auto` | no user gate; the brake list below replaces it |
| Stop condition | plan complete | `goal "…"` | implies `plan` + `auto`; when the plan is exhausted and the goal unmet, re-plan and continue until the goal, a brake, or the budget |

`goal` requires `budget=<N>`: total dispatch count across all waves and re-plans. No budget → ask once, do not start.

**Sealed decisions** are the ones the project records as final — a decision log, ADRs, fixed execution orders, published contracts. Everything else the plan and KB leave open is an *open* decision.

**`auto`/`goal` and any "don't invent decisions, ask first" rule:** the invocation *is* the asking. It covers open decisions (log them under "Pending user review" in the ledger and continue). It does **not** cover contradicting a sealed decision: that is a brake.

**Brakes — unconditional in every mode, they never soften because a gate was removed:**
- **Two fix rounds are a task's budget; a third defect stops it.** When a task has two `fix round` lines in the ledger and a new defect is found, you do not dispatch a third fix — you stop (no re-plan around it in `goal` either: three "almost done" verdicts mean the task is misunderstood, and re-planning without the user is how a wrong foundation compounds). **A fix round is any dispatch that sends the task back to a dev**, whoever found the defect — QA (an ACCEPT_WITH_FIXES verdict counts the same as REQUEST_CHANGES), the judge (a FIX verdict), your own check on a `DISAGREE` id, or the wave gate. The original implementation dispatch is not a round. A bundled fix package counts one round for every task it touches. The Finish fix package has its own counter (one round; a second Finish round is a stop). Each round is one ledger line in the fixed form `Task N: fix round K (source)`, so the brake is a count, not a recollection: `grep -c "^Task N: fix round" progress.md` = 2 and a new defect → stop.
- A BLOCKED dev report the brief cannot resolve → stop.
- Gate red twice in a row on the same task, a rate-limit failure (429) on a dispatch, or the dispatch budget reached → stop.
- **Known-flaky list.** The project contract may list known-flaky tests and transient environment errors, each with its exact symptom text. A listed failure with its listed symptom gets **one** rerun of the identical command; a second red, or the same test with a different symptom, is a real red and counts toward the brakes. A new intermittent failure enters the list only through a decision/backlog line — the gate owner does not re-decide "environmental" case by case.
- A dev report, QA finding, or plan that contradicts a sealed decision → stop.
- Commits only when the user asked; Finish review in every mode.
Stopping = write the checkpoint to the ledger, report the open items, END YOUR TURN.

## Setup (before any dispatch)

1. **Plan.** Existing mode: an approved plan must exist; none → run `plan` mode (or another planning workflow if the user prefers — its output still gets the direct-verify in "Plan mode" step 4). `plan`/`goal` mode: see "Plan mode" below.
2. **Resolve the project verification contract** from CLAUDE.md, project skills, and memories: the compile/build gate command, the functional verification method and its budget, project hazards (commands never to run, generated files never to hand-edit, files never to commit), and whether the gate command is **safe to run concurrently** (shared intermediate/output dirs are not — the contract must give each dispatch its own, e.g. per-task build output paths). None found → ask the user once, record the answers in the ledger.
3. **Start the ledger** — `<repo>/.subagent-loop/progress.md`, or the project's existing tracker if it has one. Check it first: tasks marked complete are DONE — never re-dispatch them. After compaction, trust ledger + `git log` over recollection.

## Plan mode (`plan` / `goal`)

Read `references/plan-time.md` when a plan is written, re-planned or first taken up in any mode, before its first dispatch: gather facts, planner dispatch, interview, finalize, direct-verify (wavecheck and the cut script's dry run), approval, and Sizing.

## Sizing — pick the tier after the plan exists, before any dispatch

In `references/plan-time.md` (Sizing), read with Plan mode. The tiers S / M / L decide review spend in "Per task" step 5.

## Waves — dispatch every ready task

The plan's wave table is the schedule. **Dispatch every task whose dependencies are complete, together, up to the width limit.** Width = number of dispatches in flight, dev and QA alike. It starts at **2**; after each wave that completes with no rate-limit failure, raise it by 1, to a maximum of 4 (a QA dispatch has hit a session rate limit with two in flight, so widening is earned, not assumed). At the limit, hold ready tasks until a dispatch returns. Record the current width in the ledger whenever it changes. Within a wave, tasks do not share files by construction; if a dev report shows it touched a file another in-flight task owns, that task's diff is suspect — QA it.

**Slot frees → dispatch by critical path.** Among held tasks, dispatch the one that unblocks the most downstream tasks; a docs task that gates other tasks is dispatched by that count like any other (measured: holding a docs task behind a one-task QA cost 15 minutes on three tasks). **At the width limit, write the briefs of the ready-but-held tasks while waiting** — a returning dispatch triggers a dispatch, not a brief.

Wave end: the wave's docs task runs (serial, after all code tasks are accepted), then the project's mutating/functional gate runs once (full builds, editor/IDE refreshes, integration or test runs — not per task). **The wave gate waits only on writing dispatches (dev, transcriber); read-only QA, judge and reviewer dispatches do not hold it.** When tasks are dispatched as soon as their dependencies clear, the "no writer in flight" moment never arrives by itself: name the gate points in the ledger up front (after every N acceptances, or after every task that makes tests active), hold new dispatches at a gate point until in-flight writers return, run the gate, resume. A task accepted before its tests can run (disabled tests, a fixture with no active test) is logged as "compiled, not run"; its first real run is the next gate. The per-task judge still runs as each report lands; the wave gate does not replace it. A task that compiles and registers a system (a scheduling table, a card/manifest entry) in two different waves leaves the intermediate wave's scene/build unrunnable: registration lands in the same wave as the system it registers, or the plan names the non-runnable intermediate state and who it's communicated to.

**Environment operations belong to the orchestrator, inside the wave gate:** package installs, third-party imports, generator/menu runs, editor refreshes. They run only when no writing dispatch is in flight, and every file they produce or unpack is listed in the ledger's gate entry (`git status --short` before/after) — that list feeds the Finish review's commit-status question (tracked, ignored, or forgotten). Start the gate's environment half as soon as writers return, while QA runs: a read-only QA/reviewer dispatch does not hold up menu runs, full builds, or refreshes, so the gate's functional half (the run that needs those artifacts) is ready the moment QA's findings land instead of queued behind them. Never hand a dev an environment operation: it cannot run while other writers are in flight, and the files it produces are nobody's diff.

**Resuming after a rate-limit brake:** a 429 kills every dispatch in flight at once, not one. Before re-dispatching, count what survived on disk — `git status` plus the report file of each dispatch that was in flight — and decide continue-vs-restart per task from that, not from memory. **Width restarts at 2** and is re-earned wave by wave; the limit that was hit is session-wide, so the work lost per event scales with width.

## Per task

Read `references/per-task.md` before the first task dispatch of a session and again after a context compaction: steps 1–8 (brief file — cut or written —, routing, dev dispatch, gate and judge, tiered QA, verdict handling, fix cap, completion line). "Step N" anywhere in this skill means that list.

## Phase boundary

**Default mode — hard user gate.** When a phase's tasks are all complete: write the phase summary to the ledger, notify the user if a channel exists, and END YOUR TURN. Do not start the next phase in the same turn — this gate intentionally overrides any continuous-execution default from other skills or instructions. The gate is unconditional: it does not require an open question to justify it. Within a phase, the opposite holds — proceed wave to wave without pausing.

**`auto` / `goal` — no user gate.** Write the same phase summary, then continue. What is unconditional here is the brake list, not the pause. In `goal`, when the plan is exhausted and the goal is unmet: dispatch a fresh `loop-planner` with the ledger, the previous plan and the remaining goal; the new plan is appended as a new `# Phase N` section (never overwrite), direct-verified like the first, and executed against the remaining budget.

Before that re-plan dispatch, re-read `references/plan-time.md` (also after a compaction): the planner dispatch carries the new phase's prefix and the path of `references/cutbriefs.py` as well.

## Finish

Read `references/finish.md` when all phases are done, each through its gate or brakes: whole-branch review, the Finish fix package, the brief's Checks table, the ranked hand-off queue. The Finish fix dispatch is routed per "Per task" steps 2 and 6.

## Every call — reading and prompt contracts

**Read discipline — your context is the loop's cost.** Every token in your window is re-sent on every later call: a 40k read early in a long session is paid hundreds of times. Read plans, drafts and ledgers by section (`grep -n`, then a line range), never a whole large file twice; a spilled tool result is read by range too. Jobs that need several large inputs at once — synthesising contract drafts, reconciling reports — are a dispatch, not a read. You read verdicts, findings summaries and gate output; diffs only on a `DISAGREE` id or a calibration spot-check.

Prompt contracts live in the `loop-*` agent definitions (inputs, rules, report format) and in `references/brief-template.md`. Dispatch prompts only fill them in: paths, gate command, attempt budget, deltas.

When this loop runs in one of several long-lived sessions that share a single-instance resource (an editor, a device), the outer layer — coordinator, resource lock, compile handshake, exit conditions, shared-index commit hygiene — is in `references/multi-session.md`. It sits above this loop; it changes nothing inside it.

## Rationalization table

| Excuse | Reality |
|---|---|
| "One-line fix — a dev dispatch is pure token burn" | A loop-transcriber fix dispatch costs less than this argument. Orchestrator edits are unreviewed and pollute the judge. |
| "I'll just fix the wave table myself" | The plan is authored by the planner and verified by you. Patching it makes you its author and no one its reviewer. |
| "This is about judgment, not ritual" | The role separation IS the judgment. A judge who authors changes has no reviewer. |
| "Plan approval covers the next phase too" (default mode) | Approval covered intent. The gate exists so the user inspects *reality* before more work builds on it. In `auto` the user chose to skip that inspection — and got the brake list instead, not nothing. |
| "Stopping only makes sense if there's a decision to make" (default mode) | The checkpoint IS the decision: the user decides whether reality matches intent. |
| "Pausing wastes time / context-reload tax" (default mode) | The ledger makes resume cheap. A wrong foundation compounds across every later phase. |
| "We're in goal mode, re-plan around the stuck task" | The third defect is a brake in every mode. Re-planning around a misunderstood task without the user is how a wrong foundation compounds. |
| "auto means I can decide this" | auto covers open decisions (log them). It does not cover overriding a sealed one. |
| "Run the tasks one at a time, it's safer" | Wave-mates have disjoint files by construction. Serial execution of a parallel plan pays the plan's cost and forfeits its gain. |
| "Keep models uniform for consistency" | Tier by task shape. Consistency of process ≠ uniformity of model. |
| "QA already wrote the exact fix" | Then the fix dispatch is trivially cheap — and still reviewed. |
| "QA said ACCEPT_WITH_FIXES, that's not a rejection" | The task went back to a dev. That is a fix round; log it and count it. |
| "More tasks = more rigor" | Rigor comes from the review, not the dispatch count. Merging same-file sequential tasks into one dispatch loses nothing. |
| "Width counts QA, so the gate waits for QA too" | Width limits rate. The gate waits only on writers; QA reads. |
| "Keep the pipe full, the gate can run when it's quiet" | The quiet moment never comes by itself. Name the gate point before it is needed. |
| "The dev found a bug in the neighbour module" | A claim. The verdict must cite that module's contract test; the "bug" is usually a tested promise. |
| "Haiku is cheap — let gatherers prepare the reading for devs, QA and the judge too" | Measured: re-reads across agents are ~4% of loop cost; devs and QA read the 1–2 files they edit or review, and a reviewer's value is its own pass. Gather for the planner only. |
| "Ask the gatherers how the module works" | A summary is an opinion the planner cannot check. Ask for locations and quotes; leave the understanding to the planner. |
| "I'll just skim the diff to double-check the judge" | That is the read the judge exists to save. Open code only for a `DISAGREE` id or a calibration spot-check. |
| "The compile gate is green, the test change is fine" | A compile gate cannot see teardown order or runtime exceptions. Run the test gate on that build unit. |

## Red flags — STOP

- You're about to Edit/Write a project file, or the plan file
- You're composing a third fix round for the same task (any mode)
- Default mode: you're starting phase N+1 in the same turn phase N finished
- `auto`/`goal`: you're continuing past a brake, or past the budget
- A dispatch prompt contains a pasted spec instead of a brief path
- A dispatch without an explicit `loop-*` agent type (or, when those types are unavailable, an explicit model)
- You're about to re-dispatch a task the ledger already marks complete
- You're resuming a dev's transcript for a fix a fresh loop-transcriber brief fully specifies
- You're reading a diff or a whole plan/draft file with no `DISAGREE` id, calibration spot-check or section reason
- You're dispatching a research agent before reading the project's KB
- A facts file is in a `loop-qa`, `loop-judge` or `loop-reviewer` dispatch, or a brief pastes a fact whose cited file changed since its commit
- Two in-flight dispatches are editing the same file
- A wave table you never mechanically verified is about to drive dispatches
- Two sequential dispatches on an S-tier plan are editing the same file
- A docs task marked transcriber is synthesizing more than one source
- You're briefing a fix in a module because a dev report said it has a bug, and you haven't read that module's contract tests
- You're accepting a task that changed test files on a compile gate alone
- Your brief re-tells a contract's public surface in your own words instead of quoting it
- You're dispatching a task and have not read `references/per-task.md` in this session (or since the last compaction)
- You're dispatching a planner or running Finish and have not read `references/plan-time.md` / `references/finish.md` since the last compaction
- You're writing a brief by hand for a plan the cut script accepts, or a Delta that retells the plan
