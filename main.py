import os
import statistics
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import List, Optional
# NEW IMPORT FOR INDEXNOW LOGIC
import httpx


# --- Initialization ---

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Get Supabase credentials from .env
# NOTE: Ensure your .env file has SUPABASE_URL and SUPABASE_KEY defined
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# Safety check for environment variables
if not url or not key:
    raise EnvironmentError("SUPABASE_URL or SUPABASE_KEY not found in environment variables.")

# Create a single Supabase client instance
supabase: Client = create_client(url, key)

# --- CORS Middleware ---
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Endpoints ---

@app.get("/api/jobs-by-location")
async def get_jobs_by_location(
    country: List[str] = Query(None), 
    state: List[str] = Query(None), 
    city: List[str] = Query(None),
    job_type: List[str] = Query(None),
    location_type: List[str] = Query(None), 
    company_id: List[str] = Query(None), 
    min_salary: int = None,
    page: int = 1,
    page_size: int = 20
):
    
    range_from = (page - 1) * page_size
    range_to = range_from + page_size - 1

    def apply_filters(query):
        # A set of common "empty" values sent by frontends
        ignore_values = {None, '', 'null', 'undefined'}

        def get_cleaned_list(values: Optional[List[str]]) -> Optional[List[str]]:
            """Removes all ignored values from a list."""
            if not values:
                return None
            cleaned = [v for v in values if v not in ignore_values]
            return cleaned if cleaned else None

        # Clean each filter list before using it
        cleaned_countries = get_cleaned_list(country)
        if cleaned_countries:
            query = query.in_('country', cleaned_countries)

        cleaned_states = get_cleaned_list(state)
        if cleaned_states:
            query = query.in_('state', cleaned_states)

        cleaned_cities = get_cleaned_list(city)
        if cleaned_cities:
            query = query.in_('city', cleaned_cities)

        cleaned_job_types = get_cleaned_list(job_type)
        if cleaned_job_types:
            query = query.in_('employment_type', cleaned_job_types)

        cleaned_location_types = get_cleaned_list(location_type)
        if cleaned_location_types:
            query = query.in_('location_type', cleaned_location_types)

        cleaned_company_ids = get_cleaned_list(company_id)
        if cleaned_company_ids:
            query = query.in_('company_id', cleaned_company_ids)
            
        if min_salary is not None:
            query = query.gte('salary_min', min_salary)
            
        return query

    # --- 1. Get TOTAL count ---
    count_query = supabase.table('jobs').select('id', count='exact')
    count_query = apply_filters(count_query)
    count_response = count_query.execute()

    total_count = count_response.count if count_response.count else 0

    # --- 2. Get PAGINATED results ---
    data_query = supabase.table('jobs').select('*, companies(id, name, logo_url, slug)')
    
    data_query = apply_filters(data_query)
    data_query = data_query.order('posted_at', desc=True)
    data_query = data_query.range(range_from, range_to)

    data_response = data_query.execute()

    return {
        "jobs": data_response.data,
        "total_count": total_count
    }


@app.get("/api/job/{job_id}")
async def get_job_by_id(job_id: str):
    response = supabase.table('jobs')\
                        .select('*, companies(id, name, logo_url, slug)')\
                        .eq('id', job_id)\
                        .single()\
                        .execute()
    return {"job": response.data}

@app.get("/api/locations/countries")
async def get_countries(
    company_id: List[str] = Query(None),
    job_type: List[str] = Query(None),
    location_type: List[str] = Query(None),
):
    """Returns countries, optionally filtered by company/employment type/work model."""
    query = supabase.table('jobs').select('country')
    
    if company_id:
        query = query.in_('company_id', company_id)
    if job_type:
        query = query.in_('employment_type', job_type)
    if location_type:
        query = query.in_('location_type', location_type)
    
    response = query.execute()
    countries = list(set(item['country'] for item in response.data if item['country']))
    countries.sort()
    return {"countries": countries}

@app.get("/api/locations/states")
async def get_states(
    country: str = None,
    company_id: List[str] = Query(None),
    job_type: List[str] = Query(None),
    location_type: List[str] = Query(None),
):
    """Returns states, optionally filtered by country and other filters."""
    query = supabase.table('jobs').select('state')
    
    if country:
        query = query.eq('country', country)
    if company_id:
        query = query.in_('company_id', company_id)
    if job_type:
        query = query.in_('employment_type', job_type)
    if location_type:
        query = query.in_('location_type', location_type)
        
    response = query.execute()
    states = list(set(item['state'] for item in response.data if item['state']))
    states.sort()
    return {"states": states}

