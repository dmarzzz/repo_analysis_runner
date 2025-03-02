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
import PIL

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Load environment variables
openai_key = os.getenv('OPENAI_KEY')
github_token = os.getenv('GITHUB_TOKEN')
repos = os.getenv('REPOS')

aclient = AsyncOpenAI(api_key=openai_key)

# Just for debugging
print(f"OpenAI API Key from .env: {openai_key}")

# Parse the REPOS environment variable
repos = eval(repos)  # Convert string repr of list to an actual list

def generate_index_html(project_summaries):
    report_dir = 'weekly_report'
    if not os.path.exists(report_dir):
        print("No weekly_report directory found. Skipping index generation.")
        return

    projects = os.listdir(report_dir)
    
    # Group repositories by organization
    organizations = {}
    
    for project in projects:
        if not os.path.isdir(os.path.join(report_dir, project)):
            continue
            
        # Initialize default stats for the repository
        repo_stats = {
            'description': 'Repository analysis and status tracking',
            'open_prs': 0,
            'open_issues': 0,
            'last_updated': 'N/A'
        }
        
        # Try to find data.json for the most recent week
        weeks = sorted([w for w in os.listdir(os.path.join(report_dir, project)) 
                        if os.path.isdir(os.path.join(report_dir, project, w))], reverse=True)
        
        data_json_path = None
        if weeks:
            data_json_path = os.path.join(report_dir, project, weeks[0], 'data.json')
            
        # 1. Start with a default
        repo_owner = None
        
        # 2. First priority: Get the organization name from the global repos list
        # This is the most reliable source since it's manually configured
        for repo_name, owner in repos:
            if repo_name == project:
                repo_owner = owner
                print(f"Found owner '{owner}' for repo '{project}' in global repos list")
                break
        
        # 3. If we still don't have an owner, try to get it from PR data
        # This is a fallback in case the repo wasn't in our global list
        if not repo_owner and os.path.exists(data_json_path):
            try:
                with open(data_json_path, 'r') as f:
                    data = json.load(f)
                
                # Extract stats regardless of owner determination
                if 'opened_prs' in data:
                    repo_stats['open_prs'] = len(data['opened_prs'])
                if 'opened_issues' in data:
                    repo_stats['open_issues'] = len(data['opened_issues'])
                
                # Calculate time since last update
                end_date = datetime.fromisoformat(data['end_date'])
                hours_since = round((datetime.now() - end_date).total_seconds() / 3600)
                repo_stats['last_updated'] = f"{hours_since}h ago"
                
                # Try to extract organization name from PR URLs
                if not repo_owner and 'opened_prs' in data and data['opened_prs']:
                    for pr in data['opened_prs']:
                        repo_url = pr.get('html_url', '')
                        if repo_url:
                            # PR URLs are in format: https://github.com/ORGANIZATION/REPO/pull/NUMBER
                            parts = repo_url.split('/')
                            if len(parts) >= 5:
                                # The organization name is the third part of the URL after splitting
                                repo_owner = parts[3]  # Index 3 instead of -3
                                print(f"Extracted organization '{repo_owner}' for repo '{project}' from PR URL")
                                break
            except Exception as e:
                print(f"Error reading data for {project}: {e}")
        
        # 4. Last resort: Use project name as owner (likely incorrect but prevents errors)
        if not repo_owner:
            print(f"No organization found for '{project}', using project name as fallback")
            repo_owner = project
        
        # Generate random project ID in Evangelion style
        project_id = f"PRJ-{hash(project) % 1000:03d}"
        
        # Add repository to the organization's list
        if repo_owner not in organizations:
            organizations[repo_owner] = {
                'repos': [],
                'total_open_prs': 0,
                'total_open_issues': 0,
                'last_updated': repo_stats['last_updated']
            }
        
        # Add this repository to the organization
        organizations[repo_owner]['repos'].append({
            'name': project,
            'id': project_id,
            'stats': repo_stats
        })
        
        # Update organization totals
        organizations[repo_owner]['total_open_prs'] += repo_stats['open_prs']
        organizations[repo_owner]['total_open_issues'] += repo_stats['open_issues']
        
        # Update organization's last updated time if this repo is more recent
        if repo_stats['last_updated'] != 'N/A' and (
            organizations[repo_owner]['last_updated'] == 'N/A' or 
            (repo_stats['last_updated'].endswith('h ago') and 
             organizations[repo_owner]['last_updated'].endswith('h ago') and
             int(repo_stats['last_updated'].split('h')[0]) < int(organizations[repo_owner]['last_updated'].split('h')[0]))
        ):
            organizations[repo_owner]['last_updated'] = repo_stats['last_updated']
    
    # Debug: Print found organizations
    print(f"\nFound {len(organizations)} organizations:")
    for org_name, org_data in organizations.items():
        print(f"  - {org_name} with {len(org_data['repos'])} repositories")
    
    # Now create the main index page with Evangelion-inspired UI
    index_content = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>NERV Repository Analysis System</title>
        <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #00ffa0;
                --secondary: #ff5000;
                --warning: #ffcf00;
                --background: #0a0a0a;
                --panel: #101418;
                --terminal-green: #00ffa0;
                --terminal-orange: #ff5000;
            }
            
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Share Tech Mono', monospace;
                color: var(--primary);
            }
            
            @keyframes scanline {
                0% {
                    transform: translateY(-100%);
                }
                100% {
                    transform: translateY(100%);
                }
            }
            
            body {
                background-color: var(--background);
                padding: 20px;
                min-height: 100vh;
                position: relative;
                overflow-x: hidden;
            }
            
            body::before {
                content: "";
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: repeating-linear-gradient(
                    0deg,
                    rgba(0, 255, 160, 0.1),
                    rgba(0, 255, 160, 0.1) 1px,
                    transparent 1px,
                    transparent 2px
                );
                pointer-events: none;
                z-index: 10;
            }
            
            body::after {
                content: "";
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 200px;
                background: rgba(0, 255, 160, 0.07);
                animation: scanline 8s linear infinite;
                pointer-events: none;
                z-index: 11;
            }
            
            .container {
                max-width: 1400px;
                margin: 0 auto;
                position: relative;
                z-index: 1;
            }
            
            .nerv-header {
                text-align: center;
                margin-bottom: 40px;
                position: relative;
                padding: 20px 0;
            }
            
            .nerv-header::before {
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: var(--primary);
                box-shadow: 0 0 15px var(--primary);
            }
            
            .nerv-logo {
                font-size: 2.5em;
                letter-spacing: 8px;
                margin-bottom: 10px;
                text-shadow: 0 0 10px var(--primary);
            }
            
            .nerv-subtitle {
                font-size: 1.2em;
                letter-spacing: 3px;
                color: var(--secondary);
                text-shadow: 0 0 10px var(--secondary);
            }
            
            .status-bar {
                display: flex;
                justify-content: space-between;
                margin-bottom: 30px;
                border: 1px solid var(--primary);
                padding: 10px 20px;
                background: rgba(0, 255, 160, 0.05);
                position: relative;
                overflow: hidden;
            }
            
            .status-bar::before {
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(0, 255, 160, 0.1), transparent);
                animation: scan 3s ease-in-out infinite;
            }
            
            @keyframes scan {
                0% { transform: translateX(-100%); }
                100% { transform: translateX(100%); }
            }
            
            .status-item {
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            
            .status-label {
                font-size: 0.8em;
                margin-bottom: 5px;
                opacity: 0.7;
            }
            
            .status-value {
                font-size: 1.2em;
            }
            
            .separator-line {
                height: 2px;
                background: var(--primary);
                margin: 30px 0;
                position: relative;
                overflow: hidden;
                box-shadow: 0 0 10px var(--primary);
                opacity: 0.7;
            }
            
            .separator-line::after {
                content: "ORGANIZATION DATA ANALYSIS";
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: 1.2em;
                color: var(--primary);
                font-weight: bold;
                letter-spacing: 2px;
                white-space: nowrap;
                background: var(--background);
                padding: 0 20px;
            }
            
            .repo-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }
            
            .repo-card, .org-card {
                background: rgba(10, 10, 10, 0.5);
                border: 1px solid var(--primary);
                border-radius: 16px;
                padding: 20px;
                position: relative;
                overflow: hidden;
                transition: all 0.3s ease;
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
            }
            
            .repo-card:hover, .org-card:hover {
                box-shadow: 0 0 20px rgba(0, 255, 160, 0.3);
                transform: translateY(-5px);
            }
            
            .repo-card::before, .org-card::before {
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 2px;
                background: var(--primary);
                border-radius: 16px 16px 0 0;
            }
            
            .repo-card-header, .org-card-header {
                display: flex;
                align-items: center;
                margin-bottom: 15px;
                border-bottom: 1px dashed var(--primary);
                padding-bottom: 10px;
            }
            
            .repo-logo, .org-logo {
                width: 40px;
                height: 40px;
                border: 1px solid var(--secondary);
                margin-right: 15px;
                object-fit: cover;
            }
            
            .repo-name, .org-name {
                font-size: 1.3em;
                letter-spacing: 2px;
                flex-grow: 1;
            }
            
            .repo-id, .org-id {
                font-size: 0.8em;
                color: var(--secondary);
                margin-top: -3px;
            }
            
            .repo-desc, .org-desc {
                font-size: 0.9em;
                margin-bottom: 20px;
                opacity: 0.8;
                line-height: 1.4;
            }
            
            .repo-stats, .org-stats {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
                margin-bottom: 20px;
                font-size: 0.9em;
            }
            
            .repo-stat, .org-stat {
                display: flex;
                justify-content: space-between;
            }
            
            .repo-stat-label, .org-stat-label {
                opacity: 0.7;
            }
            
            .repo-stat-value, .org-stat-value {
                font-weight: bold;
                text-shadow: 0 0 5px var(--primary);
            }
            
            .eva-button {
                display: block;
                width: 100%;
                background: linear-gradient(
                    90deg,
                    rgba(0, 255, 160, 0.1),
                    rgba(0, 255, 160, 0.2),
                    rgba(0, 255, 160, 0.1)
                );
                border: 1px solid var(--primary);
                color: var(--primary);
                padding: 10px 0;
                text-align: center;
                text-decoration: none;
                font-size: 1em;
                text-transform: uppercase;
                letter-spacing: 2px;
                transition: all 0.3s ease;
                border-radius: 12px;
                backdrop-filter: blur(5px);
                -webkit-backdrop-filter: blur(5px);
            }
            
            .eva-button:hover {
                background: linear-gradient(
                    90deg,
                    rgba(0, 255, 160, 0.2),
                    rgba(0, 255, 160, 0.3),
                    rgba(0, 255, 160, 0.2)
                );
                box-shadow: 0 0 10px rgba(0, 255, 160, 0.5);
                transform: translateY(-2px);
            }
            
            .summary-section {
                background: rgba(10, 10, 10, 0.5);
                border: 1px solid var(--primary);
                padding: 20px;
                margin-top: 30px;
                position: relative;
                overflow: hidden;
                border-radius: 16px;
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
            }
            
            .summary-header {
                font-size: 1.4em;
                letter-spacing: 3px;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 1px dashed var(--primary);
                text-shadow: 0 0 10px var(--primary);
            }
            
            .summary-list {
                list-style-type: none;
            }
            
            .summary-list li {
                margin-bottom: 10px;
                padding-left: 20px;
                position: relative;
            }
            
            .summary-list li::before {
                content: ">";
                position: absolute;
                left: 0;
                color: var(--secondary);
            }
            
            footer {
                text-align: center;
                margin-top: 50px;
                padding: 20px 0;
                font-size: 0.8em;
                opacity: 0.7;
                border-top: 1px dashed var(--primary);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="nerv-header">
                <div class="nerv-logo">NERV</div>
                <div class="nerv-subtitle">REPOSITORY ANALYSIS SYSTEM</div>
            </div>
            
            <div class="status-bar">
                <div class="status-item">
                    <div class="status-label">ORGANIZATIONS</div>
                    <div class="status-value">${len(organizations)}</div>
                </div>
                <div class="status-item">
                    <div class="status-label">REPOSITORIES</div>
                    <div class="status-value">${len(projects)}</div>
                </div>
                <div class="status-item">
                    <div class="status-label">SYSTEM STATUS</div>
                    <div class="status-value">OPERATIONAL</div>
                </div>
                <div class="status-item">
                    <div class="status-label">LAST UPDATE</div>
                    <div class="status-value">${datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
                </div>
            </div>
            
            <div class="separator-line"></div>
            
            <div class="repo-grid">
    '''
    
    # Now add organization cards instead of repository cards
    for org_name, org_data in organizations.items():
        # Generate random organization ID in Evangelion style
        org_id = f"ORG-{hash(org_name) % 1000:03d}"
        
        # Construct the logo URL for the organization
        logo_url = f"https://github.com/{org_name}.png"
        
        repo_count = len(org_data['repos'])
        
        index_content += f'''
            <div class="org-card">
                <div class="org-card-header">
                    <img src="{logo_url}" alt="{org_name}" class="org-logo">
                    <div>
                        <div class="org-name">{org_name.upper()}</div>
                        <div class="org-id">{org_id}</div>
                    </div>
                </div>
                <div class="org-desc">Organization with {repo_count} repositories under analysis</div>
                <div class="org-stats">
                    <div class="org-stat">
                        <div class="org-stat-label">REPOSITORIES:</div>
                        <div class="org-stat-value">{repo_count}</div>
                    </div>
                    <div class="org-stat">
                        <div class="org-stat-label">OPEN PRS:</div>
                        <div class="org-stat-value">{org_data['total_open_prs']}</div>
                    </div>
                    <div class="org-stat">
                        <div class="org-stat-label">OPEN ISSUES:</div>
                        <div class="org-stat-value">{org_data['total_open_issues']}</div>
                    </div>
                    <div class="org-stat">
                        <div class="org-stat-label">LAST UPDATE:</div>
                        <div class="org-stat-value">{org_data['last_updated']}</div>
                    </div>
                </div>
                <a href="org_{org_name}.html" class="eva-button">View Repositories</a>
            </div>
        '''
    
    index_content += '''
            </div>
            
            <div class="separator-line"></div>
            
            <div class="summary-section">
                <div class="summary-header">Executive Summary</div>
                <ul class="summary-list">
    '''
    
    # FIX: Handle project_summaries as a list instead of dictionary
    if isinstance(project_summaries, list):
        for summary in project_summaries:
            if summary:
                index_content += f'<li>{summary}</li>\n'
    else:
        # Fallback for dictionary format (if it ever comes in that format)
        for project, summary in project_summaries.items():
            if summary:
                index_content += f'<li>{summary}</li>\n'

    index_content += '''
        </ul>
            </div>
            
            <footer>
                NERV REPOSITORY ANALYSIS SYSTEM v2.0 - &copy; NERV TECHNOLOGIES
            </footer>
        </div>
    </body>
    </html>
    '''

    with open('index.html', 'w') as f:
        f.write(index_content)
    
    print("Generated index.html")
    
    # Now generate organization pages
    generate_organization_pages(organizations)

def generate_organization_pages(organizations):
    """Generate HTML pages for each organization showing their repositories"""
    
    print(f"\nGenerating pages for {len(organizations)} organizations:")
    
    for org_name, org_data in organizations.items():
        print(f"  - Generating page for {org_name} with {len(org_data['repos'])} repositories")
        
        # Construct the logo URL for the organization
        logo_url = f"https://github.com/{org_name}.png"
        
        # Generate random organization ID in Evangelion style
        org_id = f"ORG-{hash(org_name) % 1000:03d}"
        
        org_page_content = f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>{org_name.upper()} - NERV Repository Analysis System</title>
            <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
            <style>
                :root {{
                    --primary: #00ffa0;
                    --secondary: #ff5000;
                    --warning: #ffcf00;
                    --background: #0a0a0a;
                    --panel: #101418;
                    --terminal-green: #00ffa0;
                    --terminal-orange: #ff5000;
                }}
                
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                    font-family: 'Share Tech Mono', monospace;
                    color: var(--primary);
                }}
                
                @keyframes scanline {{
                    0% {{
                        transform: translateY(-100%);
                    }}
                    100% {{
                        transform: translateY(100%);
                    }}
                }}
                
                body {{
                    background-color: var(--background);
                    padding: 20px;
                    min-height: 100vh;
                    position: relative;
                    overflow-x: hidden;
                }}
                
                body::before {{
                    content: "";
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: repeating-linear-gradient(
                        0deg,
                        rgba(0, 255, 160, 0.1),
                        rgba(0, 255, 160, 0.1) 1px,
                        transparent 1px,
                        transparent 2px
                    );
                    pointer-events: none;
                    z-index: 10;
                }}
                
                body::after {{
                    content: "";
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 200px;
                    background: rgba(0, 255, 160, 0.07);
                    animation: scanline 8s linear infinite;
                    pointer-events: none;
                    z-index: 11;
                }}
                
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                    position: relative;
                    z-index: 1;
                }}
                
                .nerv-header {{
                    text-align: center;
                    margin-bottom: 40px;
                    position: relative;
                    padding: 20px 0;
                }}
                
                .nerv-header::before {{
                    content: "";
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    height: 4px;
                    background: var(--primary);
                    box-shadow: 0 0 15px var(--primary);
                }}
                
                .nav-link {{
                    position: absolute;
                    left: 20px;
                    top: 20px;
                    text-decoration: none;
                    display: flex;
                    align-items: center;
                    padding: 10px 15px;
                    background: rgba(0, 255, 160, 0.1);
                    border: 1px solid var(--primary);
                    border-radius: 8px;
                    transition: all 0.3s ease;
                }}
                
                .nav-link:hover {{
                    background: rgba(0, 255, 160, 0.2);
                    box-shadow: 0 0 10px rgba(0, 255, 160, 0.3);
                }}
                
                .nav-link-arrow {{
                    margin-right: 8px;
                }}
                
                .nerv-logo {{
                    font-size: 2.5em;
                    letter-spacing: 8px;
                    margin-bottom: 10px;
                    text-shadow: 0 0 10px var(--primary);
                }}
                
                .nerv-subtitle {{
                    font-size: 1.2em;
                    letter-spacing: 3px;
                    color: var(--secondary);
                    text-shadow: 0 0 10px var(--secondary);
                }}
                
                .org-profile {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 30px;
                    padding: 20px;
                    background: rgba(10, 10, 10, 0.5);
                    border: 1px solid var(--primary);
                    border-radius: 16px;
                    backdrop-filter: blur(20px);
                    -webkit-backdrop-filter: blur(20px);
                }}
                
                .org-logo-large {{
                    width: 100px;
                    height: 100px;
                    border: 2px solid var(--secondary);
                    margin-right: 30px;
                    object-fit: cover;
                }}
                
                .org-info {{
                    flex-grow: 1;
                }}
                
                .org-name-large {{
                    font-size: 2em;
                    letter-spacing: 3px;
                    margin-bottom: 10px;
                    text-shadow: 0 0 10px var(--primary);
                }}
                
                .org-id-large {{
                    font-size: 1em;
                    color: var(--secondary);
                    margin-bottom: 15px;
                }}
                
                .org-stats-large {{
                    display: flex;
                    gap: 30px;
                }}
                
                .org-stat-large {{
                    display: flex;
                    flex-direction: column;
                }}
                
                .org-stat-label-large {{
                    font-size: 0.8em;
                    opacity: 0.7;
                    margin-bottom: 5px;
                }}
                
                .org-stat-value-large {{
                    font-size: 1.4em;
                    font-weight: bold;
                    text-shadow: 0 0 5px var(--primary);
                }}
                
                .separator-line {{
                    height: 2px;
                    background: var(--primary);
                    margin: 30px 0;
                    position: relative;
                    overflow: hidden;
                    box-shadow: 0 0 10px var(--primary);
                    opacity: 0.7;
                }}
                
                .separator-line::after {{
                    content: "REPOSITORY DATA ANALYSIS";
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    font-size: 1.2em;
                    color: var(--primary);
                    font-weight: bold;
                    letter-spacing: 2px;
                    white-space: nowrap;
                    background: var(--background);
                    padding: 0 20px;
                }}
                
                .repo-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
                    gap: 20px;
                    margin-bottom: 40px;
                }}
                
                .repo-card {{
                    background: rgba(10, 10, 10, 0.5);
                    border: 1px solid var(--primary);
                    border-radius: 16px;
                    padding: 20px;
                    position: relative;
                    overflow: hidden;
                    transition: all 0.3s ease;
                    backdrop-filter: blur(20px);
                    -webkit-backdrop-filter: blur(20px);
                    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
                }}
                
                .repo-card:hover {{
                    box-shadow: 0 0 20px rgba(0, 255, 160, 0.3);
                    transform: translateY(-5px);
                }}
                
                .repo-card::before {{
                    content: "";
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    height: 2px;
                    background: var(--primary);
                    border-radius: 16px 16px 0 0;
                }}
                
                .repo-card-header {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 15px;
                    border-bottom: 1px dashed var(--primary);
                    padding-bottom: 10px;
                }}
                
                .repo-name {{
                    font-size: 1.3em;
                    letter-spacing: 2px;
                    flex-grow: 1;
                }}
                
                .repo-id {{
                    font-size: 0.8em;
                    color: var(--secondary);
                    margin-top: -3px;
                }}
                
                .repo-desc {{
                    font-size: 0.9em;
                    margin-bottom: 20px;
                    opacity: 0.8;
                    line-height: 1.4;
                }}
                
                .repo-stats {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 10px;
                    margin-bottom: 20px;
                    font-size: 0.9em;
                }}
                
                .repo-stat {{
                    display: flex;
                    justify-content: space-between;
                }}
                
                .repo-stat-label {{
                    opacity: 0.7;
                }}
                
                .repo-stat-value {{
                    font-weight: bold;
                    text-shadow: 0 0 5px var(--primary);
                }}
                
                .eva-button {{
                    display: block;
                    width: 100%;
                    background: linear-gradient(
                        90deg,
                        rgba(0, 255, 160, 0.1),
                        rgba(0, 255, 160, 0.2),
                        rgba(0, 255, 160, 0.1)
                    );
                    border: 1px solid var(--primary);
                    color: var(--primary);
                    padding: 10px 0;
                    text-align: center;
                    text-decoration: none;
                    font-size: 1em;
                    text-transform: uppercase;
                    letter-spacing: 2px;
                    transition: all 0.3s ease;
                    border-radius: 12px;
                    backdrop-filter: blur(5px);
                    -webkit-backdrop-filter: blur(5px);
                }}
                
                .eva-button:hover {{
                    background: linear-gradient(
                        90deg,
                        rgba(0, 255, 160, 0.2),
                        rgba(0, 255, 160, 0.3),
                        rgba(0, 255, 160, 0.2)
                    );
                    box-shadow: 0 0 10px rgba(0, 255, 160, 0.5);
                    transform: translateY(-2px);
                }}
                
                footer {{
                    text-align: center;
                    margin-top: 50px;
                    padding: 20px 0;
                    font-size: 0.8em;
                    opacity: 0.7;
                    border-top: 1px dashed var(--primary);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="nerv-header">
                    <a href="index.html" class="nav-link">
                        <span class="nav-link-arrow">←</span> Back to Organizations
                    </a>
                    <div class="nerv-logo">NERV</div>
                    <div class="nerv-subtitle">REPOSITORY ANALYSIS SYSTEM</div>
                </div>
                
                <div class="org-profile">
                    <img src="{logo_url}" alt="{org_name}" class="org-logo-large">
                    <div class="org-info">
                        <div class="org-name-large">{org_name.upper()}</div>
                        <div class="org-id-large">ID: {org_id}</div>
                        <div class="org-stats-large">
                            <div class="org-stat-large">
                                <div class="org-stat-label-large">REPOSITORIES</div>
                                <div class="org-stat-value-large">{len(org_data['repos'])}</div>
                            </div>
                            <div class="org-stat-large">
                                <div class="org-stat-label-large">OPEN PRS</div>
                                <div class="org-stat-value-large">{org_data['total_open_prs']}</div>
                            </div>
                            <div class="org-stat-large">
                                <div class="org-stat-label-large">OPEN ISSUES</div>
                                <div class="org-stat-value-large">{org_data['total_open_issues']}</div>
                            </div>
                            <div class="org-stat-large">
                                <div class="org-stat-label-large">LAST UPDATE</div>
                                <div class="org-stat-value-large">{org_data['last_updated']}</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="separator-line"></div>
                
                <div class="repo-grid">
        '''
        
        # Add repository cards
        for repo in org_data['repos']:
            # Generate repository index page first
            generate_repository_index_page(repo['name'])
            
            org_page_content += f'''
                <div class="repo-card">
                    <div class="repo-card-header">
                        <div>
                            <div class="repo-name">{repo['name'].upper()}</div>
                            <div class="repo-id">{repo['id']}</div>
                        </div>
                    </div>
                    <div class="repo-desc">{repo['stats']['description']}</div>
                    <div class="repo-stats">
                        <div class="repo-stat">
                            <div class="repo-stat-label">OPEN PR COUNT:</div>
                            <div class="repo-stat-value">{repo['stats']['open_prs']}</div>
                        </div>
                        <div class="repo-stat">
                            <div class="repo-stat-label">OPEN ISSUE COUNT:</div>
                            <div class="repo-stat-value">{repo['stats']['open_issues']}</div>
                        </div>
                        <div class="repo-stat">
                            <div class="repo-stat-label">LAST UPDATE:</div>
                            <div class="repo-stat-value">{repo['stats']['last_updated']}</div>
                        </div>
                        <div class="repo-stat">
                            <div class="repo-stat-label">STATUS:</div>
                            <div class="repo-stat-value">ACTIVE</div>
                        </div>
                    </div>
                    <a href="repo_{repo['name']}.html" class="eva-button">Access Reports</a>
                </div>
            '''
        
        org_page_content += '''
                </div>
                
                <footer>
                    NERV REPOSITORY ANALYSIS SYSTEM v2.0 - &copy; NERV TECHNOLOGIES
                </footer>
            </div>
        </body>
        </html>
        '''
        
        with open(f'org_{org_name}.html', 'w') as f:
            f.write(org_page_content)
        
        print(f"Generated organization page for {org_name}")

def generate_repository_index_page(repo_name):
    """Generate an index page for a repository that lists all weekly reports"""
    print(f"  - Generating index page for repository: {repo_name}")
    
    report_dir = os.path.join('weekly_report', repo_name)
    if not os.path.exists(report_dir) or not os.path.isdir(report_dir):
        print(f"    No report directory found for {repo_name}. Skipping.")
        return
    
    # Find all weeks that have data.html files
    weeks = []
    for week_dir in os.listdir(report_dir):
        week_path = os.path.join(report_dir, week_dir)
        if os.path.isdir(week_path) and os.path.exists(os.path.join(week_path, 'data.html')):
            # Try to parse the week directory as a date range
            try:
                # Format is YYYYMMDD_YYYYMMDD 
                if '_' in week_dir and len(week_dir) == 17:  # 8 + 1 + 8
                    start_date = week_dir[:8]
                    end_date = week_dir[9:]
                    formatted_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]} to {end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
                else:
                    formatted_date = week_dir
                
                weeks.append({
                    'dir': week_dir,
                    'formatted_date': formatted_date
                })
            except:
                weeks.append({
                    'dir': week_dir,
                    'formatted_date': week_dir
                })
    
    # Sort weeks by directory name in reverse order (newest first)
    weeks.sort(key=lambda x: x['dir'], reverse=True)
    
    # Generate random repository ID in Evangelion style
    repo_id = f"PRJ-{hash(repo_name) % 1000:03d}"
    
    # Find owner for the repository
    repo_owner = None
    for repo, owner in repos:
        if repo == repo_name:
            repo_owner = owner
            break
    
    if not repo_owner:
        repo_owner = repo_name  # Fallback
    
    # Organization logo URL
    logo_url = f"https://github.com/{repo_owner}.png"
    
    repo_page_content = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>{repo_name.upper()} - NERV Repository Analysis System</title>
        <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #00ffa0;
                --secondary: #ff5000;
                --warning: #ffcf00;
                --background: #0a0a0a;
                --panel: #101418;
                --terminal-green: #00ffa0;
                --terminal-orange: #ff5000;
            }}
            
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Share Tech Mono', monospace;
                color: var(--primary);
            }}
            
            @keyframes scanline {{
                0% {{
                    transform: translateY(-100%);
                }}
                100% {{
                    transform: translateY(100%);
                }}
            }}
            
            body {{
                background-color: var(--background);
                padding: 20px;
                min-height: 100vh;
                position: relative;
                overflow-x: hidden;
            }}
            
            body::before {{
                content: "";
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: repeating-linear-gradient(
                    0deg,
                    rgba(0, 255, 160, 0.1),
                    rgba(0, 255, 160, 0.1) 1px,
                    transparent 1px,
                    transparent 2px
                );
                pointer-events: none;
                z-index: 10;
            }}
            
            body::after {{
                content: "";
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 200px;
                background: rgba(0, 255, 160, 0.07);
                animation: scanline 8s linear infinite;
                pointer-events: none;
                z-index: 11;
            }}
            
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                position: relative;
                z-index: 1;
            }}
            
            .nerv-header {{
                text-align: center;
                margin-bottom: 40px;
                position: relative;
                padding: 20px 0;
            }}
            
            .nerv-header::before {{
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: var(--primary);
                box-shadow: 0 0 15px var(--primary);
            }}
            
            .nav-link {{
                position: absolute;
                left: 20px;
                top: 20px;
                text-decoration: none;
                display: flex;
                align-items: center;
                padding: 10px 15px;
                background: rgba(0, 255, 160, 0.1);
                border: 1px solid var(--primary);
                border-radius: 8px;
                transition: all 0.3s ease;
            }}
            
            .nav-link:hover {{
                background: rgba(0, 255, 160, 0.2);
                box-shadow: 0 0 10px rgba(0, 255, 160, 0.3);
            }}
            
            .nav-link-arrow {{
                margin-right: 8px;
            }}
            
            .nerv-logo {{
                font-size: 2.5em;
                letter-spacing: 8px;
                margin-bottom: 10px;
                text-shadow: 0 0 10px var(--primary);
            }}
            
            .nerv-subtitle {{
                font-size: 1.2em;
                letter-spacing: 3px;
                color: var(--secondary);
                text-shadow: 0 0 10px var(--secondary);
            }}
            
            .repo-profile {{
                display: flex;
                align-items: center;
                margin-bottom: 30px;
                padding: 20px;
                background: rgba(10, 10, 10, 0.5);
                border: 1px solid var(--primary);
                border-radius: 16px;
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
            }}
            
            .repo-logo-large {{
                width: 100px;
                height: 100px;
                border: 2px solid var(--secondary);
                margin-right: 30px;
                object-fit: cover;
            }}
            
            .repo-info {{
                flex-grow: 1;
            }}
            
            .repo-name-large {{
                font-size: 2em;
                letter-spacing: 3px;
                margin-bottom: 10px;
                text-shadow: 0 0 10px var(--primary);
            }}
            
            .repo-id-large {{
                font-size: 1em;
                color: var(--secondary);
                margin-bottom: 15px;
            }}
            
            .separator-line {{
                height: 2px;
                background: var(--primary);
                margin: 30px 0;
                position: relative;
                overflow: hidden;
                box-shadow: 0 0 10px var(--primary);
                opacity: 0.7;
            }}
            
            .separator-line::after {{
                content: "WEEKLY REPORT ANALYSIS";
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: 1.2em;
                color: var(--primary);
                font-weight: bold;
                letter-spacing: 2px;
                white-space: nowrap;
                background: var(--background);
                padding: 0 20px;
            }}
            
            .report-list {{
                margin-bottom: 40px;
            }}
            
            .report-item {{
                background: rgba(10, 10, 10, 0.5);
                border: 1px solid var(--primary);
                border-radius: 16px;
                padding: 20px;
                margin-bottom: 20px;
                position: relative;
                overflow: hidden;
                transition: all 0.3s ease;
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
            }}
            
            .report-item:hover {{
                box-shadow: 0 0 20px rgba(0, 255, 160, 0.3);
                transform: translateY(-5px);
            }}
            
            .report-item::before {{
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 2px;
                background: var(--primary);
                border-radius: 16px 16px 0 0;
            }}
            
            .report-date {{
                font-size: 1.3em;
                letter-spacing: 2px;
                margin-bottom: 15px;
                border-bottom: 1px dashed var(--primary);
                padding-bottom: 10px;
                text-shadow: 0 0 10px var(--primary);
            }}
            
            .eva-button {{
                display: block;
                width: 100%;
                background: linear-gradient(
                    90deg,
                    rgba(0, 255, 160, 0.1),
                    rgba(0, 255, 160, 0.2),
                    rgba(0, 255, 160, 0.1)
                );
                border: 1px solid var(--primary);
                color: var(--primary);
                padding: 10px 0;
                text-align: center;
                text-decoration: none;
                font-size: 1em;
                text-transform: uppercase;
                letter-spacing: 2px;
                transition: all 0.3s ease;
                border-radius: 12px;
                backdrop-filter: blur(5px);
                -webkit-backdrop-filter: blur(5px);
            }}
            
            .eva-button:hover {{
                background: linear-gradient(
                    90deg,
                    rgba(0, 255, 160, 0.2),
                    rgba(0, 255, 160, 0.3),
                    rgba(0, 255, 160, 0.2)
                );
                box-shadow: 0 0 10px rgba(0, 255, 160, 0.5);
                transform: translateY(-2px);
            }}
            
            .empty-message {{
                text-align: center;
                padding: 40px 20px;
                font-size: 1.2em;
                opacity: 0.7;
                letter-spacing: 2px;
            }}
            
            footer {{
                text-align: center;
                margin-top: 50px;
                padding: 20px 0;
                font-size: 0.8em;
                opacity: 0.7;
                border-top: 1px dashed var(--primary);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="nerv-header">
                <a href="org_{repo_owner}.html" class="nav-link">
                    <span class="nav-link-arrow">←</span> Back to {repo_owner.upper()}
                </a>
                <div class="nerv-logo">NERV</div>
                <div class="nerv-subtitle">REPOSITORY ANALYSIS SYSTEM</div>
            </div>
            
            <div class="repo-profile">
                <img src="{logo_url}" alt="{repo_name}" class="repo-logo-large">
                <div class="repo-info">
                    <div class="repo-name-large">{repo_name.upper()}</div>
                    <div class="repo-id-large">ID: {repo_id}</div>
                </div>
            </div>
            
            <div class="separator-line"></div>
            
            <div class="report-list">
    '''
    
    if weeks:
        for week in weeks:
            week_dir = week['dir']
            formatted_date = week['formatted_date']
            
            repo_page_content += f'''
                <div class="report-item">
                    <div class="report-date">{formatted_date}</div>
                    <a href="weekly_report/{repo_name}/{week_dir}/data.html" class="eva-button">View Report</a>
                </div>
            '''
    else:
        repo_page_content += '''
                <div class="empty-message">
                    No weekly reports available for this repository.
                </div>
        '''
    
    repo_page_content += '''
            </div>
            
            <footer>
                NERV REPOSITORY ANALYSIS SYSTEM v2.0 - &copy; NERV TECHNOLOGIES
            </footer>
        </div>
    </body>
    </html>
    '''
    
    with open(f'repo_{repo_name}.html', 'w') as f:
        f.write(repo_page_content)
    
    print(f"    Generated repository index page: repo_{repo_name}.html")

project_summaries = []

# Helper to display hours as "Xh" or days as "Xd"
def format_hours_or_days(hours):
    if hours is None:
        return "N/A"
    return f"{hours}h"  # Always display in hours

def get_response_time_color(hours):
    """
    Color code response times:
    - N/A or None: red
    - Over 24 hours: red
    - 4-24 hours: yellow
    - Under 4 hours: green
    """
    if hours is None or hours == "N/A":
        return "#FF4136"  # Red for N/A
    if hours > 24:
        return "#FF4136"  # Red for >24 hours
    if hours <= 4:
        return "#2ECC40"  # Green for ≤4 hours
    return "#FFDC00"  # Yellow for 4-24 hours

# Generate a unique retro neon color based on username
def generate_retro_neon_color(username):
    # Use hash of username to generate a consistent color
    hash_obj = hashlib.md5(username.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    
    # Retro neon color palette - removed yellow and light colors that don't contrast well
    retro_neon_colors = [
        "#ff00ff",  # Magenta
        "#00ffff",  # Cyan
        "#ff0099",  # Hot Pink
        "#33cc00",  # Darker Lime Green
        "#ff3300",  # Neon Orange
        "#9900ff",  # Purple
        "#0066ff",  # Darker Blue
        "#ff0066",  # Pink
        "#cc00cc",  # Darker Magenta
        "#0099cc",  # Darker Cyan
        "#cc3300",  # Darker Orange
        "#6600cc",  # Darker Purple
    ]
    
    # Select a color from the palette based on the hash
    color_index = hash_int % len(retro_neon_colors)
    return retro_neon_colors[color_index]

for repo, repo_owner in repos:
    print(f"\n🚀 Starting processing for {repo_owner}/{repo} 🚀")

    base_url = f'https://api.github.com/repos/{repo_owner}/{repo}'
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    def is_error_response(response):
        return isinstance(response, dict) and 'message' in response

    def extract_issues_from_description(description):
        if description is None:
            return []
        return re.findall(r'#(\d+)', description)

    def fetch_pr_comments(pr_number):
        r = requests.get(f'{base_url}/issues/{pr_number}/comments', headers=headers)
        return r.json()

    def fetch_pr_reviews(pr_number):
        r = requests.get(f'{base_url}/pulls/{pr_number}/reviews', headers=headers)
        return r.json()

    def fetch_pr_review_comments(pr_number):
        r = requests.get(f'{base_url}/pulls/{pr_number}/comments', headers=headers)
        return r.json()

    def fetch_issue_comments(issue_number):
        r = requests.get(f'{base_url}/issues/{issue_number}/comments', headers=headers)
        return r.json()

    def calculate_time_to_first_response(pr):
        """ For PR or Issue, time from creation to first non-creator comment, in hours. """
        comments = fetch_pr_comments(pr['number'])
        for c in comments:
            if c['user']['login'] != pr['user']['login']:
                pr_created = datetime.fromisoformat(pr['created_at'][:-1])
                c_created = datetime.fromisoformat(c['created_at'][:-1])
                return math.ceil((c_created - pr_created).total_seconds()/3600)
        return None

    def calculate_time_to_first_response_issue(issue):
        """ For Issue, time from creation to first non-creator comment, in hours. """
        comments = fetch_issue_comments(issue['number'])
        for c in comments:
            if c['user']['login'] != issue['user']['login']:
                i_created = datetime.fromisoformat(issue['created_at'][:-1])
                c_created = datetime.fromisoformat(c['created_at'][:-1])
                return math.ceil((c_created - i_created).total_seconds()/3600)
        return None

    def calculate_days_open(pr):
        try:
            created = datetime.fromisoformat(pr['created_at'][:-1])
            return (datetime.now() - created).days
        except:
            return 0

    def calculate_hours_open(pr):
        try:
            created = datetime.fromisoformat(pr['created_at'][:-1])
            delta = datetime.now() - created
            return math.ceil(delta.total_seconds() / 3600)
        except:
            return 0

    def calculate_days_open_issue(issue):
        try:
            created = datetime.fromisoformat(issue['created_at'][:-1])
            return (datetime.now() - created).days
        except:
            return 0

    def calculate_hours_open_issue(issue):
        try:
            created = datetime.fromisoformat(issue['created_at'][:-1])
            delta = datetime.now() - created
            return math.ceil(delta.total_seconds() / 3600)
        except:
            return 0

    def get_pr_comment_count(pr_number):
        """Get the count of comments on a PR."""
        try:
            comments = fetch_pr_comments(pr_number)
            return len(comments)
        except Exception as e:
            print(f"Error fetching comments for PR #{pr_number}: {e}")
            return 0

    def get_pr_review_count(pr_number):
        """Get the count of actual reviews on a PR."""
        try:
            reviews = fetch_pr_reviews(pr_number)
            
            # Filter out non-meaningful reviews - only count actual human reviews
            # Valid states for reviews are: APPROVED, CHANGES_REQUESTED, COMMENTED
            # We'll only count reviews with these states
            real_reviews = [
                r for r in reviews 
                if r.get('state') in ['APPROVED', 'CHANGES_REQUESTED'] or 
                   (r.get('state') == 'COMMENTED' and r.get('body', '').strip() != '')
            ]
            
            # Also filter out bot reviews
            human_reviews = [
                r for r in real_reviews
                if not r.get('user', {}).get('login', '').endswith('[bot]')
            ]
            
            return len(human_reviews)
        except Exception as e:
            print(f"Error fetching reviews for PR #{pr_number}: {e}")
            return 0

    def calculate_issue_to_pr_time(pr, issues):
        """Time from an Issue creation (if referenced) to PR closure, or PR creation to closure if no references."""
        refs = extract_issues_from_description(pr.get('body',''))
        if not refs:
            c_at = datetime.fromisoformat(pr['created_at'][:-1])
            x_at = datetime.fromisoformat(pr['closed_at'][:-1])
            return math.ceil((x_at - c_at).total_seconds()/3600)
        times = []
        for rnum in refs:
            issue = next((i for i in issues if str(i['number']) == rnum), None)
            if issue and issue.get("created_at") and pr.get("closed_at"):
                i_created = datetime.fromisoformat(issue['created_at'][:-1])
                p_closed = datetime.fromisoformat(pr['closed_at'][:-1])
                times.append(math.ceil((p_closed - i_created).total_seconds()/3600))
        return min(times) if times else 0

    # =========================== Fetching ============================
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    def fetch_open_prs_within_date_range():
        url = f'{base_url}/pulls?state=open&since={start_date.isoformat()}'
        try:
            data = requests.get(url, headers=headers).json()
            if is_error_response(data):
                return []
            return data
        except:
            return []

    def fetch_closed_prs_within_date_range():
        url = f'{base_url}/pulls?state=closed&since={start_date.isoformat()}'
        try:
            data = requests.get(url, headers=headers).json()
            if is_error_response(data):
                return []
            # only keep PRs closed during [start_date, end_date]
            final = []
            for pr in data:
                if pr.get("closed_at"):
                    c_at = datetime.fromisoformat(pr['closed_at'][:-1])
                    if start_date <= c_at <= end_date:
                        final.append(pr)
            return final
        except:
            return []

    def fetch_open_issues_within_date_range():
        url = f'{base_url}/issues?state=open&since={start_date.isoformat()}'
        try:
            data = requests.get(url, headers=headers).json()
            if is_error_response(data):
                return []
            return [i for i in data if 'pull_request' not in i]
        except:
            return []

    def fetch_closed_issues_within_date_range():
        url = f'{base_url}/issues?state=closed&since={start_date.isoformat()}'
        print(f"Fetching closed issues from: {url}")
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Error fetching closed issues: {response.status_code} - {response.text}")
                return []
                
            data = response.json()
            if is_error_response(data):
                print(f"API error response for closed issues: {data.get('message', 'Unknown error')}")
                return []
                
            # Filter out PRs which appear in the issues endpoint
            real_issues = [i for i in data if 'pull_request' not in i]
            print(f"Found {len(real_issues)} closed issues in total")
            
            final = []
            for iss_ in real_issues:
                if iss_.get("closed_at"):
                    c_at = datetime.fromisoformat(iss_["closed_at"][:-1])
                    if start_date <= c_at <= end_date:
                        final.append(iss_)
            
            print(f"After date filtering: {len(final)} closed issues in period {start_date.date()} to {end_date.date()}")
            return final
            
        except Exception as e:
            print(f"Exception fetching closed issues: {str(e)}")
            return []

    open_prs = fetch_open_prs_within_date_range()
    closed_prs = fetch_closed_prs_within_date_range()
    open_issues = fetch_open_issues_within_date_range()
    closed_issues = fetch_closed_issues_within_date_range()

    # ===================== Enrich data =====================
    for pr in open_prs:
        pr["days_open"] = calculate_days_open(pr)
        pr["hours_open"] = calculate_hours_open(pr)
        pr["time_to_first_response"] = calculate_time_to_first_response(pr)

    for pr in closed_prs:
        pr["time_to_first_response"] = calculate_time_to_first_response(pr)

    for iss_ in open_issues:
        iss_["days_open"] = calculate_days_open_issue(iss_)
        iss_["hours_open"] = calculate_hours_open_issue(iss_)
        iss_["time_to_first_response"] = calculate_time_to_first_response_issue(iss_)

    for iss_ in closed_issues:
        iss_["time_to_first_response"] = calculate_time_to_first_response_issue(iss_)

    # ==================== Aggregated Stats ===================
    aggregated_stats = defaultdict(lambda: {
        'prs_opened': 0,
        'prs_closed': 0,
        'issues_opened': 0,
        'issues_closed': 0,
        'contributors': set()
    })
    all_contributors = set()

    # count open PRs => "prs_opened" on creation date
    for pr in open_prs:
        dstr = pr["created_at"][:10]
        aggregated_stats[dstr]['prs_opened'] += 1
        aggregated_stats[dstr]['contributors'].add(pr['user']['login'])
        all_contributors.add(pr['user']['login'])

    # count closed PRs => "prs_closed" on closed date
    for pr in closed_prs:
        dstr = pr["closed_at"][:10]
        aggregated_stats[dstr]['prs_closed'] += 1
        aggregated_stats[dstr]['contributors'].add(pr['user']['login'])
        all_contributors.add(pr['user']['login'])

    # count open issues => "issues_opened" on creation date
    for iss_ in open_issues:
        dstr = iss_["created_at"][:10]
        aggregated_stats[dstr]['issues_opened'] += 1

    # count closed issues => "issues_closed" on closed date
    for iss_ in closed_issues:
        dstr = iss_["closed_at"][:10]
        aggregated_stats[dstr]['issues_closed'] += 1

    for dstr, st in aggregated_stats.items():
        st['contributors'] = len(st['contributors'])

    overall_contributors_count = len(all_contributors)

    async def generate_descriptive_summary(closed_prs, open_issues, repo_owner, repo):
        pr_details = [
            f"PR #[{pr['number']}](https://github.com/{repo_owner}/{repo}/pull/{pr['number']}): {pr['title']} - {pr.get('body','No description')}"
            for pr in closed_prs
        ]
        issue_details = [
            f"Issue #{iss_['number']}: {iss_['title']} - {iss_.get('body','No description')}"
            for iss_ in open_issues
        ]
        prompt = f"""
        I want a summary of recently developments in a github repository. This repository has an Open Source Development process with various systems and rules for communicating within Pull Requests, Issues, and more.

        For the repository, return a 4 bullet point list that first summarizes the overall tone of the week's worth of PRs, whether the main focus was around merging a big feature or release, doing maintenance work, bug fixes, hardening, or generally anything which a 20 years of experience Open Source Backend Developer in the Etheruem or AI ecosystem would characterize the work as. The next three bullet points should then each be given to the most impactful PRs or Issues that we're opened or closed that week.

        Be careful to make sure you provide 4 bullet points with the first being a summary and the next three highlighting the largest developments. Be sure not to summarize the technical components so generically that they lose their meeting, they should take as much wording from the original PR or issue as possible.

        —

        The repository context:
        
        Closed PRs:
        {chr(10).join(pr_details)}
        
        Open Issues:
        {chr(10).join(issue_details)}
        """
        try:
            response = await aclient.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                n=1,
                stop=None,
                temperature=0.5
            )
            lines = response.choices[0].message.content.strip().split('\n')
            # keep only non-empty lines
            return [l for l in lines if l]
        except OpenAIError as e:
            print(f"Error generating summary: {e}")
            return []

    summary = asyncio.run(generate_descriptive_summary(closed_prs, open_issues, repo_owner, repo))
    if not summary:
        summary = ["Summary Not Available"]

    summary.append(f"Overall: {len(closed_prs)} PRs closed, {overall_contributors_count} contributors.")

    def extract_urls(text):
        if text is None:
            return []
        return re.findall(r'https?://\S+', text)

    def collect_spec_links(prs, issues):
        s = set()
        for pr in prs:
            s.update(extract_urls(pr.get('body','')))
        for iss_ in issues:
            s.update(extract_urls(iss_.get('body','')))
        return list(s)

    spec_links = collect_spec_links(closed_prs, closed_issues)

    output_data = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'opened_prs': open_prs,
        'closed_prs': closed_prs,
        'opened_issues': open_issues,
        'closed_issues': closed_issues,
        'aggregated_stats': dict(aggregated_stats),
        'wartime_milady_ceo_summary': summary,
        'spec_links': spec_links
    }

    repo_folder = f'weekly_report/{repo}'
    week_folder = f'{repo_folder}/{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}'
    os.makedirs(week_folder, exist_ok=True)

    json_out = f"{week_folder}/data.json"
    with open(json_out, 'w') as jfile:
        json.dump(output_data, jfile, indent=4)
    print(f"Data saved to {json_out}")

    project_summaries.append(f"<strong>{repo_owner}/{repo}</strong>: " + " ".join(summary))

    # ---------- Color Generation ----------
    def generate_color(username):
        h = hashlib.md5(username.encode())
        return "#" + h.hexdigest()[:6]

    def calculate_average_color(image_url):
        try:
            r = requests.get(image_url)
            if r.status_code != 200:
                print(f"Warning: Failed to fetch image from {image_url}, status code: {r.status_code}")
                return "#00ffa0"  # Default color if image can't be fetched
            
            try:
                img = Image.open(io.BytesIO(r.content)).convert('RGB')
                px = list(img.getdata())
                n = len(px)
                avg = tuple(sum(x)//n for x in zip(*px))
                return "#{:02x}{:02x}{:02x}".format(*avg)
            except (PIL.UnidentifiedImageError, OSError, IOError) as e:
                print(f"Warning: Could not process image from {image_url}: {str(e)}")
                return "#00ffa0"  # Default color if image can't be processed
        except Exception as e:
            print(f"Warning: Error in calculate_average_color for {image_url}: {str(e)}")
            return "#00ffa0"  # Default fallback color
    
    try:
        logo_url = f"https://github.com/{repo_owner}.png"
        glow_color = calculate_average_color(logo_url)
    except Exception as e:
        print(f"Warning: Error getting organization logo color: {str(e)}")
        logo_url = f"https://github.com/{repo_owner}.png"  # Still set logo_url even if color extraction fails
        glow_color = "#00ffa0"  # Default color if anything goes wrong

    # ---------- Generate HTML ----------
    def generate_html(data):
        start_d = datetime.fromisoformat(data['start_date'])
        end_d = datetime.fromisoformat(data['end_date'])

        # human readable date range
        if start_d.year == end_d.year:
            if start_d.month == end_d.month:
                date_range = f"{start_d.strftime('%b %d')} - {end_d.strftime('%d, %Y')}"
            else:
                date_range = f"{start_d.strftime('%b %d')} - {end_d.strftime('%b %d, %Y')}"
        else:
            date_range = f"{start_d.strftime('%b %d, %Y')} - {end_d.strftime('%b %d, %Y')}"

        # Debug info about closed issues
        print(f"Generating HTML with {len(data.get('closed_issues', []))} closed issues")
        
        # Chart data
        sorted_dates = sorted(data['aggregated_stats'].keys())
        pr_closed_list = []
        issue_closed_list = []
        contributors_list = []
        labels_list = []
        for dstr in sorted_dates:
            dt_obj = datetime.strptime(dstr,"%Y-%m-%d")
            short_label = dt_obj.strftime("%m/%d")
            st = data['aggregated_stats'][dstr]
            pr_closed_list.append(st['prs_closed'])
            issue_closed_list.append(st['issues_closed'])
            contributors_list.append(st['contributors'])
            labels_list.append(short_label)

        # Summaries
        if data['wartime_milady_ceo_summary']:
            # Add "Summary:" to the first bullet point
            summary_lines = data['wartime_milady_ceo_summary'].copy()
            if summary_lines and len(summary_lines) > 0:
                summary_lines[0] = f"<strong>Summary:</strong> {summary_lines[0]}"
            
            # Format bullet points properly for HTML
            formatted_lines = []
            for line in summary_lines:
                # Remove markdown bullet points if they exist and wrap in HTML list items
                line = line.strip()
                if line.startswith('- '):
                    line = line[2:]
                elif line.startswith('* '):
                    line = line[2:]
                
                # Keep any existing HTML but ensure each line is a list item
                formatted_lines.append(f"<li>{line}</li>")
            
            # Join with newlines for proper HTML formatting (not <br> tags)
            wmc_summary = "\n".join(formatted_lines)
        else:
            wmc_summary = "<li>No summary available</li>"

        html = f"""<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
    <title>{repo_owner}/{repo} - Weekly Report: {date_range}</title>
            <link href="https://fonts.googleapis.com/css2?family=VT323&display=swap" rel="stylesheet">
            <style>
        :root {{
            --repo-color: #4CAF50;
            --glow-color: {glow_color}33; /* average color + alpha */
        }}
                body {{
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            background: 
                linear-gradient(45deg, rgba(0,0,0,0.02) 25%, transparent 25%),
                linear-gradient(-45deg, rgba(0,0,0,0.02) 25%, transparent 25%),
                linear-gradient(45deg, transparent 75%, rgba(0,0,0,0.02) 75%),
                linear-gradient(-45deg, transparent 75%, rgba(0,0,0,0.02) 75%);
                    background-size: 20px 20px;
            background-color: #f8f9fa;
            color: #333;
            font-family: 'VT323', monospace;
        }}
        .scoreboard {{
            max-width: 1200px;
            margin: 0 auto;
            background: #ffffff;
            border: 1px solid var(--glow-color);
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 6px 20px var(--glow-color);
        }}
        .header {{
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
        }}
        .repo-logo {{
            width: 80px;
            height: 80px;
            border-radius: 10px;
            object-fit: cover;
        }}
        .repo-info h1 {{
            font-size: 2.5em;
            margin: 0;
            color: #333;
        }}
        .stats-display {{
            background: rgba(0, 0, 0, 0.5);
            border: 2px solid var(--repo-color);
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 30px;
                    position: relative;
            overflow: hidden;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: inset 0 0 20px var(--glow-color);
        }}
        .stats-display::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--repo-color), transparent);
            box-shadow: 0 0 15px var(--glow-color);
        }}
        .stat-group {{
            display: flex;
            align-items: center;
            padding: 0 20px;
            position: relative;
        }}
        .stat-group:not(:last-child)::after {{
            content: '';
            position: absolute;
            right: 0;
            top: 50%;
            transform: translateY(-50%);
            width: 2px;
            height: 70%;
            background: var(--repo-color);
            box-shadow: 0 0 10px var(--glow-color);
        }}
        .stat-label {{
            font-size: 1.2em;
            color: #888;
            margin-right: 10px;
        }}
        .stat-value {{
            font-size: 2.5em;
            color: var(--repo-color);
            text-shadow: 0 0 10px var(--glow-color);
            font-weight: bold;
            min-width: 80px;
            text-align: right;
        }}
        .graph-container {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            border: 1px solid var(--repo-color);
            box-shadow: 0 0 10px var(--glow-color);
        }}
        .graph-container h2 {{
            margin-top: 0;
            text-shadow: 0 0 10px var(--glow-color);
        }}
        .chart-wrapper {{
            width: 100%;
            height: 300px;
        }}
        .summary-section {{
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            border: 1px solid var(--repo-color);
            box-shadow: 0 0 10px var(--glow-color);
        }}
        .summary-section h2 {{
            color: var(--repo-color);
            margin-top: 0;
            text-shadow: 0 0 10px var(--glow-color);
        }}
        .pr-tables {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .pr-table {{
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 20px;
            width: 100%;
            border: 1px solid var(--repo-color);
            box-shadow: 0 0 10px var(--glow-color);
        }}
        .pr-table h3 {{
            margin-top: 0;
            color: var(--repo-color);
            text-shadow: 0 0 10px var(--glow-color);
        }}
                table {{
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 0;
                }}
                th, td {{
            padding: 14px 12px;
                    text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        th {{
            color: #4CAF50;
            font-size: 1.1em;
        }}
        td {{
            vertical-align: top;
            color: #333;
        }}
        
        p {{
            color: #333;
        }}
        
        /* White color scheme version */
        .white-theme {{
            background-color: #ffffff;
            color: #333;
            border: 1px solid #e0e0e0;
            border-radius: 15px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
            margin-bottom: 24px;
            padding: 24px;
            transition: box-shadow 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .white-theme:hover {{
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.08);
        }}
        
        .white-theme h2, .white-theme h3 {{
            color: #333;
            text-shadow: none;
            margin-top: 0;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 12px;
            font-size: 1.4em;
        }}
        
        .white-stats-display {{
            display: flex;
            justify-content: space-around;
            background-color: #fff;
            background-image: linear-gradient(to bottom, rgba(0,0,0,0.02) 0%, rgba(0,0,0,0) 100%);
            border-radius: 15px;
            padding: 25px 15px;
            margin-bottom: 30px;
            border: 2px solid #e0e0e0;
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.08), inset 0 1px 3px rgba(255, 255, 255, 0.7);
            position: relative;
            overflow: hidden;
        }}
        
        .white-stats-display::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.8), transparent);
        }}
        
        .white-stat-group {{
            text-align: center;
            padding: 0 20px;
            position: relative;
            min-width: 18%;
        }}
        
        .white-stat-group:not(:last-child)::after {{
            content: '';
            position: absolute;
            right: 0;
            top: 50%;
            transform: translateY(-50%);
            width: 2px;
            height: 70%;
            background: linear-gradient(to bottom, transparent, #e0e0e0, transparent);
        }}
        
        .white-stat-label {{
            font-size: 1em;
            color: #666;
            margin-bottom: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-shadow: 0 1px 1px rgba(255, 255, 255, 0.7);
        }}
        
        .white-stat-value {{
            font-size: 2.6em;
            color: var(--repo-color);
            font-weight: bold;
            text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1), 0 0 10px rgba(76, 175, 80, 0.2);
            position: relative;
            display: inline-block;
            padding: 0 5px;
            transition: transform 0.2s, text-shadow 0.2s;
        }}
        
        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.03); }}
            100% {{ transform: scale(1); }}
        }}
        
        .white-stat-value:hover {{
            animation: pulse 1s infinite ease-in-out;
            text-shadow: 3px 3px 0px rgba(0, 0, 0, 0.15), 0 0 15px rgba(76, 175, 80, 0.3);
        }}
        
        /* Style table inside white-theme */
        .white-theme table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
        }}
        
        .white-theme th, .white-theme td {{
            padding: 14px 12px;
            text-align: left;
            border-bottom: 1px solid #eaeaea;
            position: relative;
        }}
        
        .white-theme th {{
            color: var(--repo-color);
            font-size: 1.1em;
            font-weight: 500;
            background-color: rgba(0, 0, 0, 0.02);
            border-bottom: 2px solid #e0e0e0;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        
        .white-theme td {{
            vertical-align: middle;
        }}
        
        .white-theme tbody tr:nth-child(even) {{
            background-color: rgba(0, 0, 0, 0.01);
        }}
        
        .white-theme tbody tr:hover {{
            background-color: rgba(76, 175, 80, 0.05);
        }}
        
        /* Create column effect */
        .white-theme th:not(:last-child), 
        .white-theme td:not(:last-child) {{
            border-right: 1px solid rgba(0, 0, 0, 0.03);
        }}
        
        /* First column styling */
        .white-theme th:first-child,
        .white-theme td:first-child {{
            border-left: 3px solid transparent;
        }}
        
        .white-theme tbody tr:hover td:first-child {{
            border-left: 3px solid var(--repo-color);
        }}
        
        /* User avatar and name styling */
        .user-info {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .user-avatar {{
            width: 24px;
            height: 24px;
            border-radius: 50%;
            object-fit: cover;
        }}
        
        .user-name {{
            font-weight: 500;
            text-decoration: none;
        }}
        
        /* Link styling */
        .white-theme a {{
            text-decoration: none;
            color: var(--repo-color);
            transition: color 0.2s, text-decoration 0.2s;
        }}
        
        .white-theme a:hover {{
            text-decoration: underline;
        }}
        
        /* Keep user name links in their assigned colors */
        .white-theme a.user-name {{
            text-decoration: none;
        }}
        
        .white-theme a.user-name:hover {{
            text-decoration: underline;
        }}
        
        /* Chart styling */
        .white-theme .chart-wrapper {{
            width: 100%;
            height: 300px;
            padding: 20px 0;
            margin: 0 auto;
        }}
        
        /* Breadcrumb navigation */
        .breadcrumb {{
            margin-bottom: 20px;
            font-size: 1em;
            color: #666;
            display: flex;
            align-items: center;
        }}
        
        .breadcrumb a {{
            color: var(--repo-color);
            text-decoration: none;
            display: flex;
            align-items: center;
        }}
        
        .breadcrumb a:hover {{
            text-decoration: underline;
        }}
        
        .breadcrumb .separator {{
            margin: 0 8px;
            color: #999;
        }}
        
        .breadcrumb svg {{
            width: 16px;
            height: 16px;
            margin-right: 5px;
        }}
    </style>
</head>
<body>
    <div class="scoreboard">
        <div class="breadcrumb">
            <a href="../../../index.html">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                    <polyline points="9 22 9 12 15 12 15 22"></polyline>
                </svg>
                Home
            </a>
            <span class="separator">/</span>
            <span>{repo_owner}</span>
            <span class="separator">/</span>
            <span>{repo}</span>
        </div>
        <div class="header">
            <img src="{logo_url}" alt="{repo_owner} logo" class="repo-logo">
            <div class="repo-info">
                <h1>{repo_owner}/{repo} - Weekly Report</h1>
                <p>Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            </div>
        </div>

        <!-- Stats Display -->
        <div class="white-stats-display">
            <div class="white-stat-group">
                <div class="white-stat-label">OPEN PRS</div>
                <div class="white-stat-value">{len(data['opened_prs'])}</div>
            </div>
            <div class="white-stat-group">
                <div class="white-stat-label">CLOSED PRS</div>
                <div class="white-stat-value">{len(data['closed_prs'])}</div>
            </div>
            <div class="white-stat-group">
                <div class="white-stat-label">AVG RESPONSE</div>
                <div class="white-stat-value">{
                    round(sum((pr.get('time_to_first_response') or 0) for pr in data['closed_prs']) / len(data['closed_prs']),1)
                    if data['closed_prs'] else "N/A"
                }h</div>
            </div>
            <div class="white-stat-group">
                <div class="white-stat-label">AVG LIFETIME</div>
                <div class="white-stat-value">{
                    round(sum(calculate_issue_to_pr_time(pr, data['closed_issues']) for pr in data['closed_prs']) / len(data['closed_prs']),1)
                    if data['closed_prs'] else "N/A"
                }h</div>
            </div>
        </div>

        <!-- Weekly Activity Graph -->
        <div class="white-theme">
            <h2>Weekly Activity</h2>
            <div class="chart-wrapper">
                <canvas id="weeklyGraph"></canvas>
            </div>
        </div>

        <!-- Summary -->
        <div class="white-theme">
            <h2>Summary</h2>
            <ul class="summary-list">
                {wmc_summary}
            </ul>
        </div>

        <!-- 4 Tables: PRs / Issues (Open / Closed) -->
        <div class="pr-tables">

            <!-- OPEN PRS -->
            <div class="white-theme">
                <h3>Open PRs</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Title</th>
                            <th>Author</th>
                            <th>Age</th>
                            <th>Comments</th>
                            <th>Reviews</th>
                            <th>Response Time</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        for pr in data['opened_prs']:
            dt_str = datetime.fromisoformat(pr['created_at'][:-1]).strftime("%b %d")
            pr_title = pr["title"]
            pr_number = pr["number"]
            pr_url = f"https://github.com/{repo_owner}/{repo}/pull/{pr_number}"
            pr_author = pr["user"]["login"]
            pr_avatar = pr["user"]["avatar_url"]
            author_url = f"https://github.com/{pr_author}"
            author_color = generate_retro_neon_color(pr_author)
            
            # Cache the comment and review counts to avoid multiple API calls
            if 'comment_count' not in pr:
                pr['comment_count'] = get_pr_comment_count(pr_number)
            if 'review_count' not in pr:
                pr['review_count'] = get_pr_review_count(pr_number)
                
            comments = pr['comment_count']
            reviews = pr['review_count']
            
            age = format_hours_or_days(pr['hours_open'])
            resp_h = pr.get('time_to_first_response')
            resp_str = f"{resp_h}h" if resp_h else "N/A"
            resp_color = get_response_time_color(resp_h)
            html += f"""
                        <tr>
                            <td style="white-space: nowrap;">{dt_str}</td>
                            <td><a href="{pr_url}" target="_blank">{pr_title}</a></td>
                            <td>
                                <div class="user-info">
                                    <img src="{pr_avatar}" alt="{pr_author}" class="user-avatar">
                                    <a href="{author_url}" target="_blank" class="user-name" style="color: {author_color}">@{pr_author}</a>
                                </div>
                            </td>
                            <td style="white-space: nowrap;">{age}</td>
                            <td>{comments}</td>
                            <td>{reviews}</td>
                            <td style="white-space: nowrap; color: {resp_color};">{resp_str}</td>
                        </tr>
            """

        html += """
                    </tbody>
                </table>
            </div>

            <!-- RECENTLY CLOSED PRS -->
            <div class="white-theme">
                <h3>Recently Closed PRs</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Title</th>
                            <th>Author</th>
                            <th>Duration</th>
                            <th>Comments</th>
                            <th>Reviews</th>
                            <th>Response Time</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        for pr in data['closed_prs']:
            dt_str = datetime.fromisoformat(pr['closed_at'][:-1]).strftime("%b %d")
            pr_title = pr["title"]
            pr_number = pr["number"]
            pr_url = f"https://github.com/{repo_owner}/{repo}/pull/{pr_number}"
            pr_author = pr["user"]["login"]
            pr_avatar = pr["user"]["avatar_url"]
            author_url = f"https://github.com/{pr_author}"
            author_color = generate_retro_neon_color(pr_author)
            
            # Cache the comment and review counts to avoid multiple API calls
            if 'comment_count' not in pr:
                pr['comment_count'] = get_pr_comment_count(pr_number)
            if 'review_count' not in pr:
                pr['review_count'] = get_pr_review_count(pr_number)
                
            comments = pr['comment_count']
            reviews = pr['review_count']
            
            dur_hrs = calculate_issue_to_pr_time(pr, data['closed_issues'])
            dur_str = format_hours_or_days(dur_hrs)
            resp_h = pr.get('time_to_first_response')
            resp_str = f"{resp_h}h" if resp_h else "N/A"
            resp_color = get_response_time_color(resp_h)
            html += f"""
                        <tr>
                            <td style="white-space: nowrap;">{dt_str}</td>
                            <td><a href="{pr_url}" target="_blank">{pr_title}</a></td>
                            <td>
                                <div class="user-info">
                                    <img src="{pr_avatar}" alt="{pr_author}" class="user-avatar">
                                    <a href="{author_url}" target="_blank" class="user-name" style="color: {author_color}">@{pr_author}</a>
                                </div>
                            </td>
                            <td style="white-space: nowrap;">{dur_str}</td>
                            <td>{comments}</td>
                            <td>{reviews}</td>
                            <td style="white-space: nowrap; color: {resp_color};">{resp_str}</td>
                        </tr>
            """

        html += """
                    </tbody>
                </table>
            </div>

            <!-- OPEN ISSUES -->
            <div class="white-theme">
                <h3>Open Issues</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Title</th>
                            <th>Author</th>
                            <th>Age</th>
                            <th>Comments</th>
                            <th>Priority</th>
                            <th>Response Time</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        for iss_ in data['opened_issues']:
            dt_str = datetime.fromisoformat(iss_['created_at'][:-1]).strftime("%b %d")
            iss_title = iss_["title"]
            iss_number = iss_["number"]
            iss_url = f"https://github.com/{repo_owner}/{repo}/issues/{iss_number}"
            iss_author = iss_["user"]["login"]
            iss_avatar = iss_["user"]["avatar_url"]
            author_url = f"https://github.com/{iss_author}"
            author_color = generate_retro_neon_color(iss_author)
            age = format_hours_or_days(iss_['hours_open'])
            comments = "N/A"
            priority = "N/A"
            resp_h = iss_.get('time_to_first_response')
            resp_str = f"{resp_h}h" if resp_h else "N/A"
            resp_color = get_response_time_color(resp_h)
            html += f"""
                        <tr>
                            <td style="white-space: nowrap;">{dt_str}</td>
                            <td><a href="{iss_url}" target="_blank">{iss_title}</a></td>
                            <td>
                                <div class="user-info">
                                    <img src="{iss_avatar}" alt="{iss_author}" class="user-avatar">
                                    <a href="{author_url}" target="_blank" class="user-name" style="color: {author_color}">@{iss_author}</a>
                                </div>
                            </td>
                            <td style="white-space: nowrap;">{age}</td>
                            <td>{comments}</td>
                            <td>{priority}</td>
                            <td style="white-space: nowrap; color: {resp_color};">{resp_str}</td>
                        </tr>
            """

        html += """
                    </tbody>
                </table>
            </div>

            <!-- RECENTLY CLOSED ISSUES -->
            <div class="white-theme">
                <h3>Recently Closed Issues</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Title</th>
                            <th>Author</th>
                            <th>Duration</th>
                            <th>Comments</th>
                            <th>Resolution</th>
                            <th>Response Time</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        # Debug: Print first few closed issues
        if 'closed_issues' in data and data['closed_issues']:
            for idx, iss_ in enumerate(data['closed_issues'][:3]):
                print(f"Closed issue {idx+1} title: {iss_.get('title', 'No title')}")
        else:
            print("No closed issues found in data")
        
        # Ensure we're iterating over a list even if closed_issues is missing or None
        for iss_ in data.get('closed_issues', []):
            if not iss_.get('closed_at'):
                continue
                
            dt_str = datetime.fromisoformat(iss_['closed_at'][:-1]).strftime("%b %d")
            iss_title = iss_["title"]
            iss_number = iss_["number"]
            iss_url = f"https://github.com/{repo_owner}/{repo}/issues/{iss_number}"
            iss_author = iss_["user"]["login"]
            iss_avatar = iss_["user"]["avatar_url"]
            author_url = f"https://github.com/{iss_author}"
            author_color = generate_retro_neon_color(iss_author)
            created_ts = datetime.fromisoformat(iss_["created_at"][:-1])
            closed_ts = datetime.fromisoformat(iss_["closed_at"][:-1])
            dur_hrs = math.ceil((closed_ts - created_ts).total_seconds()/3600)
            dur_str = format_hours_or_days(dur_hrs)
            comments = iss_.get("comments", "N/A")
            resolution = "N/A"
            resp_h = iss_.get('time_to_first_response')
            resp_str = f"{resp_h}h" if resp_h else "N/A"
            resp_color = get_response_time_color(resp_h)
            html += f"""
                        <tr>
                            <td style="white-space: nowrap;">{dt_str}</td>
                            <td><a href="{iss_url}" target="_blank">{iss_title}</a></td>
                            <td>
                                <div class="user-info">
                                    <img src="{iss_avatar}" alt="{iss_author}" class="user-avatar">
                                    <a href="{author_url}" target="_blank" class="user-name" style="color: {author_color}">@{iss_author}</a>
                                </div>
                            </td>
                            <td style="white-space: nowrap;">{dur_str}</td>
                            <td>{comments}</td>
                            <td>{resolution}</td>
                            <td style="white-space: nowrap; color: {resp_color};">{resp_str}</td>
                        </tr>
            """

        # Add an empty state message if no closed issues
        if not data.get('closed_issues'):
            html += """
                        <tr>
                            <td colspan="7" style="text-align: center; padding: 20px;">No issues were closed during this period</td>
                        </tr>
            """

        html += """
                    </tbody>
                </table>
            </div>
        </div>
        """

        # Associated Specs
        if data['spec_links']:
            html += """
            <div class="white-theme">
                <h3>Associated Specifications</h3>
                <ul>
            """
            for link in data['spec_links']:
                html += f'<li><a href="{link}" target="_blank">{link}</a></li>'
            html += """
                </ul>
            </div>
            """

        html += f"""
    </div><!-- /scoreboard -->

    <!-- Chart.js for the Weekly Activity chart -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script>
        const ctx = document.getElementById('weeklyGraph').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
                    data: {{
                labels: {labels_list},
                        datasets: [
                            {{
                                label: 'PRs Closed',
                                data: {pr_closed_list},
                                borderColor: 'rgba(255, 99, 132, 1)',
                                backgroundColor: 'rgba(255, 99, 132, 0.1)',
                                borderWidth: 3,
                                tension: 0.4,
                                fill: true,
                                pointRadius: 4,
                                pointHoverRadius: 6
                            }},
                            {{
                                label: 'Issues Closed',
                                data: {issue_closed_list},
                                borderColor: 'rgba(54, 162, 235, 1)',
                                backgroundColor: 'rgba(54, 162, 235, 0.1)',
                                borderWidth: 3,
                                tension: 0.4,
                                fill: true,
                                pointRadius: 4,
                                pointHoverRadius: 6
                            }},
                            {{
                                label: 'Contributors',
                                data: {contributors_list},
                                borderColor: 'rgba(75, 192, 192, 1)',
                                backgroundColor: 'rgba(75, 192, 192, 0.1)',
                                borderWidth: 3,
                                tension: 0.4,
                                fill: true,
                                pointRadius: 4,
                                pointHoverRadius: 6
                            }}
                        ]
                    }},
                    options: {{
                responsive: true,
                maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                position: 'top',
                                labels: {{
                                    boxWidth: 15,
                                    padding: 15,
                                    font: {{
                                        size: 12
                                    }}
                                }}
                            }},
                            tooltip: {{
                                backgroundColor: 'rgba(0, 0, 0, 0.7)',
                                padding: 10,
                                cornerRadius: 4,
                                titleFont: {{
                                    size: 14
                                }},
                                bodyFont: {{
                                    size: 14
                                }}
                            }}
                        }},
                        animation: {{
                            duration: 2000,
                            easing: 'easeOutQuart'
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                grid: {{
                                    color: 'rgba(0, 0, 0, 0.05)'
                                }}
                            }},
                            x: {{
                                grid: {{
                                    display: false
                                }}
                            }}
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
"""
        return html

    final_html = generate_html(output_data)
    out_html = f"{week_folder}/data.html"
    with open(out_html, 'w') as hf:
        hf.write(final_html)
    print(f"HTML page saved to {out_html}")

    print(f"🎉 Finished processing for {repo_owner}/{repo} 🎉\n")
    time.sleep(5)  # small delay to avoid hitting rate limits quickly
    
# ====================== Ecosystem summary ========================
async def generate_ecosystem_summary(project_summaries):
    combined = '\n'.join(project_summaries)
    prompt = f"""
    Please Summarize this context:

    [ Paste the content you want to summarize]

    {combined}

    Write in simple language

    Summarize Format: Bullet points

    Tone:
    Primary Tone - Helpful and Informative
    Secondary Tone - Trustworthy and Approachable

    Perplexity
    Burstiness: Ensure heterogeneous paragraphs. Ensure heterogeneous sentence lengths.
    Unfluffing: Do not include fluff.

    Target Audience: Developers.
    """
    try:
        response = await aclient.chat.completions.create(
            model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150,
        n=1,
        stop=None,
            temperature=0.5
        )
        return response.choices[0].message.content.strip().split('\n')
    except OpenAIError as e:
        print(f"Error generating ecosystem summary: {e}")
        return []

ecosystem_summary = asyncio.run(generate_ecosystem_summary(project_summaries))
generate_index_html(ecosystem_summary)