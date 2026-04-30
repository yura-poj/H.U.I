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

Start a game on the user's current level:

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

Stop services:

```bash
docker compose down
```

Remove database volume:

```bash
docker compose down -v
```
