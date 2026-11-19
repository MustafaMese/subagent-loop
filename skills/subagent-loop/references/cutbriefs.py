#!/usr/bin/env python3
"""Brief cutter (subagent-loop: one brief per task, cut byte for byte from a new-format plan).
Usage: python3 -I references/cutbriefs.py <plan.md> ["# Phase 2"] --phase <prefix> [--out <dir>] [--dry-run] [--force]
       python3 -I references/cutbriefs.py --check <brief.md> --plan <plan.md> ["# Phase 2"]
       python3 -I references/cutbriefs.py --list-sections
The plan carries one block per task, from a whole line `<!-- brief:begin ID -->` to `<!-- brief:end ID -->`
(outside code fences). The cut writes `<out>/<prefix>-task-<ID>-brief.md` = block + `## Delta (orchestrator)` tail;
on a re-cut the existing Delta tail is kept verbatim; a re-cut whose existing brief has a different spec part is
refused (STALE BRIEF) unless `--force`, which overwrites the spec part and keeps the Delta. Non-blank text between
the end marker and the Delta heading (STRAY TEXT) is refused by a re-cut and by `--check`. `--check` proves a brief's bytes through its end marker
equal the plan's block. Needs `brief-template.md` next to this script (numbered items = required `#### k. Name`).
Checks (all collected, nothing written on any error): every Waves row has exactly one block and vice versa; marker
structure; the template's section headings once each, in order; no Delta heading inside a block; an existing brief
has a Delta line. Warns (no exit effect): cross-references the cut would lose ("see above").
Exit codes: 0 ok; 1 plan defect, check mismatch, existing brief without Delta, STALE BRIEF (re-cut over a changed spec without `--force`) or STRAY TEXT; 2 usage; 3 old-format plan
(no begin markers in scope: write briefs by hand)."""
import argparse, difflib, importlib.util, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("wavecheck", os.path.join(HERE, "wavecheck.py"))
wavecheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wavecheck)

ID_RE = r"[A-Za-z0-9][A-Za-z0-9._-]*"
BEGIN = re.compile(r"^<!-- brief:begin (" + ID_RE + r") -->$")
END = re.compile(r"^<!-- brief:end (" + ID_RE + r") -->$")
FENCE_OPEN = re.compile(r"(`{3,}|~{3,})")
FENCE_CLOSE = re.compile(r"(`{3,}|~{3,})[ \t]*")
SEC = re.compile(r"^#### (\d+)\. (.+?)\s*$")
XREF = re.compile(r"(?i)\b(see|as)\s+(above|below)\b|\bsame as (the )?(previous|above|T\w+)\b|\bas in T\w+\b")
DELTA = "## Delta (orchestrator)"


def split_lines(text):
    return re.findall(r"[^\n]*\n|[^\n]+", text)


def bare(line):
    return line.rstrip("\r\n")


def fence_map(lines):
    inf, ch, n = [False] * len(lines), None, 0
    for i, l in enumerate(lines):
        s = bare(l)
        ind = len(s) - len(s.lstrip(" "))
        t = s.lstrip(" ")
        if ch is None:
            m = FENCE_OPEN.match(t)
            if m and ind <= 3:
                ch, n, inf[i] = m.group(1)[0], len(m.group(1)), True
        else:
            inf[i] = True
            m = FENCE_CLOSE.fullmatch(t)
            if m and ind <= 3 and m.group(1)[0] == ch and len(m.group(1)) >= n:
                ch = None
    return inf


def template_sections():
    path = os.path.join(HERE, "brief-template.md")
    items = []
    try:
        with open(path, encoding="utf-8") as f:
            anchored = False
            for l in f:
                if not anchored:
                    anchored = "Sections, in order:" in l
                    continue
                m = re.match(r"^(\d+)\. \*\*(.+?)\*\*", l)
                if m:
                    items.append((int(m.group(1)), m.group(2)))
                elif l.strip() and not l[0].isspace():
                    break
    except OSError:
        pass
    if not items or [k for k, _ in items] != list(range(1, len(items) + 1)):
        print("template unreadable: brief-template.md needs numbered items 1..n as `k. **Name**`")
        sys.exit(1)
    return items


