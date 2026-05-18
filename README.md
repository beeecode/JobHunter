# JobHunter: Automated Remote Dev Job Search

An automated tool that searches for remote Frontend, Full Stack, and Backend developer jobs every day across **multiple platforms** (JSearch API, Facebook Ads, Instagram Hashtags) and delivers a beautifully styled HTML newsletter directly to your inbox.

## Features
- **Multi-Platform Search**: Aggregates jobs from JSearch API, Facebook Ads, and Instagram Hashtags.
- **Daily Automated Search**: Runs every day at 10:00 AM UTC via GitHub Actions.
- **Nigeria-Focused Search**: Prioritizes remote opportunities within Nigeria, with global jobs as fallback.
- **Smart Filtering**: Targets Frontend, Full Stack, and Backend roles while excluding executive/C-level positions.
- **Remote + Local**: Searches for both remote opportunities and local Nigeria-based postings on social media.
- **Salary Insights**: Extracts and displays salary information whenever available.
- **AI-Ready Keywords**: Automatically extracts top 5 keywords and technical skills from each job description to help with your resume SEO.
- **Professional Newsletter**: Delivers results in a clean, responsive HTML table with visual indicators for Nigeria-based jobs (`NG`) and source badges (JSearch, Facebook, Instagram).

## Prerequisites
- **Python 3.11+**
- **RapidAPI Account**: To access the JSearch API.
- **Gmail Account**: To send the notification emails.
- **Google Custom Search API** (Optional): For enhanced Facebook/Instagram job searches.

## Setup Instructions

