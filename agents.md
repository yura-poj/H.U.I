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

Damage is always an integer from `0` to `100`, inclusive. Any scoring logic must clamp or otherwise guarantee the final damage value stays in this range.

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
- User progress / current level.
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

## Levels

Levels are stored in the database, not hardcoded across routes and not read from a static config file.

Levels are not selected directly by the player. The backend assigns the current level from the user's progress. After the player defeats the monster on the current level, the backend advances the user to the next level.

A level includes:

- Level id.
- Level title.
- Level description.
- Monster name.
- Monster icon.
- Monster HP.
- Minimum number of words required in an insult.

Possible future level fields:

- Turn limit.
- Damage multiplier.
- Difficulty.
- Damage rules.

## Progression

The user's current level changes only through progression.

When an accepted insult reduces the monster HP to `0` or below, the current game is won. After victory, the backend should advance the user's current level to the next level.

The player must not be able to skip ahead or manually choose a later level.

Example level shape:

```json
{
  "id": "swamp_troll",
  "title": "Swamp Troll",
  "description": "A beginner monster that is easy to offend.",
  "monster": {
    "name": "Slopjaw",
    "icon": "/assets/monsters/swamp-troll.png"
  },
  "rules": {
    "hp": 100,
    "min_words_per_insult": 3
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
- Ensure calculated damage is always in the `0..100` range.
- Use PostgreSQL for persistent project data.
- Keep Docker Compose as the standard local development entrypoint.

## Editing Rule

At the moment, only edit this `agents.md` file unless the user explicitly asks to create or modify other files.
