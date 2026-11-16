-- Runs once, when the Postgres volume is first created.
-- POSTGRES_DB already made the "wardrobe" database; memory gets its own.
CREATE DATABASE memory;
\connect wardrobe
CREATE EXTENSION IF NOT EXISTS vector;
