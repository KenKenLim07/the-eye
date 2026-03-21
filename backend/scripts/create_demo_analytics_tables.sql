-- Demo-mode analytics snapshot tables (frontend reads from Supabase; no deployed FastAPI required).
-- Run this in the Supabase SQL editor.

-- 1) Sentiment Trends snapshots (timeline + summary stored as JSON).
create table if not exists public.sentiment_trends_snapshots (
  key text primary key,
  period text not null check (period in ('7d', '30d')),
  source text null,
  include_today boolean not null default true,
  computed_at timestamptz not null default now(),
  summary jsonb not null,
  timeline jsonb not null
);

create index if not exists sentiment_trends_snapshots_period_source_time_idx
  on public.sentiment_trends_snapshots (period, source, computed_at desc);

-- 2) Correlation snapshots (matrix stored as JSON).
create table if not exists public.correlation_snapshots (
  key text primary key,
  period text not null check (period in ('7d', '30d')),
  include_today boolean not null default true,
  computed_at timestamptz not null default now(),
  sources jsonb not null,
  matrix jsonb not null,
  p_values jsonb not null
);

create index if not exists correlation_snapshots_period_time_idx
  on public.correlation_snapshots (period, computed_at desc);

-- 3) Public sentiment cache for per-article badges (one row per article).
create table if not exists public.article_sentiment_public (
  article_id bigint primary key references public.articles(id) on delete cascade,
  sentiment_label text null,
  sentiment_score double precision null,
  updated_at timestamptz not null default now()
);

create index if not exists article_sentiment_public_updated_at_idx
  on public.article_sentiment_public (updated_at desc);

alter table public.sentiment_trends_snapshots enable row level security;
alter table public.correlation_snapshots enable row level security;
alter table public.article_sentiment_public enable row level security;

drop policy if exists "Public read sentiment trend snapshots" on public.sentiment_trends_snapshots;
create policy "Public read sentiment trend snapshots"
  on public.sentiment_trends_snapshots
  for select
  using (true);

drop policy if exists "Public read correlation snapshots" on public.correlation_snapshots;
create policy "Public read correlation snapshots"
  on public.correlation_snapshots
  for select
  using (true);

drop policy if exists "Public read article sentiment public" on public.article_sentiment_public;
create policy "Public read article sentiment public"
  on public.article_sentiment_public
  for select
  using (true);

-- Supabase requires GRANTs in addition to RLS policies.
grant usage on schema public to anon, authenticated;
grant select on table public.sentiment_trends_snapshots to anon, authenticated;
grant select on table public.correlation_snapshots to anon, authenticated;
grant select on table public.article_sentiment_public to anon, authenticated;

grant usage on schema public to service_role;
grant select, insert, update, delete on table public.sentiment_trends_snapshots to service_role;
grant select, insert, update, delete on table public.correlation_snapshots to service_role;
grant select, insert, update, delete on table public.article_sentiment_public to service_role;

