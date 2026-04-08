from src.utils.repo import normalize_repo


class TestNormalizeRepo:
    def test_lowercase(self):
        assert normalize_repo("Owner/Repo") == "owner/repo"

    def test_strips_trailing_slash(self):
        assert normalize_repo("owner/repo/") == "owner/repo"

    def test_combined(self):
        assert normalize_repo("Owner/Repo/") == "owner/repo"

    def test_strips_leading_slash(self):
        assert normalize_repo("/owner/repo") == "owner/repo"

    def test_already_normalized(self):
        assert normalize_repo("owner/repo") == "owner/repo"
