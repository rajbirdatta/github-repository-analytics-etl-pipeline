from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from scripts.exceptions import ConfigurationError, get_db_engine
from scripts.logger import get_logger


logger = get_logger("db_healthcheck")


def check_connection() -> None:
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version();")).scalar_one()
            logger.info("Connected to PostgreSQL successfully: %s", version)
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        check_connection()
    except (ConfigurationError, SQLAlchemyError):
        logger.exception("PostgreSQL connection healthcheck failed.")
        raise SystemExit(1)