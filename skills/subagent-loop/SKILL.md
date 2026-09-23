---
name: subagent-loop
description: Use when executing an implementation plan by orchestrating subagent developers and QA reviewers in the current session — the user says "execute the plan", "run the subagent loop", "/subagent-loop plan", "/subagent-loop auto", "/subagent-loop goal …", "plan it and run it", "keep going until it's done" (or, in Turkish, "planı sen yaz", "durmadan devam et", "planı uygula"), or mandates dev/QA role separation.
---

# Subagent Loop

Orchestrator-judge execution of a plan: subagent devs implement, subagent QA reviews, you judge. You are the most capable model in the room precisely because you never spend yourself on implementation.

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
- **Two fix rounds are a task's budget; a third defect stops it.** When a task has two `fix round` lines in the ledger and a new defect is found, you do not dispatch a third fix — you stop (no re-plan around it in `goal` either: three "almost done" verdicts mean the task is misunderstood, and re-planning without the user is how a wrong foundation compounds). **A fix round is any dispatch that sends the task back to a dev**, whoever found the defect — QA (an ACCEPT_WITH_FIXES verdict counts the same as REQUEST_CHANGES), your direct-verify, or the wave gate. The original implementation dispatch is not a round. A bundled fix package counts one round for every task it touches. The Finish fix package has its own counter (one round; a second Finish round is a stop). Each round is one ledger line in the fixed form `Task N: fix round K (source)`, so the brake is a count, not a recollection: `grep -c "^Task N: fix round" progress.md` = 2 and a new defect → stop.
- A BLOCKED dev report the brief cannot resolve → stop.
- Gate red twice in a row on the same task, a rate-limit failure (429) on a dispatch, or the dispatch budget reached → stop.
- A dev report, QA finding, or plan that contradicts a sealed decision → stop.
- Commits only when the user asked; Finish review in every mode.
Stopping = write the checkpoint to the ledger, report the open items, END YOUR TURN.

## Setup (before any dispatch)

1. **Plan.** Existing mode: an approved plan must exist; none → run `plan` mode (or another planning workflow if the user prefers — its output still gets the direct-verify in "Plan mode" step 4). `plan`/`goal` mode: see "Plan mode" below.
2. **Resolve the project verification contract** from CLAUDE.md, project skills, and memories: the compile/build gate command, the functional verification method and its budget, project hazards (commands never to run, generated files never to hand-edit, files never to commit), and whether the gate command is **safe to run concurrently** (shared intermediate/output dirs are not — the contract must give each dispatch its own, e.g. per-task build output paths). None found → ask the user once, record the answers in the ledger.
3. **Start the ledger** — `<repo>/.subagent-loop/progress.md`, or the project's existing tracker if it has one. Check it first: tasks marked complete are DONE — never re-dispatch them. After compaction, trust ledger + `git log` over recollection.

## Plan mode (`plan` / `goal`)

