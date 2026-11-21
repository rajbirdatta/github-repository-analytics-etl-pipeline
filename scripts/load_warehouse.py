from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from scripts.exceptions import DatabaseLoadError, get_db_engine
from scripts.logger import get_logger


logger = get_logger("load_warehouse")


def load_repository_dimension(connection) -> None:
    """Insert or update repository metadata."""
    result = connection.execute(text("""
        INSERT INTO dim_repository (
            repository_id,
            repository_name,
            full_name,
            created_at
        )
        SELECT
            c.id,
            c.name,
            r.full_name,
            c.created_at
        FROM repositories_clean AS c
        LEFT JOIN repositories_raw AS r
            ON r.id = c.id
        ON CONFLICT (repository_id) DO UPDATE SET
            repository_name = EXCLUDED.repository_name,
            full_name = EXCLUDED.full_name,
            created_at = EXCLUDED.created_at;
    """))
    logger.info("Repository dimension processed: %s rows.", result.rowcount)


def load_language_dimension(connection) -> None:
    """Insert distinct programming languages."""
    result = connection.execute(text("""
        INSERT INTO dim_language (language_name)
        SELECT DISTINCT
            COALESCE(NULLIF(TRIM(language), ''), 'Unknown')
        FROM repositories_clean
        ON CONFLICT (language_name) DO NOTHING;
    """))
    logger.info("Language dimension inserted %s new rows.", result.rowcount)


def load_daily_metrics(connection) -> None:
    """Insert one metric snapshot per repository per date."""
    result = connection.execute(text("""
        INSERT INTO fact_repository_metrics_daily (
            repository_id,
            snapshot_date,
            language_id,
            stars,
            forks,
            repository_age_days
        )
        SELECT
            c.id,
            CURRENT_DATE,
            dl.language_id,
            c.stars,
            c.forks,
            c.repository_age_days
        FROM repositories_clean AS c
        LEFT JOIN dim_language AS dl
            ON dl.language_name =
                COALESCE(NULLIF(TRIM(c.language), ''), 'Unknown')
        ON CONFLICT (repository_id, snapshot_date) DO UPDATE SET
            language_id = EXCLUDED.language_id,
            stars = EXCLUDED.stars,
            forks = EXCLUDED.forks,
            repository_age_days = EXCLUDED.repository_age_days;
    """))
    logger.info("Daily metrics snapshot processed: %s rows.", result.rowcount)


def main() -> None:
    engine = None
    try:
        engine = get_db_engine()
        with engine.begin() as connection:
            connection.execute(text("SELECT 1"))
            load_repository_dimension(connection)
            load_language_dimension(connection)
            load_daily_metrics(connection)

        logger.info("Warehouse loading completed successfully.")
    except SQLAlchemyError as exc:
        logger.exception("Warehouse loading failed; transaction rolled back.")
        raise SystemExit(1) from DatabaseLoadError(str(exc))
    except Exception:
        logger.exception("Warehouse loading stage aborted.")
        raise SystemExit(1)
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()