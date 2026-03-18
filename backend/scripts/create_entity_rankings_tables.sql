-- Entity ranking snapshot tables for frontend-only demo mode.
-- Run this in the Supabase SQL editor.

create table if not exists public.entity_rankings_snapshots (
  key text primary key,
  period text not null check (period in ('7d', '30d')),
  source text null,
  include_today boolean not null default true,
  scan_mode text not null default 'fast' check (scan_mode in ('fast', 'full')),
  limit_articles int not null default 500,
  total_cap int not null default 1000,
  max_entities int not null default 100,
  sampled int not null default 0,
  total_available int not null default 0,
  total_capped int not null default 0,
  computed_at timestamptz not null default now()
);

create index if not exists entity_rankings_snapshots_period_source_time_idx
  on public.entity_rankings_snapshots (period, source, computed_at desc);

create table if not exists public.entity_rankings_items (
  snapshot_key text not null references public.entity_rankings_snapshots(key) on delete cascade,
  entity_text text not null,
  entity_type text not null,
  mentions int not null,
  avg_sentiment double precision null,
  primary key (snapshot_key, entity_text, entity_type)
);

create index if not exists entity_rankings_items_snapshot_key_idx
  on public.entity_rankings_items (snapshot_key);

alter table public.entity_rankings_snapshots enable row level security;
alter table public.entity_rankings_items enable row level security;

drop policy if exists "Public read entity snapshots" on public.entity_rankings_snapshots;
create policy "Public read entity snapshots"
  on public.entity_rankings_snapshots
  for select
  using (true);

drop policy if exists "Public read entity snapshot items" on public.entity_rankings_items;
create policy "Public read entity snapshot items"
  on public.entity_rankings_items
  for select
  using (true);

-- Supabase also requires GRANTs in addition to RLS policies.
-- Allow the frontend (anon/authenticated) to read snapshots.
grant usage on schema public to anon, authenticated;
grant select on table public.entity_rankings_snapshots to anon, authenticated;
grant select on table public.entity_rankings_items to anon, authenticated;

-- Allow snapshot writer (service_role key) to upsert/delete/insert.
grant usage on schema public to service_role;
grant select, insert, update, delete on table public.entity_rankings_snapshots to service_role;
grant select, insert, update, delete on table public.entity_rankings_items to service_role;
