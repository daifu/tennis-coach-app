-- Migration 005: Analysis reports and coaching feedback (F3 + F4)

create table if not exists analysis_reports (
    id              uuid        primary key default gen_random_uuid(),
    job_id          uuid        not null unique references analysis_jobs(id) on delete cascade,
    user_id         uuid        not null references auth.users(id) on delete cascade,
    shot_type       varchar(20) not null,
    pro_player_id   uuid        not null references pro_players(id),
    similarity_score numeric(5,2) not null check (similarity_score between 0 and 100),
    joint_angles    jsonb       not null default '{}'::jsonb,
    -- joint_angles shape: {joint_name: {user: [angles], pro: [angles], delta_mean: float}}
    phase_metrics   jsonb       not null default '{}'::jsonb,
    -- phase_metrics shape: {phase_name: {similarity: float, key_angles: {...}}}
    warning_code    varchar(50),
    created_at      timestamptz not null default now()
);

create index idx_reports_user_id    on analysis_reports (user_id);
create index idx_reports_user_shot  on analysis_reports (user_id, shot_type);
create index idx_reports_created    on analysis_reports (user_id, created_at desc);

alter table analysis_reports enable row level security;

create policy "Users see own reports"
    on analysis_reports for select
    using (auth.uid() = user_id);

-- Add FK from analysis_jobs to analysis_reports now that the table exists
alter table analysis_jobs
    add constraint fk_jobs_report
    foreign key (report_id) references analysis_reports(id) on delete set null;


-- Coaching feedback per report (F4 — Gemini-generated)
create table if not exists coaching_feedback (
    id           uuid        primary key default gen_random_uuid(),
    report_id    uuid        not null references analysis_reports(id) on delete cascade,
    flaw_index   integer     not null check (flaw_index between 1 and 3),
    what         text        not null,
    why          text        not null,
    fix_drill    text        not null,
    impact_order integer     not null,
    created_at   timestamptz not null default now()
);

create index idx_feedback_report on coaching_feedback (report_id, flaw_index);

alter table coaching_feedback enable row level security;

create policy "Users see own coaching feedback"
    on coaching_feedback for select
    using (
        exists (
            select 1 from analysis_reports r
            where r.id = coaching_feedback.report_id
              and r.user_id = auth.uid()
        )
    );
