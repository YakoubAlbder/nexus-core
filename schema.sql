-- Nexus Core — Supabase (Postgres) schema
-- Run this once in the Supabase project's SQL editor (Database > SQL Editor > New query).
-- Single-user personal app: no row-level auth needed, but RLS is enabled with a
-- permissive policy so the anon key can be used safely from the app while still
-- blocking public REST access by anyone who doesn't have your key.
--
-- Design note: every "why did this slip" column here (fatigue_type, barriers, root_cause...)
-- exists to be read with compassion, not to build a case against the user. See the
-- WEEKLY_SYSTEM_PROMPT in lib/gemini_client.py for how this data is actually narrated back.

-- ============================================================
-- 0. Raw entries: the original journal dump + what Gemini extracted from it
-- ============================================================
create table if not exists raw_entries (
    id            bigint generated always as identity primary key,
    entry_date    date not null default current_date,
    source        text not null check (source in ('text', 'voice')),
    raw_text      text,                 -- typed text, or the transcript Gemini produced from audio
    extracted_json jsonb,               -- full structured extraction, for audit/debugging
    created_at    timestamptz not null default now()
);

-- ============================================================
-- Box 1 — الخشوع والارتباط الروحي (Spiritual connection)
-- One row per prayer per day (fajr/dhuhr/asr/maghrib/isha)
-- ============================================================
create table if not exists prayer_log (
    id              bigint generated always as identity primary key,
    entry_date      date not null default current_date,
    prayer_name     text not null check (prayer_name in ('fajr','dhuhr','asr','maghrib','isha')),
    sunan_done      boolean,
    tafakkur_done   boolean,            -- تفكر / reflection before prayer
    wudu_mindful    boolean,            -- وضوء بخشوع
    khushoo_score   smallint check (khushoo_score between 1 and 5),
    adhkar_after    boolean,            -- أذكار ما بعد الصلاة
    notes           text,
    created_at      timestamptz not null default now(),
    unique (entry_date, prayer_name)
);

-- Daily (not per-prayer) spiritual habits
create table if not exists spiritual_daily_log (
    id                  bigint generated always as identity primary key,
    entry_date          date not null unique default current_date,
    morning_adhkar_done boolean,
    evening_adhkar_done boolean,
    notes               text,
    created_at          timestamptz not null default now()
);

-- ============================================================
-- Box 2 — الصحة البدنية والأكل (Physical health & eating, no deprivation)
-- ============================================================
create table if not exists health_log (
    id                  bigint generated always as identity primary key,
    entry_date          date not null unique default current_date,
    gym_went            boolean,
    motivation_score    smallint check (motivation_score between 1 and 5),
    fatigue_type        text check (fatigue_type in ('real_physical_fatigue','low_motivation','time_conflict','other')),
                                        -- WHY the gym/eating slipped, read with compassion — not a blame field
    barriers            text,           -- what made the day harder, described factually and kindly
    triggers            text,           -- context that preceded a skip — not a confession
    healthy_eating      boolean,
    sugar_avoided       boolean,
    calorie_deficit     boolean,
    calories_estimate   integer,        -- optional, if user tracks numbers
    satiety_meal_used   boolean,        -- وجبة شبع لمنع الحرمان
    notes               text,
    created_at          timestamptz not null default now()
);

-- ============================================================
-- Box 3 — السلام الداخلي ومحاربة الهروب (Inner peace / anti-escapism)
-- ============================================================
create table if not exists inner_peace_log (
    id              bigint generated always as identity primary key,
    entry_date      date not null unique default current_date,
    escape_flag     smallint check (escape_flag in (0,1)),   -- a data point for pattern-understanding, never a verdict
    root_cause      text,               -- the underlying pressure, e.g. "poor sleep", "housing friction" — the thing worth treating, not the symptom
    context_tag     text,               -- short category label, used for correlation grouping
    stress_level    smallint check (stress_level between 1 and 5),
    sense_of_control_score smallint check (sense_of_control_score between 1 and 5),
                                        -- how in-control the user felt of their own reactions today
    early_stopping_used boolean,        -- did they catch/interrupt the spiral in time — a genuine win worth naming
    notes           text,
    created_at      timestamptz not null default now()
);

-- ============================================================
-- Box 4 — التطوير المهني والذكاء الاصطناعي والعقلي (Professional/AI/mental growth)
-- ============================================================
create table if not exists growth_log (
    id                  bigint generated always as identity primary key,
    entry_date          date not null unique default current_date,
    work_tasks_done     text,
    deep_work_hours     numeric(4,1),
    ai_skill_practice   boolean,        -- عملت/تدربت على AI/agents اليوم
    ai_practice_notes   text,           -- ورقة بحثية / كود / أداة معينة
    mental_nutrition    text,           -- كتاب / بودكاست
    felt_sustainable    boolean,        -- هل الوتيرة حسّت مستدامة، ولا قريبة من الاحتراق؟
    notes               text,
    created_at          timestamptz not null default now()
);

-- ============================================================
-- Weekly Automated Interviewer output
-- ============================================================
create table if not exists weekly_reports (
    id              bigint generated always as identity primary key,
    week_start      date not null,
    week_end        date not null,
    stats_json      jsonb,              -- computed aggregates/correlations that fed the prompt
    report_text     text,               -- Gemini's opening analysis message
    conversation    jsonb,              -- full chat transcript (list of {role, content})
    hypothesis      text,               -- the user's stated hypothesis/plan for next week
    created_at      timestamptz not null default now(),
    unique (week_start, week_end)
);

-- ============================================================
-- Row Level Security — lock the tables down to the service/anon key you control.
-- For a single-user app it's fine to allow all operations for the key you keep secret.
-- ============================================================
alter table raw_entries enable row level security;
alter table prayer_log enable row level security;
alter table spiritual_daily_log enable row level security;
alter table health_log enable row level security;
alter table inner_peace_log enable row level security;
alter table growth_log enable row level security;
alter table weekly_reports enable row level security;

do $$
declare
    t text;
begin
    foreach t in array array['raw_entries','prayer_log','spiritual_daily_log','health_log',
                              'inner_peace_log','growth_log','weekly_reports']
    loop
        -- Postgres has no "create policy if not exists", so drop-then-create instead
        -- (this is what makes the whole script safe to re-run from scratch).
        execute format('drop policy if exists "allow all for authenticated key" on %I;', t);
        execute format(
            'create policy "allow all for authenticated key" on %I
             for all using (true) with check (true);', t);
    end loop;
end $$;

-- NOTE: this policy allows anyone holding your Supabase anon/service key to read & write.
-- Keep that key only in Streamlit Cloud's secrets manager (never in the repo), and keep the
-- app itself behind the password gate in lib/auth.py.
