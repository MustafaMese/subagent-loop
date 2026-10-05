# Direct-verify checklists

The orchestrator runs these itself, on the diff and the gate, before any QA dispatch. Each item is a
check that was skipped at least once in a real run and cost a full round. The project's verification
contract (e.g. `.subagent-loop/gate.md`) adds language- and engine-specific greps under the same headings.

## Per task (after every dev report)

1. **Diff scope vs report.** `git diff --stat` against the report's "files changed" list. A file in the
   diff but not in the report is silent scope creep → QA it. A contract/spec/wiki `.md` in a *code*
   task's diff is scope creep unless the brief named it (the docs task owns that text).
2. **Build inclusion.** When the gate compiles from generated project files, compare the project file's
   source list to the task's owned files. A file that leaked in from another task's template compiles by
   accident when the references happen to suffice; a file that leaked out is never compiled at all.
   Build-file references must mirror the module manifest; a reference only in the generated build file
   is a false green (it compiles the build unit but the module manifest itself would not resolve).
3. **Public surface.** For every new type, put its visibility (access modifiers or exports — e.g.
   `grep -n "public\|internal"` in C#) next to the contract's surface list. Ten seconds; catches the brief that re-told the contract wrongly.
4. **Cross-module symbols.** Every symbol the brief names as a call target or as a field the task
   reads/writes: check its visibility from the calling module *before* dispatch, and again in the diff.
5. **Test lifecycle.** In every new or changed test class read setup/teardown end to end: each resource
   bound to a container or context (a world, session, connection, arena) must be released *before* that
   container. Scope-based release that sits in the same scope as the container's own release runs after
   it — that is the trap. The project contract carries the language-specific form and grep.
6. **Disabled tests are unread, not green.** A test that is disabled/skipped or waits on a hook: read its
   assertions against a *running* precedent in the repo. Typical miss: asserting that an update loop
   throws when the group catches and logs the exception.
7. **Fixture exercised?** A fixture only counts as run when at least one active test drives its
   container/context setup and teardown path. Pure-formula tests do not exercise teardown.
8. **Positive control.** A test whose claim ends in "no violation → pass" must have gone red once on a
   planted violation; the dev's report shows the red. No red seen → the test is unverified.
9. **Test files changed → functional gate.** A compile-only green on test code is not a test green; run
   the project's test gate on that build unit before acceptance. A compile gate cannot see teardown order,
   log expectations, or runtime exceptions.
10. **Gate ownership on red.** First question on a red gate: which project/assembly/package owns the error? An
    error in another in-flight task's project is not this task's red — rerun when that task lands.
11. **Anchored counts.** Any acceptance gate that counts text is anchored at line start (`^`) and the
    dev and orchestrator run the identical command from the brief. Prose that quotes the pattern
    otherwise inflates the count.
12. **Out-of-scope observations.** Move the report's "out-of-scope observations" section to the review
    list; they are findings about files the dev did not own.
13. **After a docs task lands:** re-read the briefs of tasks that depended on it against the docs
    report's deviation list (renumbered contract items, moved sections) before dispatching them.
14. **Count every assertion in the file, not the ones you remember.** When an auto decision
    carries a test's assertions forward (a rename, a moved threshold), read the whole file and count — a
    partial recollection undercounts and the missed assertions surface as a later fix round.
15. **Containers the framework does not track.** A shared/singleton data component that holds its own
    native or unmanaged container (array, map) is invisible to the framework's dependency tracking: the
    writer must declare write access explicitly, readers read-only, and every test fixture completes
    in-flight jobs before disposing it. A missing declaration is a race in a build and a safety exception
    in the editor — and a fixture that "happens to pass" only because another system completes dependencies
    first is not evidence.
16. **Byte-equality over padded structs.** A determinism test that compares raw bytes of a struct with
    padding fails intermittently: padding is refilled by every whole-struct copy (sort swaps, scratch
    copies, container adds). Either the struct is designed without padding, or the test compares field by
    field. Quick check: `sizeof(T)` ≠ sum of field sizes.

## Plan (before any dispatch; the plan is a claim too)

Shape: same-wave file sets disjoint, every dependency points to an earlier wave, shared docs only in
wave-end docs tasks, tier stated. Then content:

- **Code in plan lines compiles.** Every plan line that contains code: grep the API signature in the
  package/framework source once. "The dev will fix it" buries the fix in a report nobody reads.
- **State owner.** Every "task X writes field Y of data Z" where another module owns Z: grep that
  module's contract and contract tests for Y. A contradiction returns the plan to the planner (typical:
  the plan routes a value through a field the owner's own creation path resets, and the reset is tested).
- **Who writes the state.** Every promise about visible or runtime state (what a camera frames, what a
  screen shows, which way an object faces): who sets that state, where, and does third-party code
  overwrite it later? A task with visual output is accepted on a capture, never on a test green alone.
- **Docs agent type.** A docs task that transcribes one source (one report, one diff) is transcriber
  work; one that synthesizes or reconciles several reports needs `loop-dev`. Re-check at dispatch.
- **Item numbering.** New numbered contract items say "next after <last ID>" (read the contract's last
  number), never a fixed number the contract may already hold.
- **Gate points.** In pipelined execution the plan names where the mutating/functional gate runs
  (after which tasks); otherwise it never runs.
- **Build chains.** Same-wave tasks connected by a project-reference chain: each dev's gate compiles
  only its own build unit; wide gates (ones that pull in many units) run at wave end.
- **Modules created in the same or a later wave.** A task whose module manifest references a build unit
  that another task creates in the same or a later wave cannot compile when it starts — disjoint file
  sets do not catch it. `wavecheck.py` warns on created modules named in an earlier/same-wave task's spec.
- **Deleted and renamed symbols.** For every symbol or field a task deletes or renames, grep its readers
  repo-wide when the plan is written. A reader inside a frozen test body makes the task a sealed-decision
  question for the interview (list the bodies by name) — not a surprise at dispatch. Non-frozen readers join
  the task's file list.
- **Grep-count acceptance criteria are run, not predicted.** A criterion of the form "grep X → N hits" is
  executed against the disk when the plan is written; hits in frozen folders are subtracted or listed by
  name, or the criterion is unmeetable and gets rewritten at Finish.

## Finish (standard questions in the reviewer brief)

- Types-and-tests phases (bodies written now, run by a later phase): trace every disabled/hook-waiting body
  against the NEXT phase's plan if it is written (else the contract and a running precedent) — which
  mechanism will make it pass, and does the fixture install everything that mechanism reads? A body that
  agrees with the contract in isolation can still be unpassable by the planned mechanism.

- Cross-module symmetry: do sibling modules handle shared concerns the same way (e.g. test fixtures
  releasing persistent resources)? Per-task QA sees each module as correct in isolation.
- Third-party imports: files an import unpacked — tracked, or ignored (`git check-ignore`)? A project
  file that references ignored third-party files is unrecoverable from a clean clone.
- Environment-operation output: every file the ledger's wave-gate entries list as produced (generated assets,
  imported packages, tool metadata) — tracked, ignored, or forgotten? Reconcile against `git status --short`.
- Plan lines the dev silently corrected: compare plan pseudo-code to the diff.
- Every build unit whose test files changed in the fix package: run in the functional gate before hand-off.
- A reviewer's proposed fix is a claim, not an approved change: name which frozen
  tests/fixtures it touches and check it against them before it becomes a dispatch.
- A composition promise ("this container has/lacks field X") is accepted on a live probe, not on a fixture
  — a fixture built by hand can omit an engine-level step (e.g. an entity-composition
  framework silently forcing a referenced root into a different mode) that only a running instance exposes.
