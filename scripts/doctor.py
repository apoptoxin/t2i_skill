#!/usr/bin/env python3
"""Audit whether this copied Skill is ready to run on the current computer."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


MINIMUM_PYTHON = (3, 9)
MINIMUM_PILLOW = (10, 4)
MAXIMUM_PILLOW = (12, 0)
EXPECTED_HASHES = {
    "assets/fonts/SourceHanSansCN-Heavy.otf":
        "b63729574723ece8c090ca5fc31cf1d4dd970ca13dcba95f6c1cfe0c4e9501f4",
    "assets/fonts/OFL.txt":
        "6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2",
}
REQUIRED_FILES = (
    "SKILL.md",
    "requirements.txt",
    "agents/openai.yaml",
    "assets/examples/process-demo-debranded.png",
    "assets/examples/comparison-demo-debranded.png",
    "assets/examples/evidence-demo-debranded.png",
    "assets/fonts/SourceHanSansCN-Heavy.otf",
    "assets/fonts/OFL.txt",
    "references/few-shot-guide.md",
    "references/layouts.md",
    "references/style-system.md",
    "references/variable-schema.md",
    "scripts/project_state.py",
    "scripts/prompt_bundle.py",
    "scripts/render_cover.py",
    "scripts/validate_output.py",
)


def _check(name: str, passed: bool, details: str) -> Dict:
    return {"name": name, "passed": bool(passed), "details": details}


def _version_tuple(value: str) -> Tuple[int, ...]:
    numbers = []
    for part in value.split("."):
        digits = "".join(character for character in part if character.isdigit())
        if not digits:
            break
        numbers.append(int(digits))
    return tuple(numbers)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_environment(
    skill_root: Optional[Path] = None,
    python_version: Optional[Sequence[int]] = None,
    pillow_version: Optional[str] = None,
    pillow_available: Optional[bool] = None,
) -> Dict:
    """Return a machine-readable readiness report for a copied Skill."""
    root = (
        Path(skill_root).resolve()
        if skill_root is not None
        else Path(__file__).resolve().parents[1]
    )
    checks: List[Dict] = []
    fixes: List[str] = []

    actual_python = tuple(python_version or sys.version_info[:3])
    python_ok = actual_python >= MINIMUM_PYTHON
    checks.append(
        _check(
            "python",
            python_ok,
            "{}.{}.{}".format(*actual_python[:3]),
        )
    )
    if not python_ok:
        fixes.append("Install Python 3.9+ and rerun the doctor.")

    missing = [
        relative
        for relative in REQUIRED_FILES
        if not (root / relative).is_file()
    ]
    checks.append(
        _check(
            "bundled_files",
            not missing,
            "complete"
            if not missing
            else "missing: {}".format(", ".join(missing)),
        )
    )
    if missing:
        fixes.append(
            "Copy the complete generate-douyin-cover directory again."
        )

    hash_failures = []
    for relative, expected in EXPECTED_HASHES.items():
        path = root / relative
        if path.is_file() and _sha256(path) != expected:
            hash_failures.append(relative)
    checks.append(
        _check(
            "licensed_font_integrity",
            not hash_failures,
            "font and license match bundled checksums"
            if not hash_failures
            else "checksum mismatch: {}".format(
                ", ".join(hash_failures)
            ),
        )
    )
    if hash_failures:
        fixes.append(
            "Restore the bundled font and OFL.txt from the original Skill."
        )

    pil_module = None
    if pillow_available is None:
        try:
            import PIL as pil_module  # type: ignore
            from PIL import Image, ImageFont  # noqa: F401

            pillow_available = True
        except (ImportError, OSError):
            pillow_available = False
    elif pillow_available:
        try:
            import PIL as pil_module  # type: ignore
        except (ImportError, OSError):
            pillow_available = False

    checks.append(
        _check(
            "pillow_installed",
            bool(pillow_available),
            "installed" if pillow_available else "not available",
        )
    )
    if not pillow_available:
        fixes.append(
            "Run: python3 -m pip install -r <skill-root>/requirements.txt"
        )

    resolved_pillow_version = (
        pillow_version
        if pillow_version is not None
        else getattr(pil_module, "__version__", "")
    )
    pillow_range_ok = False
    if pillow_available:
        parsed = _version_tuple(resolved_pillow_version)
        pillow_range_ok = (
            parsed >= MINIMUM_PILLOW and parsed < MAXIMUM_PILLOW
        )
        checks.append(
            _check(
                "pillow_version",
                pillow_range_ok,
                resolved_pillow_version or "unknown",
            )
        )
        if not pillow_range_ok:
            fixes.append(
                "Run: python3 -m pip install -r "
                "<skill-root>/requirements.txt"
            )

    assets_ok = False
    asset_details = "skipped because Pillow is unavailable"
    if pillow_available and pillow_range_ok and not missing:
        try:
            from PIL import Image, ImageFont

            for relative in (
                "assets/examples/process-demo-debranded.png",
                "assets/examples/comparison-demo-debranded.png",
                "assets/examples/evidence-demo-debranded.png",
            ):
                with Image.open(root / relative) as image:
                    image.verify()
                    width, height = image.size
                    if width * 4 != height * 3:
                        raise ValueError(
                            "{} is not 3:4".format(relative)
                        )
            ImageFont.truetype(
                str(root / "assets/fonts/SourceHanSansCN-Heavy.otf"),
                size=64,
            )
            assets_ok = True
            asset_details = "three 3:4 demos and bundled font load correctly"
        except (OSError, ValueError) as error:
            asset_details = str(error)
            fixes.append(
                "Restore unreadable image/font assets from the original Skill."
            )
    checks.append(_check("asset_readability", assets_ok, asset_details))

    fixes = list(dict.fromkeys(fixes))
    return {
        "ready": all(item["passed"] for item in checks),
        "skill_root": str(root),
        "checks": checks,
        "fixes": fixes,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    report = audit_environment(args.skill_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
