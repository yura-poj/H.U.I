from flask import Blueprint, jsonify, request

from app.auth import current_user_required
from app.repositories import list_leaderboard
from app.serializers import serialize_leaderboard_entry

leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.get("/leaderboard")
@current_user_required
def leaderboard(user):
    section = request.args.get("section", "top")

    if section not in {"top", "all"}:
        return jsonify({"error": "invalid_leaderboard_section"}), 400

    page = _positive_int(request.args.get("page"), default=1)
    page_size = (
        10
        if section == "top"
        else min(_positive_int(request.args.get("page_size"), default=100), 100)
    )

    leaders, current_user_rank = list_leaderboard(
        current_user_id=user["id"],
        section=section,
        page=page,
        page_size=page_size,
    )

    return jsonify(
        {
            "section": section,
            "page": page,
            "page_size": page_size,
            "leaders": [
                serialize_leaderboard_entry(leader)
                for leader in leaders
            ],
            "current_user_rank": serialize_leaderboard_entry(current_user_rank),
        }
    )


def _positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        return default

    return max(parsed, 1)
