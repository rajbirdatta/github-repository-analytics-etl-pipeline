import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from scripts.exceptions import TransformationError, get_db_engine
from scripts.logger import get_logger


PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSON_FILE = PROJECT_ROOT / "data" / "raw" / "repos.json"

logger = get_logger("transform")

CLEAN_COLUMNS = [
    "id",
    "name",
    "language",
    "stars",
    "forks",
    "created_at",
    "updated_at",
    "repository_age_days",
]


def read_batch_ids() -> list[int]:
    """Get IDs from the current extraction batch."""
    if not JSON_FILE.exists():
        raise TransformationError(f"Extraction batch file missing: {JSON_FILE}")

    try:
        with JSON_FILE.open("r", encoding="utf-8") as file:
            repositories = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise TransformationError(f"Could not parse {JSON_FILE}: {exc}") from exc

    if not isinstance(repositories, list):
        raise TransformationError("Expected data/raw/repos.json to contain a JSON list.")

    ids = []
    for repo in repositories:
        if not isinstance(repo, dict) or not isinstance(repo.get("id"), int):
            raise TransformationError("Each repository in the batch must have an integer ID.")
        ids.append(repo["id"])

    if len(ids) != len(set(ids)):
        raise TransformationError("Duplicate repository IDs found in extraction batch.")

    return ids


def load_batch_data(engine, repository_ids: list[int]) -> pd.DataFrame:
    """Read only raw rows touched by this extraction batch."""
    if not repository_ids:
        return pd.DataFrame(columns=[
            "id", "name", "language", "stars", "forks", "created_at", "updated_at"
        ])

    query = text("""
        SELECT id, name, language, stars, forks, created_at, updated_at
        FROM repositories_raw
        WHERE id = ANY(:repository_ids)
    """)
    try:
        return pd.read_sql(query, engine, params={"repository_ids": repository_ids})
    except SQLAlchemyError as exc:
        raise TransformationError(f"Failed querying repositories_raw: {exc}") from exc


def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the current batch and calculate repository age."""
    if df.empty:
        return pd.DataFrame(columns=CLEAN_COLUMNS)

    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True, errors="coerce")
    df["language"] = df["language"].fillna("Unknown")
    df["name"] = df["name"].fillna("")

    today = pd.Timestamp.now(tz="UTC").normalize()
    df["repository_age_days"] = (today - df["created_at"].dt.normalize()).dt.days

    clean_df = df[CLEAN_COLUMNS].copy()

    if clean_df["id"].isna().any():
        raise TransformationError("Repository IDs cannot be NULL.")
    if clean_df["id"].duplicated().any():
        raise TransformationError("Duplicate repository IDs found in source batch.")
    if clean_df["name"].eq("").any():
        raise TransformationError("Repository names cannot be missing.")
    if (clean_df["stars"].dropna() < 0).any():
        raise TransformationError("Repository star counts cannot be negative.")
    if (clean_df["forks"].dropna() < 0).any():
        raise TransformationError("Repository fork counts cannot be negative.")
    if (clean_df["repository_age_days"].dropna() < 0).any():
        raise TransformationError("Repository creation dates cannot be in the future.")

    return clean_df


def upsert_data(engine, clean_df: pd.DataFrame) -> None:
    """Insert new rows and update existing clean rows in one transaction."""
    if clean_df.empty:
        logger.info("No changed repository rows to transform or upsert.")
        return

    insert_query = text("""
        INSERT INTO repositories_clean (
            id, name, language, stars, forks, created_at, updated_at,
            repository_age_days
        )
        VALUES (
            :id, :name, :language, :stars, :forks, :created_at, :updated_at,
            :repository_age_days
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            language = EXCLUDED.language,
            stars = EXCLUDED.stars,
            forks = EXCLUDED.forks,
            created_at = EXCLUDED.created_at,
            updated_at = EXCLUDED.updated_at,
            repository_age_days = EXCLUDED.repository_age_days
    """)

    records = clean_df.to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None
            elif isinstance(value, pd.Timestamp):
                record[key] = value.to_pydatetime()
            elif hasattr(value, "item"):
                record[key] = value.item()

    try:
        with engine.begin() as connection:
            connection.execute(insert_query, records)
    except SQLAlchemyError as exc:
        raise TransformationError(f"Failed upserting into repositories_clean: {exc}") from exc

    logger.info("Successfully upserted %s clean repository records.", len(records))


def main() -> None:
    engine = None
    try:
        engine = get_db_engine()
        repository_ids = read_batch_ids()
        logger.info("Current extraction batch contains %s IDs.", len(repository_ids))

        df = load_batch_data(engine, repository_ids)
        logger.info("Loaded %s matching raw rows for transformation.", len(df))

        if len(df) != len(repository_ids):
            raise TransformationError(
                f"Expected {len(repository_ids)} raw rows for this batch, found {len(df)}."
            )

        clean_df = transform_data(df)
        if not clean_df.empty:
            logger.info("Transformed data preview:\n%s", clean_df.head().to_string(index=False))

        upsert_data(engine, clean_df)
        logger.info("Batch transformation and loading completed successfully.")
    except Exception:
        logger.exception("Transformation stage aborted.")
        raise SystemExit(1)
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()