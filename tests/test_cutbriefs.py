import shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/subagent-loop/references/cutbriefs.py"
WAVECHECK = ROOT / "skills/subagent-loop/references/wavecheck.py"
FIX = Path(__file__).resolve().parent / "fixtures/cutbriefs"
DELTA = "## Delta (orchestrator)\n"


def run(*args):
    p = subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        self.out = self.tmp / "out"
        self.out.mkdir()

    def plan(self, name="good.md"):
        dst = self.tmp / name
        shutil.copy(FIX / name, dst)
        return dst

    def cut(self, plan, *extra, phase="m"):
        return run(plan, *extra, "--phase", phase, "--out", self.out)

    def brief(self, i, phase="m"):
        return self.out / f"{phase}-task-{i}-brief.md"

    def expect_block(self, plan, i):
        text = Path(plan).read_bytes().decode("utf-8")
        b = text.index(f"<!-- brief:begin {i} -->\n")
        endm = f"<!-- brief:end {i} -->\n"
        return text[b:text.index(endm, b) + len(endm)]

    def negative(self, name, code, *needles, plan_args=()):
        plan = self.plan(name)
        rc, out = self.cut(plan, *plan_args)
        self.assertEqual(rc, code, out)
        for n in needles:
            self.assertIn(n, out)
        self.assertEqual(list(self.out.iterdir()), [], out)
        return out


