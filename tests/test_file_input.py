import pytest

from src.input.file import read_messages


class TestReadMessages:
    def test_reads_n_lines_ending_at_end_line(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: one\nBob: two\nCharlie: three\nDave: four\n")

        result = read_messages(f, end_line=3, count=2)

        assert result == ["Bob: two", "Charlie: three"]

    def test_end_line_1_returns_just_first_line(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("first\nsecond\nthird\n")

        result = read_messages(f, end_line=1, count=5)

        assert result == ["first"]

    def test_count_exceeds_available_lines_clamps_to_start(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: one\nBob: two\nCharlie: three\n")

        result = read_messages(f, end_line=3, count=50)

        assert result == ["Alice: one", "Bob: two", "Charlie: three"]

    def test_end_line_beyond_file_clamps_to_end(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: one\nBob: two\nCharlie: three\n")

        result = read_messages(f, end_line=100, count=5)

        assert result == ["Alice: one", "Bob: two", "Charlie: three"]

    def test_end_line_clamps_with_count(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("a\nb\nc\nd\ne\n")

        result = read_messages(f, end_line=100, count=2)

        assert result == ["d", "e"]

    def test_count_1_returns_single_line(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("first\nsecond\nthird\n")

        result = read_messages(f, end_line=2, count=1)

        assert result == ["second"]

    def test_empty_file_returns_empty(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("")

        result = read_messages(f, end_line=1, count=10)

        assert result == []

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            read_messages("/nonexistent/path.txt")

    def test_end_line_zero_raises(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: one\n")

        with pytest.raises(ValueError):
            read_messages(f, end_line=0)

    def test_negative_count_raises(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: one\n")

        with pytest.raises(ValueError):
            read_messages(f, count=-1)
