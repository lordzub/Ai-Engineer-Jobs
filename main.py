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
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost",
    "https://aiengineerjobs.ai",
    "https://www.aiengineerjobs.ai",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
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

        # FRESHNESS FILTER: Exclude jobs older than 60 days
        from datetime import datetime, timedelta
        sixty_days_ago = (datetime.now() - timedelta(days=60)).isoformat()
        query = query.gte('posted_at', sixty_days_ago)

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
    from datetime import datetime, timedelta
    
    query = supabase.table('jobs').select('country')
    
    # FRESHNESS FILTER: Exclude jobs older than 60 days
    sixty_days_ago = (datetime.now() - timedelta(days=60)).isoformat()
    query = query.gte('posted_at', sixty_days_ago)
    
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
    from datetime import datetime, timedelta
    
    query = supabase.table('jobs').select('state')
    
    # FRESHNESS FILTER: Exclude jobs older than 60 days
    sixty_days_ago = (datetime.now() - timedelta(days=60)).isoformat()
    query = query.gte('posted_at', sixty_days_ago)
    
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
    from datetime import datetime, timedelta
    
    query = supabase.table('jobs').select('city')
    
    # FRESHNESS FILTER: Exclude jobs older than 60 days
    sixty_days_ago = (datetime.now() - timedelta(days=60)).isoformat()
    query = query.gte('posted_at', sixty_days_ago)
    
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
    from datetime import datetime, timedelta
    
    query = supabase.table('jobs').select('companies(id, name, slug)')
    
    # FRESHNESS FILTER: Exclude jobs older than 60 days
    sixty_days_ago = (datetime.now() - timedelta(days=60)).isoformat()
    query = query.gte('posted_at', sixty_days_ago)
    
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
    from datetime import datetime, timedelta
    
    query = supabase.table('jobs').select('employment_type')
    
    # FRESHNESS FILTER: Exclude jobs older than 60 days
    sixty_days_ago = (datetime.now() - timedelta(days=60)).isoformat()
    query = query.gte('posted_at', sixty_days_ago)
    
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
    from datetime import datetime, timedelta
    
    query = supabase.table('jobs').select('location_type')
    
    # FRESHNESS FILTER: Exclude jobs older than 60 days
    sixty_days_ago = (datetime.now() - timedelta(days=60)).isoformat()
    query = query.gte('posted_at', sixty_days_ago)
    
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


# --- Salary Statistics Endpoint ---
@app.get("/api/stats/salary")
async def get_salary_stats(
    country: List[str] = Query(None), 
    state: List[str] = Query(None), 
    city: List[str] = Query(None),
    job_type: List[str] = Query(None),
    location_type: List[str] = Query(None), 
    company_id: List[str] = Query(None),
):
    """
    Returns salary statistics for the given filters.
    Provides avg, min, max salary plus job counts.
    """
    from datetime import datetime, timedelta
    
    # Build base query for jobs with salary data
    query = supabase.table('jobs').select(
        'salary_min, salary_max, salary_currency, location_type'
    )
    
    # FRESHNESS FILTER: Exclude jobs older than 60 days
    sixty_days_ago = (datetime.now() - timedelta(days=60)).isoformat()
    query = query.gte('posted_at', sixty_days_ago)
    
    # Apply filters
    ignore_values = {None, '', 'null', 'undefined'}
    
    def clean_list(values):
        if not values:
            return None
        cleaned = [v for v in values if v not in ignore_values]
        return cleaned if cleaned else None
    
    cleaned_countries = clean_list(country)
    if cleaned_countries:
        query = query.in_('country', cleaned_countries)
    
    cleaned_states = clean_list(state)
    if cleaned_states:
        query = query.in_('state', cleaned_states)
    
    cleaned_cities = clean_list(city)
    if cleaned_cities:
        query = query.in_('city', cleaned_cities)
    
    cleaned_job_types = clean_list(job_type)
    if cleaned_job_types:
        query = query.in_('employment_type', cleaned_job_types)
    
    cleaned_location_types = clean_list(location_type)
    if cleaned_location_types:
        query = query.in_('location_type', cleaned_location_types)
    
    cleaned_company_ids = clean_list(company_id)
    if cleaned_company_ids:
        query = query.in_('company_id', cleaned_company_ids)
    
    response = query.execute()
    jobs = response.data
    
    if not jobs:
        return {
            "total_jobs": 0,
            "jobs_with_salary": 0,
            "avg_salary": None,
            "min_salary": None,
            "max_salary": None,
            "remote_count": 0,
            "remote_percentage": 0,
        }
    
    # Calculate salary stats
    salaries = []
    for job in jobs:
        if job.get('salary_min') and job.get('salary_max'):
            # Use midpoint for average calculation
            mid = (job['salary_min'] + job['salary_max']) / 2
            salaries.append(mid)
        elif job.get('salary_min'):
            salaries.append(job['salary_min'])
        elif job.get('salary_max'):
            salaries.append(job['salary_max'])
    
    # Calculate remote stats
    remote_count = sum(1 for job in jobs if job.get('location_type', '').lower() == 'remote')
    
    total_jobs = len(jobs)
    jobs_with_salary = len(salaries)
    
    result = {
        "total_jobs": total_jobs,
        "jobs_with_salary": jobs_with_salary,
        "avg_salary": round(statistics.mean(salaries)) if salaries else None,
        "min_salary": round(min(salaries)) if salaries else None,
        "max_salary": round(max(salaries)) if salaries else None,
        "median_salary": round(statistics.median(salaries)) if salaries else None,
        "remote_count": remote_count,
        "remote_percentage": round((remote_count / total_jobs) * 100) if total_jobs > 0 else 0,
        "currency": "USD",  # Default currency
    }
    
    return result

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


