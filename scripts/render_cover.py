#!/usr/bin/env python3
"""Overlay accurate Chinese typography on an irregular generated collage."""

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageOps


CANVAS = (1080, 1440)
SAFE_MARGIN = 54

INK = "#15130F"
OFF_WHITE = "#FFF9EA"
ORANGE = "#F05A28"
YELLOW = "#F4B900"
TEAL = "#2D8C82"


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    max_width: int,
    max_height: int,
    start_size: int,
    min_size: int,
    stroke_width: int = 0,
) -> ImageFont.FreeTypeFont:
    """Return the largest font fitting a single-line box."""
    for size in range(start_size, min_size - 1, -2):
        font = ImageFont.truetype(str(font_path), size)
        box = draw.textbbox(
            (0, 0), text, font=font, stroke_width=stroke_width
        )
        if box[2] - box[0] <= max_width and box[3] - box[1] <= max_height:
            return font
    raise ValueError(
        "Text {!r} cannot fit inside {}x{} at minimum size {}".format(
            text, max_width, max_height, min_size
        )
    )


def _load_background(background_path: Optional[Path]) -> Image.Image:
    if background_path is None:
        raise ValueError(
            "A generated collage background is required for formal rendering"
        )
    if not background_path.exists():
        raise FileNotFoundError(
            "background image not found: {}".format(background_path)
        )
    with Image.open(background_path) as source:
        return ImageOps.fit(
            source.convert("RGB"),
            CANVAS,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )


def _add_print_texture(image: Image.Image) -> None:
    """Add restrained deterministic grain without flattening the source art."""
    draw = ImageDraw.Draw(image, "RGBA")
    rng = random.Random(20260730)
    for _ in range(1050):
        x = rng.randrange(CANVAS[0])
        y = rng.randrange(CANVAS[1])
        alpha = rng.randrange(2, 9)
        color = (
            (20, 18, 14, alpha)
            if rng.random() < 0.72
            else (255, 250, 235, alpha)
        )
        draw.point((x, y), fill=color)


def _record_box(
    manifest: Dict,
    role: str,
    text: str,
    box: Sequence[int],
    target_box: Sequence[int],
    font_size: int,
    collision_group: str,
) -> None:
    manifest["text_boxes"].append(
        {
            "role": role,
            "text": text,
            "box": [int(value) for value in box],
            "target_box": [int(value) for value in target_box],
            "font_size": int(font_size),
            "collision_group": collision_group,
        }
    )


def _draw_text_in_box(
    draw: ImageDraw.ImageDraw,
    manifest: Dict,
    role: str,
    text: str,
    box: Sequence[int],
    font_path: Path,
    start_size: int,
    min_size: int,
    fill: str,
    stroke_fill: Optional[str] = None,
    stroke_width: int = 0,
    align: str = "center",
    collision_group: str = "primary",
) -> Optional[List[int]]:
    if not text:
        return None
    x1, y1, x2, y2 = map(int, box)
    font = fit_font(
        draw,
        text,
        font_path,
        x2 - x1,
        y2 - y1,
        start_size,
        min_size,
        stroke_width,
    )
    raw = draw.textbbox(
        (0, 0), text, font=font, stroke_width=stroke_width
    )
    width = raw[2] - raw[0]
    height = raw[3] - raw[1]
    if align == "left":
        px = x1 - raw[0]
    elif align == "right":
        px = x2 - width - raw[0]
    else:
        px = x1 + (x2 - x1 - width) / 2 - raw[0]
    py = y1 + (y2 - y1 - height) / 2 - raw[1]
    draw.text(
        (px, py),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill or fill,
    )
    actual = [
        int(value)
        for value in draw.textbbox(
            (px, py), text, font=font, stroke_width=stroke_width
        )
    ]
    _record_box(
        manifest,
        role,
        text,
        actual,
        (x1, y1, x2, y2),
        font.size,
        collision_group,
    )
    return actual


