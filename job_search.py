import argparse
import os
import re
import requests
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from dotenv import load_dotenv
from jinja2 import Environment, select_autoescape

# Load environment variables from .env file
load_dotenv()

# --- Configuration & Environment Variables ---
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")  # Optional: for searching Facebook/Instagram
SEARCH_ENGINE_ID = os.environ.get("SEARCH_ENGINE_ID")  # Optional: for Google Custom Search

# --- Constants ---
JSEARCH_API_URL = "https://jsearch.p.rapidapi.com/search"
SEARCH_QUERIES = [
    # Nigeria-specific searches (highest priority). Include Nigeria in the query
    # as well as the country filter because some APIs return blank location fields.
    {"query": "Frontend Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "Full Stack Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "Backend Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "React Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "Node.js Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "Web Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "Python Developer Nigeria", "country": "NG", "priority": "nigeria"},
    # Worldwide searches (fallback, still fully searched after Nigeria).
    {"query": "Frontend Developer remote", "country": None, "priority": "worldwide"},
    {"query": "Full Stack Developer remote", "country": None, "priority": "worldwide"},
    {"query": "Backend Developer remote", "country": None, "priority": "worldwide"},
    {"query": "React Developer remote", "country": None, "priority": "worldwide"},
    {"query": "Node.js Developer remote", "country": None, "priority": "worldwide"},
    {"query": "Web Developer remote", "country": None, "priority": "worldwide"},
    {"query": "Python Developer remote", "country": None, "priority": "worldwide"},
]
NUM_PAGES = 1           # Number of JSearch result pages to fetch per query
DATE_POSTED = "today"   # Filtering for jobs posted within the last 24 hours
REMOTE_ONLY = True      # Filter for remote-only positions
PRIORITY_COUNTRY = "Nigeria"  # Country to prioritize in results
PRIORITY_COUNTRY_CODE = "NG"
PRIORITY_CITIES = ["lagos", "abuja", "kano", "ibadan", "port harcourt", "lekki", "ikeja"]
PRIORITY_TERMS = ["nigeria", "nigerian", "ng", "lagos", "abuja", "naira", "remote nigeria"]
REQUEST_TIMEOUT_SECONDS = 20
REQUEST_RETRIES = 2
PREVIEW_HTML_PATH = "job_alert_preview.html"


def validate_required_env(email_required=True):
    """
    Fail early when required secrets are missing.
    Optional Google Search credentials are checked only by the social search functions.
    """
    required_vars = {"RAPIDAPI_KEY": RAPIDAPI_KEY}
    if email_required:
        required_vars.update({
            "GMAIL_USER": GMAIL_USER,
            "GMAIL_APP_PASSWORD": GMAIL_APP_PASSWORD,
            "RECIPIENT_EMAIL": RECIPIENT_EMAIL,
        })
    missing = [name for name, value in required_vars.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Add them to your .env file or GitHub Actions secrets."
        )


def get_json(url, *, headers=None, params=None):
    """
    Fetch JSON with a timeout and a small retry budget for transient API failures.
    """
    last_error = None
    for attempt in range(1, REQUEST_RETRIES + 2):
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code is not None and status_code < 500:
                raise RuntimeError(format_request_error(exc)) from exc
            if attempt <= REQUEST_RETRIES:
                print(f"Request failed (attempt {attempt}); retrying: {format_request_error(exc)}")

    raise RuntimeError(format_request_error(last_error)) from last_error


