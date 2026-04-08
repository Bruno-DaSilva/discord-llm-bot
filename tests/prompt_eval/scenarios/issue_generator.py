import json
from dataclasses import dataclass, field
from pathlib import Path

CONVOS_DIR = Path(__file__).resolve().parents[3] / "convos"


def load_discord_messages(filename: str, *, max_messages: int | None = None) -> list[str]:
    """Load a Discord API JSON response and format as 'Author: content' strings.

    Messages are reversed (API returns newest-first) and empty-content
    messages are skipped.  Uses global_name with fallback to username.
    """
    with open(CONVOS_DIR / filename) as f:
        raw = json.load(f)

    raw.reverse()

    formatted: list[str] = []
    for msg in raw:
        content = msg.get("content", "").strip()
        if not content:
            continue
        author = msg.get("author", {})
        name = author.get("global_name") or author.get("username", "unknown")
        formatted.append(f"{name}: {content}")

    if max_messages is not None:
        formatted = formatted[-max_messages:]

    return formatted


@dataclass
class Scenario:
    name: str
    focus: str
    messages: list[str]
    description: str = ""
    runs: int = 3
    unwanted_keywords: list[str] = field(default_factory=list)
    required_keywords: list[str] = field(default_factory=list)


_SECTION_HEADERS = [r"###\s+Task", r"###\s+Context", r"###\s+Acceptance Criteria"]

SCENARIOS: list[Scenario] = [
    Scenario(
        name="bug_fighters_out_of_map",
        focus="Fighter units traveling outside map boundaries and disappearing",
        messages=load_discord_messages("bug-fighters-out-of-map.json"),
        description="Bug report about fighters escaping map bounds — replay file troubleshooting is unrelated",
        unwanted_keywords=["replay", "demo"],
        required_keywords=_SECTION_HEADERS,
    ),
    Scenario(
        name="bug_qtpfs_assertions",
        focus="Fix Invalid QTPFS pathfinding assertions",
        messages=load_discord_messages("bug-QTPFS-assertions.json"),
        description="Pathfinding assertion bug — rendering circles and camera transitions are unrelated",
        unwanted_keywords=["DrawGroundCircle", "camera"],
        required_keywords=_SECTION_HEADERS,
    ),
    Scenario(
        name="enhancement_graphics",
        focus="add physics params to the CBitmapMuzzleFlame CEG; float speed, float speedSpread, float airdrag, float3 gravity;",
        messages=load_discord_messages("enhancement-graphics.json", max_messages=300),
        description="CEG physics params enhancement — mushroom cloud discussion is unrelated",
        unwanted_keywords=["mushroom"],
        required_keywords=_SECTION_HEADERS,
    ),
    Scenario(
        name="enhancement_multi_unit_transport",
        focus="Multi-unit transport Lua implementation issues",
        messages=load_discord_messages("enhancement-multi-unit-transport.json"),
        description="Transport system enhancement — cloak/dgun mechanics tangent is unrelated",
        unwanted_keywords=["cloak", "dgun"],
        required_keywords=_SECTION_HEADERS,
    ),
    Scenario(
        name="enhancement_sync_testing",
        focus="Multi-platform sync testing (and also multi version)",
        messages=load_discord_messages("enhancement-multi-platform-sync-testing.json"),
        description="Sync testing infrastructure — animation/mesh rendering and flecs ECS discussion are unrelated",
        unwanted_keywords=["animation", "bones", "flecs", "mesh"],
        required_keywords=_SECTION_HEADERS,
    ),
]