@app.get("/api/locations/cities")
async def get_cities(
    state: str = None,
    company_id: List[str] = Query(None),
    job_type: List[str] = Query(None),
    location_type: List[str] = Query(None),
):
    """Returns cities, optionally filtered by state and other filters."""
    query = supabase.table('jobs').select('city')
    
    if state:
        query = query.eq('state', state)
    if company_id:
        query = query.in_('company_id', company_id)
    if job_type:
        query = query.in_('employment_type', job_type)
    if location_type:
        query = query.in_('location_type', location_type)
        
    response = query.execute()
    
    cities = list(set(item['city'] for item in response.data if item['city']))
    cities.sort()
    return {"cities": cities}


# --- Options Endpoints ---

@app.get("/api/options/companies")
async def get_companies(
    country: List[str] = Query(None),
    state: List[str] = Query(None),
    city: List[str] = Query(None),
    job_type: List[str] = Query(None),
    location_type: List[str] = Query(None),
    min_salary: Optional[int] = None
):
    query = supabase.table('jobs').select('companies(id, name, slug)')
    
    if city:
        query = query.in_('city', city)
    if state:
        query = query.in_('state', state)
    if country:
        query = query.in_('country', country)
    if job_type:
        query = query.in_('employment_type', job_type)
    if location_type:
        query = query.in_('location_type', location_type)
    if min_salary:
        query = query.gte('salary_min', min_salary)

    response = query.execute()
    
    companies = {}
    if response.data:
        for item in response.data:
            company_data = item.get('companies')
            if company_data and company_data.get('id') and company_data.get('name'):
                companies[company_data['id']] = {
                            "name": company_data['name'],
                            "slug": company_data.get('slug')
                            }
            
    unique_companies = [
        {
            "id": id, 
            "name": data['name'], 
            "slug": data['slug']
        } 
    for id, data in companies.items()
        if data['slug']
        ]
    
    unique_companies.sort(key=lambda x: x['name'])
    
    return {"companies": unique_companies}

@app.get("/api/options/employment-types")
async def get_employment_types(
    country: List[str] = Query(None),
    state: List[str] = Query(None),
    city: List[str] = Query(None),
    location_type: List[str] = Query(None),
    company_id: List[str] = Query(None),
    min_salary: Optional[int] = None
):
    query = supabase.table('jobs').select('employment_type')
    
    if city:
        query = query.in_('city', city)
    if state:
        query = query.in_('state', state)
    if country:
        query = query.in_('country', country)
    if location_type:
        query = query.in_('location_type', location_type)
    if company_id:
        query = query.in_('company_id', company_id)
    if min_salary:
        query = query.gte('salary_min', min_salary)
    
    response = query.execute()
    types = list(set(item['employment_type'] for item in response.data if item['employment_type']))
    types.sort()
    return {"employment_types": types}


@app.get("/api/options/work-models")
async def get_work_models(
    country: List[str] = Query(None),
    state: List[str] = Query(None),
    city: List[str] = Query(None),
    job_type: List[str] = Query(None),
    company_id: List[str] = Query(None),
    min_salary: Optional[int] = None
):
    query = supabase.table('jobs').select('location_type')
    
    if city:
        query = query.in_('city', city)
    if state:
        query = query.in_('state', state)
    if country:
        query = query.in_('country', country)
    if job_type:
        query = query.in_('employment_type', job_type)
    if company_id:
        query = query.in_('company_id', company_id)
    if min_salary:
        query = query.gte('salary_min', min_salary)

    response = query.execute()
    models = list(set(item['location_type'] for item in response.data if item['location_type']))
    models.sort()
    return {"location_type": models}

@app.get("/api/company-by-slug/{slug}")
async def get_company_by_slug(slug: str):
    response = supabase.table('companies').select('id, name, logo_url, slug').eq('slug', slug).single().execute()
    
    if response.data:
        return {"company": response.data}
    return {"error": "Company not found"}, 404

# --- FAQ Data ---
@app.get("/api/faqs")
async def get_faq_data(
    country: str = None,
    state: str = None,
    city: str = None,
    employment_type: str = None,
    location_type: str = None,
    company_id: str = None,
):
    rpc_params = {
        'filter_country': country,
        'filter_state': state,
        'filter_city': city,
        'filter_employment_type': employment_type,
        'filter_location_type': location_type,
        'filter_company_id': company_id
    }
    
    # Call the highly-optimized PostgreSQL function
    response = supabase.rpc('get_location_faqs', rpc_params).execute()
    
    faq_data = response.data

    # Normalize Supabase response (handle list or single dict)
    if isinstance(faq_data, list):
        faq_data = faq_data[0] if faq_data else None

    # If still no data or total_jobs == 0
    if not faq_data or faq_data.get('total_jobs', 0) == 0:
        return {"error": "No jobs found for this location"}, 404

    return faq_data