def redact_url(url):
    """
    Remove sensitive query values before logging API errors.
    """
    if not url:
        return url

    parts = urlsplit(url)
    redacted_keys = {"key"}
    query = urlencode(
        [
            (name, "<redacted>" if name.lower() in redacted_keys else value)
            for name, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def format_request_error(error):
    """
    Format request errors without exposing API keys.
    """
    if error is None:
        return "Unknown request error"

    response = getattr(error, "response", None)
    if response is not None:
        return f"{response.status_code} {response.reason} for url: {redact_url(response.url)}"

    request = getattr(error, "request", None)
    request_url = redact_url(request.url) if request is not None else None
    if request_url:
        return f"{error.__class__.__name__} for url: {request_url}"

    return str(error)


def normalize_text(value):
    """
    Normalize strings for dedupe and comparisons.
    """
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def build_remote_query(query):
    """
    Ensure a query asks for remote jobs without duplicating the word.
    """
    return query if "remote" in normalize_text(query) else f"{query} remote"


def nigeria_priority_score(job, description):
    """
    Score how strongly a job appears to be Nigeria-focused.
    Higher scores are ranked first in the newsletter.
    """
    if job.get("source") in ["facebook", "instagram"] or job.get("is_priority"):
        return 100

    search_country = normalize_text(job.get("search_country"))
    search_priority = normalize_text(job.get("search_priority"))
    if search_country == PRIORITY_COUNTRY_CODE.lower() or search_priority == "nigeria":
        return 90

    location_values = [
        job.get("job_country"),
        job.get("country"),
        job.get("job_posting_country"),
        job.get("location_country"),
        job.get("job_location"),
        job.get("job_city"),
        job.get("job_state"),
        job.get("city"),
        job.get("location"),
    ]
    location_text = normalize_text(" ".join(str(value or "") for value in location_values))
    description_text = normalize_text(description)

    if PRIORITY_COUNTRY.lower() in location_text or PRIORITY_COUNTRY_CODE.lower() == location_text:
        return 80

    if any(city in location_text for city in PRIORITY_CITIES):
        return 70

    if any(term in description_text for term in PRIORITY_TERMS):
        return 60

    return 0


def search_jobs(query, country=None):
    """
    Search for jobs using the JSearch API via RapidAPI.
    Args:
        query: Job title/role to search for
        country: Optional country code (e.g., 'NG' for Nigeria, None for worldwide)
    """
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    
    params = {
        "query": build_remote_query(query),
        "page": "1",
        "num_pages": str(NUM_PAGES),
        "date_posted": DATE_POSTED,
        "remote_jobs_only": str(REMOTE_ONLY).lower(),
    }
    
    # Add country filter if specified
    if country:
        params["country"] = country
    
    try:
        data = get_json(JSEARCH_API_URL, headers=headers, params=params)
        return data.get("data", [])
    except Exception as e:
        print(f"Error fetching jobs for query '{query}' in country {country}: {e}")
        return []

def search_facebook_jobs(keywords):
    """
    Search for job postings on Facebook pages in Nigeria.
    Uses Google Custom Search to find Facebook job posts.
    
    Args:
        keywords: List of job-related keywords to search for
    
    Returns:
        List of job dictionaries extracted from Facebook posts
    """
    facebook_jobs = []
    
    if not GOOGLE_SEARCH_API_KEY or not SEARCH_ENGINE_ID:
        print("Warning: Google Search API credentials not configured. Skipping Facebook search.")
        print("   To enable: Set GOOGLE_SEARCH_API_KEY and SEARCH_ENGINE_ID in your .env file")
        return facebook_jobs
    
    try:
        for keyword in keywords:
            # Search specifically on Facebook for Nigeria-based job posts
            search_query = f"site:facebook.com {keyword} job nigeria hiring"
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "q": search_query,
                "key": GOOGLE_SEARCH_API_KEY,
                "cx": SEARCH_ENGINE_ID,
                "num": 10  # Get top 10 results per keyword
            }
            
            data = get_json(url, params=params)
            
            # Parse search results
            for item in data.get("items", []):
                job_entry = {
                    "source": "facebook",
                    "job_title": keyword.title(),
                    "company": "N/A",
                    "location": "Nigeria",
                    "country": "Nigeria",
                    "is_priority": True,
                    "salary": "Not listed",
                    "direct_link": item.get("link"),
                    "job_description": item.get("snippet", "")[:500],
                    "snippet": item.get("snippet", "")
                }
                facebook_jobs.append(job_entry)
                
    except Exception as e:
        print(f"Error searching Facebook jobs: {e}")
    
    return facebook_jobs

def search_instagram_hashtags(hashtags):
    """
    Search for job postings on Instagram using hashtag-based scraping.
    Note: Instagram API has restrictions. This function searches via public data.
    
    Args:
        hashtags: List of hashtags to search for job posts
    
    Returns:
        List of job dictionaries extracted from Instagram posts
    """
    instagram_jobs = []
    
    try:
        # Since direct Instagram scraping is restricted, we use a fallback approach
        # with Google search for Instagram job posts
        if not GOOGLE_SEARCH_API_KEY or not SEARCH_ENGINE_ID:
            print("Warning: Google Search API credentials not configured. Skipping Instagram search.")
            return instagram_jobs
        
        for hashtag in hashtags:
            search_query = f"site:instagram.com #{hashtag} developer job nigeria"
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "q": search_query,
                "key": GOOGLE_SEARCH_API_KEY,
                "cx": SEARCH_ENGINE_ID,
                "num": 10
            }
            
            data = get_json(url, params=params)
            
            for item in data.get("items", []):
                job_entry = {
                    "source": "instagram",
                    "job_title": f"Developer - #{hashtag}",
                    "company": "N/A",
                    "location": "Nigeria",
                    "country": "Nigeria",
                    "is_priority": True,
                    "salary": "Not listed",
                    "direct_link": item.get("link"),
                    "job_description": item.get("snippet", "")[:500],
                    "snippet": item.get("snippet", "")
                }
                instagram_jobs.append(job_entry)
                
    except Exception as e:
        print(f"Error searching Instagram hashtags: {e}")
    
    return instagram_jobs

