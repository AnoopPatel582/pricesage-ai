# PriceSage AI

An agentic price tracker built with Python, FastAPI, SQLAlchemy, and a browser dashboard. Users can track supported product URLs, review price history, set target prices, and ask an AI assistant about their own tracked products.

## Features

- Account registration and JWT based sign in.
- Product tracking with an initial price history record and periodic price checks.
- Target price alerts by email when SMTP is configured. Without SMTP, alerts use a logged dry run.
- A tool calling assistant powered by Groq for tracked products, searches, history, and adding a product. It can process multiple tool calls, use their results in a final answer, and continue a user's conversation. The rest of the app runs without an AI key.
- SQLite by default, with PostgreSQL supported through `DATABASE_URL`.
- FastAPI documentation at `/docs` and a dashboard at `/`.

## Supported product pages

The scraper factory supports `books.toscrape.com`, `amazon.in`, and `amazon.com`. Books to Scrape is useful for a reproducible demo. Amazon pages require Playwright Chromium and may trigger bot checks or change their markup; scraping success is not guaranteed.

## Run locally

Use Python 3.11 or newer. From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. Change `SECRET_KEY` in `.env` before sharing or deploying the app. Set `GROQ_API_KEY` to enable the AI assistant. Set `SMTP_USER`, `SMTP_PASSWORD`, and optionally `EMAIL_FROM` to enable email alerts and password reset. Without SMTP, password reset returns a configuration error.

The dashboard is served by FastAPI. When developing `frontend/index.html` on port 5500, the backend also accepts that local origin.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The tests use an in-memory SQLite database and a mocked scraper. They do not call live product sites or AI services.

## How it works

1. `app/scrapers/` selects an adapter for a supported URL and extracts a product name, price, currency, availability, and image.
2. `app/services/product_service.py` stores one product per URL and creates a tracking record for each user.
3. `app/scheduler/` runs periodic checks; `app/services/tracker_service.py` records new prices and evaluates target alerts.
4. `app/agent/` registers database tools. The authenticated `/api/agent/chat` endpoint passes the current user's identity to those tools, returns tool results to the model, and stores user and assistant messages for follow-up questions. Tracked product searches and history are scoped to that user.
5. `frontend/index.html` calls the FastAPI endpoints for authentication, tracking, history, alerts, and chat.

## Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The Compose setup keeps SQLite data in `./data` and installs Playwright Chromium in the image. Provide `SECRET_KEY` and any optional API or SMTP keys through the environment. Do not commit `.env` or the database.

## Project origin

PriceSage AI is an independent adaptation of [Shreyansh912's price-tracker](https://github.com/Shreyansh912/price-tracker), used with permission. This version has a new repository history, branding, configuration, AI route, scraper fixes, access scoping, tests, and documentation.
