#!/usr/bin/env python3
"""Sync HEATPUMP_MODELS_39 from HeishaMon's HeatPumpType.md."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_DIR = REPOSITORY_ROOT / "custom_components" / "aquarea"
MODELS_PATH = INTEGRATION_DIR / "models.py"
sys.path.insert(0, str(INTEGRATION_DIR))
from model_source import SOURCE_URL, parse_heatpump_models  # noqa: E402


def render_mapping(models: dict[str, str]) -> str:
    """Render a stable Python dictionary assignment."""
    lines = ["HEATPUMP_MODELS_39 = {"]
    lines.extend(
        f"    {json.dumps(signature)}: {json.dumps(label)},"
        for signature, label in models.items()
    )
    lines.append("}")
    return "\n".join(lines)


def replace_mapping(source: str, models: dict[str, str]) -> str:
    """Replace only the top-level HEATPUMP_MODELS_39 assignment."""
    tree = ast.parse(source)
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "HEATPUMP_MODELS_39"
            for target in node.targets
        )
    ]
    if len(assignments) != 1:
        raise ValueError(
            "Expected exactly one top-level HEATPUMP_MODELS_39 assignment, "
            f"found {len(assignments)}"
        )
    assignment = assignments[0]
    if not isinstance(assignment.value, ast.Dict):
        raise ValueError("HEATPUMP_MODELS_39 must be assigned a dictionary literal")

    lines = source.splitlines(keepends=True)
    start = assignment.lineno - 1
    end = assignment.end_lineno
    return "".join(lines[:start]) + render_mapping(models) + "\n" + "".join(lines[end:])


def fetch_source() -> str:
    request = Request(
        SOURCE_URL,
        headers={"User-Agent": "heishamon-homeassistant-model-sync"},
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report whether models.py needs an update without writing it",
    )
    args = parser.parse_args()

    try:
        models = parse_heatpump_models(fetch_source())
        current = MODELS_PATH.read_text(encoding="utf-8")
        updated = replace_mapping(current, models)
    except (OSError, URLError, UnicodeDecodeError, SyntaxError, ValueError) as error:
        print(f"Model sync failed: {error}", file=sys.stderr)
        return 1

    if updated == current:
        print("Heat pump models are already up to date.")
        return 0
    if args.check:
        print("Heat pump models are out of date.", file=sys.stderr)
        return 1

    MODELS_PATH.write_text(updated, encoding="utf-8")
    relative_path = MODELS_PATH.relative_to(REPOSITORY_ROOT)
    print(f"Updated {relative_path} with {len(models)} models.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
