import hashlib
import secrets
import uuid

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.config import Config
from app.db import get_connection


class RegistrationIpLimitExceeded(Exception):
    pass


def create_user(username: str, password_hash: str, registration_ip: str | None = None) -> dict:
    first_level = get_first_level()

    with get_connection() as connection:
        try:
            with connection.cursor() as cursor:
                if registration_ip:
                    cursor.execute(
                        """
                        insert into registration_ip_limits (
                            ip_address,
                            successful_registrations,
                            updated_at
                        )
                        values (%s, 1, now())
                        on conflict (ip_address) do update set
                            successful_registrations = case
                                when registration_ip_limits.updated_at <=
                                    now() - make_interval(secs => %s)
                                    then 1
                                else registration_ip_limits.successful_registrations + 1
                            end,
                            updated_at = now()
                        where registration_ip_limits.updated_at <=
                                now() - make_interval(secs => %s)
                            or registration_ip_limits.successful_registrations < %s
                        returning successful_registrations
                        """,
                        (
                            registration_ip,
                            Config.REGISTRATION_IP_WINDOW_SECONDS,
                            Config.REGISTRATION_IP_WINDOW_SECONDS,
                            Config.REGISTRATION_IP_LIMIT,
                        ),
                    )

                    if cursor.fetchone() is None:
                        raise RegistrationIpLimitExceeded(registration_ip)

                cursor.execute(
                    """
                    insert into users (
                        id,
                        username,
                        password_hash,
                        registration_ip,
                        current_level_id,
                        current_monster_hp
                    )
                    values (%s, %s, %s, %s, %s, %s)
                    returning id, username, current_level_id, current_monster_hp, created_at
                    """,
                    (
                        str(uuid.uuid4()),
                        username,
                        password_hash,
                        registration_ip,
                        first_level["id"],
                        first_level["monster_hp"],
                    ),
                )
                user = cursor.fetchone()
            connection.commit()
        except (RegistrationIpLimitExceeded, UniqueViolation):
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
    if not token:
        return None

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
                where auth_tokens.token_hash = %s
                    and auth_tokens.expires_at > now()
                """,
                (_hash_auth_token(token),),
            )
            return cursor.fetchone()


def create_auth_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into auth_tokens (token_hash, user_id, expires_at)
                values (%s, %s, now() + make_interval(days => %s))
                """,
                (_hash_auth_token(token), user_id, Config.AUTH_TOKEN_TTL_DAYS),
            )
        connection.commit()

    return token


def _hash_auth_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
            if status == "active":
                cursor.execute(
                    """
                    select *
                    from game_sessions
                    where user_id = %s
                        and level_id = %s
                        and monster_hp = %s
                        and status = 'active'
                    order by updated_at desc, created_at desc, id desc
                    limit 1
                    """,
                    (user_id, level["id"], starting_hp),
                )
                existing_game = cursor.fetchone()

                if existing_game:
                    return existing_game

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
            return _get_game_for_user(cursor, game_id, user_id)


def _get_game_for_user(cursor, game_id: str, user_id: str) -> dict | None:
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


def _get_game_for_user_locked(cursor, game_id: str, user_id: str) -> dict | None:
    cursor.execute(
        """
        select game_sessions.*, levels.title, levels.description, levels.monster_name,
               levels.monster_icon, levels.monster_hp as monster_max_hp,
               levels.min_words_per_insult
        from game_sessions
        join levels on levels.id = game_sessions.level_id
        where game_sessions.id = %s and game_sessions.user_id = %s
        for update of game_sessions
        """,
        (game_id, user_id),
    )
    return cursor.fetchone()


def _get_next_level(cursor, current_level_id: str) -> dict | None:
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
) -> dict | None:
    result = apply_current_insult_damage(
        game_id=game_id,
        user_id=user_id,
        level_id=level_id,
        original_text=original_text,
        normalized_text=normalized_text,
        damage=damage,
        score_metadata=score_metadata,
    )

    if result["status"] != "accepted":
        return None

    return result["game"]


def apply_current_insult_damage(
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
                select id, username, current_level_id, current_monster_hp, created_at
                from users
                where id = %s
                for update
                """,
                (user_id,),
            )
            user = cursor.fetchone()

            if not user:
                return {"status": "game_not_found"}

            game = _get_game_for_user_locked(cursor, game_id, user_id)

            if not game:
                return {"status": "game_not_found"}

            if game["status"] != "active":
                return {"status": "game_already_finished", "game": game}

            if game["level_id"] != user["current_level_id"]:
                return {"status": "stale_game_session", "game": game}

            cursor.execute(
                """
                select id
                from game_sessions
                where user_id = %s
                    and level_id = %s
                    and monster_hp = %s
                    and status = 'active'
                order by updated_at desc, created_at desc, id desc
                limit 1
                """,
                (user_id, user["current_level_id"], user["current_monster_hp"]),
            )
            canonical_game = cursor.fetchone()

            if not canonical_game or canonical_game["id"] != game_id:
                return {"status": "stale_game_session", "game": game}

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
                on conflict (user_id, normalized_text) do nothing
                returning id
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

            if cursor.fetchone() is None:
                return {"status": "duplicate_insult", "game": game}

            cursor.execute(
                """
                update game_sessions
                set monster_hp = greatest(monster_hp - %s, 0),
                    status = case when greatest(monster_hp - %s, 0) = 0 then 'won' else status end,
                    updated_at = now()
                where id = %s
                    and user_id = %s
                    and level_id = %s
                    and status = 'active'
                returning *
                """,
                (damage, damage, game_id, user_id, level_id),
            )
            updated_game = cursor.fetchone()

            if not updated_game:
                connection.rollback()
                return {"status": "stale_game_session", "game": game}

            cursor.execute(
                """
                update users
                set current_monster_hp = %s
                where id = %s and current_level_id = %s
                returning id, username, current_level_id, current_monster_hp, created_at
                """,
                (updated_game["monster_hp"], user_id, level_id),
            )
            updated_user = cursor.fetchone()

            if not updated_user:
                connection.rollback()
                return {"status": "stale_game_session", "game": game}

            full_game = _get_game_for_user(cursor, game_id, user_id)
            advanced_user = None

            if full_game["status"] == "won":
                next_level = _get_next_level(cursor, full_game["level_id"])
                if next_level:
                    cursor.execute(
                        """
                        update users
                        set current_level_id = %s,
                            current_monster_hp = %s
                        where id = %s and current_level_id = %s
                        returning id, username, current_level_id, current_monster_hp, created_at
                        """,
                        (next_level["id"], next_level["monster_hp"], user_id, level_id),
                    )
                    advanced_user = cursor.fetchone()

        connection.commit()

    return {
        "status": "accepted",
        "game": full_game,
        "advanced_user": advanced_user,
    }


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
