import pytest

from src.input.file import read_messages


class TestReadMessages:
    def test_reads_first_n_lines(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: hello\nBob: world\nCharlie: hey\n")

        result = read_messages(f, start_line=1, count=2)

        assert result == ["Alice: hello", "Bob: world"]

    def test_reads_from_offset(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: one\nBob: two\nCharlie: three\nDave: four\n")

        result = read_messages(f, start_line=3, count=2)

        assert result == ["Charlie: three", "Dave: four"]

    def test_count_exceeds_available_lines(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: one\nBob: two\n")

        result = read_messages(f, start_line=1, count=50)

        assert result == ["Alice: one", "Bob: two"]

    def test_start_line_beyond_file_returns_empty(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: one\n")

        result = read_messages(f, start_line=100, count=5)

        assert result == []

    def test_start_line_is_one_indexed(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("first\nsecond\nthird\n")

        result = read_messages(f, start_line=1, count=1)

        assert result == ["first"]

    def test_empty_file_returns_empty(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("")

        result = read_messages(f, start_line=1, count=10)

        assert result == []

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            read_messages("/nonexistent/path.txt")

    def test_start_line_zero_raises(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: one\n")

        with pytest.raises(ValueError):
            read_messages(f, start_line=0)

    def test_negative_count_raises(self, tmp_path):
        f = tmp_path / "convo.txt"
        f.write_text("Alice: one\n")

        with pytest.raises(ValueError):
            read_messages(f, count=-1)
