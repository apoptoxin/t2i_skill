import unittest
from pathlib import Path

from scripts.doctor import audit_environment


SKILL_ROOT = Path(__file__).resolve().parents[1]


class DoctorTests(unittest.TestCase):
    def test_current_skill_copy_is_ready(self):
        report = audit_environment(SKILL_ROOT)
        self.assertTrue(report["ready"], report)

    def test_rejects_old_python(self):
        report = audit_environment(
            SKILL_ROOT,
            python_version=(3, 8, 18),
        )
        self.assertFalse(report["ready"])
        self.assertTrue(
            any("Python 3.9+" in fix for fix in report["fixes"])
        )

    def test_rejects_missing_pillow(self):
        report = audit_environment(
            SKILL_ROOT,
            pillow_available=False,
        )
        self.assertFalse(report["ready"])
        self.assertTrue(
            any("requirements.txt" in fix for fix in report["fixes"])
        )

    def test_skill_instructions_do_not_assume_skill_cwd(self):
        instructions = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("python3 scripts/", instructions)
        self.assertIn("<skill-root>/scripts/doctor.py", instructions)


if __name__ == "__main__":
    unittest.main()
