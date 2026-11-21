import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from scripts.exceptions import DataQualityError, get_db_engine
from scripts.logger import get_logger


PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSON_FILE = PROJECT_ROOT / "data" / "raw" / "repos.json"

logger = get_logger("validate_clean")


def load_expected_batch_ids() -> set[int]:
    """Read repository IDs from the current extraction batch."""
    if not JSON_FILE.exists():
        raise DataQualityError(f"Extraction batch file not found: {JSON_FILE}")

    with JSON_FILE.open("r", encoding="utf-8") as file:
        repositories = json.load(file)

    return {repo["id"] for repo in repositories if isinstance(repo, dict) and "id" in repo}


def validate_data() -> None:
    """Run comprehensive schema, temporal, and batch-reconciliation checks on repositories_clean."""
    engine = get_db_engine()
    try:
        df = pd.read_sql("SELECT * FROM repositories_clean", engine)
        db_now = pd.read_sql(text("SELECT NOW() AS current_ts"), engine).loc[0, "current_ts"]
    except SQLAlchemyError as exc:
        raise DataQualityError(f"Failed to query repositories_clean: {exc}") from exc
    finally:
        engine.dispose()

    total_rows = len(df)
    logger.info("Starting clean data validation (total rows: %s)", total_rows)

    if total_rows == 0:
        raise DataQualityError("Validation failed: repositories_clean is empty.")

    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True)
    now_utc = pd.to_datetime(db_now, utc=True)

    checks = {
        "duplicate repository IDs": int(df["id"].duplicated().sum()),
        "missing or blank repository names": int(df["name"].fillna("").str.strip().eq("").sum()),
        "missing or blank languages": int(df["language"].fillna("").str.strip().eq("").sum()),
        "negative star counts": int((df["stars"] < 0).sum()),
        "negative fork counts": int((df["forks"] < 0).sum()),
        "null or negative repository_age_days": int(
            (df["repository_age_days"].isna() | (df["repository_age_days"] < 0)).sum()
        ),
        "records with updated_at earlier than created_at": int(
            (df["updated_at"] < df["created_at"]).sum()
        ),
        "records with future created_at timestamps": int((df["created_at"] > now_utc).sum()),
    }

    failures = []
    for label, count in checks.items():
        if count > 0:
            logger.error("FAIL: Found %s %s.", count, label)
            failures.append(f"{count} {label}")
        else:
            logger.info("PASS: 0 %s.", label)

    # Batch completeness reconciliation against data/raw/repos.json
    expected_ids = load_expected_batch_ids()
    present_ids = set(df["id"].tolist())
    missing_batch_ids = expected_ids - present_ids

    if missing_batch_ids:
        msg = f"{len(missing_batch_ids)} extracted batch IDs missing from repositories_clean"
        logger.error("FAIL: %s (sample: %s)", msg, list(missing_batch_ids)[:5])
        failures.append(msg)
    else:
        logger.info("PASS: All %s extracted batch IDs verified in repositories_clean.", len(expected_ids))

    if failures:
        raise DataQualityError("Clean data validation failed due to: " + "; ".join(failures))

    logger.info("Clean data validation passed (%s total repositories verified).", total_rows)


def main() -> None:
    try:
        validate_data()
    except Exception:
        logger.exception("Clean validation stage aborted.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()