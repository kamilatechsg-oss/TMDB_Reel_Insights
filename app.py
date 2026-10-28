"""
Reel Insights – TMDB Movie Dashboard (Streamlit)
Run:  streamlit run app.py
Pages: 1) Filters  2) Dashboard  3) Query Explorer
Data source: PostgreSQL (db_config.py). Falls back to data/clean/*.csv if the DB is unreachable.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

from db_config import get_engine
from queries import QUERIES, DEFAULT_PARAMS

st.set_page_config(page_title="Reel Insights – TMDB", page_icon="🎬", layout="wide")
CLEAN = Path("data/clean")

# ---------------------------------------------------------------- design tokens
SURFACE, CARD, BORDER = "#141416", "#1e1f24", "#34363d"
TEXT, TEXT_2, MUTED = "#f0efec", "#c3c2b7", "#8d8c85"
BLUE, ORANGE, AQUA = "#3987e5", "#d95926", "#199e70"
BLUE_RAMP = ["#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"]

st.markdown(f"""
<style>
  .block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px; }}
  h1, h2, h3 {{ letter-spacing: -0.01em; }}
  .hero {{ padding: 4px 0 18px 0; border-bottom: 1px solid {BORDER}; margin-bottom: 22px; }}
  .hero h1 {{ font-size: 2.1rem; margin: 0; color: {TEXT}; }}
  .hero p  {{ color: {TEXT_2}; margin: 6px 0 0 0; font-size: 0.98rem; }}
  .pill {{ display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.75rem;
           background: rgba(57,135,229,.15); color: #9ec5f4; border: 1px solid rgba(57,135,229,.35);
           margin-left: 8px; vertical-align: middle; }}
  .kpi {{ background: linear-gradient(160deg, #23252c 0%, {CARD} 100%); border: 1px solid {BORDER}; border-radius: 14px; padding: 16px 18px;
          height: 100%; }}
  .kpi .label {{ color: {MUTED}; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .06em; }}
  .kpi .value {{ color: {TEXT}; font-size: 1.75rem; font-weight: 700; margin-top: 6px; line-height: 1.1; }}
  .kpi .sub   {{ color: {TEXT_2}; font-size: 0.8rem; margin-top: 6px; }}
  .kpi .bar   {{ height: 3px; width: 36px; border-radius: 3px; background: {BLUE}; margin-bottom: 10px; }}
  .card-title {{ color: {TEXT}; font-weight: 600; font-size: 1.02rem; margin: 0 0 2px 0; }}
  .card-sub   {{ color: {MUTED}; font-size: 0.82rem; margin: 0 0 6px 0; }}
  .insight {{ background: linear-gradient(90deg, rgba(57,135,229,.12), rgba(57,135,229,.03));
              border: 1px solid rgba(57,135,229,.35); border-left: 4px solid {BLUE};
              border-radius: 12px; padding: 16px 20px; color: {TEXT}; margin-top: 8px; }}
  .insight b {{ color: #9ec5f4; }}
  div[data-testid="stVerticalBlockBorderWrapper"] {{ background: {CARD}; border-radius: 14px; }}
  section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #1b1d24 0%, #15161a 100%); border-right: 1px solid {BORDER}; }}
  .stApp {{ background: radial-gradient(1200px 500px at 70% -10%, rgba(57,135,229,.10), transparent 60%), {SURFACE}; }}
  .preset-note {{ color: {MUTED}; font-size: .8rem; margin-top: -4px; }}
  .big-count {{ font-size: 3.2rem; font-weight: 800; color: {TEXT}; line-height: 1; }}
</style>
""", unsafe_allow_html=True)


def style_fig(fig, height=360):
    """Apply one consistent dark theme to every Plotly chart."""
    fig.update_layout(
        template="plotly_dark", height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_2, size=12), margin=dict(l=8, r=16, t=8, b=8),
        hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER, font_color=TEXT),
        barcornerradius=4, showlegend=False,
    )
    fig.update_xaxes(gridcolor=BORDER, zeroline=False, linecolor=BORDER, title_font_color=MUTED)
    fig.update_yaxes(gridcolor=BORDER, zeroline=False, linecolor=BORDER, title_font_color=MUTED)
    return fig


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="bar"></div><div class="label">{label}</div>'
                 f'<div class="value">{value}</div><div class="sub">{sub}</div></div>',
                 unsafe_allow_html=True)


def card_header(title, sub=""):
    st.markdown(f'<p class="card-title">{title}</p><p class="card-sub">{sub}</p>', unsafe_allow_html=True)


# ---------------------------------------------------------------- data loading
@st.cache_resource(ttl=60)
def engine_or_none():
    """Return a live engine, or None if PostgreSQL is not reachable (re-checked every 60s)."""
    try:
        eng = get_engine()
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        return eng
    except Exception:
        return None


@st.cache_data
def load_data():
    """Load movies + genres into one movie-level frame (genres as a list per movie)."""
    eng = engine_or_none()
    if eng is not None:
        movies = pd.read_sql("SELECT * FROM movies", eng, parse_dates=["release_date"])
        mg = pd.read_sql("SELECT mg.movie_id, g.genre_name FROM movie_genres mg "
                         "JOIN genres g USING (genre_id) ORDER BY mg.ctid", eng)
        src = "PostgreSQL"
    else:
        movies = pd.read_csv(CLEAN / "movies.csv", parse_dates=["release_date"])
        mg = pd.read_csv(CLEAN / "movie_genres.csv").merge(pd.read_csv(CLEAN / "genres.csv"), on="genre_id")
        src = "CSV fallback"
    for c in ["runtime", "popularity", "vote_average", "budget", "revenue", "vote_count"]:
        movies[c] = pd.to_numeric(movies[c], errors="coerce")
    movies["release_year"] = movies["release_date"].dt.year
    # TMDB rule: 0 = unknown -> NaN for money metrics
    movies["budget_m"] = movies["budget"].replace(0, np.nan) / 1e6
    movies["revenue_m"] = movies["revenue"].replace(0, np.nan) / 1e6
    genre_lists = mg.groupby("movie_id", sort=False)["genre_name"].agg(list)
    movies["genres"] = movies["movie_id"].map(genre_lists).apply(lambda g: g if isinstance(g, list) else [])
    return movies, mg, src


@st.cache_data
def load_people():
    """Cast, directors and keywords for the Talent / Themes tabs."""
    eng = engine_or_none()
    if eng is not None:
        cast = pd.read_sql('SELECT movie_id, person_id, actor_name, cast_order FROM "cast"', eng)
        dirs = pd.read_sql("SELECT movie_id, person_id, person_name FROM crew WHERE job = 'Director'", eng)
        kw = pd.read_sql("SELECT movie_id, keyword_name FROM movie_keywords", eng)
    else:
        cast = pd.read_csv(CLEAN / "cast.csv")
        crew = pd.read_csv(CLEAN / "crew.csv")
        dirs = crew[crew["job"] == "Director"][["movie_id", "person_id", "person_name"]]
        kw = pd.read_csv(CLEAN / "movie_keywords.csv")[["movie_id", "keyword_name"]]
    return cast, dirs, kw


movies, movie_genres, SOURCE = load_data()
CAST, DIRECTORS, KEYWORDS = load_people()
ALL_GENRES = sorted(movie_genres["genre_name"].unique())
ALL_LANGS = sorted(movies["original_language"].dropna().unique())
yr_min, yr_max = int(movies["release_year"].min()), int(movies["release_year"].max())

# default filter state (shared across pages)
defaults = {"f_genres": [], "f_years": (yr_min, yr_max), "f_rating": (0.0, 10.0), "f_langs": []}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)


def apply_filters(df):
    """Apply the filters saved on Page 1 to the movie frame."""
    s = st.session_state
    out = df[df["release_year"].between(*s.f_years) & df["vote_average"].between(*s.f_rating)]
    if s.f_genres:
        out = out[out["genres"].apply(lambda g: any(x in g for x in s.f_genres))]
    if s.f_langs:
        out = out[out["original_language"].isin(s.f_langs)]
    return out


def money(m):
    """Format a $-million value as $xM / $xB."""
    if pd.isna(m):
        return "n/a"
    return f"${m / 1e3:,.2f}B" if m >= 1000 else f"${m:,.0f}M"


# ---------------------------------------------------------------- sidebar
st.sidebar.markdown("## 🎬 Reel Insights")
st.sidebar.caption("TMDB Movie Industry EDA")
page = st.sidebar.radio("Navigate", ["Filters", "Dashboard", "Query Explorer"],
                        index=1, label_visibility="collapsed")
filtered = apply_filters(movies)
st.sidebar.divider()
st.sidebar.metric("Movies matching filters", f"{len(filtered):,}")
st.sidebar.caption(f"{len(filtered) / len(movies):.0%} of {len(movies):,} movies")
active = [f"{len(st.session_state.f_genres)} genre(s)" if st.session_state.f_genres else None,
          f"{st.session_state.f_years[0]}–{st.session_state.f_years[1]}",
          f"rating {st.session_state.f_rating[0]:.1f}–{st.session_state.f_rating[1]:.1f}"]
st.sidebar.caption("Active filters: " + " · ".join(a for a in active if a))
dot = "🟢" if SOURCE == "PostgreSQL" else "🟠"
st.sidebar.caption(f"{dot} Data source: **{SOURCE}**")


def hero(title, subtitle):
    st.markdown(f'<div class="hero"><h1>{title}<span class="pill">{SOURCE}</span></h1>'
                f'<p>{subtitle}</p></div>', unsafe_allow_html=True)


# ================================================================= PAGE 1 – FILTERS
if page == "Filters":
    hero("Filters", "Pick a quick preset or build your own selection – it applies across the Dashboard.")

    PRESETS = {
        "🎬 All movies": {},
        "💥 Blockbusters": {"f_genres": ["Action", "Adventure", "Science Fiction"], "f_years": (2000, yr_max)},
        "🏆 Critically acclaimed": {"f_rating": (7.5, 10.0)},
        "👻 Horror (ROI kings)": {"f_genres": ["Horror"]},
        "🧸 Family & Animation": {"f_genres": ["Animation", "Family"]},
        "🎞️ Classics (pre-1990)": {"f_years": (yr_min, 1989)},
    }

    def apply_preset(cfg):
        for k, v in defaults.items():
            st.session_state[k] = cfg.get(k, v)

    st.markdown('<p class="card-title">Quick presets</p>', unsafe_allow_html=True)
    pcols = st.columns(len(PRESETS))
    for col, (name, cfg) in zip(pcols, PRESETS.items()):
        if col.button(name, width="stretch"):
            apply_preset(cfg)
            st.rerun()
    st.markdown("&nbsp;")

    # widget keys (w_*) are copied into persistent keys (f_*) so filters survive page switches
    for k in defaults:
        st.session_state["w" + k[1:]] = st.session_state[k]

    def sync():
        for k in defaults:
            st.session_state[k] = st.session_state["w" + k[1:]]

    left, right = st.columns([2, 1], gap="large")
    with left:
        with st.container(border=True):
            card_header("Custom filters", "Changes apply instantly")
            c1, c2 = st.columns(2)
            with c1:
                st.multiselect("Genre", ALL_GENRES, key="w_genres", on_change=sync, placeholder="All genres")
                st.slider("Release year", yr_min, yr_max, key="w_years", on_change=sync)
            with c2:
                st.multiselect("Original language", ALL_LANGS, key="w_langs", on_change=sync,
                               placeholder="All languages")
                st.slider("Rating (vote_average)", 0.0, 10.0, step=0.1, key="w_rating", on_change=sync)
            if st.button("↺ Reset filters"):
                apply_preset({})
                st.rerun()
    filtered = apply_filters(movies)
    with right:
        with st.container(border=True):
            st.markdown(f'<div class="kpi" style="border:none;background:none;padding:6px 4px">'
                        f'<div class="label">Live movie count</div>'
                        f'<div class="big-count">{len(filtered):,}</div>'
                        f'<div class="sub">{len(filtered) / len(movies):.0%} of {len(movies):,} movies</div></div>',
                        unsafe_allow_html=True)
            st.progress(len(filtered) / len(movies))
            if len(filtered):
                f_fin = filtered.dropna(subset=["revenue_m"])
                st.markdown(
                    f'<div class="sub" style="color:{TEXT_2};line-height:1.9">'
                    f'★ Avg rating <b style="color:{TEXT}">{filtered["vote_average"].mean():.2f}</b><br>'
                    f'💰 Total revenue <b style="color:{TEXT}">{money(f_fin["revenue_m"].sum())}</b><br>'
                    f'📅 {filtered["release_year"].min():.0f} – {filtered["release_year"].max():.0f}</div>',
                    unsafe_allow_html=True)

    if filtered.empty:
        st.warning("No movies match – try a preset or widen the filters.")
        st.stop()

    # ---- live preview of the selection
    st.markdown("&nbsp;")
    p1, p2, p3 = st.columns(3, gap="medium")
    with p1:
        with st.container(border=True):
            card_header("Genre mix", "Top 8 genres in selection")
            gm = filtered.explode("genres")["genres"].value_counts().head(8).sort_values()
            fig = go.Figure(go.Bar(y=gm.index, x=gm.values, orientation="h", marker_color=BLUE,
                                   text=gm.values, textposition="outside", cliponaxis=False,
                                   textfont=dict(color=TEXT_2, size=11),
                                   hovertemplate="<b>%{y}</b><br>%{x} movies<extra></extra>"))
            fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, gm.max() * 1.2])
            st.plotly_chart(style_fig(fig, 260), width="stretch")
    with p2:
        with st.container(border=True):
            card_header("Ratings", "Distribution of vote_average")
            fig = go.Figure(go.Histogram(x=filtered["vote_average"], xbins=dict(size=.25), marker_color=AQUA,
                                         hovertemplate="Rating %{x}<br>%{y} movies<extra></extra>"))
            fig.update_layout(bargap=.08)
            st.plotly_chart(style_fig(fig, 260), width="stretch")
    with p3:
        with st.container(border=True):
            card_header("Release timeline", "Movies per year")
            py = filtered.dropna(subset=["release_year"]).groupby("release_year").size()
            fig = go.Figure(go.Scatter(x=py.index, y=py.values, mode="lines", fill="tozeroy",
                                       line=dict(color=ORANGE, width=2), fillcolor="rgba(217,89,38,.18)",
                                       hovertemplate="<b>%{x:.0f}</b><br>%{y} movies<extra></extra>"))
            st.plotly_chart(style_fig(fig, 260), width="stretch")

    with st.container(border=True):
        card_header("Matching movies", "Top 50 by popularity")
        st.dataframe(
            filtered.sort_values("popularity", ascending=False).head(50)[
                ["title", "release_year", "original_language", "vote_average", "popularity", "budget_m", "revenue_m"]],
            hide_index=True, width="stretch", height=380,
            column_config={
                "title": "Title", "release_year": st.column_config.NumberColumn("Year", format="%d"),
                "original_language": "Lang",
                "vote_average": st.column_config.ProgressColumn("Rating", min_value=0, max_value=10, format="%.1f"),
                "popularity": st.column_config.NumberColumn("Popularity", format="%.1f"),
                "budget_m": st.column_config.NumberColumn("Budget ($M)", format="$%.0f"),
                "revenue_m": st.column_config.NumberColumn("Revenue ($M)", format="$%.0f"),
            })


# ================================================================= PAGE 2 – DASHBOARD
elif page == "Dashboard":
    hero("Movie Industry Dashboard", "Box office, genres and ratings for the filtered TMDB catalogue.")
    df = filtered
    if df.empty:
        st.warning("No movies match the current filters – widen them on the Filters page.")
        st.stop()
    fin = df.dropna(subset=["budget_m", "revenue_m"]).copy()
    fin["roi"] = (fin["revenue_m"] - fin["budget_m"]) / fin["budget_m"]

    # ---- KPI row
    k = st.columns(5, gap="small")
    kpi(k[0], "Movies", f"{len(df):,}", f"{df['release_year'].min():.0f}–{df['release_year'].max():.0f}")
    kpi(k[1], "Avg rating", f"{df['vote_average'].mean():.2f}", "out of 10")
    kpi(k[2], "Total revenue", money(df["revenue_m"].sum()), "known figures only")
    kpi(k[3], "Median budget", money(df["budget_m"].median()), "0 = unknown, excluded")
    kpi(k[4], "Median ROI", f"{fin['roi'].median():.2f}x" if len(fin) else "n/a",
        f"{(fin['roi'] > 0).mean():.0%} profitable" if len(fin) else "")
    st.markdown("&nbsp;")

    t_over, t_gen, t_tal, t_trend, t_ins = st.tabs(
        ["📊 Overview", "🎭 Genres", "⭐ Talent", "📈 Trends & Themes", "💡 Key Insights"])
    ids = set(df["movie_id"])
    mg_f = movie_genres[movie_genres["movie_id"].isin(ids)].merge(
        df[["movie_id", "vote_average", "budget_m", "revenue_m", "popularity", "release_year"]], on="movie_id")
    mg_f["roi"] = (mg_f["revenue_m"] - mg_f["budget_m"]) / mg_f["budget_m"]

    with t_over:
        # ---- row 1: top 10 revenue | genre distribution
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            with st.container(border=True):
                card_header("Top 10 movies by revenue", "Worldwide box office")
                top10 = df.dropna(subset=["revenue_m"]).nlargest(10, "revenue_m").sort_values("revenue_m")
                fig = go.Figure(go.Bar(
                    x=top10["revenue_m"], y=top10["title"], orientation="h", marker_color=BLUE,
                    text=[money(v) for v in top10["revenue_m"]], textposition="outside",
                    textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
                    customdata=top10[["release_year", "budget_m"]],
                    hovertemplate="<b>%{y}</b> (%{customdata[0]:.0f})<br>Revenue: $%{x:,.0f}M"
                                  "<br>Budget: $%{customdata[1]:,.0f}M<extra></extra>"))
                fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, top10["revenue_m"].max() * 1.18])
                st.plotly_chart(style_fig(fig), width="stretch")
        with c2:
            with st.container(border=True):
                card_header("Genre distribution", "Movies per genre (a movie can have several)")
                g = df.explode("genres")["genres"].value_counts().head(12).sort_values()
                fig = go.Figure(go.Bar(
                    x=g.values, y=g.index, orientation="h", marker_color=BLUE,
                    text=g.values, textposition="outside", textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
                    hovertemplate="<b>%{y}</b><br>%{x:,} movies<extra></extra>"))
                fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, g.max() * 1.15])
                st.plotly_chart(style_fig(fig), width="stretch")

        # ---- row 2: budget vs revenue | releases per year
        c3, c4 = st.columns([3, 2], gap="medium")
        with c3:
            with st.container(border=True):
                card_header("Budget vs revenue", "Log scale · colour = rating · dashed line = break-even")
                if len(fin):
                    fig = px.scatter(fin, x="budget_m", y="revenue_m", color="vote_average", hover_name="title",
                                     log_x=True, log_y=True, color_continuous_scale=BLUE_RAMP,
                                     range_color=(5, 8.5),
                                     custom_data=["release_year", "roi"],
                                     labels={"budget_m": "Budget ($M)", "revenue_m": "Revenue ($M)",
                                             "vote_average": "Rating"})
                    fig.update_traces(marker=dict(size=8, opacity=.75, line=dict(width=1, color=SURFACE)),
                                      hovertemplate="<b>%{hovertext}</b> (%{customdata[0]:.0f})<br>"
                                                    "Budget $%{x:,.1f}M · Revenue $%{y:,.1f}M<br>"
                                                    "ROI %{customdata[1]:.1f}x · Rating %{marker.color:.1f}<extra></extra>")
                    lo, hi = fin["budget_m"].min(), fin["budget_m"].max()
                    fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", hoverinfo="skip",
                                             line=dict(color=MUTED, dash="dash", width=1.5)))
                    style_fig(fig, 380)
                    fig.update_layout(coloraxis_colorbar=dict(title="Rating", thickness=10, len=.7,
                                                              tickfont=dict(color=TEXT_2)))
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info("No movies with known budget and revenue in this selection.")
        with c4:
            with st.container(border=True):
                card_header("Releases per year", "Number of movies")
                per_year = df.dropna(subset=["release_year"]).groupby("release_year").size()
                fig = go.Figure(go.Bar(x=per_year.index, y=per_year.values, marker_color=BLUE,
                                       hovertemplate="<b>%{x:.0f}</b><br>%{y} movies<extra></extra>"))
                fig.update_layout(bargap=0.15)
                st.plotly_chart(style_fig(fig, 380), width="stretch")

        # ---- auto-generated insight
        top_genre = df.explode("genres")["genres"].value_counts().idxmax()
        best = df.dropna(subset=["revenue_m"]).nlargest(1, "revenue_m")
        corr = fin["budget_m"].corr(fin["revenue_m"]) if len(fin) > 2 else np.nan
        best_roi = fin[fin["budget_m"] >= 1].nlargest(1, "roi")
        parts = [f"Of <b>{len(df):,}</b> movies, <b>{top_genre}</b> is the most common genre"]
        if len(best):
            parts.append(f"<b>{best.iloc[0]['title']}</b> is the top earner at <b>{money(best.iloc[0]['revenue_m'])}</b>")
        if len(fin) > 2:
            strength = "strong" if corr > .6 else "moderate" if corr > .3 else "weak"
            parts.append(f"budget and revenue show a <b>{strength}</b> link (r = {corr:.2f}), and "
                         f"<b>{(fin['roi'] > 0).mean():.0%}</b> of films with known financials made a profit")
        if len(best_roi):
            r = best_roi.iloc[0]
            parts.append(f"the best return came from <b>{r['title']}</b> ({r['roi']:.0f}x on a {money(r['budget_m'])} budget)")
        st.markdown('<div class="insight">💡 <b>Insight</b><br>' + "; ".join(parts) + ".</div>",
                    unsafe_allow_html=True)

    # ------------------------------------------------------------ GENRES
    with t_gen:
        gstats = (mg_f.groupby("genre_name")
                  .agg(movies=("movie_id", "nunique"), avg_rating=("vote_average", "mean"),
                       avg_budget=("budget_m", "mean"), avg_revenue=("revenue_m", "mean"),
                       median_roi=("roi", "median"), avg_popularity=("popularity", "mean"))
                  .query("movies >= 10"))
        if gstats.empty:
            st.info("Not enough movies per genre in this selection (need ≥ 10).")
        else:
            c1, c2 = st.columns(2, gap="medium")
            with c1:
                with st.container(border=True):
                    card_header("Genre economics", "Average budget vs average revenue ($M) · genres with ≥ 10 movies")
                    ge = gstats.sort_values("avg_revenue").tail(12)
                    fig = go.Figure([
                        go.Bar(name="Avg budget", y=ge.index, x=ge["avg_budget"], orientation="h",
                               marker_color=ORANGE, hovertemplate="<b>%{y}</b><br>Avg budget $%{x:,.0f}M<extra></extra>"),
                        go.Bar(name="Avg revenue", y=ge.index, x=ge["avg_revenue"], orientation="h",
                               marker_color=BLUE, hovertemplate="<b>%{y}</b><br>Avg revenue $%{x:,.0f}M<extra></extra>")])
                    style_fig(fig, 430)
                    fig.update_layout(barmode="group", bargap=.25, bargroupgap=.08, showlegend=True,
                                      legend=dict(orientation="h", y=1.08, x=0, font=dict(color=TEXT_2)))
                    st.plotly_chart(fig, width="stretch")
            with c2:
                with st.container(border=True):
                    card_header("Return on investment by genre", "Median ROI (x) · films with known budget & revenue")
                    gr = gstats.dropna(subset=["median_roi"]).sort_values("median_roi").tail(12)
                    fig = go.Figure(go.Bar(
                        y=gr.index, x=gr["median_roi"], orientation="h", marker_color=AQUA,
                        text=[f"{v:.1f}x" for v in gr["median_roi"]], textposition="outside",
                        textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
                        hovertemplate="<b>%{y}</b><br>Median ROI %{x:.2f}x<extra></extra>"))
                    fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, gr["median_roi"].max() * 1.18])
                    st.plotly_chart(style_fig(fig, 430), width="stretch")

            c3, c4 = st.columns([2, 3], gap="medium")
            with c3:
                with st.container(border=True):
                    card_header("Average rating by genre", "Dashed line = average for this selection")
                    rr = gstats.sort_values("avg_rating").tail(12)
                    fig = go.Figure(go.Bar(
                        y=rr.index, x=rr["avg_rating"], orientation="h", marker_color=BLUE,
                        text=[f"{v:.2f}" for v in rr["avg_rating"]], textposition="outside",
                        textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
                        hovertemplate="<b>%{y}</b><br>Avg rating %{x:.2f}<extra></extra>"))
                    fig.add_vline(x=df["vote_average"].mean(), line_dash="dash", line_color=MUTED, line_width=1.5)
                    fig.update_xaxes(range=[rr["avg_rating"].min() - .6, rr["avg_rating"].max() + .25], showgrid=False)
                    st.plotly_chart(style_fig(fig, 430), width="stretch")
            with c4:
                with st.container(border=True):
                    card_header("Genre scorecard", "All metrics side by side")
                    st.dataframe(
                        gstats.sort_values("avg_revenue", ascending=False).reset_index(),
                        hide_index=True, width="stretch", height=410,
                        column_config={
                            "genre_name": "Genre", "movies": st.column_config.NumberColumn("Movies", format="%d"),
                            "avg_rating": st.column_config.ProgressColumn("Avg rating", min_value=5, max_value=8, format="%.2f"),
                            "avg_budget": st.column_config.NumberColumn("Avg budget", format="$%.0fM"),
                            "avg_revenue": st.column_config.NumberColumn("Avg revenue", format="$%.0fM"),
                            "median_roi": st.column_config.NumberColumn("Median ROI", format="%.2fx"),
                            "avg_popularity": st.column_config.NumberColumn("Popularity", format="%.1f")})

    # ------------------------------------------------------------ TALENT
    with t_tal:
        mv = df[["movie_id", "vote_average", "revenue_m"]]

        def people_chart(frame, name_col, title, sub):
            stats = (frame.merge(mv, on="movie_id").groupby(["person_id", name_col])
                     .agg(movies=("movie_id", "nunique"), avg_rating=("vote_average", "mean"),
                          total_rev=("revenue_m", "sum"))
                     .reset_index().sort_values(["movies", "avg_rating"], ascending=False).head(10)
                     .sort_values(["movies", "avg_rating"]))
            with st.container(border=True):
                card_header(title, sub)
                if stats.empty:
                    st.info("No data for this selection.")
                    return stats
                fig = go.Figure(go.Bar(
                    y=stats[name_col], x=stats["movies"], orientation="h", marker_color=BLUE,
                    text=[f"{m} films · ★ {r:.1f}" for m, r in zip(stats["movies"], stats["avg_rating"])],
                    textposition="outside", textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
                    customdata=stats[["avg_rating", "total_rev"]],
                    hovertemplate="<b>%{y}</b><br>%{x} films · avg rating %{customdata[0]:.2f}"
                                  "<br>Total revenue $%{customdata[1]:,.0f}M<extra></extra>"))
                fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, stats["movies"].max() * 1.45])
                st.plotly_chart(style_fig(fig, 400), width="stretch")
            return stats

        c1, c2 = st.columns(2, gap="medium")
        with c1:
            people_chart(CAST, "actor_name", "Most prolific actors", "Films in selection · ★ = average rating")
        with c2:
            people_chart(DIRECTORS, "person_name", "Most prolific directors", "Films in selection · ★ = average rating")

        with st.container(border=True):
            card_header("Highest-rated directors", "Directors with at least 4 films in this selection")
            d = (DIRECTORS.merge(mv, on="movie_id").groupby("person_name")
                 .agg(films=("movie_id", "nunique"), avg_rating=("vote_average", "mean"),
                      total_revenue=("revenue_m", "sum"))
                 .query("films >= 4").sort_values("avg_rating", ascending=False).head(10).reset_index())
            if d.empty:
                st.info("No director has 4+ films in this selection.")
            else:
                st.dataframe(d, hide_index=True, width="stretch", column_config={
                    "person_name": "Director", "films": "Films",
                    "avg_rating": st.column_config.ProgressColumn("Avg rating", min_value=5, max_value=9, format="%.2f"),
                    "total_revenue": st.column_config.NumberColumn("Total revenue", format="$%.0fM")})

    # ------------------------------------------------------------ TRENDS & THEMES
    with t_trend:
        dec = df.dropna(subset=["release_year"]).assign(decade=lambda x: (x["release_year"] // 10 * 10).astype(int))
        dstats = dec.groupby("decade").agg(movies=("movie_id", "count"), avg_rating=("vote_average", "mean"),
                                           median_budget=("budget_m", "median"))
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            with st.container(border=True):
                card_header("Average rating by decade", "Older films rate higher – only the classics survive")
                fig = go.Figure(go.Scatter(
                    x=[f"{d}s" for d in dstats.index], y=dstats["avg_rating"], mode="lines+markers",
                    line=dict(color=BLUE, width=2), marker=dict(size=9, color=BLUE, line=dict(width=2, color=SURFACE)),
                    customdata=dstats["movies"],
                    hovertemplate="<b>%{x}</b><br>Avg rating %{y:.2f}<br>%{customdata} movies<extra></extra>"))
                st.plotly_chart(style_fig(fig, 340), width="stretch")
        with c2:
            with st.container(border=True):
                card_header("Median budget by decade", "$M · known budgets only")
                fig = go.Figure(go.Bar(
                    x=[f"{d}s" for d in dstats.index], y=dstats["median_budget"], marker_color=ORANGE,
                    hovertemplate="<b>%{x}</b><br>Median budget $%{y:,.1f}M<extra></extra>"))
                st.plotly_chart(style_fig(fig, 340), width="stretch")

        c3, c4 = st.columns(2, gap="medium")
        with c3:
            with st.container(border=True):
                card_header("Most common themes", "Top 12 keywords in this selection")
                kw = KEYWORDS[KEYWORDS["movie_id"].isin(ids)]["keyword_name"].value_counts().head(12).sort_values()
                fig = go.Figure(go.Bar(
                    y=kw.index, x=kw.values, orientation="h", marker_color=BLUE,
                    text=kw.values, textposition="outside", textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
                    hovertemplate="<b>%{y}</b><br>%{x} movies<extra></extra>"))
                fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, (kw.max() if len(kw) else 1) * 1.18])
                st.plotly_chart(style_fig(fig, 400), width="stretch")
        with c4:
            with st.container(border=True):
                card_header("Rating distribution", "Movies with at least 10 votes")
                rated = df[df["vote_count"] >= 10]
                fig = go.Figure(go.Histogram(x=rated["vote_average"], xbins=dict(size=.25), marker_color=BLUE,
                                             hovertemplate="Rating %{x}<br>%{y} movies<extra></extra>"))
                fig.add_vline(x=rated["vote_average"].mean(), line_dash="dash", line_color=MUTED, line_width=1.5,
                              annotation_text=f"mean {rated['vote_average'].mean():.2f}",
                              annotation_font_color=TEXT_2)
                fig.update_layout(bargap=.08)
                st.plotly_chart(style_fig(fig, 400), width="stretch")

    # ------------------------------------------------------------ KEY INSIGHTS
    with t_ins:
        def insight_card(col, icon, title, stat, stat_label, finding, action):
            col.markdown(f"""
            <div class="kpi" style="margin-bottom:16px">
              <div class="bar"></div>
              <div class="label">{icon} {title}</div>
              <div class="value">{stat}</div>
              <div class="sub" style="margin-bottom:10px">{stat_label}</div>
              <div style="color:{TEXT};font-size:.92rem;line-height:1.5">{finding}</div>
              <div style="color:#9ec5f4;font-size:.88rem;margin-top:10px;line-height:1.5">→ <b>Recommendation:</b> {action}</div>
            </div>""", unsafe_allow_html=True)

        cards = []
        if len(fin) > 2:
            corr = fin["budget_m"].corr(fin["revenue_m"])
            cards.append(("💰", "Budget drives revenue", f"r = {corr:.2f}", "budget–revenue correlation",
                          f"Bigger budgets earn more, and {(fin['roi'] > 0).mean():.0%} of films with known figures were "
                          f"profitable – but {((fin['budget_m'] > fin['budget_m'].mean()) & (fin['revenue_m'] < fin['revenue_m'].mean())).sum()} "
                          "high-budget films still under-performed.",
                          "add a stage-gate review for any project above the average budget."))
            big = fin[fin["budget_m"] >= 1]
            if len(big) >= 15:
                top15 = big.nlargest(15, "roi")
                cards.append(("🚀", "Small budgets, big returns", f"{fin['roi'].median():.2f}x",
                              f"median ROI · top-15 ROI films median budget {money(top15['budget_m'].median())}",
                              f"The best percentage returns come from low-budget films such as "
                              f"{', '.join(top15['title'].head(3))} – vs a {money(fin['budget_m'].median())} median budget overall.",
                              "keep part of the slate in low-budget genre films for outsized returns."))
        if not gstats.empty:
            g_rev = gstats["avg_revenue"].idxmax(); g_rat = gstats["avg_rating"].idxmax()
            cards.append(("🎭", "Box office ≠ acclaim", f"{g_rev} vs {g_rat}", "top revenue genre vs top rated genre",
                          f"{g_rev} leads average revenue ({money(gstats.loc[g_rev, 'avg_revenue'])}) but rates "
                          f"{gstats.loc[g_rev, 'avg_rating']:.2f}; {g_rat} rates highest ({gstats.loc[g_rat, 'avg_rating']:.2f}).",
                          "track quality and commercial KPIs separately – prestige vs theatrical slates."))
        kw_all = KEYWORDS[KEYWORDS["movie_id"].isin(ids)]["keyword_name"].value_counts()
        if len(kw_all) >= 2:
            cards.append(("📚", "Existing IP dominates", f"'{kw_all.index[0]}'", f"most used keyword ({kw_all.iloc[0]} movies)",
                          f"'{kw_all.index[0]}' and '{kw_all.index[1]}' are the top themes – the market leans on adaptations and franchises.",
                          "prioritise adaptations and sequels in acquisition; use these tags in recommendations."))
        a = CAST[CAST["movie_id"].isin(ids)].merge(df[["movie_id", "vote_average"]], on="movie_id") \
            .groupby("actor_name").agg(n=("movie_id", "nunique"), r=("vote_average", "mean")).sort_values("n", ascending=False).head(10)
        if len(a):
            hi, lo = a["r"].idxmax(), a["r"].idxmin()
            cards.append(("⭐", "Volume ≠ quality", a.index[0], f"most prolific actor ({int(a.iloc[0]['n'])} films)",
                          f"Among the 10 busiest actors, {hi} averages ★ {a.loc[hi, 'r']:.2f} while {lo} averages ★ {a.loc[lo, 'r']:.2f}.",
                          "cast talent with both high volume and above-average ratings."))
        missing = (df["budget"].fillna(0).eq(0) | df["revenue"].fillna(0).eq(0)).mean()
        cards.append(("🧹", "Data quality", f"{1 - missing:.0%}", "of movies have both budget & revenue",
                      "TMDB stores unknown money as 0. These were excluded from every financial metric instead of being guessed.",
                      "always report the sample size next to financial KPIs."))

        cols = st.columns(2, gap="medium")
        for i, c in enumerate(cards):
            insight_card(cols[i % 2], *c)

# ================================================================= PAGE 3 – QUERY EXPLORER
else:
    hero("Query Explorer", "Run the 10 saved SQL business questions live against PostgreSQL.")
    eng = engine_or_none()
    if eng is None:
        st.error("PostgreSQL is not reachable. Start it with `brew services start postgresql@16`, "
                 "then refresh this page.")
        st.stop()

    c1, c2 = st.columns([3, 2], gap="medium")
    qname = c1.selectbox("Saved query", list(QUERIES))
    params = dict(DEFAULT_PARAMS)
    if ":director" in QUERIES[qname]:
        params["director"] = c2.text_input("Director name", DEFAULT_PARAMS["director"])
    with st.expander("Show SQL"):
        st.code(QUERIES[qname].strip(), language="sql")

    with eng.connect() as conn:
        res = pd.read_sql(text(QUERIES[qname]), conn, params=params)
    # NUMERIC columns arrive as Decimal objects -> convert to float for charting
    for c in res.columns:
        if res[c].dtype == object:
            conv = pd.to_numeric(res[c], errors="coerce")
            if len(res) and conv.notna().all():
                res[c] = conv.astype(float)

    num_cols = res.select_dtypes("number").columns.tolist()
    txt_cols = [c for c in res.columns if c not in num_cols]
    m1, m2 = st.columns(2)
    kpi(m1, "Rows returned", f"{len(res):,}")
    if num_cols and len(res):
        kpi(m2, f"Top {num_cols[0].replace('_', ' ')}", f"{res[num_cols[0]].max():,.2f}".rstrip("0").rstrip("."),
            str(res.loc[res[num_cols[0]].idxmax(), txt_cols[0]]) if txt_cols else "")
    st.markdown("&nbsp;")

    chartable = bool(len(res) and num_cols and txt_cols)
    if not chartable:
        if len(res):
            st.dataframe(res, width="stretch", hide_index=True, height=420)
            st.markdown(f'<div class="insight">💡 <b>Insight</b><br>The query returned <b>{len(res):,}</b> rows, '
                        f'e.g. <b>{res.iloc[0, 0]}</b> – <b>{res.iloc[0, 1]}</b>.</div>', unsafe_allow_html=True)
        else:
            st.warning("Query returned no rows.")
        st.stop()
    tab_chart, tab_table = st.tabs(["📊 Chart", "📋 Table"])
    with tab_table:
        st.dataframe(res, width="stretch", hide_index=True)
    with tab_chart:
        if len(res) and num_cols and txt_cols:
            y, x = txt_cols[0], num_cols[0]
            chart_df = res.head(20).sort_values(x)
            fig = go.Figure(go.Bar(
                x=chart_df[x], y=chart_df[y].astype(str), orientation="h", marker_color=BLUE,
                text=[f"{v:,.2f}".rstrip("0").rstrip(".") for v in chart_df[x]], textposition="outside",
                textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
                hovertemplate=f"<b>%{{y}}</b><br>{x}: %{{x:,.2f}}<extra></extra>"))
            fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, chart_df[x].max() * 1.15])
            st.plotly_chart(style_fig(fig, max(320, 28 * len(chart_df))), width="stretch")
            top = chart_df.iloc[-1]
            st.markdown(f'<div class="insight">💡 <b>Insight</b><br><b>{top[y]}</b> ranks highest on '
                        f'<b>{x.replace("_", " ")}</b> ({top[x]:,.2f}) among {len(res):,} result rows.</div>',
                        unsafe_allow_html=True)
        elif len(res):
            st.info("This query returns a list (no numeric column to chart) – see the Table tab.")
            st.markdown(f'<div class="insight">💡 <b>Insight</b><br>The query returned <b>{len(res):,}</b> rows, '
                        f'e.g. <b>{res.iloc[0, 0]}</b>.</div>', unsafe_allow_html=True)
        else:
            st.warning("Query returned no rows.")
