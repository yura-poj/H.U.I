import os


class Config:
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql://monster_game:monster_game_password@localhost:5432/monster_game",
    )
