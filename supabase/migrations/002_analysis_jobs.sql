-- Migration 002: analysis_jobs and analysis_keypoints

create table if not exists analysis_jobs (
    id              uuid        primary key default gen_random_uuid(),
    user_id         uuid        not null references auth.users(id) on delete cascade,
    shot_type       varchar(20) not null check (shot_type in ('serve', 'forehand', 'backhand', 'volley')),
    pro_player_id   uuid        not null references pro_players(id),
    video_s3_key    text        not null,
    status          varchar(20) not null default 'queued'
                                check (status in ('queued', 'processing', 'complete', 'failed')),
    stage           varchar(30) not null default 'queued',
    progress_pct    integer     not null default 0 check (progress_pct between 0 and 100),
    warning_code    varchar(50),
    error_code      varchar(50),
    report_id       uuid,       -- populated on completion, references analysis_reports (F3)
    created_at      timestamptz not null default now(),
    completed_at    timestamptz
);

comment on column analysis_jobs.stage is 'queued | pose_extraction | phase_detection | normalization | complete';

create index idx_jobs_user_id   on analysis_jobs (user_id);
create index idx_jobs_status    on analysis_jobs (status);
create index idx_jobs_created   on analysis_jobs (created_at desc);

-- Per-frame keypoints produced by the Modal worker
create table if not exists analysis_keypoints (
    id           uuid        primary key default gen_random_uuid(),
    job_id       uuid        not null references analysis_jobs(id) on delete cascade,
    frame_index  integer     not null,
    keypoints    jsonb       not null,  -- array of 33 {x,y,z,visibility} objects
    phase        varchar(20) not null
                             check (phase in ('preparation', 'loading', 'contact', 'follow_through'))
);

create index idx_keypoints_job_id on analysis_keypoints (job_id);
create index idx_keypoints_phase  on analysis_keypoints (job_id, phase);

-- Row-level security: users can only read their own jobs
alter table analysis_jobs      enable row level security;
alter table analysis_keypoints enable row level security;

create policy "Users see own jobs"
    on analysis_jobs for select
    using (auth.uid() = user_id);

create policy "Users see own keypoints"
    on analysis_keypoints for select
    using (
        exists (
            select 1 from analysis_jobs j
            where j.id = analysis_keypoints.job_id
              and j.user_id = auth.uid()
        )
    );
