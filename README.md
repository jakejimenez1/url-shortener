# URL Shortener with Analytics

A URL shortening web service built with FastAPI, PostgreSQL, Redis, and Docker Compose. It supports custom short codes, expiration dates, QR codes, Redis-cached redirects, Redis-based rate limiting, and per-click analytics.

## Features

- **URL shortening**: `POST /shorten` returns a short link for any valid URL
- **Custom short codes**: choose your own code; duplicates are rejected
- **Auto-generated codes**: random 6-character alphanumeric codes, regenerated if a code already exists
- **Expiration dates**: optional `expires_in_days`; expired links return `410 Gone`
- **Redis caching**: redirect lookups are cached (cache-aside) with a TTL of 24 hours or the link's expiration, whichever is sooner
- **Rate limiting**: `POST /shorten` is limited to 10 requests per minute per IP using a Redis counter (`INCR` + `EXPIRE`)
- **Click analytics**: each redirect records IP address, user agent, and referrer; `GET /analytics/{code}` returns the total and the 10 most recent clicks
- **System stats**: `GET /api/stats` returns total URLs, total clicks, and the top 5 links
- **QR codes**: `GET /qr/{code}` returns a PNG QR code for a short link
- **Web form**: a simple front end at `/` for creating short links
- **API docs**: interactive Swagger UI at `/docs`
- **Docker Compose**: one command starts the API, PostgreSQL, and Redis, with health checks and a SQL init script

## Architecture

```
Browser / API client
        |
        v
  FastAPI backend ----> Redis (redirect cache + rate limit counters)
        |
        v
   PostgreSQL (urls, clicks)
```

On a redirect, the app checks Redis for the destination first. On a cache miss it reads PostgreSQL, checks expiration, and fills the cache. Every redirect then records a click row and increments the link's click counter in PostgreSQL.

## Tech Stack

- Python 3.11, FastAPI, Pydantic
- SQLAlchemy with PostgreSQL 15 (SQLite fallback for local development)
- Redis 7
- Docker and Docker Compose

## Getting Started

### Run with Docker Compose

```bash
git clone https://github.com/jakejimenez1/url-shortener.git
cd url-shortener
docker-compose up --build
```

Then open:

- Web form: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

Stop everything with `docker-compose down`.

### Run locally without Docker

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env      # then point DATABASE_URL and REDIS_URL at your local services
uvicorn main:app --reload
```

If `DATABASE_URL` is not a PostgreSQL URL, the app falls back to a local SQLite file. Redis must be running for rate limiting and caching.

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/shorten` | Create a short link (rate limited) |
| GET | `/{short_code}` | Redirect (307) to the original URL and record a click |
| GET | `/analytics/{short_code}` | Total clicks and the 10 most recent clicks |
| GET | `/api/stats` | Total URLs, total clicks, top 5 links |
| DELETE | `/api/urls/{short_code}` | Delete a link and clear its cache entry |
| GET | `/qr/{short_code}` | QR code image (PNG) |
| GET | `/health` | Service status |

### Example

```bash
curl -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com", "custom_code": "gh", "expires_in_days": 30}'
```

```json
{
  "original_url": "https://github.com/",
  "short_code": "gh",
  "short_url": "http://localhost:8000/gh",
  "created_at": "2026-01-15T12:00:00",
  "expires_at": "2026-02-14T12:00:00",
  "click_count": 0
}
```

## Database Schema

Defined in `database/init.sql` and mirrored by the SQLAlchemy models.

- `urls`: `id`, `original_url`, `short_code` (unique, indexed), `created_at`, `expires_at`, `click_count`
- `clicks`: `id`, `url_id` (foreign key to `urls`, cascade delete), `clicked_at`, `ip_address`, `user_agent`, `referrer`

## Project Structure

```
url-shortener/
├── backend/
│   ├── main.py            # FastAPI app, routes, rate limiter
│   ├── models.py          # SQLAlchemy models
│   ├── database.py        # Engine and session setup
│   ├── cache.py           # Redis helpers
│   ├── utils.py           # Short code generation
│   ├── requirements.txt
│   └── Dockerfile
├── database/
│   └── init.sql           # Tables, indexes, sample rows
├── docker-compose.yml
├── .env.example
└── README.md
```

## Limitations

This is a learning project, not a production deployment.

- Database credentials in `docker-compose.yml` are development placeholders, and CORS allows all origins
- The delete, analytics, and stats endpoints have no authentication
- Rate limiting applies only to `POST /shorten`, and uses a simple fixed window
- Every redirect still writes a click row to PostgreSQL, so caching saves the URL lookup but not the analytics write
- There are no automated tests and no load-test results yet

## Possible Next Steps

- Add API authentication and per-user links
- Move click logging to a background queue
- Add automated tests and measure redirect latency under load

## Author

Jake Jimenez, [LinkedIn](https://www.linkedin.com/in/jake-jimenez/)