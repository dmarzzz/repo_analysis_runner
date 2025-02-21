import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json
import re
import hashlib
from collections import defaultdict
import asyncio
from openai import AsyncOpenAI, OpenAIError
from PIL import Image
import io
import logging
import time
import math

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Load environment variables
openai_key = os.getenv('OPENAI_KEY')
github_token = os.getenv('GITHUB_TOKEN')
repos = os.getenv('REPOS')

aclient = AsyncOpenAI(api_key=openai_key)

# Just for debugging, print out the loaded OpenAI Key (optional)
print(f"OpenAI API Key from .env: {openai_key}")

# Set the OpenAI API key for official openai library usage

# Parse the REPOS environment variable
repos = eval(repos)  # Convert string representation of list to an actual list

# Function to generate index.html listing available reports
def generate_index_html(project_summaries):
    # Scan the weekly_report directory
    report_dir = 'weekly_report'
    # If the directory doesn't exist yet, just skip
    if not os.path.exists(report_dir):
        print("No weekly_report directory found. Skipping index generation.")
        return

    projects = os.listdir(report_dir)
    index_content = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Weekly Reports Index</title>
        <link href="https://fonts.googleapis.com/css2?family=VT323&display=swap" rel="stylesheet">
        <style>
            * {
                font-family: 'VT323', monospace !important;
                font-size: 20px;
            }

            body {
                background-color: #ffffff;
                color: #000000;
                background-image: 
                    linear-gradient(90deg, rgba(0, 0, 0, 0.1) 1px, transparent 1px),
                    linear-gradient(0deg, rgba(0, 0, 0, 0.1) 1px, transparent 1px);
                background-size: 20px 20px;
                padding: 20px;
            }

            h1 {
                text-align: center;
                text-shadow: 1px 1px #ccc;
                font-size: 24px;
            }

            ul {
                list-style-type: none;
                padding: 0;
            }

            li {
                margin: 10px 0;
            }

            a {
                text-decoration: none;
                color: #007acc;
            }

            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <h1>Weekly Reports Index</h1>
        <ul>
    '''

    # Iterate over each project and its weeks
    for project in projects:
        project_path = os.path.join(report_dir, project)
        if os.path.isdir(project_path):
            index_content += f'<li><strong>{project}</strong><ul>'
            weeks = os.listdir(project_path)
            for week in weeks:
                week_path = os.path.join(project_path, week)
                if os.path.isdir(week_path):
                    # Convert week folder name to human-readable date range
                    start_date_str, end_date_str = week.split('_')
                    start_date = datetime.strptime(start_date_str, "%Y%m%d")
                    end_date = datetime.strptime(end_date_str, "%Y%m%d")
                    if start_date.year == end_date.year:
                        if start_date.month == end_date.month:
                            date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%d, %Y')}"
                        else:
                            date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
                    else:
                        date_range = f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
                    index_content += f'<li><a href="{week_path}/data.html">{date_range}</a></li>'
            index_content += '</ul></li>'

    # Add a combined summary section
    index_content += '<h2>Combined Project Summary</h2><ul>'
    index_content += ''.join(f'<li>{summary}</li>' for summary in project_summaries)
    index_content += '</ul>'

    index_content += '''
        </ul>
    </body>
    </html>
    '''

    # Save the index.html file
    with open('index.html', 'w') as index_file:
        index_file.write(index_content)

    print('Index page generated as index.html')


# Collect summaries for each project
project_summaries = []

# Loop through each repository tuple
for repo, repo_owner in repos:
    print(f"\n🚀 Starting processing for {repo_owner}/{repo} 🚀")

    # GitHub API base URL
    base_url = f'https://api.github.com/repos/{repo_owner}/{repo}'

    # Headers for GitHub API requests
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    # Function to fetch open PRs
    def fetch_open_prs():
        response = requests.get(f'{base_url}/pulls?state=open', headers=headers)
        return response.json()

    # Function to fetch open issues (excluding PRs)
    def fetch_open_issues():
        response = requests.get(f'{base_url}/issues?state=open', headers=headers)
        issues = response.json()
        # Filter out pull requests from issues
        return [issue for issue in issues if 'pull_request' not in issue]

    # Function to fetch closed PRs in the last week
    def fetch_closed_prs_last_week():
        last_week = (datetime.now() - timedelta(days=7)).isoformat()
        response = requests.get(f'{base_url}/pulls?state=closed&since={last_week}', headers=headers)
        return response.json()

    # Function to fetch closed issues in the last week
    def fetch_closed_issues_last_week():
        last_week = (datetime.now() - timedelta(days=7)).isoformat()
        response = requests.get(f'{base_url}/issues?state=closed&since={last_week}', headers=headers)
        return response.json()

    # Function to extract issue numbers from PR descriptions
    def extract_issues_from_description(description):
        if description is None:
            return []
        # Regex to find issue references like #123
        return re.findall(r'#(\d+)', description)

    # Calculate the start and end date for the analysis
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    # Function to fetch open PRs within the date range
    def fetch_open_prs_within_date_range():
        response = requests.get(f'{base_url}/pulls?state=open&since={start_date.isoformat()}', headers=headers)
        try:
            prs = response.json()
            logging.debug(f"Fetched open PRs: {prs}")
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON for open PRs in {repo_owner}/{repo}")
            return []
        return prs

    # Function to fetch open issues (excluding PRs) within the date range
    def fetch_open_issues_within_date_range():
        response = requests.get(f'{base_url}/issues?state=open&since={start_date.isoformat()}', headers=headers)
        issues = response.json()
        # Filter out pull requests from issues
        return [issue for issue in issues if 'pull_request' not in issue]

    # Function to fetch closed PRs within the date range
    def fetch_closed_prs_within_date_range():
        response = requests.get(f'{base_url}/pulls?state=closed&since={start_date.isoformat()}', headers=headers)
        try:
            prs = response.json()
            logging.debug(f"Fetched closed PRs: {prs}")
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON for closed PRs in {repo_owner}/{repo}")
            return []
        # Filter PRs closed within the date range
        return [
            pr for pr in prs 
            if isinstance(pr, dict) and pr.get('closed_at') 
               and start_date <= datetime.fromisoformat(pr['closed_at'][:-1]) <= end_date
        ]

    # Function to fetch closed issues within the date range
    def fetch_closed_issues_within_date_range():
        response = requests.get(f'{base_url}/issues?state=closed&since={start_date.isoformat()}', headers=headers)
        try:
            issues = response.json()
        except json.JSONDecodeError:
            print(f"Error decoding JSON for closed issues in {repo_owner}/{repo}")
            return []
        # Filter issues closed within the date range
        return [
            issue for issue in issues 
            if isinstance(issue, dict) and issue.get('closed_at') 
               and start_date <= datetime.fromisoformat(issue['closed_at'][:-1]) <= end_date
        ]

    # Function to calculate days open for PRs
    def calculate_days_open(pr):
        logging.debug(f"Calculating days open for PR: {pr}")
        try:
            created_at = datetime.fromisoformat(pr['created_at'][:-1])
            return (datetime.now() - created_at).days
        except Exception as e:
            logging.error(f"Error calculating days open for PR: {pr} - {e}")
            raise

    # Function to check if the response contains an error message
    def is_error_response(response):
        return isinstance(response, dict) and 'message' in response

    # Function to fetch comments for a PR
    def fetch_pr_comments(pr_number):
        response = requests.get(f'{base_url}/issues/{pr_number}/comments', headers=headers)
        return response.json()

    # Function to fetch comments for an issue
    def fetch_issue_comments(issue_number):
        response = requests.get(f'{base_url}/issues/{issue_number}/comments', headers=headers)
        return response.json()

    # Function to calculate time until first response for PRs in hours
    def calculate_time_to_first_response(pr):
        comments = fetch_pr_comments(pr['number'])
        for comment in comments:
            if comment['user']['login'] != pr['user']['login']:
                pr_created_at = datetime.fromisoformat(pr['created_at'][:-1])
                comment_created_at = datetime.fromisoformat(comment['created_at'][:-1])
                return math.ceil((comment_created_at - pr_created_at).total_seconds() / 3600)
        return None

    # Function to calculate time until first response for issues in hours
    def calculate_time_to_first_response_issue(issue):
        comments = fetch_issue_comments(issue['number'])
        for comment in comments:
            if comment['user']['login'] != issue['user']['login']:
                issue_created_at = datetime.fromisoformat(issue['created_at'][:-1])
                comment_created_at = datetime.fromisoformat(comment['created_at'][:-1])
                return math.ceil((comment_created_at - issue_created_at).total_seconds() / 3600)
        return None

    # Function to calculate time to close in hours
    def calculate_issue_to_pr_time(pr, issues):
        related_issues = extract_issues_from_description(pr.get('body', ''))
        if not related_issues:
            # Calculate time to close based on PR's own created_at and closed_at fields
            pr_created_at = datetime.fromisoformat(pr['created_at'][:-1])
            pr_closed_at = datetime.fromisoformat(pr['closed_at'][:-1])
            logging.debug(f"PR {pr['number']} created at: {pr_created_at}, closed at: {pr_closed_at}")
            return math.ceil((pr_closed_at - pr_created_at).total_seconds() / 3600)
        times = []
        for issue_number in related_issues:
            issue = next((issue for issue in issues if str(issue['number']) == issue_number), None)
            if issue:
                issue_created_at = datetime.fromisoformat(issue['created_at'][:-1])
                pr_closed_at = datetime.fromisoformat(pr['closed_at'][:-1])
                times.append(math.ceil((pr_closed_at - issue_created_at).total_seconds() / 3600))
        return min(times) if times else 0

    # Fetch data
    open_prs = fetch_open_prs_within_date_range()
    if is_error_response(open_prs):
        logging.error(f"Error fetching open PRs for {repo_owner}/{repo}: {open_prs['message']}")
        open_prs = []

    open_issues = fetch_open_issues_within_date_range()
    if is_error_response(open_issues):
        logging.error(f"Error fetching open issues for {repo_owner}/{repo}: {open_issues['message']}")
        open_issues = []

    closed_prs = fetch_closed_prs_within_date_range()
    if is_error_response(closed_prs):
        logging.error(f"Error fetching closed PRs for {repo_owner}/{repo}: {closed_prs['message']}")
        closed_prs = []

    closed_issues = fetch_closed_issues_within_date_range()
    if is_error_response(closed_issues):
        logging.error(f"Error fetching closed issues for {repo_owner}/{repo}: {closed_issues['message']}")
        closed_issues = []

    # Add days open to each open PR
    for pr in open_prs:
        pr['days_open'] = calculate_days_open(pr)

    # Add time to first response to each open PR
    for pr in open_prs:
        pr['time_to_first_response'] = calculate_time_to_first_response(pr)

    # Add time to first response to each open issue
    for issue in open_issues:
        issue['time_to_first_response'] = calculate_time_to_first_response_issue(issue)

    # Add time to first response to each closed PR
    for pr in closed_prs:
        pr['time_to_first_response'] = calculate_time_to_first_response(pr)

    # Add time to first response to each closed issue
    for issue in closed_issues:
        issue['time_to_first_response'] = calculate_time_to_first_response_issue(issue)

    # Create a subfolder for the repository and week's date
    repo_folder = f'weekly_report/{repo}'
    week_folder = f'{repo_folder}/{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}'
    os.makedirs(week_folder, exist_ok=True)

    # Calculate aggregate statistics
    aggregated_stats = defaultdict(lambda: {
        'prs_opened': 0,
        'prs_closed': 0,
        'issues_opened': 0,
        'issues_closed': 0,
        'contributors': set()
    })

    # Aggregate all contributors into a single set for the entire period
    all_contributors = set()

    # Process opened PRs
    for pr in open_prs:
        date = pr['created_at'][:10]
        aggregated_stats[date]['prs_opened'] += 1
        aggregated_stats[date]['contributors'].add(pr['user']['login'])
        all_contributors.add(pr['user']['login'])

    # Process closed PRs
    for pr in closed_prs:
        date = pr['closed_at'][:10]
        aggregated_stats[date]['prs_closed'] += 1
        aggregated_stats[date]['contributors'].add(pr['user']['login'])
        all_contributors.add(pr['user']['login'])

    # Process opened issues
    for issue in open_issues:
        date = issue['created_at'][:10]
        aggregated_stats[date]['issues_opened'] += 1

    # Process closed issues
    for issue in closed_issues:
        date = issue['closed_at'][:10]
        aggregated_stats[date]['issues_closed'] += 1

    # Convert contributors set to count
    for date, stats in aggregated_stats.items():
        stats['contributors'] = len(stats['contributors'])

    # Use the unique count of all contributors for the overall stats
    overall_contributors_count = len(all_contributors)

    # Function to generate a descriptive summary using async openai call
    async def generate_descriptive_summary(closed_prs, open_issues, repo_owner, repo):
        # Collect detailed PR and issue data
        pr_details = [
            f"PR #[{pr['number']}](https://github.com/{repo_owner}/{repo}/pull/{pr['number']}): {pr['title']} - {pr.get('body', 'No description')}"
            for pr in closed_prs
        ]
        issue_details = [
            f"Issue #{issue['number']}: {issue['title']} - {issue.get('body', 'No description')}"
            for issue in open_issues
        ]
        
        # Update the prompt to include detailed PR and issue data
        prompt = f"""
        Generate three concise bullet points capturing the most important technical updates, merged PRs, opened issues, or discussions from the past week:
        
        Closed PRs:
        {chr(10).join(pr_details)}
        
        Open Issues:
        {chr(10).join(issue_details)}
        
        """
        
        try:
            response = await aclient.chat.completions.create(model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            n=1,
            stop=None,
            temperature=0.5)
            # Filter out empty bullet points and ensure only three are returned
            return [bullet for bullet in response.choices[0].message.content.strip().split('\n') if bullet][:3]
        except OpenAIError as e:
            print(f"Error generating summary: {e}")
            return []

    # Generate a descriptive summary
    summary = asyncio.run(generate_descriptive_summary(closed_prs, open_issues, repo_owner, repo))

    # Modify the overall statistics bullet point
    overall_stats = (
        f"Overall: {len(closed_prs)} PRs closed, "
        f"{overall_contributors_count} contributors."
    )

    # Check if the summary is empty and add a bullet point if necessary
    if not summary:
        summary.append("Summary Not Available")

    # Append the overall statistics to the summary
    summary.append(overall_stats)

    # Function to extract URLs from text
    def extract_urls(text):
        if text is None:
            return []
        # Regex to find URLs
        return re.findall(r'https?://\S+', text)

    # Collect URLs from PRs and issues
    def collect_spec_links(prs, issues):
        spec_links = set()
        for pr in prs:
            spec_links.update(extract_urls(pr.get('body', '')))
        for issue in issues:
            spec_links.update(extract_urls(issue.get('body', '')))
        return list(spec_links)

    # Collect spec links for the week
    spec_links = collect_spec_links(closed_prs, closed_issues)

    # Store the spec links in the JSON object
    output_data = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'opened_prs': open_prs,
        'opened_issues': open_issues,
        'closed_prs': closed_prs,
        'closed_issues': closed_issues,
        'aggregated_stats': aggregated_stats,
        'wartime_milady_ceo_summary': summary,
        'spec_links': spec_links
    }

    # Save data to JSON file in the week's folder
    output_filename = f'{week_folder}/data.json'
    with open(output_filename, 'w') as json_file:
        json.dump(output_data, json_file, indent=4)

    print(f'Data saved to {output_filename}')

    # Append the summary to the project summaries list
    project_summaries.append(f"<strong>{repo_owner}/{repo}</strong>: " + ' '.join(summary))

    # Function to generate a unique color based on a username
    def generate_color(username):
        hash_object = hashlib.md5(username.encode())
        color = '#' + hash_object.hexdigest()[:6]
        return color

    # Function to calculate the average color of an image
    def calculate_average_color(image_url):
        response = requests.get(image_url)
        image = Image.open(io.BytesIO(response.content))
        image = image.convert('RGB')
        pixels = list(image.getdata())
        num_pixels = len(pixels)
        avg_color = tuple(sum(x) // num_pixels for x in zip(*pixels))
        return '#{:02x}{:02x}{:02x}'.format(*avg_color)

    # Fetch organization logo
    org_logo_url = f'https://github.com/{repo_owner}.png'

    # Generate a color for the glow based on the organization logo
    glow_color = calculate_average_color(org_logo_url)

    # Generate HTML content with additional data
    def generate_html(data):
        start_date_local = datetime.fromisoformat(data['start_date'])
        end_date_local = datetime.fromisoformat(data['end_date'])
        # Format dates
        if start_date_local.year == end_date_local.year:
            if start_date_local.month == end_date_local.month:
                date_range = f"{start_date_local.strftime('%b %d')} - {end_date_local.strftime('%d, %Y')}"
            else:
                date_range = f"{start_date_local.strftime('%b %d')} - {end_date_local.strftime('%b %d, %Y')}"
        else:
            date_range = f"{start_date_local.strftime('%b %d, %Y')} - {end_date_local.strftime('%b %d, %Y')}"

        # Prepare data for graph
        dates = sorted(data['aggregated_stats'].keys())
        prs_closed = [data['aggregated_stats'][date]['prs_closed'] for date in dates]
        issues_closed = [data['aggregated_stats'][date]['issues_closed'] for date in dates]
        contributors = [data['aggregated_stats'][date]['contributors'] for date in dates]

        # Breadcrumb navigation
        breadcrumb = f"<a href='../../../index.html'>home</a> / <a href='../index.html'>{repo}</a> / {start_date_local.strftime('%Y%m%d')}_{end_date_local.strftime('%Y%m%d')}"

        html_content = f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title style="text-align: center;">{repo_owner}/{repo} - Wartime Milady CEO Weekly Report: {date_range}</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=VT323&display=swap" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                * {{
                    font-family: 'VT323', monospace !important;
                    font-size: 20px;
                }}

                body {{
                    background-color: #ffffff;
                    color: #000000;
                    background-image: 
                        linear-gradient(90deg, rgba(0, 0, 0, 0.1) 1px, transparent 1px),
                        linear-gradient(0deg, rgba(0, 0, 0, 0.1) 1px, transparent 1px);
                    background-size: 20px 20px;
                    padding: 20px;
                    max-width: 1200px; /* Allow wider text */
                    margin: auto;
                }}

                h1, h2, h3 {{
                    text-shadow: 1px 1px #ccc;
                    position: relative;
                    font-size: 24px;
                }}

                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                    background-color: #f9f9f9;
                }}

                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                    font-size: 18px;
                }}

                th {{
                    background-color: #e0e0e0;
                }}

                tr:nth-child(even) {{
                    background-color: #ffffff;
                }}

                tr:nth-child(odd) {{
                    background-color: #f2f2f2;
                }}

                a {{
                    color: #0000ee;
                    text-decoration: none;
                }}

                a:hover {{
                    text-decoration: underline;
                }}

                .summary-container {{
                    max-width: 800px;
                    margin: 0 auto;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div style="text-align: left; margin-bottom: 20px;">{breadcrumb}</div>
            <h1 style="text-align: center;">
                Wartime Milady CEO Weekly Report: {date_range}
            </h1>
            <h2 style="text-align: center;">
                <img src="{org_logo_url}" alt="{repo_owner} logo" style="width:50px;height:50px;vertical-align:middle;margin-right:10px;">
                <a href="https://github.com/{repo_owner}/{repo}" target="_blank" style="color: inherit; text-decoration: none;">
                    {repo_owner}/{repo}
                </a>
                <img src="{org_logo_url}" alt="{repo_owner} logo" style="width:50px;height:50px;vertical-align:middle;margin-left:10px;">
            </h2>
            <div style="display: flex; justify-content: center; align-items: flex-start;">
                <canvas id="statsChart" width="800" height="400" style="background-color: #ffffff; display: block; margin: 0 auto; box-shadow: 0 0 20px {glow_color}, 0 0 30px {glow_color}, 0 0 40px {glow_color};"></canvas>
            </div>
            <div class="summary-container">
                <h3>Wartime Milady CEO Summary</h3>
                <ul>
                    {''.join(f'<li>{line}</li>' for line in data['wartime_milady_ceo_summary'])}
                </ul>
            </div>
            <script>
                const ctx = document.getElementById('statsChart').getContext('2d');
                const statsChart = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: {dates},
                        datasets: [
                            {{
                                label: 'PRs Closed',
                                data: {prs_closed},
                                borderColor: 'rgba(255, 99, 132, 1)',
                                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                                borderWidth: 1
                            }},
                            {{
                                label: 'Issues Closed',
                                data: {issues_closed},
                                borderColor: 'rgba(255, 206, 86, 1)',
                                backgroundColor: 'rgba(255, 206, 86, 0.2)',
                                borderWidth: 1
                            }},
                            {{
                                label: 'Contributors',
                                data: {contributors},
                                borderColor: 'rgba(153, 102, 255, 1)',
                                backgroundColor: 'rgba(153, 102, 255, 0.2)',
                                borderWidth: 1
                            }}
                        ]
                    }},
                    options: {{
                        scales: {{
                            y: {{
                                beginAtZero: true
                            }}
                        }}
                    }}
                }});
            </script>
            <h2>✧ Closed Pull Requests ✧</h2>
            <table>
                <tr><th>Date</th><th>Title</th><th>Creator</th><th>Created At</th><th>Closed At</th><th>Last Updated</th><th>Related Issues</th><th>Time to Close (hours)</th><th>Time to First Response (hours)</th><th>Status</th></tr>
                ''' + ''.join(
                    f'<tr>'
                    f'<td>{datetime.fromisoformat(pr["created_at"][:-1]).strftime("%b %d")}</td>'
                    f'<td><a href="{pr["html_url"]}" target="_blank">{pr["title"]}</a></td>'
                    f'<td><img src="{pr["user"]["avatar_url"]}" alt="{pr["user"]["login"]} avatar" '
                    f'style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;">'
                    f'<a href="https://github.com/{pr["user"]["login"]}" '
                    f'style="color: {generate_color(pr["user"]["login"])};" target="_blank">'
                    f'{pr["user"]["login"]}</a></td>'
                    f'<td>{datetime.fromisoformat(pr["created_at"][:-1]).strftime("%H:%M")}</td>'
                    f'<td>{datetime.fromisoformat(pr["closed_at"][:-1]).strftime("%H:%M")}</td>'
                    f'<td>{datetime.fromisoformat(pr["updated_at"][:-1]).strftime("%H:%M")}</td>'
                    f'<td>' + ', '.join(
                        f'<a href="https://github.com/{repo_owner}/{repo}/issues/{issue}">#{issue}</a>'
                        for issue in extract_issues_from_description(pr.get("body", ""))
                    ) + f'</td>'
                    f'<td>{calculate_issue_to_pr_time(pr, closed_issues)}</td>'
                    f'<td>{pr.get("time_to_first_response", "None")}</td>'
                    f'<td>{"✅" if pr.get("merged_at") else "❌"}</td></tr>'
                    for pr in data['closed_prs']
                ) + '''
            </table>
            <h2>✧ Closed Issues ✧</h2>
            <table>
                <tr><th>Date</th><th>Title</th><th>Creator</th><th>Closed At</th><th>Last Updated</th><th>Time to First Response (hours)</th></tr>
                ''' + ''.join(
                    f'<tr>'
                    f'<td>{datetime.fromisoformat(issue["created_at"][:-1]).strftime("%b %d")}</td>'
                    f'<td><a href="{issue["html_url"]}" target="_blank">{issue["title"]}</a></td>'
                    f'<td><img src="{issue["user"]["avatar_url"]}" alt="{issue["user"]["login"]} avatar" '
                    f'style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;">'
                    f'<a href="https://github.com/{issue["user"]["login"]}" '
                    f'style="color: {generate_color(issue["user"]["login"])};" target="_blank">'
                    f'{issue["user"]["login"]}</a></td>'
                    f'<td>{datetime.fromisoformat(issue["closed_at"][:-1]).strftime("%H:%M")}</td>'
                    f'<td>{datetime.fromisoformat(issue["updated_at"][:-1]).strftime("%H:%M")}</td>'
                    f'<td>{issue.get("time_to_first_response", "None")}</td></tr>'
                    for issue in data['closed_issues']
                ) + '''
            </table>
            <h2>✧ Open Pull Requests ✧</h2>
            <table>
                <tr><th>Date</th><th>Title</th><th>Creator</th><th>Created At</th><th>Days Open</th></tr>
                ''' + ''.join(
                    f'<tr>'
                    f'<td>{datetime.fromisoformat(pr["created_at"][:-1]).strftime("%b %d")}</td>'
                    f'<td><a href="{pr["html_url"]}" target="_blank">{pr["title"]}</a></td>'
                    f'<td><img src="{pr["user"]["avatar_url"]}" alt="{pr["user"]["login"]} avatar" '
                    f'style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;">'
                    f'<a href="https://github.com/{pr["user"]["login"]}" '
                    f'style="color: {generate_color(pr["user"]["login"])};" target="_blank">'
                    f'{pr["user"]["login"]}</a></td>'
                    f'<td>{datetime.fromisoformat(pr["created_at"][:-1]).strftime("%H:%M")}</td>'
                    f'<td>{pr["days_open"]}</td></tr>'
                    for pr in data['opened_prs']
                ) + '''
            </table>
            <h2>✧ Associated Specifications ✧</h2><ul>
            ''' + ''.join(f'<li><a href="{link}" target="_blank">{link}</a></li>' for link in data['spec_links']) + '''
            </ul>
        </body>
        </html>
        '''
        print("CSS block is being processed correctly.")
        return html_content

    # Generate HTML content
    html_content = generate_html(output_data)

    # Save HTML content to a file in the week's folder
    html_filename = f'{week_folder}/data.html'
    with open(html_filename, 'w') as html_file:
        html_file.write(html_content)

    print(f'HTML page saved to {html_filename}')

    print(f"🎉 Finished processing for {repo_owner}/{repo} 🎉\n")
    
    # Add a delay to reduce the likelihood of hitting the rate limit
    time.sleep(5)  # Sleep for 5 seconds between each repo

