import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scripts.exceptions import CheckpointError, ExtractionError
from scripts.logger import get_logger


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_FILE = OUTPUT_DIR / "repos.json"

STATE_DIR = PROJECT_ROOT / "data" / "state"
CHECKPOINT_FILE = STATE_DIR / "last_successful_extraction.json"
PENDING_CHECKPOINT_FILE = STATE_DIR / "pending_extraction.json"

USERNAME = os.getenv("GITHUB_USERNAME", "microsoft").strip()
API_URL = f"https://api.github.com/users/{USERNAME}/repos"

PER_PAGE = 100
OVERLAP_HOURS = 24

logger = get_logger("extract")


# ============================================================
# TIMESTAMP AND CHECKPOINT HELPERS
# ============================================================

def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def parse_github_timestamp(value):
    """Convert an ISO-8601 timestamp to a UTC-aware datetime."""
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, AttributeError):
        return None


def read_checkpoint():
    """Read the last successfully committed extraction watermark."""
    if not CHECKPOINT_FILE.exists():
        return None

    try:
        with CHECKPOINT_FILE.open("r", encoding="utf-8") as file:
            checkpoint = json.load(file)

        watermark = parse_github_timestamp(checkpoint.get("watermark"))
        if watermark is None:
            raise CheckpointError("Checkpoint does not contain a valid watermark.")

        return watermark

    except CheckpointError:
        raise
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise CheckpointError(
            f"Could not read extraction checkpoint at {CHECKPOINT_FILE}: {exc}"
        ) from exc


# ============================================================
# HTTP SESSION WITH RETRIES
# ============================================================

def create_session() -> requests.Session:
    """Create a GitHub API session with retry handling."""
    retry_strategy = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
        raise_on_status=True,
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)

    session.headers.update({
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "GitHub-Repository-Analytics-ETL",
    })

    token = os.getenv("GITHUB_TOKEN")
    if token:
        session.headers["Authorization"] = f"Bearer {token}"

    return session


# ============================================================
# VALIDATION AND DEDUPLICATION
# ============================================================

def validate_repository(repo: dict) -> None:
    """Validate the fields required for safe extraction."""
    if not isinstance(repo, dict):
        raise ExtractionError("GitHub returned a non-object repository record.")

    repo_id = repo.get("id")
    if not isinstance(repo_id, int) or isinstance(repo_id, bool):
        raise ExtractionError("Repository ID is missing or invalid.")

    if not repo.get("name") or not repo.get("full_name"):
        raise ExtractionError(
            f"Repository {repo_id} is missing its name or full_name."
        )

    if parse_github_timestamp(repo.get("updated_at")) is None:
        raise ExtractionError(
            f"Repository {repo_id} has a missing or invalid updated_at timestamp."
        )


def deduplicate_repositories(repositories: list[dict]) -> list[dict]:
    """Keep one record per repository ID, retaining the newest updated_at."""
    unique_repositories = {}
    duplicate_count = 0

    for repo in repositories:
        repo_id = repo["id"]
        existing = unique_repositories.get(repo_id)

        if existing is None:
            unique_repositories[repo_id] = repo
            continue

        duplicate_count += 1
        existing_updated = parse_github_timestamp(existing.get("updated_at"))
        candidate_updated = parse_github_timestamp(repo.get("updated_at"))

        if candidate_updated is not None and (
            existing_updated is None or candidate_updated > existing_updated
        ):
            unique_repositories[repo_id] = repo

    if duplicate_count:
        logger.warning(
            "Found %s duplicate records across API pages. Kept the newest record per ID.",
            duplicate_count,
        )

    result = list(unique_repositories.values())
    ids = [repo["id"] for repo in result]
    if len(ids) != len(set(ids)):
        raise ExtractionError("Duplicate repository IDs remain after deduplication.")

    return result


# ============================================================
# EXTRACTION
# ============================================================

