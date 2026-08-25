import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine


# -----------------------------------
# Load environment variables
# -----------------------------------

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


# -----------------------------------
# Database connection
# -----------------------------------

def get_engine():

    return create_engine(
        f"postgresql+psycopg2://"
        f"{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/"
        f"{os.getenv('DB_NAME')}"
    )


# -----------------------------------
# Validate clean data
# -----------------------------------

def validate_data():

    engine = get_engine()

    query = """
        SELECT *
        FROM repositories_clean
    """

    df = pd.read_sql(query, engine)

    engine.dispose()

    print("\n" + "=" * 60)
    print("DATA VALIDATION")
    print("=" * 60)

    # Number of records
    print(f"\n📦 Total repositories: {len(df)}")

    if len(df) == 0:
        print("❌ Validation failed: No repositories found.")
        return False

    # Duplicate IDs
    duplicate_ids = df["id"].duplicated().sum()

    print(f"🔑 Duplicate IDs: {duplicate_ids}")

    if duplicate_ids > 0:
        print("❌ Validation failed: Duplicate repository IDs found.")
        return False

    # Missing names
    missing_names = df["name"].isnull().sum()

    print(f"📝 Missing repository names: {missing_names}")

    if missing_names > 0:
        print("❌ Validation failed: Missing repository names.")
        return False

    # Negative stars
    negative_stars = (df["stars"] < 0).sum()

    print(f"⭐ Negative stars: {negative_stars}")

    if negative_stars > 0:
        print("❌ Validation failed: Negative star values found.")
        return False

    # Negative forks
    negative_forks = (df["forks"] < 0).sum()

    print(f"🍴 Negative forks: {negative_forks}")

    if negative_forks > 0:
        print("❌ Validation failed: Negative fork values found.")
        return False

    # Missing languages
    missing_languages = df["language"].isnull().sum()

    print(f"💻 Missing languages: {missing_languages}")

    # Final result
    print("\n" + "=" * 60)
    print("✅ DATA VALIDATION PASSED")
    print("=" * 60)

    return True


# -----------------------------------
# Main
# -----------------------------------

if __name__ == "__main__":

    success = validate_data()

    if not success:
        raise SystemExit(1)