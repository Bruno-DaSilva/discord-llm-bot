from pathlib import Path

import yaml


def load_extra_context(path: Path) -> dict[str, list[str]]:
    """Load per-repo extra context from a YAML file.

    Returns an empty dict when the file does not exist.
    Raises ValueError on malformed content.
    """
    if not path.is_file():
        return {}

    raw = yaml.safe_load(path.read_text())
    if raw is None:
        return {}

    if not isinstance(raw, dict):
        raise ValueError(f"extra context: root must be a mapping, got {type(raw).__name__}")

    for key, value in raw.items():
        if not isinstance(value, list):
            raise ValueError(
                f"extra context: value for '{key}' must be a list, got {type(value).__name__}"
            )
        for i, item in enumerate(value):
            if not isinstance(item, str):
                raise ValueError(
                    f"extra context: item {i} in '{key}' must be a string, got {type(item).__name__}"
                )

    return raw