def extract_repositories():
    """Perform a full initial extraction, then incremental extractions."""
    run_started_at = utc_now()
    previous_watermark = read_checkpoint()

    if previous_watermark is None:
        mode = "full"
        cutoff = None
        logger.info("No committed checkpoint found. Starting full extraction.")
    else:
        mode = "incremental"
        cutoff = previous_watermark - timedelta(hours=OVERLAP_HOURS)
        logger.info(
            "Starting incremental extraction. Watermark=%s | Cutoff=%s",
            previous_watermark.isoformat(),
            cutoff.isoformat(),
        )

    repositories = []
    page = 1
    reached_cutoff = False

    try:
        with create_session() as session:
            while True:
                params = {
                    "per_page": PER_PAGE,
                    "page": page,
                    "type": "owner",
                    "sort": "updated",
                    "direction": "desc",
                }

                logger.info(
                    "Fetching '%s' repositories: page %s, mode=%s",
                    USERNAME,
                    page,
                    mode,
                )

                response = session.get(API_URL, params=params, timeout=(5, 30))
                response.raise_for_status()

                page_data = response.json()
                if not isinstance(page_data, list):
                    raise ExtractionError(
                        "GitHub API returned an unexpected non-list response format."
                    )

                if not page_data:
                    logger.info("No more repository records returned.")
                    break

                page_eligible = 0
                page_reached_cutoff = False

                for repo in page_data:
                    validate_repository(repo)
                    updated_at = parse_github_timestamp(repo["updated_at"])

                    if mode == "incremental" and updated_at < cutoff:
                        page_reached_cutoff = True
                        continue

                    repositories.append(repo)
                    page_eligible += 1

                logger.info(
                    "Page %s: %s eligible records; %s records returned.",
                    page,
                    page_eligible,
                    len(page_data),
                )

                if page_reached_cutoff:
                    reached_cutoff = True
                    break

                if len(page_data) < PER_PAGE:
                    break

                page += 1
    except requests.RequestException as exc:
        raise ExtractionError(f"GitHub API request failed on page {page}: {exc}") from exc

    repositories = deduplicate_repositories(repositories)

    if mode == "full" and not repositories:
        raise ExtractionError(
            "Full extraction returned zero repositories. Refusing to overwrite existing batch."
        )

    logger.info(
        "Extraction completed. Mode=%s | Unique records=%s | Cutoff reached=%s",
        mode,
        len(repositories),
        reached_cutoff,
    )

    pending_checkpoint = {
        "username": USERNAME,
        "mode": mode,
        "watermark": run_started_at.isoformat(),
        "previous_watermark": (
            previous_watermark.isoformat() if previous_watermark else None
        ),
        "overlap_hours": OVERLAP_HOURS,
        "extracted_at": utc_now().isoformat(),
        "record_count": len(repositories),
        "unique_repository_count": len(repositories),
    }

    return repositories, pending_checkpoint


# ============================================================
# ATOMIC FILE WRITING
# ============================================================

def atomic_write_json(file_path: Path, data) -> None:
    """Write JSON to a temporary file, then replace the destination."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = file_path.with_suffix(file_path.suffix + ".tmp")

    try:
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")
        temp_file.replace(file_path)
    except OSError as exc:
        raise ExtractionError(f"Failed writing JSON file {file_path}: {exc}") from exc
    finally:
        if temp_file.exists():
            temp_file.unlink()


def save_repositories(repositories: list[dict]) -> None:
    """Save the extracted batch for load_raw.py."""
    atomic_write_json(OUTPUT_FILE, repositories)
    logger.info("Saved %s repository records to %s", len(repositories), OUTPUT_FILE)


def save_pending_checkpoint(checkpoint: dict) -> None:
    """Save a pending watermark to be committed only after all stages succeed."""
    atomic_write_json(PENDING_CHECKPOINT_FILE, checkpoint)
    logger.info("Saved pending checkpoint (awaiting downstream pipeline completion).")


def main() -> None:
    try:
        repositories, pending_checkpoint = extract_repositories()
        save_repositories(repositories)
        save_pending_checkpoint(pending_checkpoint)
        logger.info("Extraction stage completed successfully.")
    except Exception:
        logger.exception("Extraction stage aborted.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()