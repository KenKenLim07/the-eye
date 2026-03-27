-- Sentiment misclassification reports (user feedback) for fine-tuning.
--
-- Run this in Supabase Dashboard → SQL Editor.
-- Stores anonymous “this sentiment label is wrong” reports submitted from Quick View.

create extension if not exists pgcrypto;

create table if not exists public.sentiment_misclassification_reports (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  article_id bigint not null references public.articles(id) on delete cascade,

  -- The sentiment row we showed when the user filed the report.
  predicted_label text null,
  predicted_score real null,
  predicted_model_version text null,
  predicted_created_at timestamptz null,

  -- What the user claims it should be.
  reported_label text not null check (reported_label in ('positive','neutral','negative','unlabeled')),
  reported_score real null,
  note text null,

  -- Context metadata (for debugging UX / entry points).
  context_path text null,

  -- Idempotency + anti-spam.
  client_report_id uuid not null unique,
  reporter_ip_hash text null,
  user_agent text null,

  -- Review workflow (optional).
  status text not null default 'new' check (status in ('new','reviewed','spam')),
  review_notes text null,
  reviewed_at timestamptz null,

  constraint sentiment_misclassification_reports_note_len
    check (note is null or char_length(note) <= 800),
  constraint sentiment_misclassification_reports_context_path_len
    check (context_path is null or char_length(context_path) <= 300),
  constraint sentiment_misclassification_reports_user_agent_len
    check (user_agent is null or char_length(user_agent) <= 400)
);

create index if not exists sentiment_misclassification_reports_article_time_idx
  on public.sentiment_misclassification_reports (article_id, created_at desc);

create index if not exists sentiment_misclassification_reports_ip_time_idx
  on public.sentiment_misclassification_reports (reporter_ip_hash, created_at desc);

alter table public.sentiment_misclassification_reports enable row level security;

-- Do NOT add anon/authenticated insert/select policies.
-- Writes are performed server-side using the Supabase service role key (bypasses RLS).

grant select, insert, update, delete on table public.sentiment_misclassification_reports to service_role;