def filter_jobs(jobs):
    """
    Filter and clean the raw job list based on specific criteria.
    Prioritizes jobs from the priority country (Nigeria).
    Handles jobs from multiple sources (JSearch, Facebook, Instagram).
    """
    seen_job_ids = set()
    filtered_jobs = []
    
    target_keywords = ["frontend", "front-end", "full stack", "fullstack", "backend", "back-end", "web developer", "developer", "react", "node.js", "python", "javascript"]
    exclude_seniority = ["executive", "c-level", "vp", "vice president", "director", "head of"]
    
    for job in jobs:
        # Generate unique ID based on title, company, and link
        title = normalize_text(job.get("job_title"))
        company = normalize_text(job.get("company") or job.get("employer_name"))
        link = normalize_text(job.get("direct_link") or job.get("job_apply_link"))
        job_id = f"{title}-{company}-{link}"
        if job_id in seen_job_ids:
            continue
            
        description = job.get("job_description", "")
        
        # 1. Job title must contain target keywords
        if not any(kw in title for kw in target_keywords):
            continue
            
        # 2. Exclude executive/high-level seniority
        if any(ex in title for ex in exclude_seniority):
            continue
            
        # 3. Remote check (for JSearch jobs only; Facebook/Instagram are inherently local)
        if job.get("source") == "jsearch":
            is_remote = job.get("job_is_remote", False)
            if not is_remote:
                continue
        
        # Extract salary info if available
        min_salary = job.get("job_min_salary")
        max_salary = job.get("job_max_salary")
        currency = job.get("job_salary_currency", "USD")
        
        salary_str = job.get("salary", "Not listed")
        if min_salary and max_salary:
            salary_str = f"{currency} {min_salary:,} - {max_salary:,}"
        elif min_salary:
            salary_str = f"{currency} {min_salary:,}+"
        
        # Get country and city information (try multiple possible field names)
        job_country = job.get("job_country") or job.get("country") or job.get("job_posting_country") or job.get("location_country") or "Unknown"
        job_city = job.get("job_city") or job.get("city") or job.get("job_location") or job.get("location") or "Remote"
        priority_score = nigeria_priority_score(job, description)
        is_priority_country = priority_score > 0

        # Clean job dictionary and include raw fields for debugging if needed
        clean_job = {
            "job_title": job.get("job_title"),
            "company": job.get("company", job.get("employer_name", "N/A")),
            "location": f"{job_city}, {job_country}".strip(", "),
            "country": job_country,
            "raw_country_fields": {k: job.get(k) for k in ["job_country", "country", "job_posting_country", "location_country", "job_location", "job_city", "job_state"]},
            "is_priority": is_priority_country,
            "priority_score": priority_score,
            "search_priority": job.get("search_priority", "worldwide"),
            "search_query": job.get("search_query", ""),
            "salary": salary_str,
            "source": job.get("source", "jsearch"),  # Track the source
            "direct_link": job.get("direct_link", job.get("job_apply_link", "#")),
            "job_description": description[:500] + "..." if len(description) > 500 else description
        }
        
        filtered_jobs.append(clean_job)
        seen_job_ids.add(job_id)
    
    # Sort strongest Nigeria matches first, then by source.
    source_priority = {"jsearch": 0, "facebook": 1, "instagram": 2}
    filtered_jobs.sort(key=lambda x: (-x["priority_score"], source_priority.get(x["source"], 3)))
        
    return filtered_jobs