def load_plan(plan, section):
    with open(plan, "rb") as f:
        lines = split_lines(f.read().decode("utf-8"))
    inf = fence_map(lines)
    h1 = [i for i, l in enumerate(lines) if not inf[i] and l.startswith("# ")]
    s, e = 0, len(lines)
    if section:
        start = None
        for i in h1:
            t = bare(lines[i])
            if t == section or t.startswith(section + " "):
                start = i
                break
        if start is None:
            print(f"section not found: {section}")
            sys.exit(1)
        s = start
        e = next((i for i in h1 if i > start), len(lines))
    return lines, inf, s, e, h1


def scan_markers(lines, inf, s, e):
    """Returns (blocks {id: (b, e)}, order, errors)."""
    blocks, order, errs, open_ = {}, [], [], None
    for i in range(s, e):
        if inf[i]:
            continue
        t = bare(lines[i])
        if not t.startswith("<!-- brief:"):
            continue
        mb, me = BEGIN.match(t), END.match(t)
        if mb:
            if open_ is not None:
                errs.append(f"NESTED begin {mb.group(1)} line {i + 1} inside open block {open_[0]}")
                continue
            open_ = (mb.group(1), i)
        elif me:
            if open_ is None or open_[0] != me.group(1):
                errs.append(f"MISMATCHED END {me.group(1)} line {i + 1}")
                open_ = None if open_ is None else open_
                continue
            if open_[0] in blocks:
                errs.append(f"DUPLICATE ID {open_[0]} (second block at line {open_[1] + 1})")
            else:
                blocks[open_[0]] = (open_[1], i)
                order.append(open_[0])
            open_ = None
        else:
            errs.append(f"BAD MARKER line {i + 1}")
    if open_ is not None:
        errs.append(f"UNCLOSED block {open_[0]} begun at line {open_[1] + 1}")
    return blocks, order, errs


def wave_rows(lines, inf, s, e):
    """Rows exactly as wavecheck.py collects them. Returns (found_header, [cell-of-task])."""
    rows, headers, found = [], None, False
    for i in range(s, e):
        line = bare(lines[i])
        if inf[i] or not line.strip().startswith("|"):
            headers = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if headers is None:
            if wavecheck.col(cells, "task") is not None and wavecheck.col(cells, "wave") is not None:
                headers, found = cells, True
            continue
        if set(line.replace("|", "").strip()) <= set("-: "):
            continue
        if len(cells) < len(headers):
            continue
        ti, wi = wavecheck.col(headers, "task"), wavecheck.col(headers, "wave")
        if not re.search(r"\d+", cells[wi]):
            continue
        rows.append(cells[ti])
    return found, rows


def validate(lines, inf, s, e, blocks, order, errs, tmpl):
    warns = []
    found, cells = wave_rows(lines, inf, s, e)
    if not found:
        errs.append("NO WAVES TABLE")
    ids = []
    for c in cells:
        cell = c.replace("*", "").replace("`", "").strip()
        tok = cell.split()[0] if cell.split() else ""
        if not re.fullmatch(ID_RE, tok):
            errs.append(f"BAD ID '{c}'")
            continue
        if tok.casefold() in [x.casefold() for x in ids]:
            errs.append(f"DUPLICATE ID {tok}")
        else:
            ids.append(tok)
    for i in ids:
        if i not in blocks:
            errs.append(f"NO BLOCK {i}")
    for i in order:
        if i not in ids:
            errs.append(f"NO WAVES ROW {i}")
    names = dict(tmpl)
    for bid in order:
        b, en = blocks[bid]
        seen, last = set(), 0
        for n in range(b, en + 1):
            t = bare(lines[n])
            if t == DELTA:
                errs.append(f"DELTA LINE IN BLOCK {bid} line {n + 1}")
            if XREF.search(t):
                warns.append(f"WARN {bid} line {n + 1}: cross-reference the cut would lose")
            if inf[n]:
                continue
            m = SEC.match(t)
            if not m:
                continue
            k, name = int(m.group(1)), m.group(2)
            if names.get(k) != name:
                errs.append(f"UNKNOWN SECTION {bid} line {n + 1}: {t}")
                continue
            if k in seen:
                errs.append(f"SECTION DUPLICATE {bid} line {n + 1}: {t}")
                continue
            if k < last:
                errs.append(f"SECTION ORDER {bid} line {n + 1}: {t}")
            last = max(last, k)
            seen.add(k)
        for k, name in tmpl:
            if k not in seen:
                errs.append(f"SECTION MISSING {bid} #### {k}. {name}")
    return warns