### 1. Get your JSearch API Key
1. Go to [JSearch on RapidAPI](https://rapidapi.com/letscrape-6bR47QEBZ/api/jsearch).
2. Sign up or log in.
3. Subscribe to the "Free" tier (which offers plenty of requests for daily use).
4. Copy your **X-RapidAPI-Key** from the "Endpoints" tab.

### 2. Create a Gmail App Password
For security, this script uses an "App Password" rather than your main Gmail password.
1. Go to your [Google Account Security settings](https://myaccount.google.com/security).
2. Enable **2-Step Verification** if it's not already on.
3. Search for "App Passwords" in the search bar at the top.
4. Create a new app password (select "Other" and name it "JobHunter").
5. Copy the 16-character code provided.
   > [Detailed Guide: How to create App Passwords](https://support.google.com/accounts/answer/185833)

### 3. (Optional) Set Up Google Custom Search for Facebook/Instagram Scraping
To search Facebook Ads and Instagram Hashtags for job postings, enable Google Custom Search:

1. Go to [Google Custom Search Console](https://cse.google.com/cse/).
2. Click **Create** to create a new search engine.
3. In "Sites to search," enter: `facebook.com` and `instagram.com`.
4. Name your search engine "JobHunter Social" and click **Create**.
5. Copy your **Search Engine ID** from the **Setup** section.
6. Go to [Google Cloud Console](https://console.cloud.google.com/).
7. Enable the **Custom Search API**.
8. Create an API key under **Credentials** > **Create Credentials** > **API Key**.
9. Copy your **API Key**.

**Note**: The free tier of Google Custom Search allows 100 free searches per day. For higher limits, consider upgrading to a paid plan.

### 4. Fork and Configure the Repository
1. **Fork** this repository to your own GitHub account.
2. Navigate to your forked repository's **Settings** > **Secrets and variables** > **Actions**.
3. Click **New repository secret** and add the following secrets:
   - `RAPIDAPI_KEY`: Your JSearch API key from Step 1.
   - `GMAIL_USER`: Your Gmail address (e.g., `yourname@gmail.com`).
   - `GMAIL_APP_PASSWORD`: The 16-character code from Step 2.
   - `RECIPIENT_EMAIL`: The email address where you want to receive the alerts.
   - *(Optional)* `GOOGLE_SEARCH_API_KEY`: Your Google Custom Search API key from Step 3.
   - *(Optional)* `SEARCH_ENGINE_ID`: Your Custom Search Engine ID from Step 3.

### 5. Enable GitHub Actions
1. Click on the **Actions** tab in your repository.
2. Click the button that says **"I understand my workflows, go ahead and enable them"**.

### 6. Trigger a Manual Test
1. In the **Actions** tab, select the **"Daily Remote Job Search"** workflow on the left.
2. Click the **Run workflow** dropdown on the right and click the green button.
3. Wait a few minutes and check your inbox!

### Run Locally Without Sending Email
Use dry-run mode to search jobs and generate a local HTML preview without using Gmail:

```bash
python job_search.py --dry-run
```

By default, the preview is written to `job_alert_preview.html`. You can change that path:

```bash
python job_search.py --dry-run --preview-path preview.html
```

For API field diagnostics, add `--debug`:

```bash
python job_search.py --dry-run --debug
```

## Customization

### Change Search Queries or Priority Country
Open `job_search.py` and modify the `SEARCH_QUERIES` list. Currently set to search Nigeria first, then run matching worldwide remote searches as fallback coverage:
```python
SEARCH_QUERIES = [
    # Nigeria-specific searches (highest priority)
    {"query": "Frontend Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "Full Stack Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "Backend Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "React Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "Node.js Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "Web Developer Nigeria", "country": "NG", "priority": "nigeria"},
    {"query": "Python Developer Nigeria", "country": "NG", "priority": "nigeria"},
    # Worldwide searches (fallback, still fully searched after Nigeria)
    {"query": "Frontend Developer remote", "country": None, "priority": "worldwide"},
    {"query": "Full Stack Developer remote", "country": None, "priority": "worldwide"},
    {"query": "Backend Developer remote", "country": None, "priority": "worldwide"},
    {"query": "React Developer remote", "country": None, "priority": "worldwide"},
    {"query": "Node.js Developer remote", "country": None, "priority": "worldwide"},
    {"query": "Web Developer remote", "country": None, "priority": "worldwide"},
    {"query": "Python Developer remote", "country": None, "priority": "worldwide"},
]
```

To change the priority country, modify the `country` parameter. Use country codes like:
- `"NG"` for Nigeria
- `"US"` for United States
- `"GB"` for United Kingdom
- `"CA"` for Canada
- `None` for worldwide

Jobs from Nigeria-targeted searches or Nigeria-related locations/descriptions appear first in the newsletter. Worldwide jobs are searched separately and kept as fallback results after Nigeria-priority matches.

### Customize Facebook & Instagram Search Keywords
In `job_search.py`, modify the `facebook_keywords` and `instagram_hashtags` in the `main()` function:

```python
# Facebook search keywords (expanded for better coverage)
facebook_keywords = [
    "Full Stack Developer",
    "Frontend Developer",
    "Backend Developer",
    "React Developer",
    "Node.js Developer",
    "Web Developer",
    "Python Developer",
    "JavaScript Developer",
    "Developer Nigeria",
    "Tech Jobs Nigeria"
]

# Instagram hashtags to search (Nigeria-focused)
instagram_hashtags = [
    "hiringnigeria",
    "jobopeningnigeria",
    "techjobnigeria",
    "developerjob",
    "remotework",
    "techcareers",
    "devjobs",
    "frontendjobs",
    "backendjobs",
    "nigeriajobs",
    "africanjobs",
    "techjobsng",
    "webdevjobs",
    "reactjobs"
]
```

Add or remove keywords/hashtags based on your preferences. The expanded list provides better coverage of Nigeria-based tech communities and job boards.

### Add Additional Job Roles
Simply add more dictionaries to `SEARCH_QUERIES`:
```python
{"query": "React Developer", "country": "NG"},
{"query": "Python Developer", "country": None}
```

### Change the Notification Time
Open `.github/workflows/daily_job_search.yml` and modify the cron schedule:
```yaml
- cron: '0 14 * * *' # This would run at 2:00 PM UTC
```

## Troubleshooting

- **No Emails Received?**
  - Check your "Spam" or "Promotions" folder.
  - Verify that `GMAIL_APP_PASSWORD` is correct and has no spaces.
  - Check the **Actions** tab in GitHub to see if the script failed with an error message.
- **API Errors?**
  - Ensure you are subscribed to the JSearch API on RapidAPI.
  - Verify that your `RAPIDAPI_KEY` hasn't expired or reached its daily limit.
- **Gmail Authentication Errors?**
  - Ensure 2-Step Verification is enabled on your Google account; otherwise, App Passwords will not work.
- **Facebook/Instagram Search Not Working?**
  - Verify that `GOOGLE_SEARCH_API_KEY` and `SEARCH_ENGINE_ID` are correctly set in your GitHub Actions secrets.
  - Check if you've exceeded the free tier limit of Google Custom Search (100 searches/day).
  - Make sure the Custom Search Engine is configured to search both `facebook.com` and `instagram.com`.

## Testing

Run the unit tests with:

```bash
python -m unittest discover
```
