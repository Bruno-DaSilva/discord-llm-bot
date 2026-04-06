from dataclasses import dataclass, field


@dataclass
class Scenario:
    name: str
    focus: str
    messages: list[str]
    description: str = ""
    runs: int = 3
    unwanted_keywords: list[str] = field(default_factory=list)
    required_keywords: list[str] = field(default_factory=list)


SCENARIOS: list[Scenario] = [
    Scenario(
        name="simple_bug_report",
        description="Straightforward bug — should not mention backwards compatibility or migration",
        focus="Login page returns 500 error after deploy",
        messages=[
            "alice: login page is giving me a 500 error since the last deploy",
            "bob: same here, started about 30 minutes ago",
            "alice: it works fine on staging though",
        ],
        unwanted_keywords=[r"backwards?\s+compatib", "migration"],
        required_keywords=["### Task", "### Context", "### Acceptance Criteria"],
    ),
    Scenario(
        name="api_versioning_discussion",
        description="Migration with explicit backwards compat discussion — topic is relevant",
        focus="Migrate REST API endpoints from v1 to v2",
        messages=[
            "dev1: we need to migrate the /users and /orders endpoints to v2",
            "dev2: what about backwards compat for existing mobile clients?",
            "dev1: we'll keep v1 around for 6 months with a deprecation notice",
            "dev3: sounds good, let's document the breaking changes too",
        ],
        required_keywords=["### Task", "### Context", "### Acceptance Criteria"],
    ),
    Scenario(
        name="new_feature_request",
        description="Pure new feature — should not mention backwards compat or migration",
        focus="Add dark mode toggle to settings page",
        messages=[
            "designer: users have been requesting dark mode for months",
            "dev1: should be doable, we already have CSS variables set up",
            "designer: here's the figma link with the color palette",
        ],
        unwanted_keywords=[r"backwards?\s+compatib", "migration", r"breaking\s+change"],
        required_keywords=["### Task", "### Context", "### Acceptance Criteria"],
    ),
]
