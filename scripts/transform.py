import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


def get_engine():
    """Create and return a SQLAlchemy engine."""
    return create_engine(
        f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )


def load_data(engine):
    """Load raw repository data from PostgreSQL."""
    query = """
    SELECT *
    FROM repositories_raw
    """
    return pd.read_sql(query, engine)


def transform_data(df):
    """Clean and transform the repository data."""

    # Convert timestamps
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["updated_at"] = pd.to_datetime(df["updated_at"])

    # Fill missing languages
    df["language"] = df["language"].fillna("Unknown")

    # Create new feature
    today = pd.Timestamp.now()

    df["repository_age_days"] = (
        today - df["created_at"]
    ).dt.days

    # Select required columns
    clean_df = df[
        [
            "id",
            "name",
            "language",
            "stars",
            "forks",
            "created_at",
            "updated_at",
            "repository_age_days"
        ]
    ].copy()

    return clean_df


def main():

    engine = get_engine()

    df = load_data(engine)

    clean_df = transform_data(df)

    print(clean_df.head())

    clean_df.to_sql(
        "repositories_clean",
        engine,
        if_exists="replace",
        index=False
    )
    print("✅ Clean data loaded into PostgreSQL!")
    engine.dispose()


if __name__ == "__main__":
    main()