class CutTests(Base):
    def test01_good_cut(self):
        plan = self.plan()
        rc, out = self.cut(plan)
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["m-task-T1-brief.md", "m-task-T2-brief.md"])
        for i in ("T1", "T2"):
            block = self.expect_block(plan, i)
            text = self.brief(i).read_bytes().decode("utf-8")
            self.assertTrue(text.startswith(block))
            self.assertEqual(text[len(block):], "\n" + DELTA)
        self.assertIn("#### 5. Spec\n<!-- brief:begin FAKE -->", self.brief("T1").read_text())

    def test02_check(self):
        plan = self.plan()
        self.assertEqual(self.cut(plan)[0], 0)
        for i in ("T1", "T2"):
            rc, out = run("--check", self.brief(i), "--plan", plan)
            self.assertEqual(rc, 0, out)
            self.assertIn("0 changes", out)

    def test03_recut_keeps_delta(self):
        plan = self.plan()
        self.assertEqual(self.cut(plan)[0], 0)
        with open(self.brief("T2"), "a", encoding="utf-8", newline="") as f:
            f.write("- T1 landed foo()\n")
        tail = self.brief("T2").read_bytes().decode().split(DELTA, 1)[1]
        self.assertEqual(tail, "- T1 landed foo()\n")
        t = plan.read_text(encoding="utf-8")
        i = t.index("Body of T2 item 1 Goal word.")
        plan.write_text(t[:i] + t[i:].replace("Goal word", "Goal term", 1), encoding="utf-8", newline="")
        rc, out = self.cut(plan, "--force")
        self.assertEqual(rc, 0, out)
        new = self.brief("T2").read_bytes().decode()
        self.assertIn("Goal term", new)
        self.assertTrue(new.endswith(DELTA + "- T1 landed foo()\n"))
        self.assertEqual(new.split(DELTA, 1)[1], tail)
        self.assertIn("delta 17 chars kept", out)
        rc, out = run("--check", self.brief("T2"), "--plan", plan)
        self.assertEqual(rc, 0, out)

    def test04_check_detects_change(self):
        plan = self.plan()
        self.assertEqual(self.cut(plan)[0], 0)
        b = self.brief("T1")
        b.write_bytes(b.read_bytes().replace(b"Body of T1 item 5.", b"Body of T1 item 6.", 1))
        rc, out = run("--check", b, "--plan", plan)
        self.assertEqual(rc, 1, out)
        self.assertIn("CHANGED", out)

    def test05_old_format(self):
        self.negative("old-format.md", 3, "OLD-FORMAT")

    def test06_missing_block(self):
        self.negative("missing-block.md", 1, "NO BLOCK T3")

    def test07_orphan_block(self):
        self.negative("orphan-block.md", 1, "NO WAVES ROW T9")

    def test08_missing_section(self):
        self.negative("missing-section.md", 1, "SECTION MISSING T1 #### 6. Tests")

    def test09_misordered(self):
        self.negative("misordered.md", 1, "SECTION ORDER T1")

    def test10_duplicates(self):
        self.negative("duplicate.md", 1, "DUPLICATE ID T1")
        self.negative("duplicate-row.md", 1, "DUPLICATE ID T1")

    def test11_unclosed(self):
        self.negative("unclosed.md", 1, "UNCLOSED", "T2")

    def test12_delta_in_block(self):
        self.negative("delta-in-block.md", 1, "DELTA LINE IN BLOCK T1")

    def test13_two_phase(self):
        self.negative("two-phase.md", 1, "multi-phase")
        plan = self.plan("two-phase.md")
        rc, out = self.cut(plan, "# Phase 2")
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(list(self.out.iterdir())), 2)
        rc, out = run("--check", self.brief("T1"), "--plan", plan, "# Phase 2")
        self.assertEqual(rc, 0, out)
        for f in self.out.iterdir():
            f.unlink()
        rc, out = self.cut(plan, "# Phase 1")
        self.assertEqual(rc, 3, out)
        self.assertEqual(list(self.out.iterdir()), [])

    def test13c_old_format_any_section_arg(self):
        plan = self.plan("old-format.md")
        text = plan.read_text()
        h2 = self.tmp / "h2.md"
        h2.write_text(text.replace("# Phase 1 — old", "## Phase 2 — old", 1))
        colon = self.tmp / "colon.md"
        colon.write_text(text.replace("# Phase 1 — old", "# Phase 2: more", 1))
        for p, arg in ((h2, "## Phase 2"), (h2, "# Phase 2"), (colon, "# Phase 2"), (plan, "# Phase 9")):
            rc, out = self.cut(p, arg)
            self.assertEqual(rc, 3, f"{p.name} {arg}: {out}")
            self.assertIn("OLD-FORMAT", out)
        self.assertEqual(list(self.out.iterdir()), [])

    def test13d_old_format_before_template_parse(self):
        scratch = self.tmp / "refs"
        scratch.mkdir()
        for n in ("cutbriefs.py", "wavecheck.py", "brief-template.md"):
            shutil.copy(SCRIPT.parent / n, scratch / n)
        with open(scratch / "brief-template.md", "a") as f:
            f.write("\n1. **Bind the pattern** to code.\n")
        plan = self.plan("old-format.md")
        cmd = [sys.executable, "-I", str(scratch / "cutbriefs.py"), str(plan), "--phase", "m", "--out", str(self.out)]
        p = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertEqual(list(self.out.iterdir()), [])
        p = subprocess.run([*cmd[:3], str(FIX / "good.md"), *cmd[4:]], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(sorted(x.name for x in self.out.iterdir()), ["m-task-T1-brief.md", "m-task-T2-brief.md"])

    def test13b_nested_fence(self):
        plan = self.plan("nested-fence.md")
        rc, out = self.cut(plan)
        self.assertEqual(rc, 0, out)
        self.assertEqual([p.name for p in self.out.iterdir()], ["m-task-T1-brief.md"])
        self.assertNotIn("FAKE", self.brief("T1").read_text())

    def test14_existing_without_delta(self):
        plan = self.plan()
        self.brief("T1").write_bytes(b"hand written\n")
        rc, out = self.cut(plan)
        self.assertEqual(rc, 1, out)
        self.assertIn("EXISTING BRIEF WITHOUT DELTA", out)
        self.assertEqual(self.brief("T1").read_bytes(), b"hand written\n")
        self.assertEqual([p.name for p in self.out.iterdir()], ["m-task-T1-brief.md"])

    def test15_wavecheck_accepts_good(self):
        p = subprocess.run([sys.executable, "-I", str(WAVECHECK), str(FIX / "good.md")], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test16_template_sections(self):
        rc, out = run("--list-sections")
        self.assertEqual(rc, 0, out)
        names = [l.split(". ", 1)[1] for l in out.splitlines()]
        self.assertEqual(names, ["Goal", "Read first", "Owned files", "Don't touch", "Spec", "Tests", "Gate", "Report path"])

    def test17_dry_run(self):
        rc, out = self.cut(self.plan(), "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertIn("would write", out)
        self.assertEqual(list(self.out.iterdir()), [])

    def test18_warn(self):
        plan = self.plan()
        plan.write_text(plan.read_text(encoding="utf-8").replace("Body of T2 item 3.", "Body, see above for more.", 1),
                        encoding="utf-8", newline="")
        rc, out = self.cut(plan)
        self.assertEqual(rc, 0, out)
        self.assertIn("WARN T2", out)

    def test19_crlf_identity(self):
        plan = self.plan()
        plan.write_bytes(plan.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(self.cut(plan)[0], 0)
        self.assertEqual(run("--check", self.brief("T1"), "--plan", plan)[0], 0)
        self.assertTrue(self.brief("T1").read_bytes().startswith(b"<!-- brief:begin T1 -->\r\n"))

    def edit(self, plan, *pairs):
        s = plan.read_text(encoding="utf-8")
        for a, b in pairs:
            self.assertIn(a, s)
            s = s.replace(a, b, 1)
        plan.write_text(s, encoding="utf-8", newline="")

    def test20_no_bytecode(self):
        d = self.tmp / "iso"
        d.mkdir()
        for f in (SCRIPT, WAVECHECK, SCRIPT.parent / "brief-template.md"):
            shutil.copy(f, d / f.name)
        p = subprocess.run([sys.executable, "-I", str(d / "cutbriefs.py"), "--list-sections"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse((d / "__pycache__").exists())

    def test21_check_no_final_newline(self):
        plan = self.plan()
        plan.write_bytes(plan.read_bytes().rstrip(b"\n"))
        self.assertFalse(plan.read_bytes().endswith(b"\n"))
        rc, out = self.cut(plan)
        self.assertEqual(rc, 0, out)
        rc, out = run("--check", self.brief("T2"), "--plan", plan)
        self.assertEqual(rc, 0, out)
        self.assertIn("0 changes", out)

    def test22_check_fenced_end_marker(self):
        plan = self.plan()
        self.edit(plan, ("public: Foo()", "<!-- brief:end T1 -->"))
        rc, out = self.cut(plan)
        self.assertEqual(rc, 0, out)
        rc, out = run("--check", self.brief("T1"), "--plan", plan)
        self.assertEqual(rc, 0, out)

    def test23_check_multiphase_guard(self):
        good = self.plan().read_text(encoding="utf-8")
        b = good.replace("# Phase 1 \u2014 fixture plan", "# Phase 2 \u2014 b").replace(
            "Body of T2 item 1 Goal word.", "Phase two body.")
        plan = self.tmp / "multi.md"
        plan.write_text(good.replace("# Phase 1 \u2014 fixture plan", "# Phase 1 \u2014 a") + "\n" + b,
                        encoding="utf-8", newline="")
        rc, out = self.cut(plan, "# Phase 2")
        self.assertEqual(rc, 0, out)
        rc, out = run("--check", self.brief("T2"), "--plan", plan)
        self.assertEqual(rc, 1, out)
        self.assertIn("multi-phase", out)
        rc, out = run("--check", self.brief("T2"), "--plan", plan, "# Phase 2")
        self.assertEqual(rc, 0, out)

    def test24_id_cell_markup(self):
        plan = self.plan()
        self.edit(plan, ("| T1 Alpha thing |", "| **T1** Alpha thing |"), ("| T2 |", "| `T2` |"))
        rc, out = self.cut(plan)
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["m-task-T1-brief.md", "m-task-T2-brief.md"])

    def test25_case_duplicate_id(self):
        plan = self.plan()
        self.edit(plan, ("| T2 |", "| t1 |"), ("<!-- brief:begin T2 -->", "<!-- brief:begin t1 -->"),
                  ("<!-- brief:end T2 -->", "<!-- brief:end t1 -->"))
        rc, out = self.cut(plan)
        self.assertEqual(rc, 1, out)
        self.assertIn("DUPLICATE ID t1", out)
        self.assertEqual(list(self.out.iterdir()), [], out)

    def test26_all_markers_malformed(self):
        plan = self.plan()
        self.edit(plan, ("<!-- brief:begin T1 -->", "<!-- brief:begin  T1 -->"),
                  ("<!-- brief:begin T2 -->", "<!-- brief:begin  T2 -->"))
        rc, out = self.cut(plan)
        self.assertEqual(rc, 1, out)
        self.assertIn("BAD MARKER", out)
        self.assertNotIn("OLD-FORMAT", out)
        self.assertEqual(list(self.out.iterdir()), [], out)


    def test27_stale_recut_refused_force_keeps_delta(self):
        plan = self.plan()
        self.assertEqual(self.cut(plan)[0], 0)
        with open(self.brief("T1"), "a", encoding="utf-8", newline="") as f:
            f.write("- T1 delta line\n")
        before = {i: self.brief(i).read_bytes() for i in ("T1", "T2")}
        self.edit(plan, ("Body of T1 item 1 Goal word.", "Body of another phase."))
        rc, out = self.cut(plan)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"STALE BRIEF {self.brief('T1')}: spec part differs from plan block T1; "
                      "re-run with --force to overwrite (Delta is kept)", out)
        self.assertNotIn("STALE BRIEF " + str(self.brief("T2")), out)
        self.assertEqual({i: self.brief(i).read_bytes() for i in ("T1", "T2")}, before)
        rc, out = self.cut(plan, "--force")
        self.assertEqual(rc, 0, out)
        new = self.brief("T1").read_bytes().decode()
        self.assertIn("Body of another phase.", new)
        self.assertTrue(new.endswith(DELTA + "- T1 delta line\n"))
        self.assertEqual(run("--check", self.brief("T1"), "--plan", plan)[0], 0)
        self.assertEqual(self.cut(plan)[0], 0)

    def test28_stray_text_check_and_recut(self):
        plan = self.plan()
        self.assertEqual(self.cut(plan)[0], 0)
        b = self.brief("T2")
        text = b.read_bytes().decode()
        marker = "<!-- brief:end T2 -->\n"
        k = text.index(marker) + len(marker)
        b.write_bytes((text[:k] + "\nNOTE BETWEEN: T1 landed foo()\n" + text[k:]).encode())
        stray = b.read_bytes()
        rc, out = run("--check", b, "--plan", plan)
        self.assertEqual(rc, 1, out)
        lineno = stray.decode()[:stray.decode().index("NOTE BETWEEN")].count("\n") + 1
        self.assertIn(f"STRAY TEXT {b}:{lineno}", out)
        for extra in ((), ("--force",)):
            rc, out = self.cut(plan, *extra)
            self.assertEqual(rc, 1, out)
            self.assertIn(f"STRAY TEXT {b}:{lineno}", out)
            self.assertEqual(b.read_bytes(), stray)

    def test29_old_format_before_template_parse_inside_list(self):
        scratch = self.tmp / "refs"
        scratch.mkdir()
        for n in ("cutbriefs.py", "wavecheck.py", "brief-template.md"):
            shutil.copy(SCRIPT.parent / n, scratch / n)
        t = (scratch / "brief-template.md").read_text(encoding="utf-8")
        self.assertIn("3. **Owned files**", t)
        (scratch / "brief-template.md").write_text(t.replace("3. **Owned files**", "4. **Owned files**", 1), encoding="utf-8")
        cmd = [sys.executable, "-I", str(scratch / "cutbriefs.py"), "--phase", "m", "--out", str(self.out)]
        p = subprocess.run([*cmd[:3], str(self.plan("old-format.md")), *cmd[3:]], capture_output=True, text=True)
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertIn("OLD-FORMAT", p.stdout)
        p = subprocess.run([*cmd[:3], str(FIX / "good.md"), *cmd[3:]], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("template unreadable", p.stdout)
        self.assertEqual(list(self.out.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
