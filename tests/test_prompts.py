from src.transform.prompts import render_issue_prompt


class TestRenderIssuePrompt:
    def test_interpolates_focus(self):
        rendered = render_issue_prompt("login bug", "msg")
        assert "login bug" in rendered
        assert "{{ context.ticket_focus }}" not in rendered

    def test_interpolates_messages(self):
        rendered = render_issue_prompt("focus", "user1: broken\nuser2: same")
        assert "user1: broken" in rendered
        assert "user2: same" in rendered
        assert "{{ context.messages }}" not in rendered


class TestRenderIssuePromptAmendments:
    def test_no_amendments_unchanged(self):
        base = render_issue_prompt("topic", "msg")
        assert render_issue_prompt("topic", "msg", amendments=[]) == base

    def test_amendments_appended(self):
        rendered = render_issue_prompt(
            "topic", "msg", amendments=["Focus on engine internals"]
        )
        assert "<extra_instructions>" in rendered
        assert "- Focus on engine internals" in rendered
        assert "</extra_instructions>" in rendered

    def test_multiple_amendments(self):
        amendments = ["First instruction", "Second instruction"]
        rendered = render_issue_prompt("topic", "msg", amendments=amendments)
        assert "- First instruction" in rendered
        assert "- Second instruction" in rendered