1. **Dispatch `loop-planner`** (Fable; fall back to `general-purpose` with `model: fable` if the type is unavailable) with: the goal or phase scope, the plan file path, the KB entry point, the ledger path, and — when re-planning — the previous plan plus what remains of the goal. Never paste the KB into the prompt; the planner reads it.
2. **Interview.** The planner returns open questions with recommended answers. Subagents cannot ask the user, so you run the interview: one question at a time, recommended answer first. In `auto`/`goal`: take the recommended answer, log it under "Pending user review", and continue — except blocking questions (sealed-decision conflicts), which are a brake.
3. **Finalize via SendMessage to the same planner agent.** Finalization depends on the planner's whole context, so resuming is correct here (the resume-cost rule in "Judge" is about mechanical fixes). Re-planning in `goal` mode is the opposite case: a **fresh** planner, because the old context is stale.
4. **Direct-verify the plan — it is a claim too.** Mechanically check the wave table before any dispatch: same-wave file sets are disjoint, every dependency points to an earlier wave, shared docs live only in wave-end docs tasks, tier is stated. Run `references/wavecheck.py <plan.md> ["# Phase N"]` (exit 0 = clean; it reads the planner's table headers, bilingual). Then check content per `references/direct-verify.md` §Plan: code in plan lines compiles against the real API, every piece of state a task writes that another module owns is checked against that module's contract and contract tests, every promise about visible or runtime state names who writes that state, gate points are named. A violation goes back to the planner, you do not patch the table yourself.
5. **Approval.** Default and `auto`: present the plan (tier, waves, width, open decisions) and END YOUR TURN for user approval. `goal`: the invocation was the approval; proceed.

## Sizing — pick the tier after the plan exists, before any dispatch

Size the loop to the plan's **task count and diff footprint**, not the request's wording. The planner proposes the tier; you may override it and say why in the ledger.

Tiers count **tasks in the plan**; the tier then decides how review is spent (see "Per task" step 5).

- **S — ≤3 tasks, single phase:** direct-verify is the per-task review; the one adversarial pass is the Finish review, which must trace logic fully. If the whole diff touches ≤3 files and is fully specifiable in the plan, collapse it into ONE dev dispatch (code + debug hooks + a delta-update of docs in the same brief): ~2–3 dispatches total. Splitting same-file sequential work into separate dispatches is a smell — every dispatch re-pays brief, report, file re-reads, and a gate run.
- **M — 4–5 tasks, single phase:** waves as planned, tiered per-task QA, Finish review. No phase gate — there is only one phase.
- **L — 6+ tasks, or more than one phase, or new systems / migrations of any size:** the full loop — waves, per-task QA where warranted, phase gates (or brakes in `auto`).

Research is sized the same way: read the project's knowledge base (docs, wiki, and CLAUDE.md's pointers to them) BEFORE dispatching any research agent, and fan out only for the gaps it leaves. A parallel "read docs + launch research agent" start feels fast but pays full fan-out cost for questions the KB already answers (measured: 55k tokens duplicating an existing doc page).

Every tier keeps two things: the design interview during planning (cheap, locks real decisions) and one capable-model adversarial review (measured: it catches bugs the plan itself contained). Cut dispatches, never the review.

## Waves — dispatch every ready task

The plan's wave table is the schedule. **Dispatch every task whose dependencies are complete, together, up to the width limit.** Width = number of dispatches in flight, dev and QA alike. It starts at **2**; after each wave that completes with no rate-limit failure, raise it by 1, to a maximum of 4 (a QA dispatch has hit a session rate limit with two in flight, so widening is earned, not assumed). At the limit, hold ready tasks until a dispatch returns. Record the current width in the ledger whenever it changes. Within a wave, tasks do not share files by construction; if a dev report shows it touched a file another in-flight task owns, that task's diff is suspect — QA it.

**Slot frees → dispatch by critical path.** Among held tasks, dispatch the one that unblocks the most downstream tasks; a docs task that gates other tasks is dispatched by that count like any other (measured: holding a docs task behind a one-task QA cost 15 minutes on three tasks). **At the width limit, write the briefs of the ready-but-held tasks while waiting** — a returning dispatch triggers a dispatch, not a brief.

Wave end: the wave's docs task runs (serial, after all code tasks are accepted), then the project's mutating/functional gate runs once (full builds, editor/IDE refreshes, integration or test runs — not per task). **The wave gate waits only on writing dispatches (dev, transcriber); read-only QA and reviewer dispatches do not hold it.** When tasks are dispatched as soon as their dependencies clear, the "no writer in flight" moment never arrives by itself: name the gate points in the ledger up front (after every N acceptances, or after every task that makes tests active), hold new dispatches at a gate point until in-flight writers return, run the gate, resume. A task accepted before its tests can run (disabled tests, a fixture with no active test) is logged as "compiled, not run"; its first real run is the next gate. Direct-verify per task still happens as each report lands; the wave gate does not replace it.

