import json
from pathlib import Path

import psycopg2

from scripts.exceptions import DatabaseLoadError, validate_db_env
from scripts.logger import get_logger


PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSON_FILE = PROJECT_ROOT / "data" / "raw" / "repos.json"

logger = get_logger("load_raw")


def load_repositories() -> list[dict]:
    """Read and validate the extracted repository batch."""
    if not JSON_FILE.exists():
        raise DatabaseLoadError(f"Raw extraction batch file not found: {JSON_FILE}")

    try:
        with JSON_FILE.open("r", encoding="utf-8") as file:
            repositories = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise DatabaseLoadError(f"Failed to read {JSON_FILE}: {exc}") from exc

    if not isinstance(repositories, list):
        raise DatabaseLoadError("Expected data/raw/repos.json to contain a JSON list.")

    for repo in repositories:
        if not isinstance(repo, dict) or not isinstance(repo.get("id"), int):
            raise DatabaseLoadError("Each repository must be an object with an integer ID.")

    ids = [repo["id"] for repo in repositories]
    if len(ids) != len(set(ids)):
        raise DatabaseLoadError("Duplicate repository IDs found in extraction batch.")

    return repositories


def main() -> None:
    connection = None
    try:
        repositories = load_repositories()
        logger.info("Found %s repositories in the current extraction batch.", len(repositories))

        if not repositories:
            logger.info("The extraction batch is empty; no raw rows need loading.")
            return

        db_cfg = validate_db_env()
        connection = psycopg2.connect(
            host=db_cfg["host"],
            port=db_cfg["port"],
            dbname=db_cfg["database"],
            user=db_cfg["username"],
            password=db_cfg["password"],
        )

        with connection:
            with connection.cursor() as cursor:
                query = """
                    INSERT INTO repositories_raw (
                        id, name, full_name, language, stars, forks,
                        created_at, updated_at, api_data
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        full_name = EXCLUDED.full_name,
                        language = EXCLUDED.language,
                        stars = EXCLUDED.stars,
                        forks = EXCLUDED.forks,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at,
                        api_data = EXCLUDED.api_data;
                """

                rows = [
                    (
                        repo["id"],
                        repo.get("name"),
                        repo.get("full_name"),
                        repo.get("language"),
                        repo.get("stargazers_count", 0),
                        repo.get("forks_count", 0),
                        repo.get("created_at"),
                        repo.get("updated_at"),
                        json.dumps(repo),
                    )
                    for repo in repositories
                ]
                cursor.executemany(query, rows)

        logger.info("Successfully upserted %s raw repository records.", len(repositories))

    except psycopg2.Error as exc:
        logger.exception("PostgreSQL error during raw loading; transaction rolled back.")
        raise SystemExit(1) from exc
    except Exception:
        logger.exception("Raw loading stage aborted.")
        raise SystemExit(1)
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()