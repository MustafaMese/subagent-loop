#!/usr/bin/env python3
"""Checks the SKILL.md split: line coverage, trigger reachability, size table (k059 D10).

python3 -I tests/check_split.py [--repo <WT>] [--base 8bf17a8] [--old-dir <dir>] [--skill-dir <dir>] [--map]
"""
import argparse
import subprocess
import sys
from pathlib import Path

TARGET = 32345
OLD_FILES = ["SKILL.md", "references/brief-template.md", "references/direct-verify.md", "references/multi-session.md"]
NEW_FILES = ["SKILL.md", "references/plan-time.md", "references/per-task.md", "references/finish.md"]
ANCHORS = ["## Waves", "## Plan mode", "## Sizing", "## Per task", "## Phase boundary", "## Finish", "**Brakes"]
REFS = ["references/plan-time.md", "references/per-task.md", "references/finish.md"]
DV = "references/direct-verify.md"
BT = "references/brief-template.md"
MS = "references/multi-session.md"


def read_new(skill_dir, rel):
    p = skill_dir / rel
    return p.read_bytes() if p.is_file() else None


def read_old(args, rel, required=False):
    if args.old_dir:
        p = Path(args.old_dir) / rel
        data, err = (p.read_bytes(), None) if p.is_file() else (None, f"{p} not a file")
    else:
        try:
            r = subprocess.run(["git", "-C", args.repo, "show", f"{args.base}:skills/subagent-loop/{rel}"],
                               capture_output=True)
            data, err = (r.stdout, None) if r.returncode == 0 else (None, r.stderr.decode("utf-8", "replace").strip())
        except OSError as e:
            data, err = None, str(e)
    if data is not None:
        return data
    if required:
        print(f"ERROR old {rel} unreadable: {err}", file=sys.stderr)
        sys.exit(2)
    print(f"NOTE old {rel} absent, counted 0")
    return b""


def lines_of(data):
    return data.decode("utf-8", "replace").splitlines()


