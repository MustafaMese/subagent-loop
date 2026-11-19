import subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests/check_split.py"
TARGET = 32345

OLD_SKILL = [
    "# Skill",
    "## Waves",
    "wave text",
    "## Plan mode",
    "plan text",
    "## Finish",
    "finish text",
]
ANCH = ["## Waves", "## Plan mode", "## Sizing", "## Per task", "## Phase boundary", "## Finish", "**Brakes"]
REF_LINES = ["references/plan-time.md", "references/per-task.md", "references/finish.md"]


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class T(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.old = Path(self._td.name) / "old"
        self.new = Path(self._td.name) / "new"
        w(self.old / "SKILL.md", "\n".join(OLD_SKILL) + "\n")

    def good_new(self, skill_extra=None, finish_extra=None):
        # anchors and reference paths are new lines in SKILL.md
        w(self.new / "SKILL.md", "\n".join(OLD_SKILL[:6]) + "\n" + "\n".join(ANCH[2:5] + ["**Brakes"] + REF_LINES)
          + "\n" + "\n".join(skill_extra or []) + ("\n" if skill_extra else "") + "")
        w(self.new / "references/finish.md", "\n".join([OLD_SKILL[6]] + (finish_extra or [])) + "\n")
        w(self.new / "references/direct-verify.md", "## Per task\n## Plan\n## Finish\n")
        w(self.new / "references/brief-template.md", "b\n")

    def run_check(self, *extra):
        p = subprocess.run([sys.executable, "-I", str(SCRIPT), "--old-dir", str(self.old),
                            "--skill-dir", str(self.new), *extra], capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    def test_a_clean_split(self):
        self.good_new()
        rc, out = self.run_check()
        self.assertEqual(rc, 0, out)
        self.assertIn("EDITED/REMOVED old lines: none", out)
        self.assertIn("coverage: ok, reachability: ok, size: ok", out)

    def test_a_plant_violation_goes_red(self):
        self.good_new()
        w(self.new / "references/finish.md", "finish reworded\n")
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)

    def test_b_reworded_line(self):
        self.good_new()
        t = (self.new / "SKILL.md").read_text().replace("plan text", "plan text!")
        w(self.new / "SKILL.md", t)
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("old 5: plan text", out)
        self.assertIn("coverage: FAIL", out)

    def test_c_duplicated_line(self):
        self.good_new(finish_extra=["wave text"])
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("DUPLICATED old lines:\n  old 3: wave text", out)

    def test_d_size_arithmetic(self):
        self.good_new()
        w(self.new / "references/plan-time.md", "p" * 100)
        w(self.new / "references/per-task.md", "q" * 200)
        w(self.new / "references/brief-template.md", "b" * 50)
        w(self.old / "references/brief-template.md", "c" * 30)
        w(self.new / "references/direct-verify.md",
          "## Per task (x)\n" + "t" * 20 + "\n## Plan (y)\n" + "u" * 30 + "\n## Finish (z)\n" + "v" * 40 + "\n")
        w(self.old / "references/direct-verify.md", "## Plan (y)\n" + "u" * 10 + "\n## Finish (z)\n")
        w(self.new / "references/multi-session.md", "m" * 70)
        w(self.old / "references/multi-session.md", "n" * 90)
        sk = (self.new / "SKILL.md").stat().st_size
        fn = (self.new / "references/finish.md").stat().st_size
        osk = (self.old / "SKILL.md").stat().st_size
        plan_sec = len("## Plan (y)\n") + 30 + 1
        fin_sec = len("## Finish (z)\n") + 40 + 1
        pt_sec_old = len("## Plan (y)\n") + 10 + 1
        rc, out = self.run_check()
        self.assertEqual(rc, 0, out)
        row = lambda n: [c.strip() for c in next(l for l in out.splitlines() if l.startswith(f"| {n} |")).split("|")[1:-1]]
        self.assertEqual(row(1)[3:5], [f"{sk:,}", f"{osk:,}"])
        self.assertEqual(row(2)[3:5], [f"{sk + 100 + plan_sec:,}", f"{osk + pt_sec_old:,}"])
        self.assertEqual(row(3)[3], f"{sk + 200:,}")
        self.assertEqual(row(4)[3:5], [f"{sk + 250:,}", f"{osk + 30:,}"])
        self.assertEqual(row(5)[3], f"{sk + fn + 200 + fin_sec:,}")
        self.assertEqual(row(6)[3], f"{sk + 200 + len('## Per task (x)') + 1 + 20 + 1:,}")
        self.assertEqual(row(9)[3], f"{sk + 100 + plan_sec + 200 + fn + fin_sec:,}")
        self.assertEqual(row(7)[3], f"{sk + 250 + len('## Per task (x)') + 1 + 20 + 1:,}")
        self.assertEqual(row(8)[3:5], [f"{sk + 270:,}", f"{osk + 90:,}"])
        self.assertEqual(row(5)[4], f"{osk + len('## Finish (z)') + 1:,}")
        self.assertEqual(row(9)[4], f"{osk + pt_sec_old + len('## Finish (z)') + 1:,}")

    def test_e_padded_past_target(self):
        self.good_new()
        w(self.new / "references/per-task.md", "x" * TARGET)
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("size: FAIL", out)

    def test_f_missing_anchor(self):
        self.good_new()
        t = (self.new / "SKILL.md").read_text().replace("## Sizing\n", "")
        w(self.new / "SKILL.md", t)
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("MISSING in SKILL.md: ## Sizing", out)
        self.assertIn("reachability: FAIL", out)

    def test_g_old_skill_unreadable(self):
        self.good_new()
        empty = Path(self._td.name) / "empty"
        empty.mkdir()
        p = subprocess.run([sys.executable, "-I", str(SCRIPT), "--old-dir", str(empty),
                            "--skill-dir", str(self.new)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("ERROR old SKILL.md unreadable", p.stderr)

    def test_g2_bad_base_ref(self):
        self.good_new()
        nogit = Path(self._td.name) / "nogit"
        nogit.mkdir()
        p = subprocess.run([sys.executable, "-I", str(SCRIPT), "--repo", str(nogit), "--base", "deadbeef",
                            "--skill-dir", str(self.new)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("ERROR old SKILL.md unreadable", p.stderr)

    def test_h_missing_dv_section(self):
        self.good_new()
        w(self.new / "references/direct-verify.md", "## Per task\n## Plan\n")
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("MISSING section direct-verify §Finish", out)
        self.assertIn("size: FAIL", out)

    def test_h2_missing_brief_template(self):
        self.good_new()
        (self.new / "references/brief-template.md").unlink()
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("MISSING references/brief-template.md", out)
        self.assertIn("size: FAIL", out)

    def test_i_map(self):
        self.good_new()
        rc, out = self.run_check("--map")
        self.assertEqual(rc, 0, out)
        self.assertIn("7 \u2192 references/finish.md:1", out)
        self.assertIn("  references/finish.md: 1", out)

    def test_j_heading_level_anchor(self):
        self.good_new()
        t = (self.new / "SKILL.md").read_text().replace("## Sizing\n", "### Sizing\n")
        w(self.new / "SKILL.md", t)
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("MISSING in SKILL.md: ## Sizing", out)

    def test_k_fenced_heading_keeps_section(self):
        self.good_new()
        w(self.new / "references/direct-verify.md",
          "## Per task\n## Plan\n## Finish\n```\n## fake\n```\nxx\n")
        w(self.old / "references/direct-verify.md", "## Finish\n")
        sk_finish = len("## Finish\n```\n## fake\n```\nxx\n")
        rc, out = self.run_check()
        self.assertEqual(rc, 0, out)
        sk = (self.new / "SKILL.md").stat().st_size
        fn = (self.new / "references/finish.md").stat().st_size
        row5 = [c.strip() for c in next(l for l in out.splitlines() if l.startswith("| 5 |")).split("|")[1:-1]]
        self.assertEqual(row5[3], f"{sk + fn + 0 + sk_finish:,}")


if __name__ == "__main__":
    unittest.main()
