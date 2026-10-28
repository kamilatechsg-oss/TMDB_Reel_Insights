
DROP TABLE IF EXISTS movie_keywords, crew, "cast", movie_genres, genres, movies CASCADE;

CREATE TABLE movies (
    movie_id          INTEGER PRIMARY KEY,
    title             TEXT NOT NULL,
    original_language VARCHAR(10),
    release_date      DATE,
    runtime           NUMERIC,
    budget            BIGINT DEFAULT 0,
    revenue           BIGINT DEFAULT 0,
    popularity        NUMERIC,
    vote_average      NUMERIC(3,1),
    vote_count        INTEGER,
    status            VARCHAR(30),
    overview          TEXT
);
CREATE TABLE genres (
    genre_id   INTEGER PRIMARY KEY,
    genre_name VARCHAR(50) NOT NULL
);
CREATE TABLE movie_genres (
    movie_id INTEGER REFERENCES movies(movie_id),
    genre_id INTEGER REFERENCES genres(genre_id),
    PRIMARY KEY (movie_id, genre_id)
);
CREATE TABLE "cast" (
    cast_row_id    INTEGER PRIMARY KEY,
    movie_id       INTEGER REFERENCES movies(movie_id),
    person_id      INTEGER,
    actor_name     TEXT NOT NULL,
    character_name TEXT,
    cast_order     INTEGER
);
CREATE TABLE crew (
    crew_row_id INTEGER PRIMARY KEY,
    movie_id    INTEGER REFERENCES movies(movie_id),
    person_id   INTEGER,
    person_name TEXT NOT NULL,
    job         VARCHAR(100),
    department  VARCHAR(100)
);
CREATE TABLE movie_keywords (
    movie_id     INTEGER REFERENCES movies(movie_id),
    keyword_id   INTEGER,
    keyword_name TEXT,
    PRIMARY KEY (movie_id, keyword_id)
);
CREATE INDEX idx_cast_movie  ON "cast"(movie_id);
CREATE INDEX idx_crew_movie  ON crew(movie_id);
CREATE INDEX idx_crew_job    ON crew(job);
CREATE INDEX idx_mk_movie    ON movie_keywords(movie_id);
