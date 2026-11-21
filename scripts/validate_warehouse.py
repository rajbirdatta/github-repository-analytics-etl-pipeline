from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from scripts.exceptions import DataQualityError, get_db_engine
from scripts.logger import get_logger


logger = get_logger("validate_warehouse")


def run_check(connection, description: str, query: str) -> bool:
    """Run a scalar quality check and fail if its result is nonzero."""
    result = connection.execute(text(query)).scalar_one()

    if result != 0:
        logger.error("FAIL: %s — %s issue(s) found.", description, result)
        return False

    logger.info("PASS: %s", description)
    return True


def main() -> None:
    engine = None
    all_passed = True

    try:
        engine = get_db_engine()
        with engine.connect() as connection:
            logger.info("Starting warehouse data quality checks.")

            checks = [
                (
                    "Clean repositories missing from the repository dimension",
                    """
                    SELECT COUNT(*)
                    FROM repositories_clean c
                    LEFT JOIN dim_repository d
                        ON d.repository_id = c.id
                    WHERE d.repository_id IS NULL
                    """,
                ),
                (
                    "Language dimension rows with blank or whitespace-only names",
                    """
                    SELECT COUNT(*)
                    FROM dim_language
                    WHERE language_name IS NULL
                       OR TRIM(language_name) = ''
                    """,
                ),
                (
                    "Today's snapshot count dropped below previous snapshot date",
                    """
                    SELECT CASE
                        WHEN COALESCE(
                            (SELECT COUNT(*) FROM fact_repository_metrics_daily WHERE snapshot_date = CURRENT_DATE),
                            0
                        ) < COALESCE(
                            (SELECT COUNT(*) FROM fact_repository_metrics_daily
                             WHERE snapshot_date = (
                                 SELECT MAX(snapshot_date)
                                 FROM fact_repository_metrics_daily
                                 WHERE snapshot_date < CURRENT_DATE
                             )),
                            0
                        ) THEN 1
                        ELSE 0
                    END
                    """,
                ),
                (
                    "Repository dimension rows missing from the clean table",
                    """
                    SELECT COUNT(*)
                    FROM dim_repository d
                    LEFT JOIN repositories_clean c
                        ON c.id = d.repository_id
                    WHERE c.id IS NULL
                    """,
                ),
                (
                    "Today's repository snapshots missing",
                    """
                    SELECT COUNT(*)
                    FROM dim_repository d
                    LEFT JOIN fact_repository_metrics_daily f
                        ON f.repository_id = d.repository_id
                       AND f.snapshot_date = CURRENT_DATE
                    WHERE f.repository_id IS NULL
                    """,
                ),
                (
                    "Fact rows with missing repository dimension records",
                    """
                    SELECT COUNT(*)
                    FROM fact_repository_metrics_daily f
                    LEFT JOIN dim_repository d
                        ON d.repository_id = f.repository_id
                    WHERE d.repository_id IS NULL
                    """,
                ),
                (
                    "Fact rows with invalid negative metrics",
                    """
                    SELECT COUNT(*)
                    FROM fact_repository_metrics_daily
                    WHERE stars < 0
                       OR forks < 0
                       OR repository_age_days < 0
                    """,
                ),
                (
                    "Clean languages missing from the language dimension",
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT DISTINCT
                            COALESCE(
                                NULLIF(TRIM(language), ''),
                                'Unknown'
                            ) AS language_name
                        FROM repositories_clean
                    ) source_languages
                    LEFT JOIN dim_language dl
                        ON dl.language_name = source_languages.language_name
                    WHERE dl.language_id IS NULL
                    """,
                ),
                (
                    "Duplicate repository/date snapshots",
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT repository_id, snapshot_date
                        FROM fact_repository_metrics_daily
                        GROUP BY repository_id, snapshot_date
                        HAVING COUNT(*) > 1
                    ) duplicates
                    """,
                ),
            ]

            for description, query in checks:
                try:
                    if not run_check(connection, description, query):
                        all_passed = False
                except SQLAlchemyError:
                    logger.exception("Could not complete check: %s", description)
                    all_passed = False

            summary = connection.execute(text("""
                SELECT
                    (SELECT COUNT(*) FROM dim_repository),
                    (SELECT COUNT(*) FROM dim_language),
                    (SELECT COUNT(*)
                     FROM fact_repository_metrics_daily
                     WHERE snapshot_date = CURRENT_DATE)
            """)).one()

            logger.info(
                "Warehouse summary — dim_repository: %s | dim_language: %s | today's snapshots: %s",
                summary[0],
                summary[1],
                summary[2],
            )

        if not all_passed:
            raise DataQualityError("One or more warehouse data quality checks failed.")

        logger.info("WAREHOUSE VALIDATION PASSED.")

    except Exception:
        logger.exception("Warehouse validation stage aborted.")
        raise SystemExit(1)
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()