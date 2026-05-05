# Project Notes for Agents

## Project

This project is a game backend. The player faces a monster and defeats it by sending funny insults. The monster does not attack the player, and the player has no HP. The frontend will be built with Vue later, but current work is backend-only.

The backend stack is Python with Flask.

PostgreSQL is the database for the whole project.

## Current Scope

The frontend is Vue. Work on frontend files when the user explicitly asks for frontend work.

Current backend goals:

- Provide a Flask API for game sessions.
- Provide basic user registration.
- Support project-defined game levels stored in the database.
- Validate insults using rules from the current level.
- Return stable JSON responses that a future Vue frontend can consume.

## Game Concept

The project defines game levels in the database. Each level describes one monster encounter and its rules.

The player does not choose levels, design levels, or configure monsters. The player's level grows automatically based on game progress. The player only submits insults. The backend determines the user's current level, checks the insult against that level's rules, calculates damage, updates monster HP, and returns the monster response.

This is not a turn-based combat exchange. The monster can react with text or animation metadata, but it does not deal damage back. There is no player health, defense, healing, or death state.

Each user must have a history of insults they have already used. Repeated insults by the same user should not damage the monster again, even if they are submitted in a different game session. The backend should detect duplicates for the current user and return a clear response explaining that the insult was already used.

Damage is always an integer from `0` to `10`, inclusive. Any scoring logic must clamp or otherwise guarantee the final damage value stays in this range.

Damage should come from the local `model` package when available. The backend uses `model.predict.predict_text(text)["insult_score"]` as damage and falls back to a simple heuristic only if model inference is unavailable.

The tone should be comic and absurd rather than hateful or personally abusive.

## Users

The backend needs basic user registration so insult history can belong to a specific user.

Initial user model:

- User id.
- Username.
- Password hash.
- Created timestamp.

Do not store plain text passwords. Passwords must be hashed before storage.

Authentication can start simple, but API design should make it clear which user is submitting an insult. The used-insult history is keyed by user id.

## Database

Use PostgreSQL as the primary database.

Data that should live in PostgreSQL:

- Users.
- Levels.
- Game sessions.
- User progress / current level and current monster HP on that level.
- Used insult history per user.

Do not use SQLite for the project unless the user explicitly asks for a temporary local fallback.

## Docker

Run the local development environment with Docker Compose.

Expected services:

- `postgres`: PostgreSQL database for all persistent data.
- `backend`: Flask API service.
- `frontend`: Vue development server.

The backend should read `DATABASE_URL` from environment variables and connect to the `postgres` Compose service.

The frontend should read `VITE_API_URL` from environment variables and call the Flask API.

The backend Docker image needs access to both `backend/` and `model/`; keep the backend Compose build context at the project root or otherwise mount/copy `model/` into `/app/model`.

## Levels

Levels are stored in the database, not hardcoded across routes and not read from a static config file.

Levels are not selected directly by the player. The backend assigns the current level from the user's progress. After the player defeats the monster on the current level, the backend advances the user to the next level.

A level includes:

- Level id.
- Level title.
- Level description.
- Monster name.
- Monster icon filename stored in the database.
- Monster HP.
- Minimum number of words required in an insult.

The active seed grid has exactly 10 levels: `level_1` through `level_10`. The level number is also the minimum required word count for an accepted insult. HP starts at `20` on level 1 and doubles on each next level. Monster image filenames are stored as `1.png`, `2.png`, ..., `10.png`; the API should expose both `monster.icon_file` with that stored filename and `monster.icon` as a frontend-friendly URL such as `/1.png`.

Possible future level fields:

- Turn limit.
- Damage multiplier.
- Difficulty.
- Damage rules.

## Progression

The user's current level and current monster HP change only through progression and accepted insult damage.

When an accepted insult reduces the monster HP to `0` or below, the current game is won. After victory, the backend should advance the user's current level to the next level.

The player must not be able to skip ahead or manually choose a later level.

The frontend should not require a manual "start level" action after authentication. It should automatically request the current fight and use the saved monster HP for the user's current level.

Example level shape:

```json
{
  "id": "level_1",
  "title": "Level 1",
  "description": "Requires at least 1 word(s) per insult.",
  "monster": {
    "name": "Monster 1",
    "icon": "/1.png",
    "icon_file": "1.png"
  },
  "rules": {
    "hp": 20,
    "min_words_per_insult": 1
  }
}
```

## Expected API Direction

Planned endpoints:

- `GET /api/health` checks that the backend is running.
- `POST /api/users/register` creates a basic user account.
- `POST /api/users/login` authenticates a user if login is needed for the current implementation.
- `GET /api/levels` returns available levels from the database.
- `POST /api/games` starts a game on the user's current level.
- `GET /api/games/<game_id>` returns current game state.
- `POST /api/games/<game_id>/insults` submits an insult attempt.

For insults with too few words, prefer a game-style response with `accepted: false`, `damage: 0`, and no turn penalty, unless the user decides otherwise.

For repeated insults by the same user, prefer a game-style response with `accepted: false`, `reason: "duplicate_insult"`, `damage: 0`, and no monster HP change.

The accepted-insult history must store each insult text and its damage score. Blocked attempts must not be stored in the full history.

The accepted-insult history should also store model score metadata: source, toxicity flag, toxicity score, label, and model signals. Toxicity is informational for now and must not block accepted damage unless the user changes the design.

The leaderboard is global and sorted by total accepted damage. It has two sections: `Top 10` and paginated `All players`; the all-players section starts at rank 1 and includes the top 10. The API and frontend should always show the current user's rank.

## Implementation Preferences

- Keep level persistence and lookup separate from route code.
- Keep route handlers thin.
- Put game mechanics in service modules.
- Keep response JSON explicit and frontend-friendly.
- Do not add player HP or monster counterattacks unless the user explicitly changes the game design.
- Do not let the player choose an arbitrary level; determine level from user progress.
- Advance the user's level after victory over the current monster.
- Track used insults per user so repeat submissions can be rejected consistently across game sessions.
- Store user passwords only as hashes.
- Ensure calculated damage is always in the `0..10` range.
- Use PostgreSQL for persistent project data.
- Keep Docker Compose as the standard local development entrypoint.

## Editing Rule

Keep edits scoped to the user's requested backend, frontend, Docker, and model integration work. Do not edit unrelated files or the source training data unless explicitly requested.