**Environment operations belong to the orchestrator, inside the wave gate:** package installs, third-party imports, generator/menu runs, editor refreshes. They run only when no writing dispatch is in flight, and every file they produce or unpack is listed in the ledger's gate entry (`git status --short` before/after) — that list feeds the Finish review's commit-status question (tracked, ignored, or forgotten). Never hand a dev an environment operation: it cannot run while other writers are in flight, and the files it produces are nobody's diff.

**Resuming after a rate-limit brake:** a 429 kills every dispatch in flight at once, not one. Before re-dispatching, count what survived on disk — `git status` plus the report file of each dispatch that was in flight — and decide continue-vs-restart per task from that, not from memory. **Width restarts at 2** and is re-earned wave by wave; the limit that was hit is session-wide, so the work lost per event scales with width.

## Per task

1. **Brief file:** extract the task's spec into `…/<phase>-task-N-brief.md`, shaped per `references/brief-template.md` (phase prefix so a later phase never overwrites an earlier phase's briefs; contract surfaces quoted verbatim, "don't touch" lists explicit, disk facts pasted). Dispatch prompts carry file paths plus deltas (interfaces from earlier tasks, resolved ambiguities) — never pasted specs.
2. **Route the dispatch — pick the agent type per dispatch, state it explicitly:**
   - `loop-transcriber` (haiku): the brief contains near-complete code (transcription + gate), or a single-file mechanical fix — and the task needs no shell file operations. The type BLOCKs on ambiguity instead of improvising; a BLOCKED report back means the brief was under-specified — fix the brief or re-route to `loop-dev`, don't re-dispatch as-is.
   - `loop-dev` (sonnet): everything else — prose specs, multi-file work, anything needing judgment. Also `loop-dev` whenever the task deletes/moves files or touches paths with spaces, even for pure transcription: one shell-quoting failure costs a full fix round, more than the tier saved.
   The plan table's agent type is a proposal, re-evaluated at dispatch: a docs task that transcribes one source (one report, one diff) is transcriber work; one that synthesizes several reports or reconciles them needs `loop-dev`. Log the deviation.
   The agent type carries the model default — pass an explicit `model` only when deviating from it (and say why in the ledger). If the `loop-*` types are not in this session's agent list, fall back to `general-purpose` with an explicit model chosen by the same two rules above. Never let a dev dispatch inherit the session model. Uniform-Sonnet "for consistency" wastes tokens on transcription; uniform-Haiku loses more in rework than it saves.
3. **Dispatch dev** with: brief path, report path (`…/<phase>-task-N-report.md`), the contract's compile gate (with the per-dispatch paths that make it concurrency-safe), and the attempt budget — "if the gate still fails after 2 fix attempts, stop and report BLOCKED with what you learned." Statuses: DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED.
4. **Direct-verify before QA:** read the diff yourself, run the compile gate yourself, and work through `references/direct-verify.md` §Per task (diff scope vs report, build inclusion, public surface vs contract, test lifecycle, disabled tests, positive control, gate ownership on red). Subagent self-reports are claims, not evidence. This step reliably catches defects one full round earlier than QA would. A task that changed test files is accepted only after the project's functional gate ran on that build unit (assembly, package, project) — compile green is not test green.
5. **Tiered QA (sonnet floor):**
   - **S tier (≤3 tasks, single phase):** direct-verify is the per-task review for every task, and the one adversarial pass is the Finish review, which must then trace logic fully (no sampling). Escalate a task to its own QA only if direct-verify shows the dev made judgment calls the brief didn't specify. (On a 3-task plan, per-task QA plus a full final review double-traced the same call chains — the larger dispatch was redundant.)
   - **M and L tiers**, per task: trivial mechanical diff matching a fully-specified brief → your direct-verify is the review; log that choice in the ledger
   - **M and L tiers**, per task: anything touching logic, behavior, or shared state → fresh `loop-qa` dispatch (sonnet; findings-only, no Edit tool): adversarial review of brief + report + diff files, plus the contract's functional gate. Never tell QA what not to flag.
