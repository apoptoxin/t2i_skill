import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.render_cover import CANVAS, SAFE_MARGIN, render_cover


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "assets" / "fonts" / "SourceHanSansCN-Heavy.otf"
FIXTURE = Path(__file__).parent / "fixtures" / "sample-variables.json"


def sample_variables(layout_type="process"):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["layout_type"] = layout_type
    return data


def boxes_overlap(a, b):
    return not (
        a[2] <= b[0]
        or b[2] <= a[0]
        or a[3] <= b[1]
        or b[3] <= a[1]
    )


class RenderCoverTests(unittest.TestCase):
    def _render(
        self,
        layout_type="process",
        mutate=None,
        body_offset=0,
    ):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        background = root / "background.png"
        output = root / "cover-candidate.png"
        Image.new("RGB", CANVAS, "#F4E7CE").save(background)
        variables = sample_variables(layout_type)
        if mutate:
            mutate(variables)
        manifest = render_cover(
            background,
            variables,
            output,
            FONT,
            body_offset=body_offset,
        )
        return output, manifest

    def test_renders_exact_douyin_dimensions(self):
        output, manifest = self._render()
        with Image.open(output) as image:
            self.assertEqual(image.size, (1080, 1440))
        self.assertEqual(manifest["canvas"], [1080, 1440])

    def test_all_text_boxes_stay_inside_safe_area(self):
        _, manifest = self._render()
        for item in manifest["text_boxes"]:
            left, top, right, bottom = item["box"]
            self.assertGreaterEqual(left, SAFE_MARGIN)
            self.assertGreaterEqual(top, SAFE_MARGIN)
            self.assertLessEqual(right, CANVAS[0] - SAFE_MARGIN)
            self.assertLessEqual(bottom, CANVAS[1] - SAFE_MARGIN)

    def test_renders_each_layout_without_primary_overlap(self):
        for layout in ("process", "comparison", "evidence"):
            with self.subTest(layout=layout):
                _, manifest = self._render(layout)
                primary = [
                    item
                    for item in manifest["text_boxes"]
                    if item["collision_group"] == "primary"
                ]
                for index, item in enumerate(primary):
                    for other in primary[index + 1 :]:
                        self.assertFalse(
                            boxes_overlap(item["box"], other["box"]),
                            "{} overlaps {}".format(
                                item["role"], other["role"]
                            ),
                        )

    def test_brand_none_draws_no_brand_text(self):
        _, manifest = self._render()
        self.assertNotIn(
            "brand_name",
            {item["role"] for item in manifest["text_boxes"]},
        )

    def test_brand_text_draws_configured_name_only(self):
        def mutate(variables):
            variables["brand_mode"] = "text"
            variables["brand_name"] = "测试账号"

        _, manifest = self._render(mutate=mutate)
        brands = [
            item["text"]
            for item in manifest["text_boxes"]
            if item["role"] == "brand_name"
        ]
        self.assertEqual(brands, ["测试账号"])

    def test_title_is_at_most_two_lines(self):
        def mutate(variables):
            variables["title_line_3"] = "不该存在"

        with self.assertRaisesRegex(ValueError, "title"):
            self._render(mutate=mutate)

    def test_process_body_offset_does_not_move_header(self):
        _, base = self._render(body_offset=0)
        _, shifted = self._render(body_offset=60)
        base_boxes = {item["role"]: item["box"] for item in base["text_boxes"]}
        shifted_boxes = {
            item["role"]: item["box"] for item in shifted["text_boxes"]
        }
        self.assertEqual(
            base_boxes["title_line_1"],
            shifted_boxes["title_line_1"],
        )
        self.assertEqual(
            shifted_boxes["evidence_a"][1] - base_boxes["evidence_a"][1],
            60,
        )

    def test_missing_font_is_a_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "cover.png"
            with self.assertRaisesRegex(FileNotFoundError, "font"):
                render_cover(
                    None,
                    sample_variables(),
                    output,
                    Path(tmp) / "missing.otf",
                )


if __name__ == "__main__":
    unittest.main()
