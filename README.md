# HUI

## Local Docker Run

```bash
docker compose up --build
```

Backend: `http://localhost:5001`

Frontend: `http://localhost:5173`

## Production Docker Run

Production compose keeps the same localhost-only ports, runs the backend with
Gunicorn, and serves the built Vue app through nginx:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Check the proxied backend through the frontend container:

```bash
curl http://127.0.0.1:5173/api/health
```