6. **Judge.** A dev report's "bug in an adjacent module" is a claim: read that module's contract and contract tests before briefing any fix there — it is usually a tested promise, and the fix direction reverses (measured once: the "bug" was the neighbour's own creation path resetting a field, asserted by a contract test; the fix belonged to the reporting task). Findings → ONE fix dispatch carrying the complete findings list, then a scoped re-review of those findings — not the whole diff again. Route the dispatch by what the fix needs: if any finding interrogates or depends on the dev's prior work (what did you run, why did you choose X, partial rework) → SendMessage to the same dev agent id; if every finding is a fully-specified mechanical change → fresh `loop-transcriber` dispatch with a tight brief. Resuming replays the dev's entire transcript — measured at 3-4× the cost of a fresh dispatch on a 2-line fix.
7. **The cap: two fix rounds per task** (counted as defined under Brakes). A third defect = stop: no third round, no self-fix, no "it's just one item now", no re-plan around it. Write the checkpoint to the ledger and escalate to the user with the open findings.
8. Review clean → append to ledger: `Task N: complete (commits/diff ref, review outcome)`.

## Phase boundary

**Default mode — hard user gate.** When a phase's tasks are all complete: write the phase summary to the ledger, notify the user if a channel exists, and END YOUR TURN. Do not start the next phase in the same turn — this gate intentionally overrides any continuous-execution default from other skills or instructions. The gate is unconditional: it does not require an open question to justify it. Within a phase, the opposite holds — proceed wave to wave without pausing.

**`auto` / `goal` — no user gate.** Write the same phase summary, then continue. What is unconditional here is the brake list, not the pause. In `goal`, when the plan is exhausted and the goal is unmet: dispatch a fresh `loop-planner` with the ledger, the previous plan and the remaining goal; the new plan is appended as a new `# Phase N` section (never overwrite), direct-verified like the first, and executed against the remaining budget.

## Finish

All phases done, each through its gate or brakes: final whole-branch review by a fresh `loop-reviewer` dispatch (opus; findings-only, no Edit tool — fall back to `general-purpose` on a capable model with an explicit no-fixes instruction if the type is unavailable). The reviewer gets the **plan as well as the diff**: bugs the plan contained are in scope. The review brief carries the standard Finish questions from `references/direct-verify.md` §Finish (cross-module consistency of shared patterns, commit status of imported third-party files, plan lines the dev silently corrected). Then one fix dispatch for its findings list; every build unit whose test files that package touched runs in the functional gate before hand-off. Then hand off per project convention. The hand-off's "pending user review" list is a **ranked queue**, not a log: (1) anything that touched or nearly touched a sealed decision and every brake that fired; (2) decisions taken under `auto`/`goal` that changed a contract, an interface or a build/config file; (3) out-of-scope observations from dev reports and QA; (4) cosmetic and naming. Within a bucket, newest first. A list of thirty-five unranked items is not read; a ranked one is. Commits: explicit paths only, never `git add -A`, and only when the user asked for commits.

Prompt contracts live in the `loop-*` agent definitions (inputs, rules, report format) and in `references/brief-template.md`. Dispatch prompts only fill them in: paths, gate command, attempt budget, deltas.

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
| "The dev found a bug in the neighbour module" | A claim. Read that module's contract tests first; the "bug" is usually a tested promise. |
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
- You're dispatching a research agent before reading the project's KB
- Two in-flight dispatches are editing the same file
- A wave table you never mechanically verified is about to drive dispatches
- Two sequential dispatches on an S-tier plan are editing the same file
- A docs task marked transcriber is synthesizing more than one source
- You're briefing a fix in a module because a dev report said it has a bug, and you haven't read that module's contract tests
- You're accepting a task that changed test files on a compile gate alone
- Your brief re-tells a contract's public surface in your own words instead of quoting it