def _draw_torn_label(
    image: Image.Image,
    manifest: Dict,
    role: str,
    text: str,
    box: Sequence[int],
    font_path: Path,
    fill: str,
    text_fill: str,
    angle: float = 0,
    collision_group: str = "decoration",
) -> None:
    """Draw a slightly rotated paper label; never use it as a repeated card."""
    if not text:
        return
    x1, y1, x2, y2 = map(int, box)
    width, height = x2 - x1, y2 - y1
    patch = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    patch_draw = ImageDraw.Draw(patch)
    points = [
        (4, 9),
        (width - 11, 2),
        (width - 2, height - 12),
        (12, height - 2),
    ]
    patch_draw.polygon(points, fill=fill)
    font = fit_font(
        patch_draw,
        text,
        font_path,
        width - 28,
        height - 24,
        min(52, height - 18),
        26,
    )
    raw = patch_draw.textbbox((0, 0), text, font=font)
    tx = (width - (raw[2] - raw[0])) / 2 - raw[0]
    ty = (height - (raw[3] - raw[1])) / 2 - raw[1]
    patch_draw.text((tx, ty), text, font=font, fill=text_fill)
    rotated = patch.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    px = int(cx - rotated.width / 2)
    py = int(cy - rotated.height / 2)
    image.alpha_composite(rotated, (px, py))
    alpha = rotated.getchannel("A").getbbox()
    if alpha:
        actual = [
            px + alpha[0],
            py + alpha[1],
            px + alpha[2],
            py + alpha[3],
        ]
        _record_box(
            manifest,
            role,
            text,
            actual,
            (x1, y1, x2, y2),
            font.size,
            collision_group,
        )


def _draw_header(
    image: Image.Image,
    variables: Dict,
    manifest: Dict,
    font_path: Path,
) -> None:
    draw = ImageDraw.Draw(image)
    _draw_torn_label(
        image,
        manifest,
        "top_label",
        variables["top_label"],
        (60, 52, 360, 132),
        font_path,
        YELLOW,
        INK,
        angle=-2.2,
        collision_group="header",
    )
    if variables["brand_mode"] == "text":
        _draw_text_in_box(
            draw,
            manifest,
            "brand_name",
            variables["brand_name"],
            (690, 62, 920, 124),
            font_path,
            42,
            28,
            OFF_WHITE,
            INK,
            5,
            align="right",
            collision_group="header",
        )

    # Deliberately unequal line sizes and offsets preserve editorial tension.
    _draw_text_in_box(
        draw,
        manifest,
        "title_line_1",
        variables["title_line_1"],
        (62, 150, 900, 290),
        font_path,
        112,
        58,
        OFF_WHITE,
        INK,
        13,
        align="left",
    )
    _draw_text_in_box(
        draw,
        manifest,
        "title_line_2",
        variables["title_line_2"],
        (98, 292, 925, 455),
        font_path,
        134,
        64,
        YELLOW,
        INK,
        14,
        align="left",
    )
    draw.line((108, 470, 748, 458), fill=ORANGE, width=13)


def _draw_process(
    image: Image.Image,
    variables: Dict,
    manifest: Dict,
    font_path: Path,
    body_offset: int = 0,
) -> None:
    draw = ImageDraw.Draw(image)

    def shifted(box: Sequence[int]) -> Sequence[int]:
        return (
            box[0],
            box[1] + body_offset,
            box[2],
            box[3] + body_offset,
        )

    _draw_torn_label(
        image,
        manifest,
        "highlight_phrase",
        variables["highlight_phrase"],
        shifted((88, 556, 414, 648)),
        font_path,
        INK,
        OFF_WHITE,
        angle=-3.5,
    )
    targets = [
        (
            "evidence_a",
            variables["evidence_a"],
            shifted((620, 610, 910, 690)),
        ),
        (
            "evidence_b",
            variables["evidence_b"],
            shifted((590, 756, 900, 838)),
        ),
        (
            "evidence_c",
            variables["evidence_c"],
            shifted((630, 900, 915, 982)),
        ),
    ]
    for role, text, box in targets:
        _draw_text_in_box(
            draw,
            manifest,
            role,
            text,
            box,
            font_path,
            52,
            30,
            INK,
        )
    _draw_text_in_box(
        draw,
        manifest,
        "result_value",
        variables["result_value"],
        shifted((565, 1160, 900, 1260)),
        font_path,
        66,
        36,
        OFF_WHITE,
        INK,
        6,
    )


