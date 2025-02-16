import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json
import re
import hashlib
from collections import defaultdict
import asyncio
import openai  # Use the official openai library

# Load environment variables from .env file
load_dotenv()

# Load environment variables
openai_key = os.getenv('OPENAI_KEY')
github_token = os.getenv('GITHUB_TOKEN')
repos = os.getenv('REPOS')

# Set the OpenAI API key for official openai library usage
openai.api_key = openai_key

# Parse the REPOS environment variable
repos = eval(repos)  # Convert string representation of list to an actual list

# Function to generate index.html listing available reports
def generate_index_html():
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

    index_content += '''
        </ul>
    </body>
    </html>
    '''

    # Save the index.html file
    with open('index.html', 'w') as index_file:
        index_file.write(index_content)

    print('Index page generated as index.html')


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
        return response.json()

    # Function to fetch open issues (excluding PRs) within the date range
    def fetch_open_issues_within_date_range():
        response = requests.get(f'{base_url}/issues?state=open&since={start_date.isoformat()}', headers=headers)
        issues = response.json()
        # Filter out pull requests from issues
        return [issue for issue in issues if 'pull_request' not in issue]

    # Function to fetch closed PRs within the date range
    def fetch_closed_prs_within_date_range():
        response = requests.get(f'{base_url}/pulls?state=closed&since={start_date.isoformat()}', headers=headers)
        prs = response.json()
        # Filter PRs closed within the date range
        return [
            pr for pr in prs 
            if pr.get('closed_at') 
               and start_date <= datetime.fromisoformat(pr['closed_at'][:-1]) <= end_date
        ]

    # Function to fetch closed issues within the date range
    def fetch_closed_issues_within_date_range():
        response = requests.get(f'{base_url}/issues?state=closed&since={start_date.isoformat()}', headers=headers)
        issues = response.json()
        # Filter issues closed within the date range
        return [
            issue for issue in issues 
            if issue.get('closed_at') 
               and start_date <= datetime.fromisoformat(issue['closed_at'][:-1]) <= end_date
        ]

    # Function to calculate days open for PRs
    def calculate_days_open(pr):
        created_at = datetime.fromisoformat(pr['created_at'][:-1])
        return (datetime.now() - created_at).days

    # Fetch data
    open_prs = fetch_open_prs_within_date_range()
    open_issues = fetch_open_issues_within_date_range()
    closed_prs = fetch_closed_prs_within_date_range()
    closed_issues = fetch_closed_issues_within_date_range()

    # Add days open to each open PR
    for pr in open_prs:
        pr['days_open'] = calculate_days_open(pr)

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
    async def generate_descriptive_summary(open_prs, closed_prs, open_issues, closed_issues):
        prompt = f"""
        Based on the following data, generate a three-bullet-point summary of the key changes and activities:
        Open PRs: {len(open_prs)}
        Closed PRs: {len(closed_prs)}
        Open Issues: {len(open_issues)}
        Closed Issues: {len(closed_issues)}
        """
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                n=1,
                stop=None,
                temperature=0.5
            )
            return response.choices[0].message['content'].strip().split('\n')
        except openai.error.OpenAIError as e:
            print(f"Error generating summary: {e}")
            return []

    # Generate a descriptive summary
    summary = asyncio.run(generate_descriptive_summary(open_prs, closed_prs, open_issues, closed_issues))

    # Modify the overall statistics bullet point
    overall_stats = (
        f"Overall: {len(open_prs)} PRs opened, {len(closed_prs)} PRs closed, "
        f"{len(open_issues)} issues opened, {len(closed_issues)} issues closed, "
        f"{overall_contributors_count} contributors."
    )

    # Check if the summary is empty and add a bullet point if necessary
    if not summary:
        summary.append("Summary Not Available")

    # Append the overall statistics to the summary
    summary.append(overall_stats)

    # Save data to JSON file in the week's folder
    output_data = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'opened_prs': open_prs,
        'opened_issues': open_issues,
        'closed_prs': closed_prs,
        'closed_issues': closed_issues,
        'aggregated_stats': aggregated_stats,
        'wartime_milady_ceo_summary': summary
    }

    output_filename = f'{week_folder}/data.json'
    with open(output_filename, 'w') as json_file:
        json.dump(output_data, json_file, indent=4)

    print(f'Data saved to {output_filename}')

    # Function to generate a unique color based on a username
    def generate_color(username):
        hash_object = hashlib.md5(username.encode())
        color = '#' + hash_object.hexdigest()[:6]
        return color

    # Calculate time between issue creation and PR closure
    def calculate_issue_to_pr_time(pr, issues):
        related_issues = extract_issues_from_description(pr.get('body', ''))
        if not related_issues:
            return None
        times = []
        for issue_number in related_issues:
            issue = next((issue for issue in issues if str(issue['number']) == issue_number), None)
            if issue:
                issue_created_at = datetime.fromisoformat(issue['created_at'][:-1])
                pr_closed_at = datetime.fromisoformat(pr['closed_at'][:-1])
                times.append((pr_closed_at - issue_created_at).days)
        return min(times) if times else None

    # Fetch organization logo
    org_logo_url = f'https://github.com/{repo_owner}.png'

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
        prs_opened = [data['aggregated_stats'][date]['prs_opened'] for date in dates]
        prs_closed = [data['aggregated_stats'][date]['prs_closed'] for date in dates]
        issues_opened = [data['aggregated_stats'][date]['issues_opened'] for date in dates]
        issues_closed = [data['aggregated_stats'][date]['issues_closed'] for date in dates]
        contributors = [data['aggregated_stats'][date]['contributors'] for date in dates]

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
                    max-width: 300px;
                    margin: 0 auto;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
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
                <canvas id="statsChart" width="800" height="400" style="background-color: #ffffff; display: block; margin: 0 auto; box-shadow: 0 0 20px rgba(255, 20, 147, 0.7), 0 0 30px rgba(255, 20, 147, 0.5), 0 0 40px rgba(255, 20, 147, 0.3);"></canvas>
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
                                label: 'PRs Opened',
                                data: {prs_opened},
                                borderColor: 'rgba(75, 192, 192, 1)',
                                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                                borderWidth: 1
                            }},
                            {{
                                label: 'PRs Closed',
                                data: {prs_closed},
                                borderColor: 'rgba(255, 99, 132, 1)',
                                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                                borderWidth: 1
                            }},
                            {{
                                label: 'Issues Opened',
                                data: {issues_opened},
                                borderColor: 'rgba(54, 162, 235, 1)',
                                backgroundColor: 'rgba(54, 162, 235, 0.2)',
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
            <h2>✧ Open Pull Requests ✧</h2>
            <table>
                <tr><th>ID</th><th>Title</th><th>Creator</th><th>Created At</th><th>Last Updated</th><th>Days Open</th><th>Related Issues</th></tr>
                ''' + ''.join(
                    f'<tr>'
                    f'<td>{pr["id"]}</td>'
                    f'<td><a href="{pr["html_url"]}" target="_blank">{pr["title"]}</a></td>'
                    f'<td><img src="{pr["user"]["avatar_url"]}" alt="{pr["user"]["login"]} avatar" '
                    f'style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;">'
                    f'<a href="https://github.com/{pr["user"]["login"]}" '
                    f'style="color: {generate_color(pr["user"]["login"])};" target="_blank">'
                    f'{pr["user"]["login"]}</a></td>'
                    f'<td>{pr["created_at"]}</td>'
                    f'<td>{pr["updated_at"]}</td>'
                    f'<td>{pr["days_open"]}</td>'
                    f'<td>' + ', '.join(
                        f'<a href="https://github.com/{repo_owner}/{repo}/issues/{issue}">#{issue}</a>'
                        for issue in extract_issues_from_description(pr.get("body", ""))
                    ) + '</td></tr>'
                    for pr in data['opened_prs']
                ) + '''
            </table>
            <h2>✧ Open Issues ✧</h2>
            <table>
                <tr><th>ID</th><th>Title</th><th>Creator</th><th>Created At</th><th>Last Updated</th></tr>
                ''' + ''.join(
                    f'<tr>'
                    f'<td>{issue["id"]}</td>'
                    f'<td><a href="{issue["html_url"]}" target="_blank">{issue["title"]}</a></td>'
                    f'<td><img src="{issue["user"]["avatar_url"]}" alt="{issue["user"]["login"]} avatar" '
                    f'style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;">'
                    f'<a href="https://github.com/{issue["user"]["login"]}" '
                    f'style="color: {generate_color(issue["user"]["login"])};" target="_blank">'
                    f'{issue["user"]["login"]}</a></td>'
                    f'<td>{issue["created_at"]}</td>'
                    f'<td>{issue["updated_at"]}</td></tr>'
                    for issue in data['opened_issues']
                ) + '''
            </table>
            <h2>✧ Closed Pull Requests ✧</h2>
            <table>
                <tr><th>ID</th><th>Title</th><th>Creator</th><th>Closed At</th><th>Last Updated</th><th>Related Issues</th><th>Time to Close (days)</th></tr>
                ''' + ''.join(
                    f'<tr>'
                    f'<td>{pr["id"]}</td>'
                    f'<td><a href="{pr["html_url"]}" target="_blank">{pr["title"]}</a></td>'
                    f'<td><img src="{pr["user"]["avatar_url"]}" alt="{pr["user"]["login"]} avatar" '
                    f'style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;">'
                    f'<a href="https://github.com/{pr["user"]["login"]}" '
                    f'style="color: {generate_color(pr["user"]["login"])};" target="_blank">'
                    f'{pr["user"]["login"]}</a></td>'
                    f'<td>{pr["closed_at"]}</td>'
                    f'<td>{pr["updated_at"]}</td>'
                    f'<td>' + ', '.join(
                        f'<a href="https://github.com/{repo_owner}/{repo}/issues/{issue}">#{issue}</a>'
                        for issue in extract_issues_from_description(pr.get("body", ""))
                    ) + f'</td>'
                    f'<td>{calculate_issue_to_pr_time(pr, closed_issues)}</td></tr>'
                    for pr in data['closed_prs']
                ) + '''
            </table>
            <h2>✧ Closed Issues ✧</h2>
            <table>
                <tr><th>ID</th><th>Title</th><th>Creator</th><th>Closed At</th><th>Last Updated</th></tr>
                ''' + ''.join(
                    f'<tr>'
                    f'<td>{issue["id"]}</td>'
                    f'<td><a href="{issue["html_url"]}" target="_blank">{issue["title"]}</a></td>'
                    f'<td><img src="{issue["user"]["avatar_url"]}" alt="{issue["user"]["login"]} avatar" '
                    f'style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;">'
                    f'<a href="https://github.com/{issue["user"]["login"]}" '
                    f'style="color: {generate_color(issue["user"]["login"])};" target="_blank">'
                    f'{issue["user"]["login"]}</a></td>'
                    f'<td>{issue["closed_at"]}</td>'
                    f'<td>{issue["updated_at"]}</td></tr>'
                    for issue in data['closed_issues']
                ) + '''
            </table>
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

# After processing all repos, generate the index page
generate_index_html()