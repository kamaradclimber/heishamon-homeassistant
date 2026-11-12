#!/usr/bin/env python3
"""Sync HEATPUMP_MODELS_39 from HeishaMon's HeatPumpType.md."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

SOURCE_URL = "https://raw.githubusercontent.com/heishamon/HeishaMon/main/HeatPumpType.md"
MODELS_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "aquarea"
    / "models.py"
)
SIGNATURE_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}\s+){9}[0-9A-Fa-f]{2}$")


def _cells(line: str) -> list[str] | None:
    line = line.strip()
    if not line.startswith("|"):
        return None
    return [cell.strip() for cell in line.strip("|").split("|")]


def _normalized_header(cell: str) -> str:
    return re.sub(r"[^a-z0-9]", "", cell.casefold())


def parse_heatpump_models(markdown: str) -> dict[str, str]:
    """Parse the model signatures and labels from HeishaMon's Markdown table."""
    rows = markdown.splitlines()
    header_index = None
    header: list[str] | None = None
    for index, line in enumerate(rows):
        cells = _cells(line)
        if cells and "bytes129138" in map(_normalized_header, cells):
            header_index = index
            header = cells
            break

    if header is None or header_index is None:
        raise ValueError("Could not find the HeatPumpType table header")

    positions: dict[str, int] = {}
    for index, cell in enumerate(header):
        normalized = _normalized_header(cell)
        if normalized in {"bytes129138", "idu", "odu", "kit", "powerkw", "1ph3ph", "tcaphp"}:
            if normalized in positions:
                raise ValueError(f"Duplicate HeatPumpType column: {cell}")
            positions[normalized] = index

    required_columns = {
        "bytes129138",
        "idu",
        "odu",
        "kit",
        "powerkw",
        "1ph3ph",
        "tcaphp",
    }
    if missing := required_columns - positions.keys():
        raise ValueError(f"HeatPumpType table is missing columns: {', '.join(sorted(missing))}")

    models: dict[str, str] = {}
    for line_number, line in enumerate(rows[header_index + 1 :], start=header_index + 2):
        cells = _cells(line)
        if not cells:
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if max(positions.values()) >= len(cells):
            raise ValueError(f"Malformed HeatPumpType table row at line {line_number}")

        signature = re.sub(r"\s+", " ", cells[positions["bytes129138"]]).upper()
        if not SIGNATURE_RE.fullmatch(signature):
            raise ValueError(f"Invalid 10-byte model signature at line {line_number}: {signature!r}")

        candidates = [cells[positions[column]] for column in ("idu", "odu", "kit")]
        model_name = next((value for value in candidates if value.casefold() != "monoblock"), None)
        if not model_name:
            raise ValueError(f"No model name found at line {line_number}")

        details = [
            model_name,
            cells[positions["powerkw"]],
            cells[positions["1ph3ph"]],
            cells[positions["tcaphp"]],
        ]
        label = " ".join(value.strip() for value in details)
        if signature in models:
            raise ValueError(f"Duplicate model signature at line {line_number}: {signature}")
        models[signature] = label

    if not models:
        raise ValueError("No heat pump models found in the HeatPumpType table")
    return models


def render_mapping(models: dict[str, str]) -> str:
    """Render a stable Python dictionary assignment."""
    lines = ["HEATPUMP_MODELS_39 = {"]
    lines.extend(f"    {json.dumps(signature)}: {json.dumps(label)}," for signature, label in models.items())
    lines.append("}")
    return "\n".join(lines)


def replace_mapping(source: str, models: dict[str, str]) -> str:
    """Replace only the top-level HEATPUMP_MODELS_39 assignment."""
    tree = ast.parse(source)
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "HEATPUMP_MODELS_39" for target in node.targets)
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
    request = Request(SOURCE_URL, headers={"User-Agent": "heishamon-homeassistant-model-sync"})
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
    print(f"Updated {MODELS_PATH.relative_to(Path(__file__).resolve().parents[1])} with {len(models)} models.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
