from pathlib import Path


def read_messages(
    filepath: str | Path, end_line: int = 1, count: int = 20
) -> list[str]:
    if end_line < 1:
        raise ValueError(f"end_line must be >= 1, got {end_line}")
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count}")

    lines = Path(filepath).read_text().splitlines()
    end = min(end_line, len(lines))
    start = max(end - count, 0)
    return lines[start:end]
