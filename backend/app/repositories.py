import uuid

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.db import get_connection


def create_user(username: str, password_hash: str) -> dict:
    first_level = get_first_level()

    with get_connection() as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into users (
                        id,
                        username,
                        password_hash,
                        current_level_id,
                        current_monster_hp
                    )
                    values (%s, %s, %s, %s, %s)
                    returning id, username, current_level_id, current_monster_hp, created_at
                    """,
                    (
                        str(uuid.uuid4()),
                        username,
                        password_hash,
                        first_level["id"],
                        first_level["monster_hp"],
                    ),
                )
                user = cursor.fetchone()
            connection.commit()
        except UniqueViolation:
            connection.rollback()
            raise

    return user


def find_user_by_username(username: str) -> dict | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, username, password_hash, current_level_id, current_monster_hp, created_at
                from users
                where username = %s
                """,
                (username,),
            )
            return cursor.fetchone()


def find_user_by_token(token: str) -> dict | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select users.id,
                       users.username,
                       users.current_level_id,
                       users.current_monster_hp,
                       users.created_at
                from auth_tokens
                join users on users.id = auth_tokens.user_id
                where auth_tokens.token = %s
                """,
                (token,),
            )
            return cursor.fetchone()


def create_auth_token(user_id: str) -> str:
    token = str(uuid.uuid4())

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into auth_tokens (token, user_id)
                values (%s, %s)
                """,
                (token, user_id),
            )
        connection.commit()

    return token


def list_levels() -> list[dict]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select *
                from levels
                where active = true
                order by order_index
                """
            )
            return cursor.fetchall()


def get_first_level() -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select *
                from levels
                where active = true
                order by order_index
                limit 1
                """
            )
            level = cursor.fetchone()

    if not level:
        raise RuntimeError("No levels found in database.")

    return level


def get_level(level_id: str) -> dict | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select *
                from levels
                where id = %s
                """,
                (level_id,),
            )
            return cursor.fetchone()


def get_next_level(current_level_id: str) -> dict | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select next_level.*
                from levels current_level
                join levels next_level
                    on next_level.order_index = current_level.order_index + 1
                    and next_level.active = true
                where current_level.id = %s
                    and current_level.active = true
                """,
                (current_level_id,),
            )
            return cursor.fetchone()


def create_game(user_id: str, level: dict, monster_hp: int) -> dict:
    starting_hp = min(max(monster_hp, 0), level["monster_hp"])
    status = "won" if starting_hp == 0 else "active"

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into game_sessions (id, user_id, level_id, monster_hp, status)
                values (%s, %s, %s, %s, %s)
                returning *
                """,
                (str(uuid.uuid4()), user_id, level["id"], starting_hp, status),
            )
            game = cursor.fetchone()
        connection.commit()

    return game


def get_game_for_user(game_id: str, user_id: str) -> dict | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select game_sessions.*, levels.title, levels.description, levels.monster_name,
                       levels.monster_icon, levels.monster_hp as monster_max_hp,
                       levels.min_words_per_insult
                from game_sessions
                join levels on levels.id = game_sessions.level_id
                where game_sessions.id = %s and game_sessions.user_id = %s
                """,
                (game_id, user_id),
            )
            return cursor.fetchone()


