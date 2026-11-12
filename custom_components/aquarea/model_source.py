"""Parse heat pump model definitions from HeishaMon's Markdown table."""

from __future__ import annotations

import re

SOURCE_URL = "https://raw.githubusercontent.com/heishamon/HeishaMon/main/HeatPumpType.md"
SIGNATURE_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}\s+){9}[0-9A-Fa-f]{2}$")


def _cells(line: str) -> list[str] | None:
    line = line.strip()
    if not line.startswith("|"):
        return None
    return [cell.strip() for cell in line.strip("|").split("|")]


def _normalized_header(cell: str) -> str:
    return re.sub(r"[^a-z0-9]", "", cell.casefold())


def parse_heatpump_models(markdown: str) -> dict[str, str]:
    """Parse signatures and display labels from the upstream Markdown table."""
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
    column_names = {"bytes129138", "idu", "odu", "kit", "powerkw", "1ph3ph", "tcaphp"}
    for index, cell in enumerate(header):
        normalized = _normalized_header(cell)
        if normalized in column_names:
            if normalized in positions:
                raise ValueError(f"Duplicate HeatPumpType column: {cell}")
            positions[normalized] = index

    required_columns = column_names
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
