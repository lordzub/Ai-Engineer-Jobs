import os
import requests
from supabase import create_client, Client
from dotenv import load_dotenv
import time

# --- 1. SETUP ---
# (Your setup code is correct, no changes needed)
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BRIGHTDATA_ENDPOINT = os.environ.get("BRIGHTDATA_ENDPOINT")
BRIGHTDATA_HEADERS = {
    'Authorization': f'Bearer {os.environ.get("BRIGHTDATA_API_KEY")}'
}

# --- 2. BRIGHT DATA API CALL (REVISED FUNCTION) ---
def get_jobs_from_brightdata(role, city):
    """
    Calls the Bright Data scraper API, with polling to handle async responses.
    """
    print(f"--- Fetching jobs for {role} in {city} ---")
    
    payload = {
        'keyword': role,
        'location': city,
        'country': 'US',
        'time_range': 'Past week'
    }
    
    # --- FIX: Implemented a polling loop ---
    max_retries = 10  # Safety break: 10 retries * 30s = 5 minutes
    
    for i in range(max_retries):
        try:
            # We give the request a longer timeout
            response = requests.post(
                BRIGHTDATA_ENDPOINT,
                json=payload,
                headers=BRIGHTDATA_HEADERS,
                timeout=60 
            )
            response.raise_for_status() # Check for HTTP errors
            
            raw_response_data = response.json()
            print(f"DEBUG: Raw response type: {type(raw_response_data)}")
            print(f"DEBUG: Raw response (first 500 chars): {str(raw_response_data)[:500]}")

            # --- POLLING LOGIC ---

            # Case 1: SUCCESS! The data is a list.
            if isinstance(raw_response_data, list):
                print(f"Successfully fetched {len(raw_response_data)} job items.")
                return raw_response_data
            
            # Case 2: PENDING. The data is a status dictionary.
            if isinstance(raw_response_data, dict):
                status = raw_response_data.get('status')
                if status in ['starting', 'closing', 'running']:
                    message = raw_response_data.get('message', 'Snapshot not ready.')
                    print(f"Bright Data status: {message}. Retrying in 30s... (Attempt {i+1}/{max_retries})")
                    time.sleep(30) # Wait for 30 seconds as requested
                    continue # Go to the next loop iteration and try again
            
            # Case 3: UNEXPECTED. The response is not a list or a known status.
            print(f"WARNING: Received unexpected data from Bright Data: {raw_response_data}")
            return None

        except requests.exceptions.RequestException as e:
            print(f"Error calling Bright Data: {e}")
            return None
    
    print(f"Failed to fetch data for {role} in {city} after {max_retries} retries. Moving on.")
    return None

# --- 3. SUPABASE DATA HANDLING ---
# (Your function is correct, no changes needed)
def get_or_create_company(company_name, company_website=None, logo_url=None):
    clean_name = company_name.strip()
    if not clean_name:
        print("Skipping company creation: company_name is empty.")
        return None
    try:
        data, count = supabase.table('companies').upsert(
            {'name': clean_name, 'website_url': company_website, 'logo_url': logo_url},
            on_conflict='name'
        ).execute()
        return data[0]['id']
    except Exception as e:
        print(f"Error upserting company {clean_name}: {e}")
        return None

# (Your function is correct, no changes needed)
def insert_job(job_data, company_id):
    try:
        apply_url = job_data.get('apply_url')
        title = job_data.get('title', 'No Title Provided')
        if not apply_url:
            print(f"Skipping job ({title}): 'apply_url' is missing.")
            return
        existing = supabase.table('jobs').select('id').eq('apply_url', apply_url).execute()
        if existing.data:
            print(f"Skipping duplicate: {title}")
            return
        job_record = {
            'title': title,
            'description': job_data.get('description', 'No Description Provided'),
            'company_id': company_id,
            'location_name': job_data.get('location', 'N/A'),
            'location_type': job_data.get('location_type', 'On-Site'),
            'apply_url': apply_url,
            'posted_at': job_data.get('posted_at_timestamp', 'now()'),
            'source': 'BrightData',
            'is_paid': False,
            'is_featured': False
        }
        supabase.table('jobs').insert(job_record).execute()
        print(f"Successfully inserted: {title}")
    except Exception as e:
        print(f"Error inserting job {title}: {e}")

# --- 4. MAIN SCRIPT LOGIC ---
# (Your function is correct, no changes needed)
def main():
    targets = [
        # California (Bay Area)
        # ("AI Engineer", "San Francisco"),
        # ("AI Engineer", "San Jose"),
        # ("AI Engineer", "Palo Alto"),
        ("AI Engineer", "Mountain View"),
        ("AI Engineer", "Oakland"),
        ("AI Engineer", "Santa Clara"),
        ("AI Engineer", "Sunnyvale"),
        # California (SoCal)
        ("AI Engineer", "Los Angeles"),
        ("AI Engineer", "San Diego"),
        # Washington
        ("AI Engineer", "Seattle"),
        ("AI Engineer", "Bellevue"),
        ("AI Engineer", "Redmond"),
        # Massachusetts
        ("AI Engineer", "Boston"),
        ("AI Engineer", "Cambridge"),
        ("AI Engineer","Somerville"),
        # DC Metro
        ("AI Engineer", "Washington."), # Note: Typo? "Washington." with a period?
        ("AI Engineer", "Arlington"),
        # Maryland
        ("AI Engineer", "Baltimore"),
        ("AI Engineer", "Rockville"),
        ("AI Engineer", "Bethesda"),
        ("AI Engineer", "Gaithersburg"),
        ("AI Engineer", "Columbia"),
        ("AI Engineer", "Silver Spring"),
    ]
    
    for role, city in targets:
        jobs = get_jobs_from_brightdata(role, city)
        
        if not jobs or not isinstance(jobs, list):
            print(f"No valid job list returned for {role} in {city}. Skipping.")
            continue
            
        print(f"Processing {len(jobs)} job items for {city}...")
        
        for i, job in enumerate(jobs):
            if not isinstance(job, dict):
                print(f"ERROR: Job item #{i} is a {type(job)}, not a dictionary. Skipping.")
                print(f"Data: {job}")
                continue
            
            company_name = job.get('company_name')
            apply_url = job.get('apply_url')
            
            if not company_name or not apply_url:
                print(f"ERROR: Job item #{i} (Title: {job.get('title')}) is missing 'company_name' or 'apply_url'. Skipping.")
                continue

            company_id = get_or_create_company(
                company_name,
                job.get('company_website'),
                job.get('company_logo')
            )
            
            if not company_id:
                print(f"Skipping job because company could not be created for {company_name}")
                continue
            
            insert_job(job, company_id)
            time.sleep(0.2)
            
    print("--- Backfill complete ---")

if __name__ == "__main__":
    main()