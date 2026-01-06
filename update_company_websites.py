import os
import json
from supabase import create_client, Client
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL or SUPABASE_KEY not found in environment variables.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def update_company_websites():
    # Load websites data
    try:
        with open('websites.json', 'r') as f:
            websites_data = json.load(f)
    except FileNotFoundError:
        print("Error: websites.json not found.")
        return
    except json.JSONDecodeError:
        print("Error: Failed to decode websites.json.")
        return

    print(f"Found {len(websites_data)} companies to process.")

    updated_count = 0
    skipped_count = 0
    error_count = 0

    for company_name, website_url in websites_data.items():
        if not company_name or not website_url:
            print(f"Skipping empty data: {company_name} -> {website_url}")
            skipped_count += 1
            continue

        print(f"Updating {company_name} with {website_url}...")

        try:
            # Update the website_url for the company with the matching name
            # We use 'website_url' based on backfill.py line 86: 'website_url': company_website
            response = supabase.table('companies').update(
                {'website_url': website_url}
            ).eq('name', company_name).execute()
            
            # Check if any row was actually updated
            # The response object generally has a 'data' attribute which is a list of updated rows
            if response.data:
                updated_count += 1
                print(f"  Success: Updated {company_name}")
            else:
                print(f"  Warning: Company '{company_name}' not found in database or no change needed.")
                skipped_count += 1

        except Exception as e:
            print(f"  Error updating {company_name}: {e}")
            error_count += 1

    print("-" * 30)
    print(f"Processing complete.")
    print(f"Updated: {updated_count}")
    print(f"Skipped/Not Found: {skipped_count}")
    print(f"Errors: {error_count}")

if __name__ == "__main__":
    update_company_websites()
