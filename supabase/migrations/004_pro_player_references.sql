-- Migration 004: Pro player reference keypoints for DTW comparison

create table if not exists pro_player_references (
    id           uuid        primary key default gen_random_uuid(),
    pro_player_id uuid       not null references pro_players(id) on delete cascade,
    shot_type    varchar(20) not null check (shot_type in ('serve', 'forehand', 'backhand', 'volley')),
    frame_index  integer     not null,
    keypoints    jsonb       not null,  -- array of 33 {x,y,z} objects (normalized)
    phase        varchar(20) not null
                             check (phase in ('preparation', 'loading', 'contact', 'follow_through')),
    created_at   timestamptz not null default now()
);

create index idx_pro_refs_player_shot on pro_player_references (pro_player_id, shot_type);
create index idx_pro_refs_player_shot_phase on pro_player_references (pro_player_id, shot_type, phase);

comment on table pro_player_references is
    'Normalized pose keypoint templates extracted from reference pro footage. '
    'Loaded by the worker to run DTW alignment against user keypoints.';
