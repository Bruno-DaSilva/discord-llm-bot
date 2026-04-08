import json
from dataclasses import dataclass, field
from pathlib import Path

from tests.prompt_eval.evaluators import Check, required_and, unwanted

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
    repo: str | None = None
    runs: int = 5
    checks: list[Check] = field(default_factory=list)


_SECTION_HEADERS = [r"###\s+Task", r"###\s+Context", r"###\s+Acceptance Criteria"]

SCENARIOS: list[Scenario] = [
    Scenario(
        name="bug_fighters_out_of_map",
        focus="Fighter units traveling outside map boundaries and disappearing",
        messages=load_discord_messages("bug-fighters-out-of-map.json"),
        description="Bug report about fighters escaping map bounds",
        repo="beyond-all-reason/recoilengine",
        checks=[
            # unwanted(),
            required_and(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
            required_and("replay", name="replay_mentioned", description="Must mention the supporting replay that was linked in chat"),
            unwanted(r"backwards?\s*compat", name="no_backwards_compat", description="Output must NOT mention backwards compatibility as it's irrelevant"),
            unwanted("10,000", "10000", "10k", name="no_10k_units", description="Output must NOT mention the scale of the BAR RTS"),
        ],
    ),
    Scenario(
        name="bug_qtpfs_assertions",
        focus="Fix Invalid QTPFS pathfinding assertions",
        messages=load_discord_messages("bug-QTPFS-assertions.json"),
        description="Pathfinding assertion bug — rendering circles and camera transitions are unrelated",
        repo="beyond-all-reason/recoilengine",
        checks=[
            unwanted(
                "DrawGroundCircle",
                "camera",
                description="Rendering circles and camera transitions are off-topic tangents",
            ),
            required_and(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
            unwanted("replay", name="no_replay_mentioned", description="Must NOT mention the a replay as no relevant ones were linked in chat"),
            unwanted(r"backwards?\s*compat", name="no_backwards_compat", description="Output must NOT mention backwards compatibility as it's irrelevant"),
            unwanted("10,000", "10000", "10k", name="no_10k_units", description="Output must NOT mention the scale of the BAR RTS"),
        ],
    ),
    Scenario(
        name="enhancement_graphics",
        focus="add physics params to the CBitmapMuzzleFlame CEG; float speed, float speedSpread, float airdrag, float3 gravity;",
        messages=load_discord_messages("enhancement-graphics.json", max_messages=300),
        description="CEG physics params enhancement — mushroom cloud discussion is unrelated",
        repo="beyond-all-reason/recoilengine",
        checks=[
            unwanted("replay", name="no_replay_mentioned", description="Must NOT mention the a replay as no relevant ones were linked in chat"),
            required_and(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
            required_and(r"backwards?\s*compat", name="mention_backwards_compat", description="Output must mention backwards compatibility per the prompt amendments"),
            unwanted("10,000", "10000", "10k", name="no_10k_units", description="Output must NOT mention the scale of the BAR RTS"),
        ],
    ),
    Scenario(
        name="enhancement_multi_unit_transport",
        focus="Multi-unit transport Lua implementation issues",
        messages=load_discord_messages("enhancement-multi-unit-transport.json"),
        description="Transport system enhancement — cloak/dgun mechanics tangent is unrelated",
        repo="beyond-all-reason/recoilengine",
        checks=[
            unwanted("cloak", "dgun", description="Cloak/dgun mechanics are off-topic tangents"),
            unwanted("replay", name="no_replay_mentioned", description="Must NOT mention the a replay as no relevant ones were linked in chat"),
            required_and(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
            required_and(r"backwards?\s*compat", name="mention_backwards_compat", description="Output must mention backwards compatibility per the prompt amendments"),
            unwanted("10,000", "10000", "10k", name="no_10k_units", description="Output must NOT mention the scale of the BAR RTS"),
        ],
    ),
    Scenario(
        name="enhancement_sync_testing",
        focus="Multi-platform sync testing (and also multi version)",
        messages=load_discord_messages("enhancement-multi-platform-sync-testing.json"),
        description="Sync testing infrastructure — animation/mesh rendering and flecs ECS discussion are unrelated",
        repo="beyond-all-reason/recoilengine",
        checks=[
            # unwanted(),
            unwanted("replay", name="no_replay_mentioned", description="Must NOT mention the a replay as no relevant ones were linked in chat"),
            required_and(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
            # todo move this one to a llm eval since keyword isnt enough. depends what section its in.
            # unwanted(r"backwards?\s*compat", name="no_backwards_compat", description="Output must NOT mention backwards compatibility as it's irrelevant"),
            unwanted("10,000", "10000", "10k", name="no_10k_units", description="Output must NOT mention the scale of the BAR RTS"),
        ],
    ),
    Scenario(
        name="refactor_multithreaded_loading",
        focus="Multithreaded Game Loading",
        messages=load_discord_messages("refactor-multithreaded-loading.json"),
        description="MT loading refactor — PNG screenshot issues and scav/raptor conditional loading are unrelated",
        repo="beyond-all-reason/recoilengine",
        checks=[
            unwanted("screenshot", "alpha channel", description="PNG screenshot/alpha channel discussion is off-topic"),
            unwanted("replay", name="no_replay_mentioned", description="Must NOT mention the a replay as no relevant ones were linked in chat"),
            required_and(*_SECTION_HEADERS, description="Output must have Task/Context/Acceptance Criteria sections"),
            required_and(r"backwards?\s*compat", name="mention_backwards_compat", description="Output must mention backwards compatibility per the prompt amendments"),
            unwanted("10,000", "10000", "10k", name="no_10k_units", description="Output must NOT mention the scale of the BAR RTS"),
        ],
    ),
]
