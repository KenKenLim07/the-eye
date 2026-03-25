-- Trigram indexes for faster `ILIKE %...%` search.
--
-- Run this in Supabase Dashboard → SQL Editor.
--
-- Notes:
-- - This keeps substring-search semantics (`%query%`) but indexes can be large,
--   especially on `content`. If storage is a concern, index `title` only.

create extension if not exists pg_trgm;

create index if not exists articles_title_trgm_gin_idx
  on public.articles
  using gin (title gin_trgm_ops);

create index if not exists articles_content_trgm_gin_idx
  on public.articles
  using gin (content gin_trgm_ops);

