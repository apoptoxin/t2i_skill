#!/usr/bin/env python3
"""Validate a cover run and promote only passing candidates to cover.png."""

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List, Sequence

from PIL import Image

try:
    from scripts.project_state import load_config
    from scripts.prompt_bundle import validate_variables
except ImportError:
    from project_state import load_config
    from prompt_bundle import validate_variables


EXPECTED_SIZE = (1080, 1440)
RIGHT_INTERACTION_STRIP_RATIO = 0.12
CRITICAL_TEXT_ROLES = {
    "title_line_1",
    "title_line_2",
    "highlight_phrase",
    "evidence_a",
    "evidence_b",
    "evidence_c",
    "result_label",
    "result_value",
    "bottom_summary",
}
PROMPT_ONLY_FILES = {
    "cover-variables.json",
    "cover-prompt.txt",
    "negative-prompt.txt",
    "layout-spec.md",
}


def _check(name: str, passed: bool, details: str) -> Dict:
    return {"name": name, "passed": bool(passed), "details": details}


def validate_dimensions(image_path: Path) -> List[Dict]:
    if not image_path.exists():
        return [_check("dimensions", False, "image file is missing")]
    with Image.open(image_path) as image:
        size = image.size
    return [
        _check(
            "dimensions",
            size == EXPECTED_SIZE,
            "{}x{}".format(size[0], size[1]),
        )
    ]


def _overlap(a: Sequence[int], b: Sequence[int]) -> bool:
    return not (
        a[2] <= b[0]
        or b[2] <= a[0]
        or a[3] <= b[1]
        or b[3] <= a[1]
    )


def validate_text_boxes(manifest: Dict) -> List[Dict]:
    checks = []
    canvas = manifest.get("canvas", list(EXPECTED_SIZE))
    safe = int(manifest.get("safe_margin", 54))
    boxes = manifest.get("text_boxes", [])
    bounds_failures = []
    for item in boxes:
        left, top, right, bottom = item["box"]
        if (
            left < safe
            or top < safe
            or right > canvas[0] - safe
            or bottom > canvas[1] - safe
            or right <= left
            or bottom <= top
        ):
            bounds_failures.append(item["role"])
    checks.append(
        _check(
            "bounds",
            not bounds_failures,
            "inside safe area"
            if not bounds_failures
            else "out of bounds: {}".format(", ".join(bounds_failures)),
        )
    )

    overlaps = []
    for index, item in enumerate(boxes):
        for other in boxes[index + 1 :]:
            if _overlap(item["box"], other["box"]):
                overlaps.append("{}+{}".format(item["role"], other["role"]))
    checks.append(
        _check(
            "overlap",
            not overlaps,
            "no text overlaps"
            if not overlaps
            else "overlaps: {}".format(", ".join(overlaps)),
        )
    )

    strip_start = canvas[0] * (1 - RIGHT_INTERACTION_STRIP_RATIO)
    strip_failures = [
        item["role"]
        for item in boxes
        if item.get("role") in CRITICAL_TEXT_ROLES
        and item["box"][2] > strip_start
    ]
    checks.append(
        _check(
            "interaction_strip",
            not strip_failures,
            "no critical text in rightmost 12%"
            if not strip_failures
            else "critical text in rightmost 12%: {}".format(
                ", ".join(strip_failures)
            ),
        )
    )
    return checks


def validate_content(
    variables: Dict,
    source_script: str,
    config: Dict,
) -> List[Dict]:
    checks = []
    variable_errors = validate_variables(variables, source_script)
    for error in variable_errors:
        name = "content"
        if "Demo" in error:
            name = "demo_leakage"
        elif "number" in error:
            name = "unbacked_number"
        checks.append(_check(name, False, error))

    expected_mode = config.get("brand_mode")
    expected_name = config.get("brand_name", "")
    actual_mode = variables.get("brand_mode")
    actual_name = variables.get("brand_name", "")
    brand_ok = expected_mode == actual_mode and expected_name == actual_name
    checks.append(
        _check(
            "brand",
            brand_ok,
            "matches project config"
            if brand_ok
            else "expected {}:{!r}, got {}:{!r}".format(
                expected_mode,
                expected_name,
                actual_mode,
                actual_name,
            ),
        )
    )
    if not variable_errors:
        checks.append(_check("content", True, "variables match source"))
    return checks


def write_qa_report(
    output_dir: Path,
    checks: List[Dict],
    delivery_mode: str,
) -> Path:
    if delivery_mode not in {"formal_cover", "prompt_only"}:
        raise ValueError("delivery_mode must be formal_cover or prompt_only")
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "passed": all(item.get("passed") is True for item in checks),
        "delivery_mode": delivery_mode,
        "checks": checks,
    }
    path = output_dir / "qa-report.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def promote_cover(
    candidate_path: Path,
    output_dir: Path,
    report: Dict,
) -> Path:
    if not report.get("passed"):
        raise ValueError("QA failed; candidate cannot be promoted")
    if report.get("delivery_mode") != "formal_cover":
        raise ValueError("Only formal_cover delivery can create cover.png")
    destination = output_dir / "cover.png"
    shutil.copy2(candidate_path, destination)
    return destination


def _prompt_files_check(run_dir: Path) -> Dict:
    present = {path.name for path in run_dir.iterdir() if path.is_file()}
    missing = sorted(PROMPT_ONLY_FILES - present)
    return _check(
        "prompt_bundle",
        not missing,
        "complete"
        if not missing
        else "missing: {}".format(", ".join(missing)),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--source-script", type=Path)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    run_dir = args.run_dir.resolve()
    variables = json.loads(
        (run_dir / "cover-variables.json").read_text(encoding="utf-8")
    )
    if args.source_script:
        source_script = args.source_script.read_text(encoding="utf-8")
    else:
        source_path = run_dir / "source-script.txt"
        source_script = (
            source_path.read_text(encoding="utf-8")
            if source_path.exists()
            else ""
        )
    checks = validate_content(
        variables,
        source_script,
        load_config(args.project_root),
    )

    candidate = run_dir / "cover-candidate.png"
    manifest_path = run_dir / "cover-candidate.manifest.json"
    if candidate.exists() and manifest_path.exists():
        delivery_mode = "formal_cover"
        checks.extend(validate_dimensions(candidate))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checks.extend(validate_text_boxes(manifest))
    else:
        delivery_mode = "prompt_only"
        checks.append(_prompt_files_check(run_dir))

    report_path = write_qa_report(run_dir, checks, delivery_mode)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    cover = None
    if report["passed"] and delivery_mode == "formal_cover":
        cover = promote_cover(candidate, run_dir, report)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "delivery_mode": delivery_mode,
                "qa_report": str(report_path),
                "cover": str(cover) if cover else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
