import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Fetch the last 5 jobs
response = supabase.table('jobs').select('id, created_at, title').order('created_at', desc=True).limit(5).execute()

print("Latest 5 jobs:")
for job in response.data:
    print(job)
