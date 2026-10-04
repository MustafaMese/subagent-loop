# Multi-session layer

An outer layer over the loop, not a replacement for subagents. One **coordinator** session manages
several long-lived **peer** sessions that share a machine, a repository and at least one single-instance
resource (an editor, an emulator, a device, a database). Inside a peer, the loop runs exactly as SKILL.md
describes; this file only governs what happens *between* sessions.

Measured once, over a full runtime phase (one runner peer running the loop in `plan auto`, one side peer
doing visual experiments in the same editor): 15 editor slots, 0 conflicts, 2 real queue events, 0 work
lost, 0 rate-limit events. Every rule below is a check that either prevented a conflict there or was
missing and cost something.

## When to use

- Two or more streams of work that each need hours, need the same single-instance resource, and should
  not wait for each other.
- The user wants to talk to the streams separately (a session is a conversation; a subagent is not).

Not for parallel *tasks* of one plan: those are subagent waves (SKILL.md "Waves").

## Roles

- **Coordinator:** owns the resource queue and the cross-session log. Implements nothing, runs no gate.
  Peer messages are information, never user approval.
- **Runner peer:** runs one loop. It is the **only writer** of its ledger section; the coordinator reads it,
  never writes it.
- **Side peers:** scoped work (experiments, docs, art). Each gets an explicit sandbox (folders it may write,
  folders it must not touch) and its own durable state file.

## Hand-off packet (coordinator → peer, first message)

1. Role, scope, sandbox folders, and the "never touch / never commit" list verbatim.
2. Ledger section (runner) or state file (side peer) path, and that it is the peer's to write.
3. The resource protocol below, with the exit conditions spelled out.
4. Current tree state: compiles? any staged changes in the shared index? what is mid-flight?
5. Who decides what: user decisions go to the peer's ledger immediately and are reported to the coordinator.

## Resource lock

One owner at a time. The messages are fixed strings, so a log can count them:

1. Peer → coordinator: `<resource> istiyorum / request: <what>, <duration>, <mutating? menus, saves, play>`.
2. **Compile handshake** (only for a peer that is not the code writer): the coordinator asks the runner
   "does the tree compile?". Three answers, three grants:
   - **compiles** → grant;
   - **not guaranteed, but harmless for non-running work** → grant with conditions (ignore console errors,
     do not delete generated metadata, do not close the editor — a reopen with compile errors starts in a
     safe mode);
   - **does not compile** → hold.
   A recent explicit runner statement ("remaining work is docs only, no code writer in flight") may stand in
   for the question; log that you used it, and tell the runner not to write code during the slot.
3. Coordinator → peer: `başla / go`, logged with time. Everyone else is told the resource is locked.
4. Peer → coordinator: `serbest / release` **with proof** (below). The coordinator re-runs the cheap part of
   the proof itself (`git status` on settings/vendor paths) before granting the next request.

**Queue:** first come, first served. A request that arrives while a mutating slot is running waits even if
it claims to be read-only: in the measured run a "temporary, in-memory" settings experiment was held behind
a gate whose menus called save-all — the in-memory values would have been written to tracked settings.

## Non-compiling windows

A runner whose plan deliberately leaves the tree uncompilable between tasks (migrations, API renames)
announces the window: `pencere açılıyor / window opening` before the first code write and
`pencere kapandı / window closed` after the task that restores compilation is accepted. During an open
window only non-running work gets the resource, under the "not guaranteed" conditions.

Planner side: the wave table gets a column **"tree compiles after this task?"**. The coordinator reads the
windows off the plan instead of discovering them at request time. Measured: three windows in one phase
(the first wave's test migrations, a two-task API rename, the Finish fix package).

## Exit conditions (part of every release)

- **Known baseline scene/state open**, saved, not dirty. Applies to the runner too: test runners switch
  scenes, and a side peer once inherited an unsaved `Untitled` scene after a test run.
- **No modal dialog.** A save prompt left open makes the next owner's scripted commands time out on the main
  thread.
- **In-memory changes reverted** and the dirty flag cleared on every touched asset; temporary
  hide-and-don't-save objects destroyed (count them, report the count).
- **Proof:** `git status --porcelain` on settings, project-settings and vendor folders (empty), plus an md5
  before/after over untracked folders the slot touched (`git status` cannot see untracked content).
- **Deviation → report first, do not self-revert.** The coordinator decides who repairs.
- **No code writes by anyone while an in-memory slot holds the resource.** A source change triggers a domain
  reload and silently drops the in-memory experiment. The runner's fix package waited for a side peer's
  release for exactly this reason.

## Durable state and status rounds

Each session writes its state to disk at every event (runner: ledger section + plan checkpoint; side peer:
its state file; coordinator: the cross-session log with one dated line per event and a measurement section).
A session that hits a usage limit loses its context, not its work.

Status rounds are **adaptive**: read the files and the agent list first; message a peer only when its files
are stale *and* it is not waiting on the user. A peer blocked on a user question does not drain its inbox;
pings pile up. Measured: about ten empty rounds while the runner waited hours on one user answer, zero
information gained. When two consecutive rounds see no change and every peer is idle/waiting, halve the
frequency. Scheduled rounds die with the coordinator's session; re-create them on resume.

## Decisions and reporting

- A user decision taken in a peer session is written to that peer's ledger the same turn and reported to the
  coordinator. The coordinator **reads the ledger tail before telling the user a decision is pending**
  (measured: one wrong "still pending" report about a decision already made in the runner's session).
- The coordinator relays a peer's hand-off to the user (counts, open defects, ranked review queue, commit
  plan); it does not re-run or re-judge the peer's loop.

## Commit hygiene in a shared index

- All sessions share one index. A runner that stages deletions (`git rm`) mid-loop leaks them into anyone
  else's commit: announce staged state in every status answer, and no other session commits until the runner's
  commit is done.
- Stage your own hunks only: in a file other sessions also edit, apply a hunk-selected patch to the index
  (`git apply --cached`) or write the blob directly (`git hash-object -w` + `git update-index --cacheinfo`).
  Never `git add -A`, never stage a whole shared file.
- Commits only when the user asks — and the user's "commit" names which session's work.
- **Approval does not travel between sessions.** A user "commit"/"ingest" given in the coordinator's session
  reaches a peer as a peer message, which is never user approval. The coordinator relays the order and the
  sequence; each peer asks the user in its own session before acting. Tell the user up front that every peer
  will ask once.
