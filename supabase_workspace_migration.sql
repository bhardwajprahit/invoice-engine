-- Invoice Engine workspace cloud sync
-- Run this in Supabase SQL Editor for the project configured in frontend/supabase-config.js.
-- The browser uses only the publishable/anon key. RLS isolates rows by authenticated user.
create table if not exists public.user_workspaces (
  owner_id uuid primary key references auth.users(id) on delete cascade,
  retail_state jsonb not null default '{"products":[],"sales":[],"purchases":[],"customers":[]}'::jsonb,
  business_settings jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.user_workspaces enable row level security;

-- RLS policies define the row boundary; SQL privileges grant only the
-- operations the signed-in workspace UI needs. Anonymous access is denied.
revoke all on table public.user_workspaces from anon, public;
grant select, insert, update on table public.user_workspaces to authenticated;

drop policy if exists "workspace_select_own" on public.user_workspaces;
drop policy if exists "workspace_insert_own" on public.user_workspaces;
drop policy if exists "workspace_update_own" on public.user_workspaces;

create policy "workspace_select_own" on public.user_workspaces
  for select to authenticated using (auth.uid() = owner_id);
create policy "workspace_insert_own" on public.user_workspaces
  for insert to authenticated with check (auth.uid() = owner_id);
create policy "workspace_update_own" on public.user_workspaces
  for update to authenticated using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

create index if not exists user_workspaces_updated_at_idx
  on public.user_workspaces(updated_at);
