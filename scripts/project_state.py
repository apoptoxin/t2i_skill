#!/usr/bin/env python3
"""Project-scoped configuration and adaptive cover-count state."""

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple


CONFIG_DIR = ".cover-skill"
CONFIG_NAME = "config.json"
STATE_NAME = "state.json"
VALID_BRAND_MODES = {"text", "none"}
VALID_RATIOS = {"3:4"}
VALID_VARIANTS = {1, 2}
VALID_FEEDBACK = {"accepted", "rejected"}


def find_project_root(start: Path, explicit: Optional[Path] = None) -> Path:
    """Return explicit root, nearest Git root, or the starting directory."""
    if explicit is not None:
        return explicit.expanduser().resolve()

    start = start.expanduser().resolve()
    current = start if start.is_dir() else start.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _validate_init(
    brand_mode: str,
    brand_name: str,
    default_ratio: str,
    output_dir: str,
    initial_variants: int,
) -> None:
    if brand_mode not in VALID_BRAND_MODES:
        raise ValueError("brand_mode must be 'text' or 'none'")
    if brand_mode == "text" and not brand_name.strip():
        raise ValueError("brand_name is required when brand_mode is 'text'")
    if brand_mode == "none" and brand_name:
        raise ValueError("brand_name must be empty when brand_mode is 'none'")
    if default_ratio not in VALID_RATIOS:
        raise ValueError("default_ratio must be '3:4' in version 1")
    if not output_dir.strip() or Path(output_dir).is_absolute():
        raise ValueError("output_dir must be a non-empty relative path")
    if initial_variants not in VALID_VARIANTS:
        raise ValueError("initial_variants must be 1 or 2")


def _write_json_atomic(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def init_project(
    project_root: Path,
    brand_mode: str,
    brand_name: str,
    default_ratio: str = "3:4",
    output_dir: str = "covers",
    initial_variants: int = 1,
) -> Tuple[Dict, Dict]:
    """Create this project's configuration and state files."""
    _validate_init(
        brand_mode,
        brand_name,
        default_ratio,
        output_dir,
        initial_variants,
    )
    project_root = project_root.expanduser().resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    config = {
        "brand_mode": brand_mode,
        "brand_name": brand_name.strip() if brand_mode == "text" else "",
        "default_ratio": default_ratio,
        "output_dir": output_dir,
        "initial_variants": initial_variants,
    }
    state = {
        "schema_version": 1,
        "rejected_streak": 0,
        "accepted_streak": 0,
        "default_variants": initial_variants,
    }
    config_dir = project_root / CONFIG_DIR
    _write_json_atomic(config_dir / CONFIG_NAME, config)
    _write_json_atomic(config_dir / STATE_NAME, state)
    return config, state


def _load_json(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(
            "Project is not initialized; missing {}".format(path)
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("{} must contain a JSON object".format(path))
    return value


def load_config(project_root: Path) -> Dict:
    return _load_json(
        project_root.expanduser().resolve() / CONFIG_DIR / CONFIG_NAME
    )


def load_state(project_root: Path) -> Dict:
    return _load_json(
        project_root.expanduser().resolve() / CONFIG_DIR / STATE_NAME
    )


def record_feedback(project_root: Path, outcome: str) -> Dict:
    """Update only streak counters and the adaptive default image count."""
    if outcome not in VALID_FEEDBACK:
        raise ValueError("outcome must be accepted or rejected")

    state = load_state(project_root)
    if outcome == "rejected":
        state["rejected_streak"] += 1
        state["accepted_streak"] = 0
        if state["rejected_streak"] >= 2:
            state["default_variants"] = 2
    else:
        state["accepted_streak"] += 1
        state["rejected_streak"] = 0
        if state["accepted_streak"] >= 2:
            state["default_variants"] = 1

    allowed = {
        "schema_version",
        "rejected_streak",
        "accepted_streak",
        "default_variants",
    }
    state = {key: state[key] for key in allowed}
    state_path = (
        project_root.expanduser().resolve() / CONFIG_DIR / STATE_NAME
    )
    _write_json_atomic(state_path, state)
    return state


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--project-root", required=True, type=Path)
    init_parser.add_argument(
        "--brand-mode", required=True, choices=sorted(VALID_BRAND_MODES)
    )
    init_parser.add_argument("--brand-name", default="")
    init_parser.add_argument("--default-ratio", default="3:4")
    init_parser.add_argument("--output-dir", default="covers")
    init_parser.add_argument("--initial-variants", type=int, default=1)

    feedback_parser = subparsers.add_parser("feedback")
    feedback_parser.add_argument("--project-root", required=True, type=Path)
    feedback_parser.add_argument(
        "--outcome", required=True, choices=sorted(VALID_FEEDBACK)
    )

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("--project-root", required=True, type=Path)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.command == "init":
        config, state = init_project(
            args.project_root,
            brand_mode=args.brand_mode,
            brand_name=args.brand_name,
            default_ratio=args.default_ratio,
            output_dir=args.output_dir,
            initial_variants=args.initial_variants,
        )
        result = {"config": config, "state": state}
    elif args.command == "feedback":
        result = record_feedback(args.project_root, args.outcome)
    else:
        result = {
            "config": load_config(args.project_root),
            "state": load_state(args.project_root),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
