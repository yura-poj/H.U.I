from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.config import Config


def _build_seed_levels() -> list[dict]:
    return [
        {
            "id": f"level_{level_number}",
            "order_index": level_number,
            "title": f"Level {level_number}",
            "description": f"Requires at least {level_number} word(s) per insult.",
            "monster_name": f"Monster {level_number}",
            "monster_icon": f"{level_number}.png",
            "monster_hp": 20 * 2 ** (level_number - 1),
            "min_words_per_insult": level_number,
            "active": True,
        }
        for level_number in range(1, 11)
    ]


SEED_LEVELS = _build_seed_levels()


@contextmanager
def get_connection():
    if not Config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required.")

    with psycopg.connect(Config.DATABASE_URL, row_factory=dict_row) as connection:
        yield connection


def check_connection() -> str | None:
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("select 1")
                cursor.fetchone()
    except psycopg.Error as exc:
        return str(exc)

    return None


def init_db() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                create table if not exists levels (
                    id text primary key,
                    order_index integer not null unique,
                    title text not null,
                    description text not null,
                    monster_name text not null,
                    monster_icon text not null,
                    monster_hp integer not null check (monster_hp > 0),
                    min_words_per_insult integer not null check (min_words_per_insult > 0),
                    active boolean not null default true,
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                alter table levels
                add column if not exists active boolean not null default true
                """
            )
            cursor.execute(
                """
                create table if not exists users (
                    id text primary key,
                    username text not null unique,
                    password_hash text not null,
                    registration_ip text,
                    current_level_id text not null references levels(id),
                    current_monster_hp integer not null default 20 check (current_monster_hp >= 0),
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                alter table users
                add column if not exists current_monster_hp integer
                """
            )
            cursor.execute(
                """
                alter table users
                add column if not exists registration_ip text
                """
            )
            cursor.execute(
                """
                create table if not exists registration_ip_limits (
                    ip_address text primary key,
                    successful_registrations integer not null default 0
                        check (successful_registrations >= 0),
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create index if not exists users_registration_ip_idx
                on users(registration_ip)
                """
            )
            cursor.execute(
                """
                create table if not exists auth_tokens (
                    token_hash text primary key,
                    user_id text not null references users(id) on delete cascade,
                    expires_at timestamptz not null,
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                alter table auth_tokens
                add column if not exists token_hash text
                """
            )
            cursor.execute(
                """
                alter table auth_tokens
                add column if not exists expires_at timestamptz
                """
            )
            cursor.execute(
                """
                do $$
                begin
                    if exists (
                        select 1
                        from information_schema.columns
                        where table_name = 'auth_tokens'
                            and column_name = 'token'
                    ) then
                        delete from auth_tokens;
                        alter table auth_tokens
                        drop constraint if exists auth_tokens_pkey;
                        alter table auth_tokens
                        drop column token;
                    end if;
                end
                $$;
                """
            )
            cursor.execute(
                """
                delete from auth_tokens
                where token_hash is null
                    or expires_at is null
                """
            )
            cursor.execute(
                """
                alter table auth_tokens
                alter column token_hash set not null
                """
            )
            cursor.execute(
                """
                alter table auth_tokens
                alter column expires_at set not null
                """
            )
            cursor.execute(
                """
                do $$
                begin
                    if not exists (
                        select 1
                        from pg_constraint
                        where conname = 'auth_tokens_pkey'
                    ) then
                        alter table auth_tokens
                        add constraint auth_tokens_pkey primary key (token_hash);
                    end if;
                end
                $$;
                """
            )
            cursor.execute(
                """
                create index if not exists auth_tokens_user_id_idx
                on auth_tokens(user_id)
                """
            )
            cursor.execute(
                """
                create index if not exists auth_tokens_expires_at_idx
                on auth_tokens(expires_at)
                """
            )
            cursor.execute(
                """
                create table if not exists game_sessions (
                    id text primary key,
                    user_id text not null references users(id) on delete cascade,
                    level_id text not null references levels(id),
                    monster_hp integer not null check (monster_hp >= 0),
                    status text not null check (status in ('active', 'won')),
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists used_insults (
                    id text primary key,
                    user_id text not null references users(id) on delete cascade,
                    game_id text references game_sessions(id),
                    level_id text references levels(id),
                    normalized_text text not null,
                    original_text text not null,
                    damage integer not null default 0,
                    score_source text not null default 'heuristic',
                    toxic boolean,
                    toxicity_score double precision,
                    toxicity_label text,
                    model_signals jsonb not null default '{}'::jsonb,
                    created_at timestamptz not null default now(),
                    unique (user_id, normalized_text)
                )
                """
            )
            cursor.execute(
                """
                alter table used_insults
                add column if not exists game_id text references game_sessions(id)
                """
            )
            cursor.execute(
                """
                alter table used_insults
                add column if not exists level_id text references levels(id)
                """
            )
            cursor.execute(
                """
                alter table used_insults
                add column if not exists damage integer not null default 0
                """
            )
            cursor.execute(
                """
                alter table used_insults
                add column if not exists score_source text not null default 'heuristic'
                """
            )
            cursor.execute(
                """
                alter table used_insults
                add column if not exists toxic boolean
                """
            )
            cursor.execute(
                """
                alter table used_insults
                add column if not exists toxicity_score double precision
                """
            )
            cursor.execute(
                """
                alter table used_insults
                add column if not exists toxicity_label text
                """
            )
            cursor.execute(
                """
                alter table used_insults
                add column if not exists model_signals jsonb not null default '{}'::jsonb
                """
            )
            cursor.execute(
                """
                do $$
                begin
                    if not exists (
                        select 1
                        from pg_constraint
                        where conname = 'used_insults_damage_range'
                    ) then
                        alter table used_insults
                        add constraint used_insults_damage_range
                        check (damage between 0 and 10);
                    end if;
                end
                $$;
                """
            )
            cursor.execute(
                """
                create index if not exists game_sessions_user_id_idx
                on game_sessions(user_id)
                """
            )
            cursor.execute(
                """
                create index if not exists used_insults_user_id_idx
                on used_insults(user_id)
                """
            )
            cursor.execute(
                """
                update levels
                set active = false,
                    order_index = order_index + 1000
                where id not in (
                    'level_1',
                    'level_2',
                    'level_3',
                    'level_4',
                    'level_5',
                    'level_6',
                    'level_7',
                    'level_8',
                    'level_9',
                    'level_10'
                )
                    and order_index < 1000
                """
            )
            cursor.execute(
                """
                update levels
                set active = false
                where id not in (
                    'level_1',
                    'level_2',
                    'level_3',
                    'level_4',
                    'level_5',
                    'level_6',
                    'level_7',
                    'level_8',
                    'level_9',
                    'level_10'
                )
                """
            )

            for level in SEED_LEVELS:
                cursor.execute(
                    """
                    insert into levels (
                        id,
                        order_index,
                        title,
                        description,
                        monster_name,
                        monster_icon,
                        monster_hp,
                        min_words_per_insult,
                        active
                    )
                    values (
                        %(id)s,
                        %(order_index)s,
                        %(title)s,
                        %(description)s,
                        %(monster_name)s,
                        %(monster_icon)s,
                        %(monster_hp)s,
                        %(min_words_per_insult)s,
                        %(active)s
                    )
                    on conflict (id) do update set
                        order_index = excluded.order_index,
                        title = excluded.title,
                        description = excluded.description,
                        monster_name = excluded.monster_name,
                        monster_icon = excluded.monster_icon,
                        monster_hp = excluded.monster_hp,
                        min_words_per_insult = excluded.min_words_per_insult,
                        active = excluded.active
                    """,
                    level,
                )

            cursor.execute(
                """
                update users
                set current_level_id = case
                    when current_level_id = 'stone_giant' then 'level_2'
                    else 'level_1'
                end
                where current_level_id in ('swamp_troll', 'stone_giant')
                """
            )
            cursor.execute(
                """
                update users
                set current_level_id = 'level_1'
                where not exists (
                    select 1
                    from levels
                    where levels.id = users.current_level_id
                        and levels.active = true
                )
                """
            )
            cursor.execute(
                """
                update users
                set current_monster_hp = coalesce(
                    (
                        select game_sessions.monster_hp
                        from game_sessions
                        where game_sessions.user_id = users.id
                            and game_sessions.level_id = users.current_level_id
                            and game_sessions.status = 'active'
                        order by game_sessions.updated_at desc,
                                 game_sessions.created_at desc
                        limit 1
                    ),
                    levels.monster_hp
                )
                from levels
                where levels.id = users.current_level_id
                    and users.current_monster_hp is null
                """
            )
            cursor.execute(
                """
                update users
                set current_monster_hp = least(greatest(current_monster_hp, 0), levels.monster_hp)
                from levels
                where levels.id = users.current_level_id
                """
            )
            cursor.execute(
                """
                alter table users
                alter column current_monster_hp set default 20
                """
            )
            cursor.execute(
                """
                alter table users
                alter column current_monster_hp set not null
                """
            )
            cursor.execute(
                """
                do $$
                begin
                    if not exists (
                        select 1
                        from pg_constraint
                        where conname = 'users_current_monster_hp_nonnegative'
                    ) then
                        alter table users
                        add constraint users_current_monster_hp_nonnegative
                        check (current_monster_hp >= 0);
                    end if;
                end
                $$;
                """
            )
        connection.commit()
