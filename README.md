# Commercial Real Estate Scraper Dashboard

A web application that automatically scrapes commercial real estate listings from multiple sources and presents them in a unified dashboard.

## Features

- Automated daily scraping of commercial real estate listings
- Web dashboard showing latest property data
- Comparison with previous scrapes to highlight new and modified listings
- Manual scrape trigger option
- Export data to CSV
- Multiple data sources including CBRE, Cushman & Wakefield, and more

## Tech Stack

- Backend: Python/Flask
- Frontend: HTML/CSS/JavaScript
- Database: PostgreSQL (Supabase)
- Hosting: Render.com (Backend) + GitHub Pages (Frontend)
- Automation: GitHub Actions

## Local Development

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the development server:
```bash
python -m backend.app
```

## Project Structure

```
├── backend/
│   ├── scrapers/     # Individual scrapers for each source
│   ├── app.py        # Flask application
│   ├── config.py     # Configuration
│   └── storage.py    # Database operations
├── frontend/         # Dashboard UI
└── .github/         # GitHub Actions workflows
```

## License

MIT License
