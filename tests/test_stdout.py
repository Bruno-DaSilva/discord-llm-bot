from src.output.stdout import send_stdout


class TestSendStdout:
    def test_prints_title_and_body(self, capsys):
        send_stdout("Bug: login broken", "Users can't log in after update.")
        captured = capsys.readouterr()
        assert "Bug: login broken" in captured.out
        assert "Users can't log in after update." in captured.out

    def test_separates_title_and_body(self, capsys):
        send_stdout("Title", "Body")
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) >= 2
