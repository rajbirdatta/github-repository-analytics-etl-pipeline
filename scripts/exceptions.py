import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class ETLPipelineError(Exception):
    """Base exception for all GitHub ETL pipeline errors."""


class ConfigurationError(ETLPipelineError):
    """Raised when required environment variables or config files are missing."""


class ExtractionError(ETLPipelineError):
    """Raised when GitHub API extraction or response validation fails."""


class DatabaseLoadError(ETLPipelineError):
    """Raised when loading data into raw or warehouse tables fails."""


class TransformationError(ETLPipelineError):
    """Raised when batch cleaning or transformation rules fail."""


class DataQualityError(ETLPipelineError):
    """Raised when staging or warehouse validation checks fail."""


class CheckpointError(ETLPipelineError):
    """Raised when reading or committing the incremental watermark fails."""


def validate_db_env() -> dict:
    """Validate and return required PostgreSQL environment variables."""
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise ConfigurationError(
            f"Missing required database environment variables: {', '.join(missing)}"
        )

    try:
        port = int(os.getenv("DB_PORT"))
    except ValueError as exc:
        raise ConfigurationError(f"DB_PORT must be an integer, got: {os.getenv('DB_PORT')}") from exc

    return {
        "host": os.getenv("DB_HOST"),
        "port": port,
        "database": os.getenv("DB_NAME"),
        "username": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }


def get_db_engine() -> Engine:
    """Create a validated SQLAlchemy PostgreSQL engine."""
    cfg = validate_db_env()
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=cfg["username"],
        password=cfg["password"],
        host=cfg["host"],
        port=cfg["port"],
        database=cfg["database"],
    )
    return create_engine(url, pool_pre_ping=True)