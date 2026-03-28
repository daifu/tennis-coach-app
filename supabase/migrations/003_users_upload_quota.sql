-- Migration 003: upload quota tracking on users table
-- Adds free-tier monthly upload counter.

-- Supabase creates auth.users automatically.
-- We extend with a public profile table.

create table if not exists user_profiles (
    id                          uuid primary key references auth.users(id) on delete cascade,
    tier                        varchar(10) not null default 'free' check (tier in ('free', 'pro')),
    free_uploads_this_month     integer     not null default 0,
    free_uploads_reset_at       timestamptz not null default date_trunc('month', now()) + interval '1 month',
    created_at                  timestamptz not null default now()
);

alter table user_profiles enable row level security;

create policy "Users read own profile"
    on user_profiles for select
    using (auth.uid() = id);

-- Auto-create profile on signup
create or replace function handle_new_user()
returns trigger language plpgsql security definer as $$
begin
    insert into public.user_profiles (id) values (new.id);
    return new;
end;
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function handle_new_user();
