---
name: brief
description: Use when a request is new or non-trivial and a missing detail would change what gets built — vague goals ("clean it up", "add a reward thing"), unstated reasons, no clear finish line — or when the user types /brief. Not for mechanical, unambiguous tasks (rename, typo, one-line fix).
---

# Brief

## Overview
A brief is a short file that pins down **why** the user wants something, **what done looks like**, and **what must not happen**, before work starts — then proves each point with evidence at the end. Requirements kept only in chat get lost at compaction, rotation and subagent handoff; a brief file survives all three.

## When to skip
The request is mechanical and unambiguous, and every reasonable reading builds the same thing → act directly, no brief.

## The brief (fill every field)

```markdown
# Brief: <short title>   (<YYYY-MM-DD>)
- Task: <one sentence>
- Why: <the user's reason, in their words where possible>
- Done when: <observable checks, one per line — a command, a screen, a file>
- Must not: <what would make it a failure even if it technically works>
- Scope: may change <paths/areas>; read first <sources>
- Limit: <time / effort / attempt cap>
- Guesses: <fields you filled yourself, marked so the user can correct them>

## Checks   (filled at the end)
| Requirement | Verdict | Evidence |
|---|---|---|
```

## Steps
1. **Fill the brief yourself first** from the request, the project's CLAUDE.md/AGENTS.md and the code. Mark every inferred field `(guess)`.
2. **Ask one question per message**, only about a field where a wrong guess changes what gets built. Ask **Why** first if it is unknown — it settles many other fields. Each question is one sentence and carries your guess for the user to correct.
3. **Show the brief** (at most 12 lines) and get an explicit OK. Changes later → edit the file, say so.
4. **Save it** where the project's instructions put such docs; if they name no place, `.briefs/<YYYY-MM-DD>-<slug>.md`, kept out of git via `.git/info/exclude` unless the user wants it tracked.
5. **Hand it on:** any plan, subagent or later session gets the brief path, not a retelling.
6. **Close with the Checks table:** one row per `Done when` line and per `Must not` line. Verdict = pass / fail / unverified. Evidence = the command and its result, a file path, or a screenshot. Leave unverified rows visible; never drop a row to make the table green. Report the table to the user.

## Common mistakes
| Mistake | Instead |
|---|---|
| Four questions in one message | One question, with your guess attached |
| "What will you add next?" in place of the reason | Ask why they want it; the feature list follows |
| Requirements restated only in chat | Save the file; pass its path |
| "Tests pass" as the whole report | One Checks row per requirement, with evidence |
| Brief for a rename | Skip; act |
