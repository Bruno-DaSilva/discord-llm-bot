from src.transform.prompts import render_issue_prompt


class TestRenderIssuePrompt:
    def test_interpolates_topic(self):
        rendered = render_issue_prompt("login bug", "msg")
        assert "login bug" in rendered
        assert "{{ context.ticket_topic }}" not in rendered

    def test_interpolates_messages(self):
        rendered = render_issue_prompt("topic", "user1: broken\nuser2: same")
        assert "user1: broken" in rendered
        assert "user2: same" in rendered
        assert "{{ context.messages }}" not in rendered
