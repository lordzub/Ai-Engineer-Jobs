# AI Engineer Jobs - Backend

This is the backend API for the AI Engineer Jobs board, built with FastAPI and Supabase.

## Setup

1. **Create and Activate Virtual Environment**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. **Install Dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Environment Variables**
   Ensure you have a `.env` file in the root directory with the following keys:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `BRIGHTDATA_API_KEY` (if using backfill feature)
   - `BRIGHTDATA_ENDPOINT` (if using backfill feature)

## Running the Server

You can run the server in two ways:

### Option 1: Using Python directly (Recommended)
```powershell
python main.py
```
This runs the server at **http://127.0.0.1:8000** with auto-reload enabled.

### Option 2: Using Uvicorn
```powershell
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

## API Documentation

Once the server is running, you can access the interactive API docs at:
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

## Key Endpoints

- `GET /`: Health check
- `GET /api/jobs`: List jobs with filters
- `GET /api/stats/salary`: Get salary statistics
- `GET /api/graph/context`: Get job context for semantic navigation

## Utility Scripts

- **Update Company Websites**: `python update_company_websites.py`
  - Reads from `websites.json` and updates the database.
- **Delete Today's Jobs**: `python delete_todays_jobs.py`
  - Deletes all jobs created on the current day (useful for cleanup during testing).
- **Backfill Jobs**: `python backfill.py`
  - Scrapes new jobs using Bright Data and inserts them into Supabase.
