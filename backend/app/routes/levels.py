from flask import Blueprint, jsonify

from app.repositories import list_levels
from app.serializers import serialize_level

levels_bp = Blueprint("levels", __name__)


@levels_bp.get("/levels")
def levels():
    return jsonify({"levels": [serialize_level(level) for level in list_levels()]})
