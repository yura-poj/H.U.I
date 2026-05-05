# HUI

Backend-first game project with Flask and PostgreSQL.

## Local Docker Run

Copy environment defaults if you want to override them:

```bash
cp .env.example .env
```

Start services:

```bash
docker compose up --build
```

Backend:

```text
http://localhost:5001
```

Frontend:

```text
http://localhost:5173
```

Monster images are served from `frontend/static`. Add level images as `1.png`, `2.png`, ..., `10.png`; the API returns them as `/1.png`, `/2.png`, and so on. The frontend falls back to `/image.webp` while a level image is missing.

Healthcheck:

```bash
curl http://localhost:5001/api/health
```

## API Sketch

Register:

```bash
curl -X POST http://localhost:5001/api/users/register \
  -H "Content-Type: application/json" \
  -d '{"username":"player1","password":"secret1"}'
```

Login:

```bash
curl -X POST http://localhost:5001/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"username":"player1","password":"secret1"}'
```

List levels:

```bash
curl http://localhost:5001/api/levels
```

Start or resume a fight on the user's current level and saved monster HP:

```bash
curl -X POST http://localhost:5001/api/games \
  -H "Authorization: Bearer <token>"
```

Submit an insult:

```bash
curl -X POST http://localhost:5001/api/games/<game_id>/insults \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text":"you soggy boot with eyebrows"}'
```

Accepted insult responses include model score metadata:

```json
{
  "damage": 7,
  "score": {
    "source": "model",
    "toxic": false,
    "toxicity_score": 0.12,
    "label": "normal",
    "signals": {}
  }
}
```

Accepted insult history:

```bash
curl http://localhost:5001/api/insults/history \
  -H "Authorization: Bearer <token>"
```

Leaderboard:

```bash
curl "http://localhost:5001/api/leaderboard?section=top" \
  -H "Authorization: Bearer <token>"

curl "http://localhost:5001/api/leaderboard?section=all&page=1&page_size=100" \
  -H "Authorization: Bearer <token>"
```

Stop services:

```bash
docker compose down
```

Remove database volume:

```bash
docker compose down -v
```
