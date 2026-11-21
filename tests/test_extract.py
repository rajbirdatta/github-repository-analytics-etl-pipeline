from datetime import timezone
import pytest

from scripts.exceptions import ExtractionError
from scripts.extract import (
    deduplicate_repositories,
    parse_github_timestamp,
    validate_repository,
)


def test_parse_github_timestamp_valid():
    dt = parse_github_timestamp("2026-11-21T10:30:00Z")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2026


def test_parse_github_timestamp_invalid():
    assert parse_github_timestamp("") is None
    assert parse_github_timestamp("not-a-timestamp") is None


def test_validate_repository_passes_valid_record():
    repo = {
        "id": 101,
        "name": "etl-pipeline",
        "full_name": "user/etl-pipeline",
        "updated_at": "2026-11-21T08:00:00Z",
    }
    validate_repository(repo)  # Should not raise


@pytest.mark.parametrize(
    "bad_repo",
    [
        "not-a-dict",
        {"id": "101", "name": "a", "full_name": "u/a", "updated_at": "2026-11-21T08:00:00Z"},
        {"id": True, "name": "a", "full_name": "u/a", "updated_at": "2026-11-21T08:00:00Z"},
        {"id": 101, "name": "", "full_name": "u/a", "updated_at": "2026-11-21T08:00:00Z"},
        {"id": 101, "name": "a", "full_name": "u/a", "updated_at": "invalid-date"},
    ],
)
def test_validate_repository_rejects_invalid_records(bad_repo):
    with pytest.raises(ExtractionError):
        validate_repository(bad_repo)


def test_deduplicate_repositories_keeps_newest():
    older = {"id": 1, "name": "repo1", "full_name": "u/repo1", "updated_at": "2026-11-20T10:00:00Z", "stargazers_count": 5}
    newer = {"id": 1, "name": "repo1", "full_name": "u/repo1", "updated_at": "2026-11-21T10:00:00Z", "stargazers_count": 12}
    other = {"id": 2, "name": "repo2", "full_name": "u/repo2", "updated_at": "2026-11-21T09:00:00Z", "stargazers_count": 3}

    result = deduplicate_repositories([older, other, newer])
    assert len(result) == 2
    by_id = {r["id"]: r for r in result}
    assert by_id[1]["stargazers_count"] == 12