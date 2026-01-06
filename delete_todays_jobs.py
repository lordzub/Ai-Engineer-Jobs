import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def delete_todays_jobs():
    # Define the date to target (Today based on user request: 2025-12-30)
    # Assuming UTC for the database interactions as seen in previous outputs
    start_date = "2025-12-30T00:00:00"
    end_date = "2025-12-30T23:59:59.999999"

    print(f"Checking for jobs created between {start_date} and {end_date} (UTC)...")

    # First count them to show what will be done
    # We use 'select' with 'count'
    count_response = supabase.table('jobs').select('id', count='exact') \
        .gte('created_at', start_date) \
        .lte('created_at', end_date) \
        .execute()
    
    count = count_response.count
    print(f"Found {count} jobs created today.")

    if count == 0:
        print("No jobs to delete.")
        return

    # Perform deletion
    print("Deleting...")
    delete_response = supabase.table('jobs').delete() \
        .gte('created_at', start_date) \
        .lte('created_at', end_date) \
        .execute()

    # The delete response 'data' contains the deleted rows
    deleted_count = len(delete_response.data)
    print(f"Successfully deleted {deleted_count} jobs.")

if __name__ == "__main__":
    delete_todays_jobs()