@app.get("/api/stats/company-job-counts")
async def get_company_job_counts(
    country: List[str] = Query(None), 
    state: List[str] = Query(None), 
    city: List[str] = Query(None)
):
    """
    Calls the 'get_company_job_counts' SQL function
    to get job counts per company based on location filters.
    """
    params = {
        'filter_countries': country,
        'filter_states': state,
        'filter_cities': city
    }
    
    # Remove null filters so the SQL function uses its defaults
    rpc_params = {k: v for k, v in params.items() if v is not None}
    
    response = supabase.rpc('get_company_job_counts', rpc_params).execute()
    
    return {"company_counts": response.data}


# --- PSEO Static Generation Endpoints ---

@app.get("/api/companies/all")
async def get_all_companies():
    """
    Returns all companies with their details for static generation.
    Used by generateStaticParams for company pages.
    """
    response = supabase.table('companies').select('id, name, slug, logo_url, website_url').execute()
    
    companies = [c for c in response.data if c.get('slug')]
    companies.sort(key=lambda x: x['name'])
    
    return {"companies": companies}


@app.get("/api/options/employment-types-all")
async def get_all_employment_types():
    """
    Returns all distinct employment types for static generation.
    """
    response = supabase.table('jobs').select('employment_type').execute()
    types = list(set(item['employment_type'] for item in response.data if item['employment_type']))
    types.sort()
    return {"employment_types": types}


@app.get("/api/options/work-models-all")
async def get_all_work_models():
    """
    Returns all distinct work models (location_type) for static generation.
    """
    response = supabase.table('jobs').select('location_type').execute()
    models = list(set(item['location_type'] for item in response.data if item['location_type']))
    models.sort()
    return {"work_models": models}


@app.get("/api/locations/states-with-country")
async def get_states_with_country():
    """
    Returns all unique state + country combinations for static generation.
    """
    response = supabase.table('jobs').select('state, country').execute()
    
    seen = set()
    result = []
    for item in response.data:
        if item.get('state') and item.get('country'):
            key = (item['state'], item['country'])
            if key not in seen:
                seen.add(key)
                result.append({"state": item['state'], "country": item['country']})
    
    result.sort(key=lambda x: (x['country'], x['state']))
    return {"states": result}


@app.get("/api/locations/cities-with-state-country")
async def get_cities_with_state_country():
    """
    Returns all unique city + state + country combinations for static generation.
    """
    response = supabase.table('jobs').select('city, state, country').execute()
    
    seen = set()
    result = []
    for item in response.data:
        if item.get('city') and item.get('state') and item.get('country'):
            key = (item['city'], item['state'], item['country'])
            if key not in seen:
                seen.add(key)
                result.append({
                    "city": item['city'],
                    "state": item['state'],
                    "country": item['country']
                })
    
    result.sort(key=lambda x: (x['country'], x['state'], x['city']))
    return {"cities": result}


## 🆕 NEW DYNAMIC ENDPOINT FOR INDEXNOW

@app.get("/api/indexnow")
async def indexnow_endpoint(url: str = Query(..., description="The URL to submit"), key: str = Query(..., description="The IndexNow API key")):
    """
    Handles IndexNow submissions to Bing and Yandex.
    This was moved from the Next.js API route to enable static export.
    """
    # Retrieve the API key from FastAPI's environment (same .env file)
    INDEXNOW_API_KEY = os.environ.get("INDEXNOW_API_KEY")

    if not url or not key:
        return {"error": "Missing url or key parameter"}, status.HTTP_400_BAD_REQUEST

    if key != INDEXNOW_API_KEY:
        return {"error": "Invalid key"}, status.HTTP_401_UNAUTHORIZED
    
    # Use httpx for asynchronous requests
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            bing_url = f"https://www.bing.com/indexnow?url={url}&key={key}"
            yandex_url = f"https://yandex.com/indexnow?url={url}&key={key}"

            bing_response = await client.get(bing_url)
            yandex_response = await client.get(yandex_url)

            if bing_response.is_success and yandex_response.is_success:
                return {"message": "URLs submitted successfully"}
            else:
                return {"error": "Error submitting URLs. Check Bing/Yandex status."}, status.HTTP_500_INTERNAL_SERVER_ERROR
        except Exception as error:
            print(f"IndexNow Error: {error}")
            return {"error": "Internal server error"}, status.HTTP_500_INTERNAL_SERVER_ERROR


# --- FRONTEND SERVING ROUTES ---

# [REMOVED] Static files are now served by the Next.js (Node.js) server.
# This Python backend is now a pure API service.

@app.get("/")
async def root():
    return {"message": "My AI Jobs API is running"}