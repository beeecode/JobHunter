import os
import re
import requests
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from jinja2 import Template

# Load environment variables from .env file
load_dotenv()

# --- Configuration & Environment Variables ---
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

# --- Constants ---
JSEARCH_API_URL = "https://jsearch.p.rapidapi.com/search"
SEARCH_QUERIES = [
    "Frontend Developer",
    "Full Stack Developer"
]
RESULTS_PER_QUERY = 20  # Number of results to fetch per role
SEARCH_RADIUS = 0       # Not used for worldwide, but good for context
DATE_POSTED = "today"   # Filtering for jobs posted within the last 24 hours
REMOTE_ONLY = True      # Filter for remote-only positions

def search_jobs(query):
    """
    Search for jobs using the JSearch API via RapidAPI.
    """
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    
    params = {
        "query": f"{query} remote",
        "page": "1",
        "num_pages": "1",
        "date_posted": "today",
        "remote_jobs_only": "true"
    }
    
    try:
        response = requests.get(JSEARCH_API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"Error fetching jobs for query '{query}': {e}")
        return []

def filter_jobs(jobs):
    """
    Filter and clean the raw job list based on specific criteria.
    """
    seen_job_ids = set()
    filtered_jobs = []
    
    target_keywords = ["frontend", "front-end", "full stack", "fullstack"]
    exclude_seniority = ["executive", "c-level", "vp", "vice president", "director", "head of"]
    
    for job in jobs:
        job_id = job.get("job_id")
        if not job_id or job_id in seen_job_ids:
            continue
            
        title = job.get("job_title", "").lower()
        description = job.get("job_description", "")
        
        # 1. Job title must contain target keywords
        if not any(kw in title for kw in target_keywords):
            continue
            
        # 2. Exclude executive/high-level seniority
        if any(ex in title for ex in exclude_seniority):
            continue
            
        # 3. Remote check (redundant but safe if API params didn't catch all)
        is_remote = job.get("job_is_remote", False)
        if not is_remote:
            continue
            
        # Extract salary info if available
        min_salary = job.get("job_min_salary")
        max_salary = job.get("job_max_salary")
        currency = job.get("job_salary_currency", "USD")
        
        salary_str = "Not listed"
        if min_salary and max_salary:
            salary_str = f"{currency} {min_salary:,} - {max_salary:,}"
        elif min_salary:
            salary_str = f"{currency} {min_salary:,}+"
            
        # Clean job dictionary
        clean_job = {
            "job_title": job.get("job_title"),
            "company": job.get("employer_name"),
            "location": f"{job.get('job_city', 'Remote')}, {job.get('job_country', '')}".strip(", "),
            "salary": salary_str,
            "direct_link": job.get("job_apply_link"),
            "job_description": description[:500] + "..." if len(description) > 500 else description
        }
        
        filtered_jobs.append(clean_job)
        seen_job_ids.add(job_id)
        
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
    
    # Process keywords for each job before rendering
    for job in jobs:
        keywords_data = extract_keywords(job["job_description"])
        job["top_keywords"] = ", ".join(keywords_data["top_keywords"])
        job["technical_skills"] = ", ".join(keywords_data["technical_skills"])

    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }
            .container { width: 100%; max-width: 900px; margin: 0 auto; background-color: #f9f9f9; }
            .header { background-color: #1a237e; color: #ffffff; padding: 30px; text-align: center; }
            .header h1 { margin: 0; font-size: 28px; }
            .header p { margin: 5px 0 0; opacity: 0.8; }
            .summary { padding: 20px; background-color: #e8eaf6; text-align: center; font-weight: bold; }
            .content { padding: 20px; }
            table { width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            th { background-color: #3949ab; color: #ffffff; text-align: left; padding: 12px; font-size: 14px; }
            td { padding: 12px; border-bottom: 1px solid #eeeeee; font-size: 13px; vertical-align: top; }
            tr:nth-child(even) { background-color: #f5f5f5; }
            tr:hover { background-color: #eeeeee; }
            .apply-btn { display: inline-block; padding: 6px 12px; background-color: #2e7d32; color: #ffffff; text-decoration: none; border-radius: 4px; font-weight: bold; }
            .no-jobs { padding: 40px; text-align: center; color: #666; font-size: 18px; }
            .footer { padding: 20px; text-align: center; font-size: 12px; color: #777; background-color: #f1f1f1; border-top: 1px solid #ddd; }
            .tag { display: inline-block; background: #e0e0e0; padding: 2px 6px; border-radius: 3px; margin: 1px; font-size: 11px; }
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
                    We found {{ count }} matching opportunities for you today!
                {% else %}
                    No matching jobs found today.
                {% endif %}
            </div>

            <div class="content">
                {% if count > 0 %}
                <table>
                    <thead>
                        <tr>
                            <th>Job Title</th>
                            <th>Company</th>
                            <th>Location</th>
                            <th>Salary</th>
                            <th>Keywords</th>
                            <th>Skills</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for job in jobs %}
                        <tr>
                            <td><strong>{{ job.job_title }}</strong></td>
                            <td>{{ job.company }}</td>
                            <td>{{ job.location }}</td>
                            <td>{{ job.salary }}</td>
                            <td>{{ job.top_keywords }}</td>
                            <td>{{ job.technical_skills }}</td>
                            <td><a href="{{ job.direct_link }}" class="apply-btn">Apply</a></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <div class="no-jobs">
                    <p>No matching jobs found today. We'll check again tomorrow!</p>
                </div>
                {% endif %}
            </div>

            <div class="footer">
                <p>Filtered: Remote &middot; Frontend & Full Stack &middot; Last 24h &middot; Entry to Senior</p>
                <p>&copy; 2026 JobHunter Automation</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    template = Template(html_template)
    return template.render(date=today_date, count=job_count, jobs=jobs)

def send_email(html_content):
    """
    Send the generated HTML content via Gmail SMTP.
    """
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = f"Remote Dev Jobs — {today_date}"
    
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

def main():
    """
    Orchestrate the job search and email notification process.
    """
    print(f"Starting job search for {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    
    all_raw_jobs = []
    for query in SEARCH_QUERIES:
        print(f"Searching for: {query}")
        results = search_jobs(query)
        all_raw_jobs.extend(results)
        
    filtered_jobs = filter_jobs(all_raw_jobs)
    print(f"Found {len(filtered_jobs)} unique jobs after filtering.")
    
    html_content = build_email_html(filtered_jobs)
    send_email(html_content)

if __name__ == "__main__":
    main()
