-- Automated Book Generation System -- Supabase schema

create extension if not exists "pgcrypto";

-- books
create table if not exists books (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  pre_notes text,                                  -- initial notes from author
  outline_notes_before text,                       -- editor "before" notes for outline
  outline jsonb,                                   -- generated outline: [{chapter_number,title,summary}]
  outline_notes_after text,                        -- editor "after" notes (for regeneration)
  outline_status text not null default 'ready_to_generate',
    -- ready_to_generate | generating | waiting_for_review | approved
  num_chapters int not null default 10,
  use_research boolean not null default false,
  genre text,
  audience text,
  style text,
  status text not null default 'created',
    -- created | outlining | chapters | compiling | done | error
  final_path text,
  error text,
  stop_requested boolean not null default false,   -- user requested stop
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- chapters
create table if not exists chapters (
  id uuid primary key default gen_random_uuid(),
  book_id uuid references books(id) on delete cascade,
  chapter_number int not null,
  title text,
  outline text,
  content text,
  summary text,
  notes text,
  status text not null default 'pending',
    -- pending | ready_to_generate | generating | waiting_for_review | approved
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (book_id, chapter_number)
);

-- events  (activity log)
create table if not exists events (
  id bigserial primary key,
  book_id uuid references books(id) on delete cascade,
  kind text,
  message text,
  created_at timestamptz default now()
);

create index if not exists idx_chapters_book on chapters(book_id, chapter_number);
create index if not exists idx_events_book on events(book_id, created_at desc);
