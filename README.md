# 📊 GitHub Repository Analytics ETL Pipeline

An end-to-end Data Engineering project that extracts GitHub repository data, loads it into PostgreSQL, transforms and validates the data, performs SQL-based analysis, and presents the results through an interactive Streamlit dashboard.

---

## 📌 Project Overview

This project demonstrates a complete **ETL (Extract, Transform, Load) pipeline** using GitHub repository data.

The pipeline performs the following steps:

1. Extracts repository data from GitHub
2. Stores the extracted data as raw data
3. Loads the raw data into PostgreSQL
4. Cleans and transforms the data using Pandas
5. Stores the cleaned data in PostgreSQL
6. Validates the quality of the cleaned data
7. Performs analytical SQL queries
8. Displays the results through an interactive Streamlit dashboard

The project demonstrates how raw API data can be transformed into useful analytical insights through a complete data engineering workflow.

---

## 🏗️ Project Architecture

```text
                    GitHub API
                        │
                        ▼
                  ┌───────────┐
                  │ Extract   │
                  │ extract.py│
                  └─────┬─────┘
                        │
                        ▼
                  Raw Repository Data
                        │
                        ▼
                  ┌────────────┐
                  │ Load Raw   │
                  │load_raw.py │
                  └──────┬─────┘
                         │
                         ▼
                    PostgreSQL
                 repositories_raw
                         │
                         ▼
                  ┌────────────┐
                  │ Transform  │
                  │transform.py│
                  └──────┬─────┘
                         │
                         ▼
                    PostgreSQL
                repositories_clean
                         │
                         ▼
                  ┌────────────┐
                  │ Validate   │
                  │validate.py │
                  └──────┬─────┘
                         │
                         ▼
                  ┌────────────┐
                  │ SQL        │
                  │ Analysis   │
                  └──────┬─────┘
                         │
                         ▼
                Streamlit Dashboard