def extract_keywords(job_description):
    """
    Extract top 5 general keywords and top 5 technical skills from a job description.
    """
    description_lower = job_description.lower()
    
    # Predefined list of technical skills to look for
    tech_skills_list = [
        "react", "node.js", "typescript", "javascript", "html", "css", 
        "postgresql", "docker", "aws", "graphql", "next.js", "vue", 
        "python", "git", "redux", "tailwind", "sass", "angular", 
        "flutter", "go", "kubernetes", "terraform", "firebase", 
        "azure", "gcp", "mongodb", "sql", "nosql", "rest api", 
        "ci/cd", "jest", "cypress", "webpack", "babel", "express"
    ]
    
    # Extract technical skills found in description
    found_skills = []
    for skill in tech_skills_list:
        # Simple word boundary check using space or punctuation
        if re.search(rf"\b{re.escape(skill)}\b", description_lower):
            found_skills.append(skill.title() if "." not in skill else skill)
            if len(found_skills) >= 5:
                break
                
    # Extract general keywords (most frequent words > 4 chars, excluding tech skills and common words)
    stop_words = {"this", "that", "with", "from", "your", "their", "will", "would", "about", "could", "should"}
    words = re.findall(r"\b\w{5,}\b", description_lower)
    
    word_freq = {}
    for word in words:
        if word not in stop_words and word not in tech_skills_list:
            word_freq[word] = word_freq.get(word, 0) + 1
            
    # Sort by frequency and take top 5
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    top_keywords = [word[0].capitalize() for word in sorted_words[:5]]
    
    return {
        "top_keywords": top_keywords,
        "technical_skills": found_skills
    }

