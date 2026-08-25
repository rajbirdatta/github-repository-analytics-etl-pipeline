import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Connect to PostgreSQL
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

cursor = conn.cursor()

# Read JSON file
with open("data/raw/repos.json", "r", encoding="utf-8") as file:
    repositories = json.load(file)

print(f"Found {len(repositories)} repositories.")

# Insert each repository
for repo in repositories:

    cursor.execute("""
        INSERT INTO repositories_raw
        (id, name, full_name, language, stars, forks, created_at, updated_at, api_data)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (
        repo["id"],
        repo["name"],
        repo["full_name"],
        repo["language"],
        repo["stargazers_count"],
        repo["forks_count"],
        repo["created_at"],
        repo["updated_at"],
        json.dumps(repo)
    ))

conn.commit()

print("✅ Data inserted successfully!")

cursor.close()
conn.close()