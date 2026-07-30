import json
import tempfile
import unittest
from pathlib import Path

from scripts.project_state import (
    find_project_root,
    init_project,
    load_config,
    load_state,
    record_feedback,
)


class ProjectStateTests(unittest.TestCase):
    def test_init_is_project_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_a = root / "a"
            project_b = root / "b"
            project_a.mkdir()
            project_b.mkdir()

            init_project(project_a, brand_mode="text", brand_name="账号A")
            init_project(project_b, brand_mode="none", brand_name="")

            self.assertEqual(load_config(project_a)["brand_name"], "账号A")
            self.assertEqual(load_config(project_b)["brand_mode"], "none")
            self.assertFalse((root / ".cover-skill").exists())

    def test_default_variants_changes_after_feedback_streaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            init_project(project, brand_mode="none", brand_name="")

            state = record_feedback(project, "rejected")
            self.assertEqual(state["default_variants"], 1)
            state = record_feedback(project, "rejected")
            self.assertEqual(state["default_variants"], 2)

            state = record_feedback(project, "accepted")
            self.assertEqual(state["default_variants"], 2)
            state = record_feedback(project, "accepted")
            self.assertEqual(state["default_variants"], 1)

    def test_state_does_not_store_content_or_brand(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            init_project(project, brand_mode="text", brand_name="测试账号")
            state = load_state(project)
            state_text = json.dumps(state, ensure_ascii=False)

            self.assertNotIn("测试账号", state_text)
            self.assertEqual(
                set(state),
                {
                    "schema_version",
                    "rejected_streak",
                    "accepted_streak",
                    "default_variants",
                },
            )

    def test_find_project_root_uses_nearest_git_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            nested = project / "a" / "b"
            nested.mkdir(parents=True)
            (project / ".git").mkdir()

            self.assertEqual(find_project_root(nested), project.resolve())

    def test_explicit_project_root_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explicit = root / "chosen"
            explicit.mkdir()
            self.assertEqual(
                find_project_root(root, explicit=explicit),
                explicit.resolve(),
            )

    def test_text_brand_requires_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "brand_name"):
                init_project(Path(tmp), brand_mode="text", brand_name="")

    def test_invalid_feedback_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            init_project(project, brand_mode="none", brand_name="")
            with self.assertRaisesRegex(ValueError, "accepted.*rejected"):
                record_feedback(project, "maybe")


if __name__ == "__main__":
    unittest.main()
