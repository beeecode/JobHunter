# 🕵️ JobHunter: Automated Remote Dev Job Search

An automated tool that searches for remote Frontend and Full Stack developer jobs every day and delivers a beautifully styled HTML newsletter directly to your inbox.

## ✨ Features
- **Daily Automated Search**: Runs every day at 10:00 AM UTC via GitHub Actions.
- **Nigeria-Focused Search**: Prioritizes remote opportunities within Nigeria, with global jobs as fallback.
- **Smart Filtering**: Targets Frontend and Full Stack roles while excluding executive/C-level positions.
- **Remote Only**: Specifically searches for "Worldwide" and "Remote" opportunities.
- **Salary Insights**: Extracts and displays salary information whenever available.
- **AI-Ready Keywords**: Automatically extracts top 5 keywords and technical skills from each job description to help with your resume SEO.
- **Professional Newsletter**: Delivers results in a clean, responsive HTML table with visual indicators for Nigeria-based jobs (🇳🇬).

## 📋 Prerequisites
- **Python 3.11+**
- **RapidAPI Account**: To access the JSearch API.
- **Gmail Account**: To send the notification emails.

## 🚀 Setup Instructions

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

### 3. Fork and Configure the Repository
1. **Fork** this repository to your own GitHub account.
2. Navigate to your forked repository's **Settings** > **Secrets and variables** > **Actions**.
3. Click **New repository secret** and add the following four secrets:
   - `RAPIDAPI_KEY`: Your JSearch API key from Step 1.
   - `GMAIL_USER`: Your Gmail address (e.g., `yourname@gmail.com`).
   - `GMAIL_APP_PASSWORD`: The 16-character code from Step 2.
   - `RECIPIENT_EMAIL`: The email address where you want to receive the alerts.

### 4. Enable GitHub Actions
1. Click on the **Actions** tab in your repository.
2. Click the button that says **"I understand my workflows, go ahead and enable them"**.

### 5. Trigger a Manual Test
1. In the **Actions** tab, select the **"Daily Remote Job Search"** workflow on the left.
2. Click the **Run workflow** dropdown on the right and click the green button.
3. Wait a few minutes and check your inbox!

## ⚙️ Customization

### Change Search Queries or Priority Country
Open `job_search.py` and modify the `SEARCH_QUERIES` list. Currently set to prioritize Nigeria:
```python
SEARCH_QUERIES = [
    {"query": "Frontend Developer", "country": "NG"},      # Nigeria priority
    {"query": "Full Stack Developer", "country": "NG"},    # Nigeria priority
    {"query": "Frontend Developer", "country": None},        # Global fallback
    {"query": "Full Stack Developer", "country": None}       # Global fallback
]
```

To change the priority country, modify the `country` parameter. Use country codes like:
- `"NG"` for Nigeria
- `"US"` for United States
- `"GB"` for United Kingdom
- `"CA"` for Canada
- `None` for worldwide

Jobs from the priority country will appear first in the newsletter with a 🇳🇬 indicator and highlighted background.

### Add Additional Job Roles
Simply add more dictionaries to `SEARCH_QUERIES`:
```python
{"query": "React Developer", "country": "NG"},
{"query": "Backend Developer", "country": None}
```

### Change the Notification Time
Open `.github/workflows/daily_job_search.yml` and modify the cron schedule:
```yaml
- cron: '0 14 * * *' # This would run at 2:00 PM UTC
```

## 🛠️ Troubleshooting

- **No Emails Received?**
  - Check your "Spam" or "Promotions" folder.
  - Verify that `GMAIL_APP_PASSWORD` is correct and has no spaces.
  - Check the **Actions** tab in GitHub to see if the script failed with an error message.
- **API Errors?**
  - Ensure you are subscribed to the JSearch API on RapidAPI.
  - Verify that your `RAPIDAPI_KEY` hasn't expired or reached its daily limit.
- **Gmail Authentication Errors?**
  - Ensure 2-Step Verification is enabled on your Google account; otherwise, App Passwords will not work.