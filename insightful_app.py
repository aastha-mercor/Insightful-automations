import requests
import pandas as pd
import logging
import json
import time
import click
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# API Configuration
INSIGHTFUL_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6Inc2YjE3aXV3dGZrbzN4ZSIsImFjY291bnRJZCI6Ind4MW13Mm5xcTJuanI1aiIsIm9yZ2FuaXphdGlvbklkIjoidy15Y2hkdHAwb3B2aTJjIiwidHlwZSI6InVzZXIiLCJ1c2VyVHlwZSI6ImFwaSIsInZlcnNpb24iOjIsImlhdCI6MTczODAzNzAxMiwiZXhwIjozMTcyODI0Nzk0MTIsImF1ZCI6WyJQUk9EIl0sImlzcyI6IlBST0QifQ.IicUPTNxwBDTugzqMW9ZyQonTxaGZ11Ms-oRkVeETI4'

# Project ID to Project Name mapping
PROJECT_MAPPING = {
    "wzx8dcze_04iuwk": "Guppy",
    "whosz5wuyuvbo2v": "Delta",
    "wlfrdwxfpd7ud61": "Heka",
    "wknprrdwhywzdg-": "Prism"
}

# Create a session with retry
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=3)
session.mount("https://", adapter)
session.mount("http://", adapter)

# Rate limiting lock
request_lock = threading.Lock()
last_request_time = [0]  # Using a list to allow modification in functions
request_delay = 0.5  # Default delay in seconds between individual requests (reduced from 3s)