def block_text(lines, blocks, bid):
    b, en = blocks[bid]
    return "".join(lines[b:en + 1])


def sep_of(block):
    return "" if block.endswith("\n") else "\n"


def delta_split(blines, bid):
    """Index of the Delta heading line after the end marker (or 0 when the marker is absent), or None."""
    start = 0
    for i, l in enumerate(blines):
        if bare(l) == f"<!-- brief:end {bid} -->":
            start = i + 1
            break
    for i in range(start, len(blines)):
        if bare(blines[i]) == DELTA:
            return i
    return None


def stray_line(blines, bid, j):
    """1-based line of the first non-blank line between the last end marker before Delta line j and j, or None."""
    k = None
    for i in range(j):
        if bare(blines[i]) == f"<!-- brief:end {bid} -->":
            k = i
    if k is None:
        return None
    for i in range(k + 1, j):
        if bare(blines[i]).strip():
            return i + 1
    return None


def spec_equal(blines, block):
    got = "".join(blines[:len(split_lines(block))])
    if not block.endswith("\n") and got.endswith("\n"):
        got = got[:-1]
    return got == block


def cmd_cut(args):
    plan, section = args.pos1, args.pos2
    with open(plan, "rb") as f:
        alines = split_lines(f.read().decode("utf-8"))
    ainf = fence_map(alines)
    if not any(not ainf[i] and bare(l).startswith("<!-- brief:begin") for i, l in enumerate(alines)):
        print(f"OLD-FORMAT PLAN: no <!-- brief:begin --> blocks in {plan}" + (f" [{section}]" if section else "")
              + '; write briefs by hand (SKILL.md "Per task" step 1). No files written.')
        return 3
    tmpl = template_sections()
    lines, inf, s, e, h1 = load_plan(plan, section)
    nbegin = sum(1 for i in range(s, e) if not inf[i] and BEGIN.match(bare(lines[i])))
    if nbegin == 0:
        bad = [i + 1 for i in range(s, e) if not inf[i] and bare(lines[i]).startswith("<!-- brief:begin")]
        if bad:
            for n in bad:
                print(f"BAD MARKER line {n}")
            return 1
        print(f"OLD-FORMAT PLAN: no <!-- brief:begin --> blocks in {plan}" + (f" [{section}]" if section else "")
              + '; write briefs by hand (SKILL.md "Per task" step 1). No files written.')
        return 3
    if not section and len(h1) >= 2:
        print('multi-phase plan: pass the phase heading, e.g. "# Phase 2"')
        return 1
    blocks, order, errs = scan_markers(lines, inf, s, e)
    warns = validate(lines, inf, s, e, blocks, order, errs, tmpl)
    out = args.out or os.path.dirname(os.path.abspath(plan))
    plans = []
    for bid in order:
        path = os.path.join(out, f"{args.phase}-task-{bid}-brief.md")
        block = block_text(lines, blocks, bid)
        if os.path.exists(path):
            with open(path, "rb") as f:
                blines = split_lines(f.read().decode("utf-8"))
            j = delta_split(blines, bid)
            if j is None:
                errs.append(f"EXISTING BRIEF WITHOUT DELTA {path} ({bid})")
                continue
            sl = stray_line(blines, bid, j)
            if sl is not None:
                errs.append(f"STRAY TEXT {path}:{sl}; move it under ## Delta (orchestrator) or delete it, then re-cut")
                continue
            if not args.force and not spec_equal(blines, block):
                errs.append(f"STALE BRIEF {path}: spec part differs from plan block {bid}; "
                            "re-run with --force to overwrite (Delta is kept)")
                continue
            kept = "".join(blines[j:])
            content = block + sep_of(block) + "\n" + kept
            nkept = len("".join(blines[j + 1:]).strip())
        else:
            content = block + sep_of(block) + "\n" + DELTA + "\n"
            nkept = 0
        plans.append((path, content, len(block.encode("utf-8")), nkept))
    for w in warns:
        print(w)
    if errs:
        for x in errs:
            print(x)
        return 1
    if not args.dry_run:
        os.makedirs(out, exist_ok=True)
    for path, content, n, m in plans:
        if not args.dry_run:
            with open(path, "wb") as f:
                f.write(content.encode("utf-8"))
        print(f"{'would write' if args.dry_run else 'wrote'} {path} (spec {n} B, delta {m} chars kept)")
    return 0