def has_used_insult(user_id: str, normalized_text: str) -> bool:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select 1
                from used_insults
                where user_id = %s and normalized_text = %s
                """,
                (user_id, normalized_text),
            )
            return cursor.fetchone() is not None


def apply_insult_damage(
    game_id: str,
    user_id: str,
    level_id: str,
    original_text: str,
    normalized_text: str,
    damage: int,
    score_metadata: dict,
) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into used_insults (
                    id,
                    user_id,
                    game_id,
                    level_id,
                    normalized_text,
                    original_text,
                    damage,
                    score_source,
                    toxic,
                    toxicity_score,
                    toxicity_label,
                    model_signals
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    game_id,
                    level_id,
                    normalized_text,
                    original_text,
                    damage,
                    score_metadata.get("source", "fallback"),
                    score_metadata.get("toxic"),
                    score_metadata.get("toxicity_score"),
                    score_metadata.get("label"),
                    Jsonb(score_metadata.get("signals", {})),
                ),
            )
            cursor.execute(
                """
                update game_sessions
                set monster_hp = greatest(monster_hp - %s, 0),
                    status = case when greatest(monster_hp - %s, 0) = 0 then 'won' else status end,
                    updated_at = now()
                where id = %s and user_id = %s
                returning *
                """,
                (damage, damage, game_id, user_id),
            )
            game = cursor.fetchone()
            cursor.execute(
                """
                update users
                set current_monster_hp = %s
                where id = %s and current_level_id = %s
                """,
                (game["monster_hp"], user_id, level_id),
            )
        connection.commit()

    return game


def list_user_insult_history(user_id: str) -> list[dict]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select used_insults.id,
                       used_insults.original_text,
                       used_insults.damage,
                       used_insults.score_source,
                       used_insults.toxic,
                       used_insults.toxicity_score,
                       used_insults.toxicity_label,
                       used_insults.model_signals,
                       used_insults.level_id,
                       levels.monster_name,
                       used_insults.created_at
                from used_insults
                left join levels on levels.id = used_insults.level_id
                where used_insults.user_id = %s
                order by used_insults.created_at desc
                """,
                (user_id,),
            )
            return cursor.fetchall()


def list_leaderboard(
    current_user_id: str,
    section: str,
    page: int,
    page_size: int,
) -> tuple[list[dict], dict | None]:
    if section == "top":
        rank_filter = "where rank <= 10"
        offset = 0
    else:
        rank_filter = ""
        offset = (page - 1) * page_size

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                with scores as (
                    select users.id as user_id,
                           users.username,
                           users.current_level_id,
                           coalesce(sum(used_insults.damage), 0)::integer as total_damage,
                           count(used_insults.id)::integer as insults_count
                    from users
                    left join used_insults on used_insults.user_id = users.id
                    group by users.id, users.username, users.current_level_id
                ),
                ranked as (
                    select row_number() over (
                               order by total_damage desc, insults_count asc, username asc
                           )::integer as rank,
                           user_id,
                           username,
                           current_level_id,
                           total_damage,
                           insults_count
                    from scores
                )
                select rank, username, current_level_id, total_damage, insults_count
                from ranked
                {rank_filter}
                order by rank
                limit %s offset %s
                """,
                (page_size, offset),
            )
            leaders = cursor.fetchall()

            cursor.execute(
                """
                with scores as (
                    select users.id as user_id,
                           users.username,
                           users.current_level_id,
                           coalesce(sum(used_insults.damage), 0)::integer as total_damage,
                           count(used_insults.id)::integer as insults_count
                    from users
                    left join used_insults on used_insults.user_id = users.id
                    group by users.id, users.username, users.current_level_id
                ),
                ranked as (
                    select row_number() over (
                               order by total_damage desc, insults_count asc, username asc
                           )::integer as rank,
                           user_id,
                           username,
                           current_level_id,
                           total_damage,
                           insults_count
                    from scores
                )
                select rank, username, current_level_id, total_damage, insults_count
                from ranked
                where user_id = %s
                """,
                (current_user_id,),
            )
            current_user_rank = cursor.fetchone()

    return leaders, current_user_rank


def advance_user_level_if_possible(user_id: str, current_level_id: str) -> dict | None:
    next_level = get_next_level(current_level_id)

    if not next_level:
        return None

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update users
                set current_level_id = %s,
                    current_monster_hp = %s
                where id = %s and current_level_id = %s
                returning id, username, current_level_id, current_monster_hp, created_at
                """,
                (next_level["id"], next_level["monster_hp"], user_id, current_level_id),
            )
            user = cursor.fetchone()
        connection.commit()

    return user
