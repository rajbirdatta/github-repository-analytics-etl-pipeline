import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent


def run_etl_pipeline():
    print("\n" + "=" * 60)
    print("🚀 STARTING ETL PIPELINE")
    print("=" * 60)

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_pipeline.py")
        ]
    )

    if result.returncode != 0:
        print("\n❌ ETL pipeline failed.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ ETL PIPELINE COMPLETED")
    print("=" * 60)


def start_dashboard():
    print("\n" + "=" * 60)
    print("📊 STARTING STREAMLIT DASHBOARD")
    print("=" * 60)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(PROJECT_ROOT / "dashboard" / "app.py")
        ]
    )


def main():
    run_etl_pipeline()
    start_dashboard()


if __name__ == "__main__":
    main()