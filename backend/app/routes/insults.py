from flask import Blueprint, jsonify

from app.auth import current_user_required
from app.repositories import list_user_insult_history
from app.serializers import serialize_insult_history_item

insults_bp = Blueprint("insults", __name__)


@insults_bp.get("/insults/history")
@current_user_required
def insult_history(user):
    history = list_user_insult_history(user["id"])

    return jsonify(
        {
            "history": [
                serialize_insult_history_item(insult)
                for insult in history
            ]
        }
    )
