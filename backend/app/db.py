from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.config import Config


SEED_LEVELS = [
    {
        "id": "swamp_troll",
        "order_index": 1,
        "title": "Swamp Troll",
        "description": "A beginner monster that is easy to offend.",
        "monster_name": "Slopjaw",
        "monster_icon": "/image.webp",
        "monster_hp": 100,
        "min_words_per_insult": 3,
    },
    {
        "id": "stone_giant",
        "order_index": 2,
        "title": "Stone Giant",
        "description": "A tougher monster that needs sharper wording.",
        "monster_name": "Gravelgut",
        "monster_icon": "/image.webp",
        "monster_hp": 180,
        "min_words_per_insult": 4,
    },
]


@contextmanager
def get_connection():
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
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists users (
                    id text primary key,
                    username text not null unique,
                    password_hash text not null,
                    current_level_id text not null references levels(id),
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists auth_tokens (
                    token text primary key,
                    user_id text not null references users(id) on delete cascade,
                    created_at timestamptz not null default now()
                )
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
                    normalized_text text not null,
                    original_text text not null,
                    created_at timestamptz not null default now(),
                    unique (user_id, normalized_text)
                )
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
                        min_words_per_insult
                    )
                    values (
                        %(id)s,
                        %(order_index)s,
                        %(title)s,
                        %(description)s,
                        %(monster_name)s,
                        %(monster_icon)s,
                        %(monster_hp)s,
                        %(min_words_per_insult)s
                    )
                    on conflict (id) do update set
                        order_index = excluded.order_index,
                        title = excluded.title,
                        description = excluded.description,
                        monster_name = excluded.monster_name,
                        monster_icon = excluded.monster_icon,
                        monster_hp = excluded.monster_hp,
                        min_words_per_insult = excluded.min_words_per_insult
                    """,
                    level,
                )

        connection.commit()