def _draw_comparison(
    image: Image.Image,
    variables: Dict,
    manifest: Dict,
    font_path: Path,
) -> None:
    draw = ImageDraw.Draw(image)
    _draw_torn_label(
        image,
        manifest,
        "evidence_a",
        variables["evidence_a"],
        (72, 535, 310, 620),
        font_path,
        TEAL,
        INK,
        angle=-4.5,
    )
    _draw_torn_label(
        image,
        manifest,
        "evidence_b",
        variables["evidence_b"],
        (575, 518, 845, 607),
        font_path,
        ORANGE,
        INK,
        angle=2.8,
    )
    _draw_torn_label(
        image,
        manifest,
        "highlight_phrase",
        variables["highlight_phrase"],
        (100, 1005, 510, 1095),
        font_path,
        INK,
        OFF_WHITE,
        angle=-2.0,
    )
    _draw_text_in_box(
        draw,
        manifest,
        "evidence_c",
        variables["evidence_c"],
        (520, 1010, 900, 1090),
        font_path,
        50,
        30,
        OFF_WHITE,
        INK,
        5,
    )
    _draw_text_in_box(
        draw,
        manifest,
        "result_value",
        variables["result_value"],
        (130, 1302, 875, 1380),
        font_path,
        64,
        36,
        INK,
    )


def _draw_evidence(
    image: Image.Image,
    variables: Dict,
    manifest: Dict,
    font_path: Path,
) -> None:
    draw = ImageDraw.Draw(image)
    boxes = [
        ("evidence_a", variables["evidence_a"], (84, 585, 326, 760)),
        ("evidence_b", variables["evidence_b"], (358, 560, 620, 745)),
        ("evidence_c", variables["evidence_c"], (650, 590, 905, 770)),
    ]
    for role, text, box in boxes:
        _draw_text_in_box(
            draw,
            manifest,
            role,
            text,
            box,
            font_path,
            70,
            36,
            ORANGE,
        )
    _draw_text_in_box(
        draw,
        manifest,
        "result_value",
        variables["result_value"],
        (255, 930, 815, 1060),
        font_path,
        86,
        42,
        INK,
    )
    _draw_torn_label(
        image,
        manifest,
        "highlight_phrase",
        variables["highlight_phrase"],
        (585, 1090, 905, 1182),
        font_path,
        OFF_WHITE,
        INK,
        angle=3.2,
    )


def _draw_footer(
    image: Image.Image,
    variables: Dict,
    manifest: Dict,
    font_path: Path,
) -> None:
    draw = ImageDraw.Draw(image)
    if variables["layout_type"] == "comparison":
        box = (285, 1150, 700, 1228)
        fill = OFF_WHITE
        stroke_fill = INK
        stroke_width = 4
        align = "center"
    else:
        box = (92, 1290, 900, 1365)
        fill = INK
        stroke_fill = OFF_WHITE
        stroke_width = 3
        align = "left"
    _draw_text_in_box(
        draw,
        manifest,
        "bottom_summary",
        variables["bottom_summary"],
        box,
        font_path,
        50,
        28,
        fill,
        stroke_fill,
        stroke_width,
        align=align,
        collision_group="footer",
    )


def render_cover(
    background_path: Optional[Path],
    variables: Dict,
    output_path: Path,
    font_path: Path,
    body_offset: int = 0,
) -> Dict:
    """Render a cover candidate and return text geometry for QA."""
    if not font_path.exists():
        raise FileNotFoundError("font file not found: {}".format(font_path))
    if "title_line_3" in variables:
        raise ValueError("title supports at most two lines")
    if variables.get("layout_type") not in {
        "process",
        "comparison",
        "evidence",
    }:
        raise ValueError("unknown layout_type")

    image = _load_background(background_path).convert("RGBA")
    _add_print_texture(image)
    manifest = {
        "canvas": list(CANVAS),
        "safe_margin": SAFE_MARGIN,
        "layout_type": variables["layout_type"],
        "body_offset": int(body_offset),
        "text_boxes": [],
    }
    _draw_header(image, variables, manifest, font_path)
    if variables["layout_type"] == "process":
        _draw_process(
            image,
            variables,
            manifest,
            font_path,
            body_offset=body_offset,
        )
    elif variables["layout_type"] == "comparison":
        _draw_comparison(image, variables, manifest, font_path)
    else:
        _draw_evidence(image, variables, manifest, font_path)
    _draw_footer(image, variables, manifest, font_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output_path, format="PNG", optimize=True)
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background", required=True, type=Path)
    parser.add_argument("--variables", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--body-offset",
        type=int,
        default=0,
        help="Shift process-layout body typography vertically in pixels.",
    )
    parser.add_argument(
        "--font",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "assets"
        / "fonts"
        / "SourceHanSansCN-Heavy.otf",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    variables = json.loads(args.variables.read_text(encoding="utf-8"))
    manifest = render_cover(
        args.background,
        variables,
        args.output,
        args.font,
        body_offset=args.body_offset,
    )
    manifest_path = args.manifest or args.output.with_suffix(
        ".manifest.json"
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "cover_candidate": str(args.output),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
