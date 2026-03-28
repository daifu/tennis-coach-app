-- Migration 001: pro_players catalog
-- Shared between F1 (picker UI) and F2 (reference pose templates).

create table if not exists pro_players (
    id            uuid primary key default gen_random_uuid(),
    name          text        not null,
    gender        varchar(3)  not null check (gender in ('atp', 'wta')),
    thumbnail_url text        not null,
    shot_types    text[]      not null default '{}',
    is_active     boolean     not null default true,
    created_at    timestamptz not null default now()
);

comment on column pro_players.shot_types  is 'Shot types with available reference data e.g. {serve,forehand}';
comment on column pro_players.is_active   is 'Set false to hide from picker without deleting';

create index idx_pro_players_active on pro_players (is_active);