def convert_to_timestamp(date_str):
    """Convert date string to Unix timestamp in milliseconds"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp() * 1000)
    except ValueError:
        raise click.BadParameter(f"Date must be in YYYY-MM-DD format, got: {date_str}")

def wait_for_rate_limit():
    """Implement rate limiting using a minimum delay between requests"""
    with request_lock:
        current_time = time.time()
        elapsed = current_time - last_request_time[0]
        
        # If not enough time has passed since the last request, wait
        if elapsed < request_delay:
            sleep_time = request_delay - elapsed
            logging.debug(f"Rate limiting: waiting {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        # Update the last request time
        last_request_time[0] = time.time()

def robust_get(url, session, headers=None, params=None, retries=3, backoff_factor=1.0):
    """Make a GET request with retry logic and rate limiting."""
    for attempt in range(retries):
        try:
            # Implement rate limiting
            wait_for_rate_limit()
            
            response = session.get(url, headers=headers, params=params, timeout=30)
            
            # Check for rate limit errors (typically 429 Too Many Requests)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', request_delay * 2))
                logging.warning(f"Rate limited! Waiting for {retry_after} seconds before retry")
                time.sleep(retry_after)
                continue
                
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logging.error("Request error (%d/%d) for %s: %s", attempt+1, retries, url, e)
            if attempt < retries - 1:
                # Add jitter to backoff
                sleep_time = backoff_factor * (2 ** attempt)
                jitter = random.uniform(0, 0.1 * sleep_time)  # 10% jitter
                total_sleep = sleep_time + jitter
                logging.info(f"Retrying in {total_sleep:.1f} seconds...")
                time.sleep(total_sleep)
            else:
                raise
    return None

def fetch_data_with_cache(url, cache, cache_key, headers=None, params=None):
    """Fetch data with caching to reduce API calls"""
    if cache_key in cache:
        return cache[cache_key]
    
    response = robust_get(url, session, headers=headers, params=params)
    result = response.json()
    cache[cache_key] = result
    return result

def fetch_employee_data():
    """Fetch employee data from Insightful API"""
    url = "https://app.insightful.io/api/v1/employee"
    headers = {"Authorization": f"Bearer {INSIGHTFUL_API_KEY}"}
    
    logging.info("Fetching employee data from Insightful API")
    
    try:
        response = robust_get(url, session, headers=headers)
        employees = response.json()
        
        logging.info(f"Successfully fetched data for {len(employees)} employees")
        return employees
    except Exception as e:
        logging.error(f"Error fetching employees: {e}")
        return []

def fetch_apps_and_websites(employee_id, project_id, start_timestamp, end_timestamp, cache=None):
    """Fetch apps and websites data for a specific employee and project"""
    cache = cache or {}
    url = "https://app.insightful.io/api/v1/analytics/app"
    headers = {"Authorization": f"Bearer {INSIGHTFUL_API_KEY}"}
    params = {
        "employeeId": employee_id,
        "projectId": project_id,
        "start": start_timestamp,
        "end": end_timestamp
    }
    
    logging.debug(f"Fetching apps data for employee {employee_id} in project {project_id}")
    
    try:
        # Create a cache key based on parameters
        cache_key = f"{employee_id}_{project_id}_{start_timestamp}_{end_timestamp}"
        
        if cache_key in cache:
            apps_data = cache[cache_key]
            logging.debug(f"Using cached data for employee {employee_id}")
        else:
            response = robust_get(url, session, headers=headers, params=params)
            apps_data = response.json()
            cache[cache_key] = apps_data
        
        if isinstance(apps_data, list) and len(apps_data) > 0:
            logging.debug(f"Found {len(apps_data)} apps/websites for employee {employee_id}")
            
            # Extract app names and usage into separate lists
            app_names = [app.get("name", "Unknown") for app in apps_data]
            app_usage = [app.get("usage", 0) for app in apps_data]
            
            return {
                "employee_id": employee_id,
                "apps": app_names,
                "usage": app_usage,
                "has_data": True
            }
        else:
            logging.debug(f"No apps/websites data found for employee {employee_id}")
            return {
                "employee_id": employee_id,
                "apps": "No data/No screenshots",
                "usage": "No data",
                "has_data": False
            }
    except Exception as e:
        logging.error(f"Error fetching apps data for employee {employee_id}: {e}")
        return {
            "employee_id": employee_id,
            "apps": "No data/No screenshots",
            "usage": "No data",
            "has_data": False
        }

def process_employees_for_project(employees, project_id, start_timestamp, end_timestamp, max_workers=10, batch_size=5, batch_delay=1):
    """Process employees in batches with a delay between batches"""
    project_name = PROJECT_MAPPING.get(project_id, project_id)
    
    logging.info(f"Processing employees for project: {project_name} ({project_id})")
    
    # Find employees assigned to this project
    project_employees = [emp for emp in employees if project_id in emp.get("projects", [])]
    
    if not project_employees:
        logging.warning(f"No employees found for project {project_name}")
        return []
    
    employee_count = len(project_employees)
    logging.info(f"Found {employee_count} employees in project {project_name}")
    logging.info(f"Processing in batches of {batch_size} with {batch_delay}s delay between batches")
    
    # Create a shared cache for API responses
    api_cache = {}
    results = []
    
    # Split employees into batches
    batches = [project_employees[i:i + batch_size] for i in range(0, len(project_employees), batch_size)]
    
    for batch_index, batch in enumerate(batches):
        logging.info(f"Processing batch {batch_index+1}/{len(batches)} ({len(batch)} employees)")
        
        batch_results = []
        batch_success = 0
        batch_failure = 0
        
        # Process a batch in parallel
        with ThreadPoolExecutor(max_workers=min(max_workers, len(batch))) as executor:
            # Submit jobs for the batch
            future_to_employee = {
                executor.submit(
                    fetch_apps_and_websites, 
                    employee.get("id"), 
                    project_id, 
                    start_timestamp, 
                    end_timestamp,
                    api_cache
                ): employee for employee in batch
            }
            
            # Process as they complete
            for future in as_completed(future_to_employee):
                employee = future_to_employee[future]
                try:
                    apps_data = future.result()
                    
                    # Add employee info to the result
                    result = {
                        "employee_id": employee.get("id"),
                        "name": employee.get("name", "Unknown"),
                        "email": employee.get("email", ""),
                        "project_id": project_id,
                        "project_name": project_name,
                        "apps": json.dumps(apps_data["apps"]) if apps_data["has_data"] else "No data/No screenshots",
                        "usage": json.dumps(apps_data["usage"]) if apps_data["has_data"] else "No data"
                    }
                    
                    batch_results.append(result)
                    batch_success += 1
                    
                except Exception as e:
                    logging.error(f"Error processing employee {employee.get('id')}: {e}")
                    batch_failure += 1
        
        # Add batch results to overall results
        results.extend(batch_results)
        
        # Log batch success rate
        total_batch = batch_success + batch_failure
        success_rate = batch_success / total_batch if total_batch > 0 else 0
        logging.info(f"Batch {batch_index+1} completed with {batch_success}/{total_batch} success rate ({success_rate:.1%})")
        
        # Add a delay between batches (except after the last batch)
        if batch_index < len(batches) - 1:
            logging.info(f"Waiting {batch_delay}s before next batch...")
            time.sleep(batch_delay)
    
    return results

def save_cache_to_disk(cache, filename="insightful_api_cache.json"):
    """Save the API response cache to disk"""
    try:
        with open(filename, 'w') as f:
            json.dump(cache, f)
        logging.info(f"Cache saved to {filename}")
    except Exception as e:
        logging.error(f"Failed to save cache: {e}")

def load_cache_from_disk(filename="insightful_api_cache.json"):
    """Load the API response cache from disk"""
    try:
        with open(filename, 'r') as f:
            cache = json.load(f)
        logging.info(f"Loaded cache from {filename} with {len(cache)} entries")
        return cache
    except FileNotFoundError:
        logging.info("No cache file found, starting with empty cache")
        return {}
    except Exception as e:
        logging.error(f"Failed to load cache: {e}")
        return {}

@click.command()
@click.option('--project', '-p', help='Project name from the mapping (e.g., "Guppy", "Delta")')
@click.option('--project-id', '-pid', help='Project ID directly (e.g., "wzx8dcze_04iuwk")')
@click.option('--output', '-o', default=None, help='Output filename (default: insightful_<project>_apps.csv)')
@click.option('--list-projects', '-l', is_flag=True, help='List all available projects and exit')
@click.option('--start-date', '-sd', help='Start date in YYYY-MM-DD format')
@click.option('--end-date', '-ed', help='End date in YYYY-MM-DD format')
@click.option('--days', '-d', type=int, default=7, help='Number of days to look back if no dates specified (default: 7)')
@click.option('--threads', '-t', type=int, default=5, help='Number of parallel threads to use (default: 5)')
@click.option('--delay', '-dl', type=float, default=0.5, help='Delay between individual API requests in seconds (default: 0.5)')
@click.option('--batch-size', '-bs', type=int, default=5, help='Number of employees to process in each batch (default: 5)')
@click.option('--batch-delay', '-bd', type=float, default=1.0, help='Delay between batches in seconds (default: 1.0)')
@click.option('--use-cache/--no-cache', default=True, help='Use disk cache for API responses (default: True)')
@click.option('--cache-file', default="insightful_api_cache.json", help='Cache file location (default: insightful_api_cache.json)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def main(project, project_id, output, list_projects, start_date, end_date, days, threads, 
         delay, batch_size, batch_delay, use_cache, cache_file, verbose):
    """Fetch Insightful employee app usage data by project.
    
    Use either --project to specify a project name from the mapping,
    or --project-id to specify a project ID directly.
    
    You can specify a date range using --start-date and --end-date options,
    or use --days to look back a specific number of days from today.
    
    The script now supports batch processing with delays between batches
    to optimize performance while respecting API rate limits.
    """
    # Set logging level based on verbose flag
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Set the request delay
    global request_delay
    request_delay = delay
    logging.info(f"Setting individual API request delay to {delay} seconds")
    logging.info(f"Batch size: {batch_size}, Batch delay: {batch_delay} seconds")
    
    # List projects if requested
    if list_projects:
        click.echo("Available projects:")
        for pid, name in sorted(PROJECT_MAPPING.items(), key=lambda x: x[1]):
            click.echo(f"  {name} (ID: {pid})")
        return
    
    # Time the execution
    start_time = time.time()
    
    # Determine the project ID to use
    target_project_id = None
    
    if project_id:
        # Use directly provided project ID
        target_project_id = project_id
        if target_project_id not in PROJECT_MAPPING:
            click.echo(f"Warning: Project ID '{target_project_id}' not found in mapping, will use ID as name")
    elif project:
        # Find project ID from name
        for pid, name in PROJECT_MAPPING.items():
            if name.lower() == project.lower():
                target_project_id = pid
                break
        
        if not target_project_id:
            click.echo(f"Error: Project '{project}' not found in mapping. Use --list-projects to see available projects.")
            return
    else:
        click.echo("Error: Either --project or --project-id must be specified. Use --list-projects to see available projects.")
        return
    
    # Determine date range
    now = datetime.now()
    
    if start_date and end_date:
        # Use provided date range
        start_timestamp = convert_to_timestamp(start_date)
        end_timestamp = convert_to_timestamp(end_date) + (24 * 60 * 60 * 1000 - 1)  # End of the day
    else:
        # Use default date range
        end_timestamp = int(now.timestamp() * 1000)
        start_timestamp = int((now - timedelta(days=days)).timestamp() * 1000)
        
        start_date_str = datetime.fromtimestamp(start_timestamp/1000).strftime("%Y-%m-%d")
        end_date_str = now.strftime("%Y-%m-%d")
        
        click.echo(f"Using default date range: {start_date_str} to {end_date_str}")
    
    # Determine output filename
    if not output:
        project_name = PROJECT_MAPPING.get(target_project_id, target_project_id)
        safe_name = project_name.lower().replace(" ", "_")
        start_str = datetime.fromtimestamp(start_timestamp/1000).strftime("%Y%m%d")
        end_str = datetime.fromtimestamp(end_timestamp/1000).strftime("%Y%m%d")
        output = f"insightful_{safe_name}_apps_{start_str}_to_{end_str}.csv"
    
    # Load cache if enabled
    api_cache = {}
    if use_cache:
        api_cache = load_cache_from_disk(cache_file)
    
    # Fetch all employees
    employees = fetch_employee_data()
    
    if not employees:
        click.echo("Error: No employee data found")
        return
    
    # Process employees for the target project
    with click.progressbar(
        length=100,
        label='Processing employees',
        show_eta=True
    ) as bar:
        # Update progress bar to 10% after fetching employees
        bar.update(10)
        
        # Process employees for the target project with batch processing
        project_results = process_employees_for_project(
            employees, 
            target_project_id, 
            start_timestamp, 
            end_timestamp,
            max_workers=threads,
            batch_size=batch_size,
            batch_delay=batch_delay
        )
        
        # Update progress bar to 90%
        bar.update(80)
        
        if not project_results:
            click.echo(f"No data found for any employees in the specified project")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(project_results)
        
        # Save to CSV
        df.to_csv(output, index=False)
        
        # Complete progress bar
        bar.update(10)
    
    # Save cache if enabled
    if use_cache:
        save_cache_to_disk(api_cache, cache_file)
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    project_name = PROJECT_MAPPING.get(target_project_id, target_project_id)
    start_readable = datetime.fromtimestamp(start_timestamp/1000).strftime("%Y-%m-%d")
    end_readable = datetime.fromtimestamp(end_timestamp/1000).strftime("%Y-%m-%d")
    
    click.echo(f"Data export complete! Saved to {output}")
    click.echo(f"Processed data for {len(project_results)} employees in project {project_name}")
    click.echo(f"Date range: {start_readable} to {end_readable}")
    click.echo(f"Execution time: {execution_time:.2f} seconds")

if __name__ == "__main__":
    main()
