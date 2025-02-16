import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json
import re
import hashlib

# Load environment variables from .env file
load_dotenv()

# Load environment variables
openai_key = os.getenv('OPENAI_KEY')
github_token = os.getenv('GITHUB_TOKEN')
repo = os.getenv('REPO')
repo_owner = os.getenv('REPO_OWNER')

# # Debug print to verify token
# print('GitHub Token:', github_token)

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
    # Regex to find issue numbers, e.g., #123
    return re.findall(r'#(\d+)', description)

# Fetch data
open_prs = fetch_open_prs()
open_issues = fetch_open_issues()
closed_prs_last_week = fetch_closed_prs_last_week()
closed_issues_last_week = fetch_closed_issues_last_week()

# Print results
# print('Open PRs:', open_prs)
# print('Open Issues:', open_issues)
# print('Closed PRs in the last week:', closed_prs_last_week)
# print('Closed Issues in the last week:', closed_issues_last_week)

# Save data to JSON file
data = {
    'open_prs': open_prs,
    'open_issues': open_issues,
    'closed_prs_last_week': closed_prs_last_week,
    'closed_issues_last_week': closed_issues_last_week
}

with open('github_data.json', 'w') as json_file:
    json.dump(data, json_file, indent=4)

print('Data saved to github_data.json')

# Function to generate a unique color based on a username
def generate_color(username):
    hash_object = hashlib.md5(username.encode())
    color = '#' + hash_object.hexdigest()[:6]
    return color

def generate_html(data):
    html_content = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>GitHub Data</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
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
            }

            h1, h2, h3 {
                text-shadow: 1px 1px #ccc;
                position: relative;
                font-size: 24px;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
                background-color: #f9f9f9;
            }

            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
                font-size: 18px;
            }

            th {
                background-color: #e0e0e0;
            }

            tr:nth-child(even) {
                background-color: #ffffff;
            }

            tr:nth-child(odd) {
                background-color: #f2f2f2;
            }

            a {
                color: #0000ee;
                text-decoration: none;
            }

            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <h1>✧ GitHub Data ✧</h1>
        <h2>✧ Open Pull Requests ✧</h2>
        <table>
            <tr><th>ID</th><th>Title</th><th>Creator</th><th>Created At</th><th>Related Issues</th></tr>
            ''' + ''.join(f'<tr><td>{pr["id"]}</td><td><a href="{pr["html_url"]}" target="_blank">{pr["title"]}</a></td><td><img src="{pr["user"]["avatar_url"]}" alt="{pr["user"]["login"]} avatar" style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;"><a href="https://github.com/{pr["user"]["login"]}" style="color: {generate_color(pr["user"]["login"])};" target="_blank">{pr["user"]["login"]}</a></td><td>{pr["created_at"]}</td><td>' + ', '.join(f'<a href="https://github.com/{repo_owner}/{repo}/issues/{issue}">#{issue}</a>' for issue in extract_issues_from_description(pr.get("body", ""))) + '</td></tr>' for pr in data['open_prs']) + '''
        </table>
        <h2>✧ Open Issues ✧</h2>
        <table>
            <tr><th>ID</th><th>Title</th><th>Creator</th><th>Created At</th></tr>
            ''' + ''.join(f'<tr><td>{issue["id"]}</td><td><a href="{issue["html_url"]}" target="_blank">{issue["title"]}</a></td><td><img src="{issue["user"]["avatar_url"]}" alt="{issue["user"]["login"]} avatar" style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;"><a href="https://github.com/{issue["user"]["login"]}" style="color: {generate_color(issue["user"]["login"])};" target="_blank">{issue["user"]["login"]}</a></td><td>{issue["created_at"]}</td></tr>' for issue in data['open_issues']) + '''
        </table>
        <h2>✧ Closed Pull Requests Last Week ✧</h2>
        <table>
            <tr><th>ID</th><th>Title</th><th>Creator</th><th>Closed At</th><th>Related Issues</th></tr>
            ''' + ''.join(f'<tr><td>{pr["id"]}</td><td><a href="{pr["html_url"]}" target="_blank">{pr["title"]}</a></td><td><img src="{pr["user"]["avatar_url"]}" alt="{pr["user"]["login"]} avatar" style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;"><a href="https://github.com/{pr["user"]["login"]}" style="color: {generate_color(pr["user"]["login"])};" target="_blank">{pr["user"]["login"]}</a></td><td>{pr["closed_at"]}</td><td>' + ', '.join(f'<a href="https://github.com/{repo_owner}/{repo}/issues/{issue}">#{issue}</a>' for issue in extract_issues_from_description(pr.get("body", ""))) + '</td></tr>' for pr in data['closed_prs_last_week']) + '''
        </table>
        <h2>✧ Closed Issues Last Week ✧</h2>
        <table>
            <tr><th>ID</th><th>Title</th><th>Creator</th><th>Closed At</th></tr>
            ''' + ''.join(f'<tr><td>{issue["id"]}</td><td><a href="{issue["html_url"]}" target="_blank">{issue["title"]}</a></td><td><img src="{issue["user"]["avatar_url"]}" alt="{issue["user"]["login"]} avatar" style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;"><a href="https://github.com/{issue["user"]["login"]}" style="color: {generate_color(issue["user"]["login"])};" target="_blank">{issue["user"]["login"]}</a></td><td>{issue["closed_at"]}</td></tr>' for issue in data['closed_issues_last_week']) + '''
        </table>
    </body>
    </html>
    '''
    return html_content

# Generate HTML content
html_content = generate_html(data)

# Save HTML content to a file
with open('github_data.html', 'w') as html_file:
    html_file.write(html_content)

print('HTML page saved to github_data.html') 