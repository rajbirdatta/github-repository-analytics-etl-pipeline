import os
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px

from dotenv import load_dotenv
from sqlalchemy import create_engine


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="GitHub Repository Analytics",
    page_icon="📊",
    layout="wide"
)


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_engine():
    return create_engine(
        f"postgresql+psycopg2://"
        f"{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/"
        f"{os.getenv('DB_NAME')}"
    )


# ============================================================
# LOAD DATA FROM POSTGRESQL
# ============================================================

@st.cache_data(ttl=300)
def load_data():

    engine = get_engine()

    query = """
        SELECT
            id,
            name,
            language,
            stars,
            forks,
            created_at,
            updated_at,
            repository_age_days
        FROM repositories_clean
    """

    df = pd.read_sql(query, engine)

    engine.dispose()

    return df


# ============================================================
# LOAD DATA
# ============================================================

df = load_data()


# ============================================================
# DATA PREPARATION
# ============================================================

df["language"] = df["language"].fillna("Unknown")

df["stars"] = pd.to_numeric(
    df["stars"],
    errors="coerce"
).fillna(0)

df["forks"] = pd.to_numeric(
    df["forks"],
    errors="coerce"
).fillna(0)

df["repository_age_days"] = pd.to_numeric(
    df["repository_age_days"],
    errors="coerce"
).fillna(0)

df["created_at"] = pd.to_datetime(
    df["created_at"],
    errors="coerce"
)

df["updated_at"] = pd.to_datetime(
    df["updated_at"],
    errors="coerce"
)

