-- View all cleaned repositories
SELECT *
FROM repositories_clean;

-- Top 10 repositories by stars
SELECT
    name,
    language,
    stars,
    forks
FROM repositories_clean
ORDER BY stars DESC
LIMIT 10;

-- Repository count by programming language
SELECT
    language,
    COUNT(*) AS repository_count
FROM repositories_clean
GROUP BY language
ORDER BY repository_count DESC;

-- Most starred repository for each programming language
SELECT
    language,
    name,
    stars
FROM (
    SELECT
        language,
        name,
        stars,
        ROW_NUMBER() OVER (
            PARTITION BY language
            ORDER BY stars DESC
        ) AS rank
    FROM repositories_clean
) ranked
WHERE rank = 1
ORDER BY stars DESC;

-- Average stars and forks by programming language
SELECT
    language,
    COUNT(*) AS repository_count,
    ROUND(AVG(stars), 2) AS average_stars,
    ROUND(AVG(forks), 2) AS average_forks
FROM repositories_clean
GROUP BY language
ORDER BY average_stars DESC;

-- Repository engagement analysis
SELECT
    name,
    language,
    stars,
    forks,
    (stars + forks) AS engagement_score
FROM repositories_clean
ORDER BY engagement_score DESC
LIMIT 10;

-- Oldest repositories
SELECT
    name,
    language,
    created_at,
    repository_age_days
FROM repositories_clean
ORDER BY repository_age_days DESC
LIMIT 10;

-- Most recently updated repositories
SELECT
    name,
    language,
    stars,
    forks,
    updated_at
FROM repositories_clean
ORDER BY updated_at DESC
LIMIT 10;