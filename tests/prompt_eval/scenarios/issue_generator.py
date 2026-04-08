import json
from dataclasses import dataclass, field
from pathlib import Path

from tests.prompt_eval.evaluators import Check, required, unwanted

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
    checks: list[Check] = field(default_factory=list)


_SECTION_HEADERS = [r"###\s+Task", r"###\s+Context", r"###\s+Acceptance Criteria"]

SCENARIOS: list[Scenario] = [
    Scenario(
        name="bug_fighters_out_of_map",
        focus="Fighter units traveling outside map boundaries and disappearing",
        messages=load_discord_messages("bug-fighters-out-of-map.json"),
        description="Bug report about fighters escaping map bounds",
        checks=[
            # unwanted(),
            required(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
            required(
                "replay",
                description="Must mention the supporting replay that was linked in chat"
            )
        ],
    ),
    Scenario(
        name="bug_qtpfs_assertions",
        focus="Fix Invalid QTPFS pathfinding assertions",
        messages=load_discord_messages("bug-QTPFS-assertions.json"),
        description="Pathfinding assertion bug — rendering circles and camera transitions are unrelated",
        checks=[
            unwanted(
                "DrawGroundCircle",
                "camera",
                description="Rendering circles and camera transitions are off-topic tangents",
            ),
            required(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
        ],
    ),
    Scenario(
        name="enhancement_graphics",
        focus="add physics params to the CBitmapMuzzleFlame CEG; float speed, float speedSpread, float airdrag, float3 gravity;",
        messages=load_discord_messages("enhancement-graphics.json", max_messages=300),
        description="CEG physics params enhancement — mushroom cloud discussion is unrelated",
        checks=[
            unwanted("mushroom", description="Mushroom cloud discussion is an unrelated tangent"),
            required(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
        ],
    ),
    Scenario(
        name="enhancement_multi_unit_transport",
        focus="Multi-unit transport Lua implementation issues",
        messages=load_discord_messages("enhancement-multi-unit-transport.json"),
        description="Transport system enhancement — cloak/dgun mechanics tangent is unrelated",
        checks=[
            unwanted("cloak", "dgun", description="Cloak/dgun mechanics are off-topic tangents"),
            required(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
        ],
    ),
    Scenario(
        name="enhancement_sync_testing",
        focus="Multi-platform sync testing (and also multi version)",
        messages=load_discord_messages("enhancement-multi-platform-sync-testing.json"),
        description="Sync testing infrastructure — animation/mesh rendering and flecs ECS discussion are unrelated",
        checks=[
            unwanted(
                "animation",
                "bones",
                "flecs",
                "mesh",
                description="Animation/mesh rendering and flecs ECS discussion are off-topic tangents",
            ),
            required(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
        ],
    ),
]