def build_email_html(jobs):
    """
    Generate a styled HTML newsletter for the job results.
    """
    today_date = datetime.now().strftime("%B %d, %Y")
    job_count = len(jobs)
    nigeria_count = sum(1 for job in jobs if job.get("is_priority"))
    worldwide_count = job_count - nigeria_count
    
    # Process keywords for each job before rendering
    for job in jobs:
        keywords_data = extract_keywords(job["job_description"])
        job["top_keywords"] = ", ".join(keywords_data["top_keywords"])
        job["technical_skills"] = ", ".join(keywords_data["technical_skills"])
        job["match_label"] = "Nigeria Priority" if job.get("is_priority") else "Worldwide"
        job["priority_class"] = "priority-ng" if job.get("is_priority") else "priority-worldwide"
        job["short_description"] = (
            job["job_description"][:220] + "..."
            if len(job["job_description"]) > 220
            else job["job_description"]
        )

    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.5; color: #22302a; margin: 0; padding: 0; background-color: #edf2ef; }
            .container { width: 100%; max-width: 760px; margin: 0 auto; background-color: #f8faf8; }
            .header { background-color: #12382c; color: #ffffff; padding: 28px 30px; }
            .header h1 { margin: 0; font-size: 28px; letter-spacing: 0; }
            .header p { margin: 6px 0 0; color: #cfe1d9; }
            .summary { padding: 18px 20px; background-color: #ffffff; border-bottom: 1px solid #dbe5df; }
            .metric-table { width: 100%; border-collapse: collapse; }
            .metric { padding: 12px; border: 1px solid #dbe5df; background-color: #f5f8f6; }
            .metric-label { margin: 0; color: #63736b; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
            .metric-value { margin: 4px 0 0; color: #12382c; font-size: 22px; font-weight: 700; }
            .content { padding: 18px 20px 8px; }
            .section-title { margin: 0 0 12px; color: #12382c; font-size: 16px; }
            .job-card { background-color: #ffffff; border: 1px solid #dbe5df; border-left: 5px solid #8da199; padding: 16px; margin: 0 0 14px; border-radius: 6px; }
            .priority-ng { border-left-color: #17834f; background-color: #fbfffc; }
            .priority-worldwide { border-left-color: #4f6f8f; }
            .job-title { margin: 0 0 8px; color: #17241f; font-size: 18px; line-height: 1.3; }
            .meta { margin: 0 0 10px; color: #4d5b55; font-size: 13px; }
            .description { margin: 10px 0; color: #31413a; font-size: 13px; }
            .tag { display: inline-block; background: #eef3f0; color: #34443d; padding: 3px 7px; border-radius: 4px; margin: 2px 3px 2px 0; font-size: 11px; }
            .badge { display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; margin: 0 4px 6px 0; }
            .badge-ng { background-color: #dff4e8; color: #12653e; }
            .badge-worldwide { background-color: #e8eef6; color: #254f7a; }
            .source-jsearch { background-color: #e7f1fb; color: #155d9c; }
            .source-facebook { background-color: #e8eaf6; color: #3949ab; }
            .source-instagram { background-color: #fce4ec; color: #a31555; }
            .apply-btn { display: inline-block; padding: 8px 13px; background-color: #17633f; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 13px; }
            .no-jobs { padding: 40px 20px; text-align: center; color: #56645f; font-size: 17px; }
            .footer { padding: 18px 20px; text-align: center; font-size: 12px; color: #68756f; background-color: #eef3f0; border-top: 1px solid #dbe5df; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Daily Remote Dev Jobs</h1>
                <p>{{ date }}</p>
            </div>
            
            <div class="summary">
                {% if count > 0 %}
                    <table class="metric-table" role="presentation">
                        <tr>
                            <td class="metric">
                                <p class="metric-label">Total Matches</p>
                                <p class="metric-value">{{ count }}</p>
                            </td>
                            <td class="metric">
                                <p class="metric-label">Nigeria Priority</p>
                                <p class="metric-value">{{ nigeria_count }}</p>
                            </td>
                            <td class="metric">
                                <p class="metric-label">Worldwide</p>
                                <p class="metric-value">{{ worldwide_count }}</p>
                            </td>
                        </tr>
                    </table>
                {% else %}
                    No matching jobs found today.
                {% endif %}
            </div>

            <div class="content">
                {% if count > 0 %}
                <h2 class="section-title">Top opportunities, Nigeria first</h2>
                {% for job in jobs %}
                <div class="job-card {{ job.priority_class }}">
                    <p>
                        <span class="badge {% if job.is_priority %}badge-ng{% else %}badge-worldwide{% endif %}">{{ job.match_label }}</span>
                        <span class="badge source-{{ job.source }}">{{ job.source | upper }}</span>
                    </p>
                    <h3 class="job-title">{{ job.job_title }}</h3>
                    <p class="meta"><strong>{{ job.company }}</strong> &middot; {{ job.location }} &middot; {{ job.salary }}</p>
                    {% if job.short_description %}
                    <p class="description">{{ job.short_description }}</p>
                    {% endif %}
                    {% if job.technical_skills %}
                    <p><strong>Skills:</strong> <span class="tag">{{ job.technical_skills }}</span></p>
                    {% endif %}
                    {% if job.top_keywords %}
                    <p><strong>Keywords:</strong> <span class="tag">{{ job.top_keywords }}</span></p>
                    {% endif %}
                    <p><a href="{{ job.direct_link }}" class="apply-btn">View job</a></p>
                </div>
                {% endfor %}
                {% else %}
                <div class="no-jobs">
                    <p>No matching jobs found today. We'll check again tomorrow!</p>
                </div>
                {% endif %}
            </div>

            <div class="footer">
                <p>Sources: JSearch API &middot; Facebook Ads &middot; Instagram Hashtags</p>
                <p>Filtered: Remote & Local &middot; Frontend, Full Stack, Backend, React, Node.js, Web & Python</p>
                <p>Nigeria-priority results are ranked first. Worldwide opportunities are included as fallback coverage.</p>
                <p>&copy; 2026 JobHunter Automation</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    template = Environment(autoescape=select_autoescape(["html", "xml"])).from_string(html_template)
    return template.render(
        date=today_date,
        count=job_count,
        nigeria_count=nigeria_count,
        worldwide_count=worldwide_count,
        jobs=jobs,
    )

def send_email(html_content):
    """
    Send the generated HTML content via Gmail SMTP.
    """
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = f"Remote Dev Jobs - {today_date}"
    
    msg.attach(MIMEText(html_content, "html"))
    
    try:
        # Connect to Gmail SMTP server
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # Upgrade connection to secure
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
            
        print(f"Successfully sent job alert email to {RECIPIENT_EMAIL}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise


def save_html_preview(html_content, output_path=PREVIEW_HTML_PATH):
    """
    Write the generated newsletter to disk for local review.
    """
    with open(output_path, "w", encoding="utf-8") as preview_file:
        preview_file.write(html_content)
    print(f"Saved HTML preview to {output_path}")


def parse_args():
    """
    Parse command-line options for local testing.
    """
    parser = argparse.ArgumentParser(description="Search for remote developer jobs and email the results.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the search and save an HTML preview without sending email.",
    )
    parser.add_argument(
        "--preview-path",
        default=PREVIEW_HTML_PATH,
        help=f"Where to save the HTML preview. Defaults to {PREVIEW_HTML_PATH}.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print raw API field diagnostics.",
    )
    return parser.parse_args()


def main(dry_run=False, preview_path=PREVIEW_HTML_PATH, debug=False):
    """
    Orchestrate the job search and email notification process.
    Searches Nigeria-based opportunities first via multiple sources:
    - JSearch API (primary)
    - Facebook Ads
    - Instagram Hashtags
    """
    validate_required_env(email_required=not dry_run)
    print(f"Starting job search for {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    
    all_raw_jobs = []
    
    # 1. Search JSearch API
    print("\nSearching JSearch API...")
    for search_item in SEARCH_QUERIES:
        query = search_item["query"]
        country = search_item.get("country")
        search_priority = search_item.get("priority", "worldwide")
        location_str = f"in {country}" if country else "worldwide"
        print(f"   Searching for: {query} {location_str}")
        results = search_jobs(query, country)
        # Tag results with source
        for job in results:
            job["source"] = "jsearch"
            job["search_country"] = country
            job["search_priority"] = search_priority
            job["search_query"] = query
        all_raw_jobs.extend(results)

    print(f"\nInfo: Collected {len(all_raw_jobs)} raw job entries from JSearch.")
    if debug:
        print("Debug: sample JSearch keys:")
        for idx, sample in enumerate(all_raw_jobs[:3], 1):
            print(f"  Sample {idx}: keys={list(sample.keys())}")
    
    # 2. Search Facebook Jobs
    print("\nSearching Facebook job posts...")
    facebook_keywords = [
        "Full Stack Developer",
        "Frontend Developer",
        "Backend Developer",
        "React Developer"
    ]
    facebook_jobs = search_facebook_jobs(facebook_keywords)
    all_raw_jobs.extend(facebook_jobs)
    print(f"   Found {len(facebook_jobs)} potential matches on Facebook")
    
    # 3. Search Instagram Hashtags
    print("\nSearching Instagram job posts...")
    instagram_hashtags = [
        "hiringnigeria",
        "jobopeningnigeria",
        "techjobnigeria",
        "devjobs",
        "frontendjobs"
    ]
    instagram_jobs = search_instagram_hashtags(instagram_hashtags)
    all_raw_jobs.extend(instagram_jobs)
    print(f"   Found {len(instagram_jobs)} potential matches on Instagram")
    
    # 4. Filter and consolidate
    print("\nFiltering and consolidating results...")
    filtered_jobs = filter_jobs(all_raw_jobs)
    
    # Debug: Show country breakdown
    countries_found = {}
    for job in filtered_jobs:
        country = job.get("country", "Unknown")
        countries_found[country] = countries_found.get(country, 0) + 1
    
    nigeria_count = sum(1 for job in filtered_jobs if job["is_priority"])
    jsearch_count = sum(1 for job in filtered_jobs if job["source"] == "jsearch")
    facebook_count = sum(1 for job in filtered_jobs if job["source"] == "facebook")
    instagram_count = sum(1 for job in filtered_jobs if job["source"] == "instagram")
    strong_nigeria_count = sum(1 for job in filtered_jobs if job["priority_score"] >= 80)
    
    print(f"Found {len(filtered_jobs)} unique jobs after filtering")
    print(f"   - JSearch: {jsearch_count}")
    print(f"   - Facebook: {facebook_count}")
    print(f"   - Instagram: {instagram_count}")
    print(f"   - Nigeria Priority: {nigeria_count}")
    print(f"   - Strong Nigeria Matches: {strong_nigeria_count}")
    print(f"   - Countries represented: {countries_found}")
    
    if debug:
        print("\nDebug: raw country fields for each job:")
        for i, job in enumerate(filtered_jobs, 1):
            print(f" {i}. title={job.get('job_title')[:60]!r} source={job.get('source')} country={job.get('country')}")
            raw = job.get('raw_country_fields') or {}
            if raw:
                print(f"    raw_country_fields: {raw}")
    
    html_content = build_email_html(filtered_jobs)

    if dry_run:
        save_html_preview(html_content, preview_path)
        print("Dry run complete; email was not sent.")
        return
    
    # Try to send email, but don't crash if it fails
    try:
        send_email(html_content)
    except Exception as e:
        print("\nWarning: Email sending failed (but job search was successful)")
        print(f"   Error: {e}")
        save_html_preview(html_content, preview_path)
        print(f"{len(filtered_jobs)} jobs found and ready to be emailed once credentials are fixed.")

if __name__ == "__main__":
    args = parse_args()
    main(dry_run=args.dry_run, preview_path=args.preview_path, debug=args.debug)
