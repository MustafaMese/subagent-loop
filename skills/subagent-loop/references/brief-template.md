# Brief template

File: `…/<phase>-task-N-brief.md`. The phase prefix is mandatory — a later phase's `task-1` must never
overwrite an earlier one. Sections, in order:

1. **Goal** — one paragraph.
2. **Read first** — narrowed to the contract items/sections the task touches, not whole contracts (measured:
   130–230k tokens per task, most of it a wide read list).
3. **Owned files** — exact paths.
4. **Don't touch** — always listed explicitly, never implied: contract/spec documents and KB pages ("the docs
   task updates contract text; a code/contract mismatch goes in your report"), generated files, third-party
   folders, other in-flight tasks' files.
5. **Spec** —
   - A type's public surface is **quoted verbatim from the contract**, not re-told. Access modifiers on
     their own line: `public: …; internal: …`.
   - Every cross-module symbol named as a call target or as a field the task reads/writes carries its checked visibility.
   - A mechanism is named as the contract/decision archive names it.
   - Facts about the disk (line numbers, ordering, existing names) are pasted from `grep`/`tail` output
     so the dev can check them — never "add at the top".
6. **Tests** — for a test whose claim is "no violation → pass": the dev plants a violation, reports the
   red, removes it. Lifecycle rules from the project contract are repeated as fixed lines.
7. **Gate** — the exact command with per-task paths. If the task's build chain includes another in-flight
   task's project, say so and name the errors to ignore.
8. **Report path** and the deviation rule, verbatim:
   > Contract surface beats brief — apply the contract, report the deviation. Disk beats brief for facts.
   > A mechanism the contract or decision archive names that the disk blocks → NEEDS_CONTEXT, never a
   > redesign. Defects in files you read but don't own → "out-of-scope observations", not edits.

**Docs briefs:** "follow the file's existing ordering rule" plus the pasted `tail`; agent type by source
count (one source → transcriber, synthesis → dev); if the task imports or unpacks third-party files, their
commit status (tracked or ignored) is an explicit review question.

**Fix briefs:** bind the pattern to code, not to a name — quote the exact form ("release the query in an explicit
block that closes before the owning container is released"), not "the same pattern as module Y"; "X pattern
verbatim" in a report is not evidence. When a
fix moves a call between execution contexts (worker/job → main thread, managed → natively compiled entry point), the brief
asks whether the entry point's calling convention changed.
