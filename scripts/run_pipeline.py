import subprocess
import sys


def run_script(script_name):
    print("\n" + "=" * 60)
    print(f"Running: {script_name}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, f"scripts/{script_name}"]
    )

    if result.returncode != 0:
        print(f"\n❌ {script_name} failed.")
        sys.exit(1)

    print(f"✅ {script_name} completed successfully.")


def main():

    print("\n🚀 Starting GitHub Repository ETL Pipeline")

    # 1. Extract data from GitHub
    run_script("extract.py")

    # 2. Load raw data into PostgreSQL
    run_script("load_raw.py")

    # 3. Transform and load clean data
    run_script("transform.py")

    # 4. Validate clean data
    run_script("validate.py")

    print("\n" + "=" * 60)
    print("🎉 ETL PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()