# Function to generate an ecosystem-level summary
async def generate_ecosystem_summary(project_summaries):
    # Combine all project summaries into a single prompt
    combined_summaries = '\n'.join(project_summaries)
    prompt = f"""
    Please Summarize this context:

    [ Paste the content you want to summarize]

    {combined_summaries}

    Write in simple language

    Summarize Format: Bullet points

    (You can adjust the format to your preferred style)

    Before rephrasing please go through the guidelines below:

    Tone:

    Primary Tone - Helpful and Informative

    Secondary Tone - Trustworthy and Approachable

    (Note: Please adjust the tone relevant to the brand identity)

    Perplexity

    Burstiness: Ensure heterogeneous paragraphs. Ensure heterogeneous sentence lengths. And stick to primarily short, straightforward sentences

    Unfluffing: Do not include any fluff when producing content. Each sentence should provide value to the overall goal of the content piece. Strictly follow this guideline

    Target Audience:

    Developers who need to keep up with multiple repositories and want concise, technical updates.

    By providing as much context as possible about the article you want to be summarized, such as the target audience or key points, through a well-structured template, you are bound to get a good-quality generated summary.
    """
    try:
        response = await aclient.chat.completions.create(model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150,
        n=1,
        stop=None,
        temperature=0.5)
        return response.choices[0].message.content.strip().split('\n')
    except OpenAIError as e:
        print(f"Error generating ecosystem summary: {e}")
        return []

# After processing all repos, generate the ecosystem-level summary
ecosystem_summary = asyncio.run(generate_ecosystem_summary(project_summaries))

# Generate the index page with the ecosystem-level summary
generate_index_html(ecosystem_summary)