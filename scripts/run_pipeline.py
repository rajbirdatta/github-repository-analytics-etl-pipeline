import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / "data" / "state"
PENDING_CHECKPOINT = STATE_DIR / "pending_extraction.json"
COMMITTED_CHECKPOINT = STATE_DIR / "last_successful_extraction.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def run_script(module_name: str):
    """Run a pipeline stage module and stop immediately if it fails."""
    logger.info("Running stage: %s", module_name)

    result = subprocess.run(
        [sys.executable, "-m", f"scripts.{module_name}"],
        cwd=PROJECT_ROOT,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Pipeline stage '{module_name}' failed with exit code {result.returncode}."
        )

    logger.info("Stage completed successfully: %s", module_name)

def commit_checkpoint():
    """
    Advance the extraction watermark only after all pipeline stages pass.
    The pending file is written by extract.py; os.replace is atomic on the same
    filesystem.
    """
    if not PENDING_CHECKPOINT.exists():
        raise FileNotFoundError(
            f"Pending checkpoint not found: {PENDING_CHECKPOINT}. "
            "Ensure scripts/extract.py is the incremental version."
        )

    with PENDING_CHECKPOINT.open("r", encoding="utf-8") as file:
        checkpoint = json.load(file)

    if not checkpoint.get("watermark"):
        raise ValueError("Pending checkpoint has no watermark; refusing to commit it.")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = COMMITTED_CHECKPOINT.with_suffix(".json.tmp")
    try:
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump(checkpoint, file, indent=2)
            file.write("\n")
        os.replace(temp_file, COMMITTED_CHECKPOINT)
        PENDING_CHECKPOINT.unlink(missing_ok=True)
    finally:
        temp_file.unlink(missing_ok=True)

    logger.info(
        "Committed extraction checkpoint: %s",
        checkpoint["watermark"],
    )


def main():
    parser = argparse.ArgumentParser(description="GitHub Repository ETL Pipeline Runner")
    parser.add_argument(
        "--commit-checkpoint",
        action="store_true",
        help="Commit pending_extraction.json to last_successful_extraction.json",
    )
    args = parser.parse_args()

    if args.commit_checkpoint:
        try:
            commit_checkpoint()
        except Exception:
            logger.exception("Failed to commit extraction checkpoint.")
            raise SystemExit(1)
        return

    logger.info("Starting GitHub Repository ETL Pipeline.")
    try:
        run_script("extract")
        run_script("load_raw")
        run_script("transform")
        run_script("validate")
        run_script("load_warehouse")
        run_script("validate_warehouse")
        commit_checkpoint()
    except Exception:
        logger.exception(
            "Pipeline failed. The committed extraction checkpoint was not advanced."
        )
        raise SystemExit(1)

    logger.info("ETL pipeline completed successfully.")


if __name__ == "__main__":
    main()