# --- Knowledge Graph Context Endpoint ---

@app.get("/api/graph/context")
async def get_graph_context(
    company_id: str = None,
    company_slug: str = None,
    country: str = None,
    state: str = None,
    city: str = None,
    work_model: str = None,
    employment_type: str = None,
    min_jobs: int = 3,  # Minimum jobs threshold for links (thin content prevention)
):
    """
    Returns hierarchical tree context for the current page.
    Used by JobContextTree component for semantic navigation.
    
    Returns:
    - hierarchy: The path from root to current node with job counts
    - siblings: Other nodes at the same level with job counts
    - current: The current node label and count
    """
    
    def slugify(text: str) -> str:
        """Convert text to URL-safe slug."""
        import re
        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    
    # Helper to build URLs preserving context
    def build_href(tgt_country=None, tgt_state=None, tgt_city=None, 
                   tgt_company_slug=None, tgt_work_model=None, tgt_emp_type=None):
        # Determine base path
        base_parts = []
        
        # Company context takes precedence
        if tgt_company_slug:
            base_parts.append(f"/company/{tgt_company_slug}")
            # If company, append filters if they exist
            if tgt_work_model:
                base_parts.append(slugify(tgt_work_model))
            elif tgt_emp_type:
                base_parts.append(slugify(tgt_emp_type))
        else:
            # Standard context
            if tgt_work_model:
                base_parts.append(f"/work-model/{slugify(tgt_work_model)}")
            elif tgt_emp_type:
                base_parts.append(f"/employment-type/{slugify(tgt_emp_type)}")
            else:
                base_parts.append("/jobs")
        
        path = "/".join(base_parts)
        
        # Append location
        if tgt_country:
            path += f"/{slugify(tgt_country)}"
        if tgt_state:
            path += f"/{slugify(tgt_state)}"
        if tgt_city:
            path += f"/{slugify(tgt_city)}"
            
        return path

    hierarchy = []
    siblings = []
    
    # --- Build base query function ---
    def get_count_with_filters(**filters):
        """Get job count with given filters."""
        from datetime import datetime, timedelta
        
        query = supabase.table('jobs').select('id', count='exact')
        
        # FRESHNESS FILTER: Exclude jobs older than 60 days  
        sixty_days_ago = (datetime.now() - timedelta(days=60)).isoformat()
        query = query.gte('posted_at', sixty_days_ago)
        
        if filters.get('company_id'):
            query = query.eq('company_id', filters['company_id'])
        if filters.get('country'):
            query = query.eq('country', filters['country'])
        if filters.get('state'):
            query = query.eq('state', filters['state'])
        if filters.get('city'):
            query = query.eq('city', filters['city'])
        if filters.get('location_type'):
            query = query.eq('location_type', filters['location_type'])
        if filters.get('employment_type'):
            query = query.eq('employment_type', filters['employment_type'])
            
        response = query.execute()
        return response.count or 0
    
    # --- 1. Get total job count (root) ---
    total_count = get_count_with_filters()
    # Root always goes to home /
    hierarchy.append({
        "label": "AI Engineer Jobs",
        "href": "/",
        "jobCount": total_count,
        "type": "root"
    })
    
    # --- 2. If company filter, add company to hierarchy ---
    current_filters = {}
    company_name = None
    # For build_href usage
    curr_company_slug = None
    
    if company_id or company_slug:
        # Get company details
        if company_slug:
            company_res = supabase.table('companies').select('id, name, slug').eq('slug', company_slug).single().execute()
        else:
            company_res = supabase.table('companies').select('id, name, slug').eq('id', company_id).single().execute()
        
        if company_res.data:
            company_name = company_res.data['name']
            curr_company_slug = company_res.data['slug']
            company_id = company_res.data['id']
            current_filters['company_id'] = company_id
            
            company_count = get_count_with_filters(**current_filters)
            # Company node href - usually just company root
            hierarchy.append({
                "label": company_name,
                "href": f"/company/{curr_company_slug}",
                "jobCount": company_count,
                "type": "company"
            })
    
    # --- 3. If work model filter, add to hierarchy ---
    if work_model:
        current_filters['location_type'] = work_model
        wm_count = get_count_with_filters(**current_filters)
        
        # Use our helper for the href
        href = build_href(tgt_company_slug=curr_company_slug, tgt_work_model=work_model)
            
        hierarchy.append({
            "label": work_model,
            "href": href,
            "jobCount": wm_count,
            "type": "work-model"
        })
    
    # --- 4. If employment type filter, add to hierarchy ---
    if employment_type:
        current_filters['employment_type'] = employment_type
        et_count = get_count_with_filters(**current_filters)
        
        href = build_href(tgt_company_slug=curr_company_slug, tgt_emp_type=employment_type)
            
        hierarchy.append({
            "label": employment_type,
            "href": href,
            "jobCount": et_count,
            "type": "employment-type"
        })
    
    # --- 5. If country filter, add to hierarchy ---
    if country:
        current_filters['country'] = country
        country_count = get_count_with_filters(**current_filters)
        
        href = build_href(tgt_country=country, 
                          tgt_company_slug=curr_company_slug, 
                          tgt_work_model=work_model, 
                          tgt_emp_type=employment_type)
            
        hierarchy.append({
            "label": country,
            "href": href,
            "jobCount": country_count,
            "type": "country"
        })
    
    # --- 6. If state filter, add to hierarchy ---
    if state:
        current_filters['state'] = state
        state_count = get_count_with_filters(**current_filters)
        
        href = build_href(tgt_country=country, tgt_state=state,
                          tgt_company_slug=curr_company_slug, 
                          tgt_work_model=work_model, 
                          tgt_emp_type=employment_type)
            
        hierarchy.append({
            "label": state,
            "href": href,
            "jobCount": state_count,
            "type": "state"
        })
    
    # --- 7. If city filter, add to hierarchy ---
    if city:
        current_filters['city'] = city
        city_count = get_count_with_filters(**current_filters)
        
        href = build_href(tgt_country=country, tgt_state=state, tgt_city=city,
                          tgt_company_slug=curr_company_slug, 
                          tgt_work_model=work_model, 
                          tgt_emp_type=employment_type)
            
        hierarchy.append({
            "label": city,
            "href": href,
            "jobCount": city_count,
            "type": "city"
        })
    
    # --- 8. Get siblings at current level ---
    # Siblings are other items at the same depth
    
    if city and state:
        # Siblings are other cities in the same state
        sibling_filters = {k: v for k, v in current_filters.items() if k != 'city'}
        cities_query = supabase.table('jobs').select('city').match(sibling_filters)
        cities_res = cities_query.execute()
        
        city_counts = {}
        for job in cities_res.data:
            if job.get('city') and job['city'] != city:
                city_counts[job['city']] = city_counts.get(job['city'], 0) + 1
        
        for sib_city, count in sorted(city_counts.items(), key=lambda x: -x[1]):
            if count >= min_jobs:
                href = build_href(tgt_country=country, tgt_state=state, tgt_city=sib_city,
                                  tgt_company_slug=curr_company_slug,
                                  tgt_work_model=work_model,
                                  tgt_emp_type=employment_type)
                siblings.append({
                    "label": sib_city,
                    "href": href,
                    "jobCount": count,
                    "type": "city"
                })
                if len(siblings) >= 6:
                    break
                    
    elif state and country:
        # Siblings are other states in the same country
        sibling_filters = {k: v for k, v in current_filters.items() if k != 'state'}
        states_query = supabase.table('jobs').select('state').match(sibling_filters)
        states_res = states_query.execute()
        
        state_counts = {}
        for job in states_res.data:
            if job.get('state') and job['state'] != state:
                state_counts[job['state']] = state_counts.get(job['state'], 0) + 1
        
        for sib_state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
            if count >= min_jobs:
                href = build_href(tgt_country=country, tgt_state=sib_state,
                                  tgt_company_slug=curr_company_slug,
                                  tgt_work_model=work_model,
                                  tgt_emp_type=employment_type)
                siblings.append({
                    "label": sib_state,
                    "href": href,
                    "jobCount": count,
                    "type": "state"
                })
                if len(siblings) >= 6:
                    break
                    
    elif country:
        # Siblings are other countries
        sibling_filters = {k: v for k, v in current_filters.items() if k != 'country'}
        countries_query = supabase.table('jobs').select('country')
        if sibling_filters.get('company_id'):
            countries_query = countries_query.eq('company_id', sibling_filters['company_id'])
        countries_res = countries_query.execute()
        
        country_counts = {}
        for job in countries_res.data:
            if job.get('country') and job['country'] != country:
                country_counts[job['country']] = country_counts.get(job['country'], 0) + 1
        
        for sib_country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
            if count >= min_jobs:
                href = build_href(tgt_country=sib_country,
                                  tgt_company_slug=curr_company_slug,
                                  tgt_work_model=work_model,
                                  tgt_emp_type=employment_type)
                siblings.append({
                    "label": sib_country,
                    "href": href,
                    "jobCount": count,
                    "type": "country"
                })
                if len(siblings) >= 6:
                    break
                    
    elif company_id:
        # Siblings are other companies (top ones by job count)
        companies_res = supabase.table('jobs').select('company_id, companies(name, slug)').execute()
        
        company_counts = {}
        for job in companies_res.data:
            if job.get('company_id') and job['company_id'] != company_id:
                comp = job.get('companies', {})
                if comp and comp.get('name') and comp.get('slug'):
                    key = (comp['name'], comp['slug'])
                    company_counts[key] = company_counts.get(key, 0) + 1
        
        for (comp_name, comp_slug), count in sorted(company_counts.items(), key=lambda x: -x[1]):
            if count >= min_jobs:
                # Switching company resets location filters in this sibling view logic, which seems okay or we could clear location
                # Usually siblings are alternatives.
                siblings.append({
                    "label": comp_name,
                    "href": f"/company/{comp_slug}",
                    "jobCount": count,
                    "type": "company"
                })
                if len(siblings) >= 6:
                    break
    
    # --- 9. Get children at next level ---
    # Children are the next level down from current context
    children = []
    
    if city:
        # City is the deepest level, no children
        pass
    elif state and country:
        # Children are cities in this state
        child_filters = dict(current_filters)
        cities_query = supabase.table('jobs').select('city').match(child_filters)
        cities_res = cities_query.execute()
        
        city_counts = {}
        for job in cities_res.data:
            if job.get('city'):
                city_counts[job['city']] = city_counts.get(job['city'], 0) + 1
        
        for child_city, count in sorted(city_counts.items(), key=lambda x: -x[1]):
            if count >= min_jobs:
                href = build_href(tgt_country=country, tgt_state=state, tgt_city=child_city,
                                  tgt_company_slug=curr_company_slug,
                                  tgt_work_model=work_model,
                                  tgt_emp_type=employment_type)
                children.append({
                    "label": child_city,
                    "href": href,
                    "jobCount": count,
                    "type": "city"
                })
                if len(children) >= 10:
                    break
                    
    elif country:
        # Children are states in this country
        child_filters = dict(current_filters)
        states_query = supabase.table('jobs').select('state').match(child_filters)
        states_res = states_query.execute()
        
        state_counts = {}
        for job in states_res.data:
            if job.get('state'):
                state_counts[job['state']] = state_counts.get(job['state'], 0) + 1
        
        for child_state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
            if count >= min_jobs:
                href = build_href(tgt_country=country, tgt_state=child_state,
                                  tgt_company_slug=curr_company_slug,
                                  tgt_work_model=work_model,
                                  tgt_emp_type=employment_type)
                children.append({
                    "label": child_state,
                    "href": href,
                    "jobCount": count,
                    "type": "state"
                })
                if len(children) >= 10:
                    break
                    
    elif company_id:
        # Children could be work models or countries for this company
        # Show countries where this company has jobs
        child_filters = dict(current_filters)
        countries_query = supabase.table('jobs').select('country').match(child_filters)
        countries_res = countries_query.execute()
        
        country_counts = {}
        for job in countries_res.data:
            if job.get('country'):
                country_counts[job['country']] = country_counts.get(job['country'], 0) + 1
        
        for child_country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
            if count >= min_jobs:
                href = build_href(tgt_country=child_country,
                                  tgt_company_slug=curr_company_slug,
                                  tgt_work_model=work_model,
                                  tgt_emp_type=employment_type)
                children.append({
                    "label": child_country,
                    "href": href,
                    "jobCount": count,
                    "type": "country"
                })
                if len(children) >= 30:  # Increased limit for Show More functionality
                    break
                    
    elif work_model or employment_type:
        # For work model or employment type pages, show countries
        child_filters = dict(current_filters)
        countries_query = supabase.table('jobs').select('country')
        if child_filters.get('location_type'):
            countries_query = countries_query.eq('location_type', child_filters['location_type'])
        if child_filters.get('employment_type'):
            countries_query = countries_query.eq('employment_type', child_filters['employment_type'])
        countries_res = countries_query.execute()
        
        country_counts = {}
        for job in countries_res.data:
            if job.get('country'):
                country_counts[job['country']] = country_counts.get(job['country'], 0) + 1
        
        for child_country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
            if count >= min_jobs:
                href = build_href(tgt_country=child_country,
                                  tgt_company_slug=curr_company_slug,
                                  tgt_work_model=work_model,
                                  tgt_emp_type=employment_type)
                children.append({
                    "label": child_country,
                    "href": href,
                    "jobCount": count,
                    "type": "country"
                })
                if len(children) >= 30:  # Increased limit for Show More functionality
                    break
    
    # --- 10. Get available filter paths (work models, employment types, companies) ---
    # These allow navigation to combined filter pages like /work-model/remote/united-kingdom
    filter_paths = {
        "workModels": [],
        "employmentTypes": [],
        "companies": []
    }
    
    # Get available work models for current context
    wm_query = supabase.table('jobs').select('location_type')
    if current_filters.get('company_id'):
        wm_query = wm_query.eq('company_id', current_filters['company_id'])
    if current_filters.get('country'):
        wm_query = wm_query.eq('country', current_filters['country'])
    if current_filters.get('state'):
        wm_query = wm_query.eq('state', current_filters['state'])
    if current_filters.get('city'):
        wm_query = wm_query.eq('city', current_filters['city'])
    if current_filters.get('employment_type'):
        wm_query = wm_query.eq('employment_type', current_filters['employment_type'])
    
    wm_res = wm_query.execute()
    wm_counts = {}
    for job in wm_res.data:
        lt = job.get('location_type')
        if lt:
            wm_counts[lt] = wm_counts.get(lt, 0) + 1
    
    for wm, count in sorted(wm_counts.items(), key=lambda x: -x[1]):
        if count >= min_jobs and wm != work_model:  # Don't show current filter
            wm_slug = slugify(wm)
            # Build URL based on context - PRIORITIZE employment_type over location
            if employment_type:
                # Preserve employment type context
                href = f"/work-model/{wm_slug}/{slugify(employment_type)}"
                if country:
                    href += f"/{slugify(country)}"
                    if state:
                        href += f"/{slugify(state)}"
                        if city:
                            href += f"/{slugify(city)}"
            elif company_name:
                # Company context
                href = f"/company/{company_slug or slugify(company_name)}/{wm_slug}"
                if country:
                    href += f"/{slugify(country)}"
                    if state:
                        href += f"/{slugify(state)}"
                        if city:
                            href += f"/{slugify(city)}"
            elif country:
                # Location context only
                href = f"/work-model/{wm_slug}/{slugify(country)}"
                if state:
                    href += f"/{slugify(state)}"
                    if city:
                        href += f"/{slugify(city)}"
            else:
                # Base work model
                href = f"/work-model/{wm_slug}"
            
            filter_paths["workModels"].append({
                "label": wm,
                "href": href,
                "jobCount": count
            })
    
    # Get available employment types for current context
    et_query = supabase.table('jobs').select('employment_type')
    if current_filters.get('company_id'):
        et_query = et_query.eq('company_id', current_filters['company_id'])
    if current_filters.get('country'):
        et_query = et_query.eq('country', current_filters['country'])
    if current_filters.get('state'):
        et_query = et_query.eq('state', current_filters['state'])
    if current_filters.get('city'):
        et_query = et_query.eq('city', current_filters['city'])
    if current_filters.get('location_type'):
        et_query = et_query.eq('location_type', current_filters['location_type'])
    
    et_res = et_query.execute()
    et_counts = {}
    for job in et_res.data:
        et = job.get('employment_type')
        if et:
            et_counts[et] = et_counts.get(et, 0) + 1
    
    for et, count in sorted(et_counts.items(), key=lambda x: -x[1]):
        if count >= min_jobs and et != employment_type:  # Don't show current filter
            et_slug = slugify(et)
            # Build URL based on context - PRIORITIZE work_model over location
            if work_model:
                # Preserve work model context
                href = f"/work-model/{slugify(work_model)}/{et_slug}"
                if country:
                    href += f"/{slugify(country)}"
                    if state:
                        href += f"/{slugify(state)}"
                        if city:
                            href += f"/{slugify(city)}"
            elif company_name:
                # Company context
                href = f"/company/{company_slug or slugify(company_name)}/{et_slug}"
                if country:
                    href += f"/{slugify(country)}"
                    if state:
                        href += f"/{slugify(state)}"
                        if city:
                            href += f"/{slugify(city)}"
            elif country:
                # Location context only
                href = f"/employment-type/{et_slug}/{slugify(country)}"
                if state:
                    href += f"/{slugify(state)}"
                    if city:
                        href += f"/{slugify(city)}"
            else:
                # Base employment type
                href = f"/employment-type/{et_slug}"
            
            filter_paths["employmentTypes"].append({
                "label": et,
                "href": href,
                "jobCount": count
            })
    
    # Get available companies for current context
    company_query = supabase.table('jobs').select('company_id, companies(name, slug)')
    
    # Apply same context filters (but don't filter by company_id since we want other companies)
    if current_filters.get('country'):
        company_query = company_query.eq('country', current_filters['country'])
    if current_filters.get('state'):
        company_query = company_query.eq('state', current_filters['state'])
    if current_filters.get('city'):
        company_query = company_query.eq('city', current_filters['city'])
    if current_filters.get('location_type'):
        company_query = company_query.eq('location_type', current_filters['location_type'])
    if current_filters.get('employment_type'):
        company_query = company_query.eq('employment_type', current_filters['employment_type'])
    
    company_res = company_query.execute()
    company_counts = {}
    
    for job in company_res.data:
        comp = job.get('companies', {})
        if comp and comp.get('name') and comp.get('slug'):
            # Skip the current company if we're on a company page
            if current_filters.get('company_id') and job.get('company_id') == current_filters['company_id']:
                continue
            key = (comp['name'], comp['slug'])
            company_counts[key] = company_counts.get(key, 0) + 1
    
    for (comp_name, comp_slug), count in sorted(company_counts.items(), key=lambda x: -x[1]):
        if count >= min_jobs:
            # Build URL that preserves location/filter context
            if country:
                href = f"/company/{comp_slug}/{slugify(country)}"
                if state:
                    href += f"/{slugify(state)}"
                if city:
                    href += f"/{slugify(city)}"
            elif work_model:
                href = f"/company/{comp_slug}/{slugify(work_model)}"
            elif employment_type:
                href = f"/company/{comp_slug}/{slugify(employment_type)}"
            else:
                href = f"/company/{comp_slug}"
            
            filter_paths["companies"].append({
                "label": comp_name,
                "href": href,
                "jobCount": count
            })
            if len(filter_paths["companies"]) >= 50:  # Increased limit for Show More functionality
                break
    
    # --- Build current node info ---
    current_node = hierarchy[-1] if hierarchy else None
    
    return {
        "hierarchy": hierarchy,
        "siblings": siblings,
        "children": children,
        "filterPaths": filter_paths,
        "current": current_node
    }


# --- FRONTEND SERVING ROUTES ---

# [REMOVED] Static files are now served by the Next.js (Node.js) server.
# This Python backend is now a pure API service.

@app.get("/")
async def root():
    return {"message": "My AI Jobs API is running"}