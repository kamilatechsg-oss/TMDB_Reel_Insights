"""The 10 SQL business questions (PostgreSQL). Shared by 02_sql_analysis.ipynb and app.py."""

QUERIES = {
    "Q1 - Action movies released after 2015": """
        SELECT m.title, m.release_date
        FROM movies m
        JOIN movie_genres mg ON mg.movie_id = m.movie_id
        JOIN genres g        ON g.genre_id  = mg.genre_id
        WHERE g.genre_name = 'Action'
          AND m.release_date > DATE '2015-12-31'
        ORDER BY m.release_date;
    """,
    "Q2 - Top 10 highest-grossing movies with genres": """
        SELECT m.title, m.revenue,
               STRING_AGG(g.genre_name, ', ' ORDER BY g.genre_name) AS genres
        FROM movies m
        LEFT JOIN movie_genres mg ON mg.movie_id = m.movie_id
        LEFT JOIN genres g        ON g.genre_id  = mg.genre_id
        WHERE m.revenue > 0
        GROUP BY m.movie_id, m.title, m.revenue
        ORDER BY m.revenue DESC
        LIMIT 10;
    """,
    "Q3 - Average budget & revenue by genre": """
        -- zeros = unknown in TMDB, so they are excluded via NULLIF
        SELECT g.genre_name,
               ROUND(AVG(NULLIF(m.budget, 0)))  AS avg_budget,
               ROUND(AVG(NULLIF(m.revenue, 0))) AS avg_revenue,
               COUNT(*)                          AS movie_count
        FROM genres g
        JOIN movie_genres mg ON mg.genre_id = g.genre_id
        JOIN movies m        ON m.movie_id  = mg.movie_id
        GROUP BY g.genre_name
        ORDER BY avg_revenue DESC NULLS LAST;
    """,
    "Q4 - Top 10 actors by movie count": """
        SELECT actor_name, COUNT(DISTINCT movie_id) AS movie_count
        FROM "cast"
        GROUP BY person_id, actor_name
        ORDER BY movie_count DESC, actor_name
        LIMIT 10;
    """,
    "Q5 - Directors with more than 3 movies": """
        SELECT person_name AS director, COUNT(DISTINCT movie_id) AS movie_count
        FROM crew
        WHERE job = 'Director'
        GROUP BY person_id, person_name
        HAVING COUNT(DISTINCT movie_id) > 3
        ORDER BY movie_count DESC, director;
    """,
    "Q6 - Top 10 most used keywords": """
        SELECT keyword_name, COUNT(*) AS usage_count
        FROM movie_keywords
        GROUP BY keyword_id, keyword_name
        ORDER BY usage_count DESC
        LIMIT 10;
    """,
    "Q7 - Above-avg budget but below-avg revenue": """
        SELECT title, budget, revenue
        FROM movies
        WHERE budget  > (SELECT AVG(budget)  FROM movies WHERE budget  > 0)
          AND revenue > 0
          AND revenue < (SELECT AVG(revenue) FROM movies WHERE revenue > 0)
        ORDER BY budget - revenue DESC;
    """,
    "Q8 - Actors in movies by a director (Christopher Nolan)": """
        SELECT DISTINCT c.actor_name, m.title
        FROM crew d
        JOIN "cast" c ON c.movie_id = d.movie_id
        JOIN movies m ON m.movie_id = d.movie_id
        WHERE d.job = 'Director' AND d.person_name = :director
        ORDER BY m.title, c.actor_name;
    """,
    "Q9 - Highest-rated genre (min 20 movies)": """
        SELECT g.genre_name,
               ROUND(AVG(m.vote_average)::numeric, 2) AS avg_rating,
               COUNT(*) AS movie_count
        FROM genres g
        JOIN movie_genres mg ON mg.genre_id = g.genre_id
        JOIN movies m        ON m.movie_id  = mg.movie_id
        WHERE m.vote_count > 0
        GROUP BY g.genre_name
        HAVING COUNT(*) >= 20
        ORDER BY avg_rating DESC;
    """,
    "Q10 - Top 10 movies by keyword count": """
        SELECT m.title, COUNT(mk.keyword_id) AS keyword_count
        FROM movies m
        JOIN movie_keywords mk ON mk.movie_id = m.movie_id
        GROUP BY m.movie_id, m.title
        ORDER BY keyword_count DESC, m.title
        LIMIT 10;
    """,
}

DEFAULT_PARAMS = {"director": "Christopher Nolan"}


def run_query(name, engine, params=None):
    """Execute one of the saved queries and return a DataFrame."""
    import pandas as pd
    from sqlalchemy import text
    with engine.connect() as conn:
        return pd.read_sql(text(QUERIES[name]), conn, params=params or DEFAULT_PARAMS)
