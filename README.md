# Reel Insights – TMDB Movie Industry EDA

End-to-end analysis of **2,503 TMDB movies** (1921–2026) across six related tables, using **PostgreSQL**, **SQL**, **Pandas**, **Matplotlib/Seaborn/Plotly** and a **Streamlit** dashboard.

## Project structure
```
TMDB_Reel_Insights/
├── data/
│   ├── movies.csv, genres.csv, movie_genres.csv, cast.csv, crew.csv, movie_keywords.csv   (raw)
│   ├── clean/                 cleaned CSVs (created by notebook 01)
│   └── tmdb_schema.sql        PostgreSQL DDL with primary/foreign keys
├── images/                    charts saved by notebook 04
├── 01_data_cleaning.ipynb     clean data + load PostgreSQL
├── 02_sql_analysis.ipynb      10 SQL questions
├── 03_pandas_analysis.ipynb   10 Pandas questions
├── 04_visualizations.ipynb    univariate / bivariate / multivariate charts
├── app.py                     Streamlit 3-page dashboard (Filters · Dashboard · Query Explorer)
├── db_config.py               PostgreSQL connection settings (password read from local_secrets.py / env var)
├── .streamlit/config.toml     dashboard theme
├── queries.py                 the 10 SQL queries (shared by notebook 02 and app.py)
└── requirements.txt
```

## How to run
1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Create an empty PostgreSQL database `tmdb` (pgAdmin → Databases → Create → Database).
4. Set your PostgreSQL user in `db_config.py`, and your password in a new file `local_secrets.py` containing `PG_PASSWORD = "your_password"` (git-ignored), or set env var `PG_PASSWORD`.
5. Run notebooks **01 → 02 → 03 → 04** in order (01 creates the tables and loads the data).
6. `streamlit run app.py`

## Data cleaning summary
| Table | Raw rows | Clean rows | Removed |
|---|---:|---:|---:|
| movies | 2,509 | 2,503 | 6 duplicates |
| genres | 19 | 19 | 0 |
| movie_genres | 6,888 | 6,878 | 10 |
| cast | 24,917 | 24,902 | 15 |
| crew | 7,297 | 7,289 | 8 |
| movie_keywords | 41,701 | 41,681 | 20 |

- Exact duplicates removed; one row per `movie_id`; orphan child rows removed so foreign keys hold.
- **Budget/revenue = 0 means *unknown* in TMDB** (90 movies with no budget, 102 with no revenue). Kept as 0 in the database but treated as missing in all analysis (`NULLIF(x,0)` in SQL, `NaN` in Pandas). No imputation. Financial KPIs use the **2,370 movies (95%)** with both figures.

## Top 5 insights
1. **Budget drives revenue – and risk.** Budget and revenue correlate strongly (r = 0.68), and 92% of films with known financials were profitable. But 273 films had above-average budgets with below-average revenue, many of them streaming-first releases (The Gray Man, Red Notice, The Irishman).
2. **The highest ROI comes from tiny budgets.** Median ROI is 2.43x, but the mean is 13.2x because of extreme hits. The top-15 ROI films (budget ≥ $1M) have a median budget of just **$3.6M** vs $40M overall, led by low-budget classics and horror (Rocky, Saw, Insidious) returning 70–124x.
3. **Blockbusters are Adventure-led.** 9 of the top 10 grossers include Adventure, and 6 are full Action–Adventure–Sci-Fi blends (Avatar $2.92B, Avengers: Endgame $2.80B); two more are Animation/Family hits (Zootopia 2, Inside Out 2). Adventure leads average revenue (≈$400M), with Animation ($372M) and Family ($353M) close behind on ~20% smaller budgets.
4. **Quality ≠ box office.** War (7.36), History (7.34) and Music (7.32) are the best-rated genres, while top-earning Adventure rates 6.83 and Horror – the ROI leader – rates lowest (6.62). Rating is almost uncorrelated with budget (−0.12).
5. **Existing IP and repeat talent dominate.** 'Based on novel or book' (449) and 'sequel' (416) are the most-used keywords. A small talent core recurs: Samuel L. Jackson (39 films) and Steven Spielberg (27 as director). Volume isn't quality, though – Tom Hanks averages 7.29 vs Mark Wahlberg 6.63.

## Recommendations
1. **Portfolio slate:** pair a few Action–Adventure–Sci-Fi tentpoles (absolute profit) with several low-budget horror/genre films (highest % return, limited downside).
2. **Back Animation & Family:** near-blockbuster revenue at lower cost – the best revenue-to-budget mix among major genres.
3. **Stage-gate big budgets:** extra review for projects above the average budget, using the 273 under-performers as cautionary comps; judge streaming titles on viewership, not box office.
4. **Separate KPIs:** track critical rating and commercial return independently. Route War/History/Drama to prestige/awards and streaming libraries, and Adventure/Action/Animation to theatrical.
5. **IP-led acquisition & marketing:** prioritise adaptations and sequels, cast actors with both high volume *and* above-average ratings, and push marketing spend on currently trending titles (high popularity, low votes) while re-promoting legacy catalogue titles.