def cmd_check(args):
    brief, plan, section = args.check, args.plan, args.pos1
    with open(brief, "rb") as f:
        blines = split_lines(f.read().decode("utf-8"))
    m = BEGIN.match(bare(blines[0])) if blines else None
    if not m:
        print(f"{brief}: first line is not a <!-- brief:begin ID --> marker")
        return 1
    bid = m.group(1)
    lines, inf, s, e, h1 = load_plan(plan, section)
    if not section and len(h1) >= 2 and any(not inf[i] and BEGIN.match(bare(lines[i])) for i in range(s, e)):
        print('multi-phase plan: pass the phase heading, e.g. "# Phase 2"')
        return 1
    blocks, order, errs = scan_markers(lines, inf, s, e)
    if bid not in blocks:
        for x in errs:
            print(x)
        print(f"block {bid} not found in {plan}" + (f" [{section}]" if section else ""))
        return 1
    block = block_text(lines, blocks, bid)
    n = len(split_lines(block))
    got = "".join(blines[:n])
    if not block.endswith("\n") and got.endswith("\n"):
        got = got[:-1]
    if got == block:
        j = delta_split(blines, bid)
        sl = stray_line(blines, bid, j) if j is not None else None
        if sl is not None:
            print(f"STRAY TEXT {brief}:{sl}; move it under ## Delta (orchestrator) or delete it, then re-cut")
            return 1
        d = len("".join(blines[j + 1:]).strip()) if j is not None else 0
        print(f"0 changes: {brief} == {plan} block {bid} (spec {len(block.encode('utf-8'))} B, delta {d} chars)")
        return 0
    print(f"CHANGED {brief}")
    diff = list(difflib.unified_diff(block.splitlines(True), got.splitlines(True), f"{plan}#{bid}", brief))
    for l in diff[:60]:
        print(l.rstrip("\n"))
    return 1


def main():
    ap = argparse.ArgumentParser(prog="cutbriefs.py", description=__doc__.split("\n")[0])
    ap.add_argument("pos1", nargs="?", help="plan.md (cut mode) or the section heading (--check mode)")
    ap.add_argument("pos2", nargs="?", help='section heading, e.g. "# Phase 2"')
    ap.add_argument("--phase", help="brief file name prefix")
    ap.add_argument("--out", help="output dir (default: the plan's dir)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-cut over a brief whose spec part differs (Delta kept)")
    ap.add_argument("--check", metavar="BRIEF")
    ap.add_argument("--plan", help="plan for --check")
    ap.add_argument("--list-sections", action="store_true")
    args = ap.parse_args()
    if args.list_sections:
        for k, n in template_sections():
            print(f"{k}. {n}")
        return 0
    if args.check:
        if not args.plan or args.pos2:
            ap.error("--check needs --plan <plan.md> and takes at most one section argument")
        return cmd_check(args)
    if not args.pos1 or not args.phase:
        ap.error("cut mode needs <plan.md> and --phase <prefix>")
    return cmd_cut(args)


if __name__ == "__main__":
    sys.exit(main())
