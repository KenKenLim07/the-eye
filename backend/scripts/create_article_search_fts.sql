-- Full-text search (FTS) for `public.articles` to replace slow `ILIKE %...%` scans.
--
-- Run this in Supabase Dashboard → SQL Editor.
-- IMPORTANT: If you have any text selected in the SQL editor, Supabase will only run
-- the selected portion. Run the whole file (or at least the `ALTER TABLE` first),
-- otherwise the backfill UPDATE will fail with: column "search_tsv" does not exist.
--
-- Notes:
-- - Uses `simple` config to be language-agnostic (PH news can be mixed language).
-- - Adds a `search_tsv` column maintained by a trigger + a GIN index.
-- - After applying, update the frontend to use `.textSearch("search_tsv", q, { type: "websearch", config: "simple" })`.

alter table public.articles
  add column if not exists search_tsv tsvector;

create or replace function public.articles_search_tsv_trigger()
returns trigger
language plpgsql
as $$
begin
  new.search_tsv :=
    to_tsvector(
      'simple',
      coalesce(new.title, '') || ' ' || coalesce(new.content, '')
    );
  return new;
end;
$$;

drop trigger if exists articles_search_tsv_update on public.articles;
create trigger articles_search_tsv_update
before insert or update of title, content
on public.articles
for each row
execute function public.articles_search_tsv_trigger();

-- Backfill existing rows (safe to re-run).
update public.articles
set search_tsv = to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, ''))
where search_tsv is null;

create index if not exists articles_search_tsv_gin_idx
  on public.articles
  using gin (search_tsv);
