import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.prompt_bundle import (
    build_positive_prompt,
    validate_variables,
    write_prompt_bundle,
)


FIXTURE = Path(__file__).parent / "fixtures" / "sample-variables.json"


def sample_variables():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class PromptBundleTests(unittest.TestCase):
    def test_rejects_title_line_that_is_too_long(self):
        variables = sample_variables()
        variables["title_line_1"] = "这是一行明显超过硬限制而且缩略图无法读清的封面标题"
        errors = validate_variables(variables, "一份提示词封面教程")
        self.assertIn("title_line_1", " ".join(errors))

    def test_rejects_unknown_layout(self):
        variables = sample_variables()
        variables["layout_type"] = "poster"
        errors = validate_variables(variables, "一份提示词封面教程")
        self.assertIn("layout_type", " ".join(errors))

    def test_rejects_brand_name_when_brand_mode_none(self):
        variables = sample_variables()
        variables["brand_name"] = "不该出现"
        errors = validate_variables(variables, "一份提示词封面教程")
        self.assertIn("brand_name", " ".join(errors))

    def test_rejects_unbacked_numbers(self):
        variables = sample_variables()
        variables["result_value"] = "提升80%"
        errors = validate_variables(
            variables,
            "这次封面稳定多了，但没有统计提升比例。",
        )
        self.assertIn("80%", " ".join(errors))

    def test_allows_number_present_in_source(self):
        variables = sample_variables()
        variables["result_value"] = "提升80%"
        errors = validate_variables(
            variables,
            "实际测试中，识别率提升80%。",
        )
        self.assertNotIn("80%", " ".join(errors))

    def test_rejects_demo_leakage_not_present_in_source(self):
        variables = sample_variables()
        variables["result_value"] = "45%"
        errors = validate_variables(variables, "三份报告给了相同建议。")
        self.assertIn("Demo", " ".join(errors))

    def test_project_brand_is_not_treated_as_demo_leakage(self):
        variables = sample_variables()
        variables["brand_mode"] = "text"
        variables["brand_name"] = "小刘学AI"
        errors = validate_variables(variables, "我把提示词拆成五块。")
        self.assertNotIn("小刘学AI", " ".join(errors))

    def test_builds_doubao_ready_prompt_without_demo_content(self):
        variables = sample_variables()
        prompt = build_positive_prompt(
            variables,
            style_text="暖米白、橙黄、撕纸拼贴、粗体中文。",
            layout_text="左侧问题，右侧清单，中间单箭头。",
        )
        self.assertIn("1080×1440", prompt)
        self.assertIn("指定中文必须逐字准确", prompt)
        self.assertNotIn("45%", prompt)
        self.assertNotIn("小刘学AI", prompt)

    def test_full_layout_reference_keeps_only_selected_section(self):
        variables = sample_variables()
        variables["layout_type"] = "comparison"
        prompt = build_positive_prompt(
            variables,
            style_text="撕纸拼贴。",
            layout_text=(
                "# Layout families\n\n"
                "## Process\n\nPROCESS ONLY\n\n"
                "## Comparison\n\nCOMPARISON ONLY\n\n"
                "## Evidence\n\nEVIDENCE ONLY\n"
            ),
        )
        self.assertIn("COMPARISON ONLY", prompt)
        self.assertNotIn("PROCESS ONLY", prompt)
        self.assertNotIn("EVIDENCE ONLY", prompt)

    def test_writes_four_fallback_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            paths = write_prompt_bundle(
                output,
                sample_variables(),
                source_script="提示词要补齐主体、构图和限制。",
                style_text="暖米白、橙黄、撕纸拼贴。",
                layout_text="左侧问题，右侧清单。",
            )
            self.assertEqual(
                {path.name for path in paths},
                {
                    "cover-variables.json",
                    "cover-prompt.txt",
                    "negative-prompt.txt",
                    "layout-spec.md",
                },
            )
            for path in paths:
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 20)


if __name__ == "__main__":
    unittest.main()
