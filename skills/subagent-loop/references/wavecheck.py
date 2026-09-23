#!/usr/bin/env python3
"""Wave-table verifier (subagent-loop: "the plan is a claim too").
Usage: python3 references/wavecheck.py <plan.md> ["# Phase 2"]
Checks: file sets inside a wave are disjoint; every dependency names an existing task in an earlier wave;
the tier (S/M/L) is stated. Table headers may be English or Turkish. Exit 0 = clean, 1 = violations.
Not checked (read it yourself): shared docs live only in wave-end docs tasks; gate points are named."""
import fnmatch, re, sys

HEAD = {"task": ("task", "görev", "gorev"), "files": ("file", "dosya"), "deps": ("depend", "bağım", "bagim"),
        "wave": ("wave", "dalga")}

def norm(cell):
    cell = re.sub(r"<br\s*/?>", ",", cell)
    return [p.strip().strip("`").strip() for p in re.split(r"[,;\n]", cell) if p.strip().strip("`").strip()]

def col(headers, key):
    for i, h in enumerate(headers):
        if any(k in h.lower() for k in HEAD[key]):
            return i
    return None

def overlap(a, b):
    a, b = a.rstrip("/"), b.rstrip("/")
    if a == b or fnmatch.fnmatch(a, b) or fnmatch.fnmatch(b, a):
        return True
    return a.startswith(b + "/") or b.startswith(a + "/") or fnmatch.fnmatch(a, b + "/*") or fnmatch.fnmatch(b, a + "/*")

def main():
    path = sys.argv[1]
    section = sys.argv[2] if len(sys.argv) > 2 else None
    text = open(path, encoding="utf-8").read()
    if section:
        i = text.find(section)
        if i < 0:
            print(f"section not found: {section}"); sys.exit(1)
        text = text[i:]
    rows, headers = [], None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            headers = None; continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if headers is None:
            if col(cells, "task") is not None and col(cells, "wave") is not None:
                headers = cells
            continue
        if set(line.replace("|", "").strip()) <= set("-: "):
            continue
        if len(cells) < len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    if not rows:
        print("no wave table found (needs a header row with a task column and a wave column)"); sys.exit(1)
    h = rows[0].keys(); hl = list(h)
    ti, fi, di, wi = (col(hl, k) for k in ("task", "files", "deps", "wave"))
    tasks = {}
    for r in rows:
        v = list(r.values())
        m = re.search(r"\d+", v[wi])
        if not m:
            continue
        tasks[v[ti].strip("*` ")] = dict(files=norm(v[fi]) if fi is not None else [], deps=norm(v[di]) if di is not None else [],
                                        wave=int(m.group()))
    bad = 0
    for t, a in tasks.items():
        for u, b in tasks.items():
            if t < u and a["wave"] == b["wave"]:
                for x in a["files"]:
                    for y in b["files"]:
                        if overlap(x, y):
                            print(f"FILE OVERLAP wave {a['wave']}: {t} `{x}` <-> {u} `{y}`"); bad += 1
        for d in a["deps"]:
            d = d.strip("*` ")
            if d in ("", "-", "—", "yok", "none"):
                continue
            hit = next((k for k in tasks if k == d or k.lower() == d.lower() or d in k), None)
            if hit is None:
                print(f"MISSING DEPENDENCY: {t} -> `{d}` is not in the table"); bad += 1
            elif tasks[hit]["wave"] >= a["wave"]:
                print(f"ORDER VIOLATION: {t} (wave {a['wave']}) -> {hit} (wave {tasks[hit]['wave']})"); bad += 1
    if not re.search(r"\b(tier|Tier)\b\s*[:*]*\s*\**\s*[SML]\b", text):
        print("TIER not stated"); bad += 1
    waves = {}
    for t, a in tasks.items():
        waves.setdefault(a["wave"], []).append(t)
    for w in sorted(waves):
        print(f"wave {w}: {len(waves[w])} tasks - {', '.join(waves[w])}")
    print(f"{len(tasks)} tasks, {len(waves)} waves, widest {max(len(v) for v in waves.values())}; violations: {bad}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