# Our simple project engagement metric
df["engagement_score"] = (
    df["stars"] + df["forks"]
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🔎 Filters")

st.sidebar.markdown(
    "Use the filters below to explore the repository data."
)


# ============================================================
# FILTER OPTIONS
# ============================================================

languages = sorted(
    df["language"].dropna().unique().tolist()
)

max_stars = (
    int(df["stars"].max())
    if not df.empty
    else 0
)

max_forks = (
    int(df["forks"].max())
    if not df.empty
    else 0
)


# ============================================================
# SESSION STATE
# ============================================================

if "language_filter" not in st.session_state:
    st.session_state["language_filter"] = languages

if "stars_filter" not in st.session_state:
    st.session_state["stars_filter"] = 0

if "forks_filter" not in st.session_state:
    st.session_state["forks_filter"] = 0

if "repository_search" not in st.session_state:
    st.session_state["repository_search"] = ""


# ============================================================
# RESET FILTER FUNCTION
# ============================================================

def reset_filters():

    st.session_state["language_filter"] = languages
    st.session_state["stars_filter"] = 0
    st.session_state["forks_filter"] = 0
    st.session_state["repository_search"] = ""


# ============================================================
# LANGUAGE FILTER
# ============================================================

selected_languages = st.sidebar.multiselect(
    "💻 Programming Language",
    options=languages,
    key="language_filter"
)


# ============================================================
# STARS FILTER
# ============================================================

min_stars = st.sidebar.slider(
    "⭐ Minimum Stars",
    min_value=0,
    max_value=max_stars,
    step=1,
    key="stars_filter"
)


# ============================================================
# FORKS FILTER
# ============================================================

min_forks = st.sidebar.slider(
    "🍴 Minimum Forks",
    min_value=0,
    max_value=max_forks,
    step=1,
    key="forks_filter"
)


# ============================================================
# REPOSITORY SEARCH
# ============================================================

search_repository = st.sidebar.text_input(
    "🔍 Search Repository",
    placeholder="Enter repository name...",
    key="repository_search"
)


# ============================================================
# RESET BUTTON
# ============================================================

st.sidebar.button(
    "🔄 Reset Filters",
    use_container_width=True,
    on_click=reset_filters
)


# ============================================================
# APPLY FILTERS
# ============================================================

filtered_df = df[
    df["language"].isin(selected_languages)
    &
    (df["stars"] >= min_stars)
    &
    (df["forks"] >= min_forks)
].copy()


# ============================================================
# SEARCH FILTER
# ============================================================

if search_repository:

    filtered_df = filtered_df[
        filtered_df["name"]
        .astype(str)
        .str.contains(
            search_repository,
            case=False,
            na=False,
            regex=False
        )
    ]


# ============================================================
# DASHBOARD HEADER
# ============================================================

st.title(
    "📊 GitHub Repository Analytics Dashboard"
)

st.caption(
    "An interactive analytics dashboard built with "
    "Python, PostgreSQL, Pandas and Streamlit."
)

st.markdown(
    f"**Showing {len(filtered_df):,} of "
    f"{len(df):,} repositories**"
)


# ============================================================
# EMPTY RESULT CHECK
# ============================================================

if filtered_df.empty:

    st.warning(
        "⚠️ No repositories match the selected filters."
    )

    st.info(
        "Try lowering the Stars/Forks filters or "
        "selecting more programming languages."
    )

    st.stop()


# ============================================================
# KPI METRICS
# ============================================================

total_repositories = len(filtered_df)

total_stars = int(
    filtered_df["stars"].sum()
)

total_forks = int(
    filtered_df["forks"].sum()
)

total_languages = filtered_df[
    "language"
].nunique()


col1, col2, col3, col4 = st.columns(4)


col1.metric(
    "📦 Repositories",
    f"{total_repositories:,}"
)

col2.metric(
    "⭐ Total Stars",
    f"{total_stars:,}"
)

col3.metric(
    "🍴 Total Forks",
    f"{total_forks:,}"
)

col4.metric(
    "💻 Languages",
    f"{total_languages:,}"
)


st.divider()


# ============================================================
# LANGUAGE DISTRIBUTION
# ============================================================

st.subheader(
    "💻 Repository Distribution by Language"
)


language_counts = (
    filtered_df["language"]
    .value_counts()
    .reset_index()
)

language_counts.columns = [
    "language",
    "repository_count"
]


fig_language = px.bar(
    language_counts,
    x="language",
    y="repository_count",
    text="repository_count",
    labels={
        "language": "Programming Language",
        "repository_count": "Repositories"
    }
)

fig_language.update_traces(
    textposition="outside"
)

fig_language.update_layout(
    height=430,
    showlegend=False,
    margin=dict(
        l=20,
        r=20,
        t=50,
        b=20
    )
)

st.plotly_chart(
    fig_language,
    use_container_width=True
)


st.divider()


# ============================================================
# TOP STARS + STARS VS FORKS
# ============================================================

col1, col2 = st.columns(2)


# ------------------------------------------------------------
# TOP REPOSITORIES BY STARS
# ------------------------------------------------------------

with col1:

    st.subheader(
        "⭐ Top 10 Repositories by Stars"
    )

    top_repositories = (
        filtered_df
        .sort_values(
            "stars",
            ascending=False
        )
        .head(10)
    )

    fig_stars = px.bar(
        top_repositories.sort_values("stars"),
        x="stars",
        y="name",
        orientation="h",
        text="stars",
        hover_data=[
            "language",
            "forks"
        ],
        labels={
            "stars": "Stars",
            "name": "Repository"
        }
    )

    fig_stars.update_traces(
        textposition="outside"
    )

    fig_stars.update_layout(
        height=500,
        showlegend=False,
        margin=dict(
            l=20,
            r=20,
            t=30,
            b=20
        )
    )

    st.plotly_chart(
        fig_stars,
        use_container_width=True
    )


# ------------------------------------------------------------
# STARS VS FORKS
# ------------------------------------------------------------

with col2:

    st.subheader(
        "⭐ Stars vs 🍴 Forks"
    )

    fig_scatter = px.scatter(
        filtered_df,
        x="stars",
        y="forks",
        size="stars",
        hover_name="name",
        hover_data=[
            "language",
            "engagement_score"
        ],
        labels={
            "stars": "GitHub Stars",
            "forks": "GitHub Forks"
        }
    )

    fig_scatter.update_layout(
        height=500,
        margin=dict(
            l=20,
            r=20,
            t=30,
            b=20
        )
    )

    st.plotly_chart(
        fig_scatter,
        use_container_width=True
    )


st.divider()


# ============================================================
# ENGAGEMENT ANALYSIS
# ============================================================

st.subheader(
    "🔥 Repository Engagement"
)


top_engagement = (
    filtered_df
    .sort_values(
        "engagement_score",
        ascending=False
    )
    .head(10)
)


fig_engagement = px.bar(
    top_engagement.sort_values(
        "engagement_score"
    ),
    x="engagement_score",
    y="name",
    orientation="h",
    text="engagement_score",
    hover_data=[
        "language",
        "stars",
        "forks"
    ],
    labels={
        "engagement_score": "Stars + Forks",
        "name": "Repository"
    }
)

fig_engagement.update_traces(
    textposition="outside"
)

fig_engagement.update_layout(
    height=500,
    showlegend=False
)

st.plotly_chart(
    fig_engagement,
    use_container_width=True
)


# ============================================================
# ENGAGEMENT TABLE
# ============================================================

with st.expander(
    "📋 View Engagement Details"
):

    st.dataframe(
        top_engagement[
            [
                "name",
                "language",
                "stars",
                "forks",
                "engagement_score"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


st.divider()


# ============================================================
# AUTOMATIC INSIGHTS
# ============================================================

st.subheader(
    "💡 Key Insights"
)


most_starred = (
    filtered_df
    .sort_values(
        "stars",
        ascending=False
    )
    .iloc[0]
)

most_forked = (
    filtered_df
    .sort_values(
        "forks",
        ascending=False
    )
    .iloc[0]
)

most_engaged = (
    filtered_df
    .sort_values(
        "engagement_score",
        ascending=False
    )
    .iloc[0]
)

most_common_language = (
    filtered_df["language"]
    .value_counts()
    .idxmax()
)

oldest_repo = (
    filtered_df
    .sort_values(
        "repository_age_days",
        ascending=False
    )
    .iloc[0]
)


insight_col1, insight_col2 = st.columns(2)


with insight_col1:

    st.info(
        f"⭐ **Most starred:** "
        f"{most_starred['name']} "
        f"with {int(most_starred['stars']):,} stars."
    )

    st.info(
        f"🍴 **Most forked:** "
        f"{most_forked['name']} "
        f"with {int(most_forked['forks']):,} forks."
    )

    st.info(
        f"🔥 **Highest engagement:** "
        f"{most_engaged['name']} "
        f"with an engagement score of "
        f"{int(most_engaged['engagement_score']):,}."
    )


with insight_col2:

    language_count = (
        filtered_df["language"]
        .value_counts()
        .iloc[0]
    )

    st.success(
        f"💻 **Most common language:** "
        f"{most_common_language} "
        f"({language_count} repositories)."
    )

    st.warning(
        f"🕰️ **Oldest repository:** "
        f"{oldest_repo['name']} "
        f"({int(oldest_repo['repository_age_days']):,} days old)."
    )


st.divider()


# ============================================================
# RECENTLY UPDATED REPOSITORIES
# ============================================================

st.subheader(
    "🕒 Recently Updated Repositories"
)


recent_repositories = (
    filtered_df
    .dropna(subset=["updated_at"])
    .sort_values(
        "updated_at",
        ascending=False
    )
    .head(10)
)


st.dataframe(
    recent_repositories[
        [
            "name",
            "language",
            "stars",
            "forks",
            "updated_at"
        ]
    ],
    use_container_width=True,
    hide_index=True
)


st.divider()


# ============================================================
# OLDEST REPOSITORIES
# ============================================================

st.subheader(
    "🕰️ Oldest Repositories"
)


oldest_repositories = (
    filtered_df
    .sort_values(
        "repository_age_days",
        ascending=False
    )
    .head(10)
)


st.dataframe(
    oldest_repositories[
        [
            "name",
            "language",
            "stars",
            "created_at",
            "repository_age_days"
        ]
    ],
    use_container_width=True,
    hide_index=True
)


st.divider()


# ============================================================
# REPOSITORY DETAILS
# ============================================================

st.subheader(
    "📋 Repository Details"
)


repository_details = (
    filtered_df
    .sort_values(
        "stars",
        ascending=False
    )
)


st.dataframe(
    repository_details[
        [
            "name",
            "language",
            "stars",
            "forks",
            "engagement_score",
            "created_at",
            "updated_at",
            "repository_age_days"
        ]
    ],
    use_container_width=True,
    hide_index=True
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "GitHub Repository Analytics ETL Pipeline | "
    "Python • Pandas • PostgreSQL • SQL • Streamlit"
)