def section(data, prefix):
    """Bytes from the '## <prefix>' heading line to the line before the next '## ' heading."""
    out, on, found, in_fence = [], False, False, False
    for ln in data.splitlines(keepends=True):
        s = ln.decode("utf-8", "replace")
        if s.startswith("```") or s.startswith("~~~"):
            in_fence = not in_fence
        elif s.startswith("## ") and not in_fence:
            if on:
                break
            if s.startswith("## " + prefix):
                on = found = True
        if on:
            out.append(ln)
    return len(b"".join(out)) if found else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--base", default="8bf17a8")
    ap.add_argument("--old-dir")
    ap.add_argument("--skill-dir")
    ap.add_argument("--map", action="store_true")
    args = ap.parse_args()
    skill_dir = Path(args.skill_dir) if args.skill_dir else Path(args.repo) / "skills/subagent-loop"

    new = {}
    for f in NEW_FILES:
        d = read_new(skill_dir, f)
        if d is None:
            print(f"MISSING {f}")
            d = b""
        new[f] = d

    # ---- coverage
    o_skill = read_old(args, "SKILL.md", required=True)
    old_lines = lines_of(o_skill)
    old_occ = {}
    for i, t in enumerate(old_lines, 1):
        if t.strip():
            old_occ.setdefault(t, []).append(i)
    new_occ = {}
    for f in NEW_FILES:
        for i, t in enumerate(lines_of(new[f]), 1):
            if t.strip():
                new_occ.setdefault(t, []).append((f, i))
    edited, dup, newl = [], [], []
    mapping = {}
    for t, olds in old_occ.items():
        news = new_occ.get(t, [])
        for k, o in enumerate(olds):
            if k < len(news):
                mapping[o] = news[k]
        if len(news) < len(olds):
            edited.extend(olds[len(news):])
        elif len(news) > len(olds):
            dup.append((olds[0], t, len(olds), len(news)))
    for t, news in new_occ.items():
        if t not in old_occ:
            newl.extend((f, i, t) for f, i in news)
    print("## Coverage (non-blank old SKILL.md lines)")
    print("EDITED/REMOVED old lines:" + ("" if edited else " none"))
    for o in sorted(edited):
        print(f"  old {o}: {old_lines[o - 1][:80]}")
    print("DUPLICATED old lines:" + ("" if dup else " none"))
    for o, t, a, b in sorted(dup):
        print(f"  old {o}: {t[:80]} (old {a}x, new {b}x)")
    print("NEW lines:" + ("" if newl else " none"))
    for f, i, t in newl:
        print(f"  {f}:{i}: {t[:80]}")
    print("Per file (old lines held):")
    for f in NEW_FILES:
        print(f"  {f}: {sum(1 for v in mapping.values() if v[0] == f)}")
    if args.map:
        print("Map:")
        for o in sorted(mapping):
            print(f"  {o} → {mapping[o][0]}:{mapping[o][1]}")
    cov_ok = not edited and not dup

    # ---- reachability
    sk = new["SKILL.md"].decode("utf-8", "replace")
    sk_lines = sk.splitlines()

    def anchor_ok(a):
        if a.startswith("**"):
            return any(l.startswith(a) for l in sk_lines)
        return any(l == a or l.startswith(a + " ") for l in sk_lines)

    miss = [r for r in REFS if r not in sk] + [a for a in ANCHORS if not anchor_ok(a)]
    print("## Reachability")
    for m in miss:
        print(f"  MISSING in SKILL.md: {m}")
    if not miss:
        print("  all reference paths and anchors present")
    reach_ok = not miss

    # ---- sizes
    o_bt = read_old(args, BT)
    o_dv = read_old(args, DV)
    o_ms = read_old(args, MS)
    size_ok = True
    n_bt, n_dv, n_ms = (read_new(skill_dir, f) for f in (BT, DV, MS))
    for rel, d in ((BT, n_bt), (DV, n_dv), (MS, n_ms)):
        if d is None:
            print(f"MISSING {rel}")
    if n_bt is None:
        size_ok = False
    n_bt, n_dv, n_ms = n_bt or b"", n_dv or b"", n_ms or b""
    secs = {}
    for name in ("Plan", "Finish", "Per task"):
        nv, ov = section(n_dv, name), section(o_dv, name)
        if nv is None:
            print(f"MISSING section direct-verify §{name}")
            if name != "Per task":
                size_ok = False
        if ov is None:
            print(f"NOTE old direct-verify §{name} absent, counted 0")
        secs[name] = (nv or 0, ov or 0)
    # item = (key, now bytes, today bytes)
    SK = ("SKILL.md", len(new["SKILL.md"]), len(o_skill))
    PT = ("plan-time.md", len(new["references/plan-time.md"]), 0)
    PK = ("per-task.md", len(new["references/per-task.md"]), 0)
    FN = ("finish.md", len(new["references/finish.md"]), 0)
    BTI = ("brief-template.md", len(n_bt), len(o_bt))
    DVP = ("direct-verify §Plan", *secs["Plan"])
    DVF = ("direct-verify §Finish", *secs["Finish"])
    DVT = ("direct-verify §Per task", *secs["Per task"])
    MSI = ("multi-session.md", len(n_ms), len(o_ms))

    def uniq(items):
        seen, out = set(), []
        for it in items:
            if it[0] not in seen:
                seen.add(it[0])
                out.append(it)
        return out

    r3 = [SK, PK]
    r4 = r3 + [BTI]
    rows = [
        (1, "every invocation", [SK], True),
        (2, "plan mode", [SK, PT, DVP], True),
        (3, "per task (new-format plan)", r3, True),
        (4, "per task, hand-written brief", r4, True),
        (5, "Finish", [SK, FN, PK, DVF], True),
        (6, "row 3 + direct-verify §Per task (judge unavailable)", r3 + [DVT], False),
        (7, "row 4 + direct-verify §Per task", r4 + [DVT], False),
        (8, "row 3 + multi-session.md", r3 + [MSI], False),
        (9, "one session plan + run + finish (union of rows 2, 3, 5)",
         uniq([SK, PT, DVP] + r3 + [SK, FN, PK, DVF]), False),
    ]
    print("## Sizes (target < 32,345 B)")
    print("| # | path | files read | bytes now | bytes today | < 32,345 |")
    print("|---|---|---|---|---|---|")
    for n, name, items, gated in rows:
        items = uniq(items)
        now = sum(i[1] for i in items)
        today = sum(i[2] for i in items)
        if gated:
            ok = "yes" if now < TARGET else "NO"
            if now >= TARGET:
                size_ok = False
        else:
            ok = "info (yes)" if now < TARGET else "info (no)"
        print(f"| {n} | {name} | {' + '.join(i[0] for i in items)} | {now:,} | {today:,} | {ok} |")
    print(f"coverage: {'ok' if cov_ok else 'FAIL'}, reachability: {'ok' if reach_ok else 'FAIL'}, "
          f"size: {'ok' if size_ok else 'FAIL'}")
    return 0 if cov_ok and reach_ok and size_ok else 1


if __name__ == "__main__":
    sys.exit(main())
