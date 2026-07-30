import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.validate_output import (
    promote_cover,
    validate_content,
    validate_dimensions,
    validate_text_boxes,
    write_qa_report,
)


class ValidateOutputTests(unittest.TestCase):
    def test_rejects_wrong_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "wrong.png"
            Image.new("RGB", (720, 1280), "white").save(image)
            failures = validate_dimensions(image)
            self.assertEqual(failures[0]["name"], "dimensions")
            self.assertFalse(failures[0]["passed"])

    def test_rejects_out_of_bounds_text_box(self):
        manifest = {
            "canvas": [1080, 1440],
            "safe_margin": 54,
            "text_boxes": [
                {
                    "role": "title_line_1",
                    "box": [20, 80, 700, 200],
                    "collision_group": "primary",
                }
            ],
        }
        failures = validate_text_boxes(manifest)
        self.assertIn("bounds", {item["name"] for item in failures})

    def test_rejects_overlapping_primary_text_boxes(self):
        manifest = {
            "canvas": [1080, 1440],
            "safe_margin": 54,
            "text_boxes": [
                {
                    "role": "a",
                    "box": [100, 100, 500, 300],
                    "collision_group": "primary",
                },
                {
                    "role": "b",
                    "box": [400, 200, 700, 400],
                    "collision_group": "primary",
                },
            ],
        }
        failures = validate_text_boxes(manifest)
        self.assertIn("overlap", {item["name"] for item in failures})

    def test_rejects_footer_overlapping_primary_text(self):
        manifest = {
            "canvas": [1080, 1440],
            "safe_margin": 54,
            "text_boxes": [
                {
                    "role": "title",
                    "box": [100, 100, 500, 300],
                    "collision_group": "primary",
                },
                {
                    "role": "footer",
                    "box": [400, 200, 700, 400],
                    "collision_group": "footer",
                },
            ],
        }
        checks = validate_text_boxes(manifest)
        overlap = next(item for item in checks if item["name"] == "overlap")
        self.assertFalse(overlap["passed"])
        self.assertIn("title+footer", overlap["details"])

    def test_rejects_critical_text_in_right_interaction_strip(self):
        manifest = {
            "canvas": [1080, 1440],
            "safe_margin": 54,
            "text_boxes": [
                {
                    "role": "result_value",
                    "box": [800, 100, 1000, 200],
                    "collision_group": "primary",
                }
            ],
        }
        checks = validate_text_boxes(manifest)
        strip = next(
            item for item in checks if item["name"] == "interaction_strip"
        )
        self.assertFalse(strip["passed"])
        self.assertIn("result_value", strip["details"])

    def test_rejects_demo_leakage(self):
        variables = self._valid_variables()
        variables["result_value"] = "45%"
        failures = validate_content(
            variables,
            source_script="三份报告给出相同建议。",
            config={"brand_mode": "none", "brand_name": ""},
        )
        self.assertTrue(
            any("Demo" in item["details"] for item in failures)
        )

    def test_rejects_wrong_brand(self):
        variables = self._valid_variables()
        variables["brand_mode"] = "text"
        variables["brand_name"] = "账号B"
        failures = validate_content(
            variables,
            source_script="提示词由主体、构图和限制组成。",
            config={"brand_mode": "text", "brand_name": "账号A"},
        )
        self.assertIn("brand", {item["name"] for item in failures})

    def test_passes_valid_cover_and_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            candidate = output / "cover-candidate.png"
            Image.new("RGB", (1080, 1440), "white").save(candidate)
            checks = validate_dimensions(candidate)
            report_path = write_qa_report(
                output,
                checks,
                delivery_mode="formal_cover",
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["passed"])

            cover = promote_cover(candidate, output, report)
            self.assertEqual(cover.name, "cover.png")
            self.assertTrue(cover.exists())

    def test_failed_cover_is_not_named_cover_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            candidate = output / "cover-candidate.png"
            Image.new("RGB", (720, 1280), "white").save(candidate)
            report = {
                "passed": False,
                "delivery_mode": "prompt_only",
                "checks": validate_dimensions(candidate),
            }
            with self.assertRaisesRegex(ValueError, "QA"):
                promote_cover(candidate, output, report)
            self.assertFalse((output / "cover.png").exists())

    @staticmethod
    def _valid_variables():
        return {
            "layout_type": "process",
            "top_label": "提示词避坑",
            "title_line_1": "提示词越写越长",
            "title_line_2": "封面反而更乱？",
            "highlight_phrase": "五块信息结构",
            "evidence_a": "主体",
            "evidence_b": "构图",
            "evidence_c": "限制",
            "result_label": "结果",
            "result_value": "稳定出图",
            "bottom_summary": "先补信息，再加形容词",
            "background_objects": ["纸条", "检查清单"],
            "accent_color": "orange",
            "brand_mode": "none",
            "brand_name": "",
        }


if __name__ == "__main__":
    unittest.main()
