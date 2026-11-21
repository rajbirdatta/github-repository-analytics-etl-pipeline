import pandas as pd
import pytest

from scripts.exceptions import TransformationError
from scripts.transform import transform_data


def test_transform_data_cleans_and_calculates_age():
    raw_df = pd.DataFrame([
        {
            "id": 1,
            "name": "analytics-repo",
            "language": None,
            "stars": 10,
            "forks": 2,
            "created_at": "2026-11-11T00:00:00Z",
            "updated_at": "2026-11-21T00:00:00Z",
        }
    ])

    clean_df = transform_data(raw_df)
    assert len(clean_df) == 1
    assert clean_df.loc[0, "language"] == "Unknown"
    assert clean_df.loc[0, "repository_age_days"] >= 0


def test_transform_data_rejects_negative_stars():
    bad_df = pd.DataFrame([
        {
            "id": 1,
            "name": "bad-repo",
            "language": "Python",
            "stars": -1,
            "forks": 0,
            "created_at": "2026-11-11T00:00:00Z",
            "updated_at": "2026-11-21T00:00:00Z",
        }
    ])

    with pytest.raises(TransformationError, match="star counts cannot be negative"):
        transform_data(bad_df)


def test_transform_data_rejects_duplicate_ids():
    dup_df = pd.DataFrame([
        {"id": 7, "name": "a", "language": "Python", "stars": 1, "forks": 0, "created_at": "2026-11-11T00:00:00Z", "updated_at": "2026-11-21T00:00:00Z"},
        {"id": 7, "name": "b", "language": "Python", "stars": 2, "forks": 0, "created_at": "2026-11-11T00:00:00Z", "updated_at": "2026-11-21T00:00:00Z"},
    ])

    with pytest.raises(TransformationError, match="Duplicate repository IDs"):
        transform_data(dup_df)