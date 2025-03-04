from pyrogram import Client
from openai import OpenAI
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
from collections import Counter
import pytz
import sys
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
import re
import json
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Define your Telegram and OpenAI credentials
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
# Channel ID now accepts comma-separated list of channel IDs
TELEGRAM_CHANNEL_IDS = [id.strip() for id in os.getenv("TELEGRAM_CHANNEL_IDS", "").split(",") if id.strip()]
OPENAI_API_KEY = os.getenv("OPENAI_KEY")

DAYS_TO_FETCH = 7  # Default to last 7 days of messages
MESSAGE_LIMIT = 2000  # Significantly increased to get more messages

# Define the output directory for reports
REPORTS_DIR = "reports"

# Ensure the reports directory exists
os.makedirs(REPORTS_DIR, exist_ok=True)

# Initialize list to store all report filenames
all_report_files = []

# First, let's list all available chats
with Client("session_name", api_id=TELEGRAM_API_ID, api_hash=TELEGRAM_API_HASH) as app:
    print("Listing all available dialogs (chats):")
    print("ID | TYPE | TITLE")
    print("-" * 50)
    
    for dialog in app.get_dialogs():
        chat = dialog.chat
        chat_type = chat.type.name
        chat_title = chat.title or chat.first_name or "Unknown"
        print(f"{chat.id} | {chat_type} | {chat_title}")
    
    print("-" * 50)
    
    if not TELEGRAM_CHANNEL_IDS:
        print("No channel IDs specified. Please set the TELEGRAM_CHANNEL_IDS environment variable.")
    else:
        print(f"Found {len(TELEGRAM_CHANNEL_IDS)} channel ID(s) to process: {', '.join(TELEGRAM_CHANNEL_IDS)}")
    
    # Process each channel ID
    for channel_id in TELEGRAM_CHANNEL_IDS:
        print(f"\n{'=' * 50}")
        print(f"Processing channel ID: {channel_id}")
        print(f"{'=' * 50}")
        
        # Only try to get chat history if a chat ID is provided
        try:
            print(f"Attempting to fetch messages from: {channel_id}")
            
            # Get chat information
            chat = app.get_chat(channel_id)
            chat_title = chat.title or chat.first_name or "Unknown Chat"
            chat_id_formatted = str(chat.id).replace("-", "n") # Make safe for filenames
            print(f"Found chat: {chat_title}")
            
            # Get end date (now) and start date (7 days ago)
            end_date = datetime.now(pytz.UTC)
            start_date = end_date - timedelta(days=DAYS_TO_FETCH)
            date_range = f"{start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')} UTC"
            
            print(f"Fetching messages from: {date_range}")
            
            # Stats counters
            messages = []
            participants = set()
            daily_message_count = defaultdict(int)
            participant_days = defaultdict(set)
            
            # Progress tracking
            print(f"Fetching up to {MESSAGE_LIMIT} messages... this may take a while.")
            msg_counter = 0
            filtered_counter = 0
            
            # Create a list to store raw message data for JSON export
            raw_messages = []
            
            # Fetch messages with increased limit
            for message in app.get_chat_history(channel_id, limit=MESSAGE_LIMIT):
                msg_counter += 1
                
                # Show progress
                if msg_counter % 100 == 0:
                    print(f"Processed {msg_counter} messages, collected {len(messages)} in time range...")
                
                # Convert message date to UTC for consistent comparison
                message_date = message.date.replace(tzinfo=pytz.UTC)
                
                # Store raw message data for JSON export
                message_dict = {
                    'id': message.id,
                    'date': message_date.strftime('%Y-%m-%d %H:%M:%S %Z'),
                    'timestamp': int(message_date.timestamp()),
                    'from_id': str(message.from_user.id) if message.from_user else None,
                    'text': message.text or message.caption or "",
                    'reply_to_msg_id': message.reply_to_message_id if hasattr(message, 'reply_to_message_id') else None,
                }
                
                # Add sender info if available
                if message.from_user:
                    if hasattr(message.from_user, 'username') and message.from_user.username:
                        message_dict['username'] = message.from_user.username
                    if hasattr(message.from_user, 'first_name') and message.from_user.first_name:
                        message_dict['first_name'] = message.from_user.first_name
                    if hasattr(message.from_user, 'last_name') and message.from_user.last_name:
                        message_dict['last_name'] = message.from_user.last_name
                
                # Add media type info if present
                message_dict['has_media'] = False
                for media_type in ['photo', 'video', 'document', 'audio', 'sticker', 'animation']:
                    if hasattr(message, media_type) and getattr(message, media_type) is not None:
                        message_dict['has_media'] = True
                        message_dict['media_type'] = media_type
                        break
                
                raw_messages.append(message_dict)
                
                # Skip messages before our date range
                if message_date < start_date:
                    filtered_counter += 1
                    continue
                
                # Skip empty messages
                if not (message.text or message.caption):
                    continue
                
                # Track daily message counts
                day_str = message_date.strftime('%Y-%m-%d')
                daily_message_count[day_str] += 1
                
                # Track participant activity by day
                if message.from_user:
                    sender_id = message.from_user.id
                    participants.add(sender_id)
                    participant_days[sender_id].add(day_str)
                
                # Only collect text messages for summarization
                if message.text or message.caption:
                    message_text = message.text or message.caption
                    sender_name = message.from_user.first_name if message.from_user else "Unknown"
                    messages.append({
                        'id': message.id,
                        'date': message_date.strftime('%Y-%m-%d %H:%M:%S'),
                        'sender_id': message.from_user.id if message.from_user else 'Unknown',
                        'sender_name': sender_name,
                        'text': message_text
                    })
            
            # Count unique participants
            unique_participants = len(participants)
            
            print(f"Total messages processed: {msg_counter}")
            print(f"Messages filtered out (before {start_date.date()}): {filtered_counter}")
            print(f"Successfully collected {len(messages)} messages from {unique_participants} participants")
            print(f"Messages by day: {dict(daily_message_count)}")
            
            # Export raw messages to JSON
            json_filename = f"{chat_title.replace(' ', '_')}_{chat_id_formatted}_raw.json"
            json_filepath = os.path.join(REPORTS_DIR, json_filename)
            
            # Add metadata to the JSON export
            json_data = {
                'metadata': {
                    'chat_title': chat_title,
                    'chat_id': str(chat.id),
                    'date_range': date_range,
                    'export_date': datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S %Z'),
                    'message_count': len(messages),
                    'total_processed': msg_counter,
                    'total_filtered_out': filtered_counter
                },
                'messages': raw_messages
            }
            
            # Write JSON data to file
            with open(json_filepath, 'w', encoding='utf-8') as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=2)
            
            print(f"Raw message data exported to: {json_filepath}")
            
            # Format the date range for display
            date_range = f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
            
            # Always generate a report, even if no messages found
            formatted_summary = ""
            weekly_focus_html = ""
            bullet_points_html = ""
            decisions_html = ""
            debates_html = ""
            chart_labels = []
            daily_message_counts = []
            daily_participant_counts = []
            
            if messages:
                # Format messages for the prompt
                formatted_messages = []
                for msg in messages:
                    formatted_messages.append(f"[{msg['date']}] {msg['sender_name']}: {msg['text']}")
                
                message_text = "\n".join(formatted_messages)
                
                # Generate summary using OpenAI
                openai_client = OpenAI(api_key=OPENAI_API_KEY)
                
                # Special handling for L2 Interop Working Group
                l2_interop_context = ""
                if "L2 Interop Working Group" in chat_title:
                    l2_interop_context = """
                    IMPORTANT REPOSITORY CONTEXT:
                    
                    Ethereum-wide Interoperability
                    Welcome to the L2 Interop repository under the Ethereum organization. This repository serves as the central hub for Ethereum-wide interoperability efforts, providing a single source of truth and collaboration space for all teams and contributors across the Ethereum ecosystem.

                    Overview
                    Our repository is organized into two main areas:

                    docs/: Contains high-level documentation, onboarding guides, roadmaps, meeting notes, and user-friendly reference material.
                    specs/: Contains detailed technical specifications, standards, and protocol definitions.
                    Discussions and collaborations in this repository focus on delivering concrete results. Expected outputs include prototypes, implementation references, and contributions to protocol improvements (e.g., EIPs, RIPs) or proposals for new or existing standards (e.g., ERCs, CAIPs).

                    Getting Started
                    System Properties
                    The most important file of this repository is: Properties. It lists and explains the system properties that guide and constraint the current design.

                    Explore the Documentation
                    Visit the docs/ directory for a comprehensive guide on the project, including architecture overviews and getting started instructions.

                    Review the Specifications
                    Check the specs/ directory for technical details, protocol specifications, and design decisions that underpin the interoperability efforts.

                    Contributing
                    We welcome contributions from the community! Please take a moment to review our Contribution Guidelines before getting started. Your input is valuable, and we aim to maintain a collaborative and inclusive environment for everyone.

                    Collaboration & Communication
                    GitHub Issues & Discussions: Use GitHub Issues for starting conversations, feature requests, and questions.
                    Project Boards: Stay updated on progress and upcoming milestones by reviewing our project boards.
                    
                    When analyzing the chat messages, please keep this repository context in mind.
                    """
                
                summary_prompt = f"""
                You are an open source software project manager which has many years of experience in the Ethereum Layer 1 core developer process, and now you are working on tracking Layer 2 core development. Your goal is to create weekly summaries of discussions happening on telegram. For each weekly summary, return a one sentence focus of the week, then return a 3 bullet point summary of the week, then return any decisions made related to those discussions, and lastly, generate a list of topics that were debated and list out the two sides of the debate. be careful to not speak vaguely as this will be consumed by participants of the chat themself to refresh themselves. be sure to use exact technical terms as theyre used not to confuse things. be careful to not make up discussions or debates if none happened as some weeks wont have discussions. And for context: {l2_interop_context}
                
                CONVERSATION:
                {message_text}
                """
                
                print("Sending chat to OpenAI for summarization...")
                response = openai_client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes conversations clearly and concisely. Always structure your response with clear headings and organization."},
                        {"role": "user", "content": summary_prompt}
                    ],
                    max_tokens=1000,  # Increased for more detailed summaries
                    temperature=0.3
                )
                
                # Extract summary
                summary = response.choices[0].message.content.strip()
                print("Summary received from OpenAI")
                
                # Process the summary to extract sections and convert line breaks to HTML
                # Initialize section trackers
                current_section = None
                weekly_focus = ""
                bullet_points = []
                decisions_made = []
                debate_topics = []
                
                for line in summary.split('\n'):
                    line_lower = line.lower()
                    
                    # Detect section headers
                    if "weekly focus" in line_lower or "focus of the week" in line_lower:
                        current_section = "focus"
                        continue
                    elif "bullet point" in line_lower or "summary of the week" in line_lower:
                        current_section = "bullet_points"
                        continue
                    elif "decision" in line_lower:
                        current_section = "decisions"
                        continue
                    elif "debate" in line_lower or "topics that were debated" in line_lower:
                        current_section = "debates"
                        continue
                    
                    # Add line to appropriate section if not empty
                    if line.strip():
                        if current_section == "focus":
                            weekly_focus = line.strip()
                        elif current_section == "bullet_points":
                            if line.strip().startswith(('-', '•', '*', '1.', '2.', '3.')):
                                bullet_points.append(line.strip())
                        elif current_section == "decisions":
                            if line.strip().startswith(('-', '•', '*')):
                                decisions_made.append(line.strip())
                        elif current_section == "debates":
                            if line.strip().startswith(('-', '•', '*')):
                                debate_topics.append(line.strip())
                
                # Format each section as HTML
                weekly_focus_html = f"<p class='weekly-focus'>{weekly_focus}</p>" if weekly_focus else "<p>No specific focus identified for this week.</p>"
                
                bullet_points_html = ""
                if bullet_points:
                    for point in bullet_points:
                        bullet_points_html += f"<li class='bullet-point'>{point}</li>\n"
                else:
                    bullet_points_html = "<li>No significant discussion points identified for this week.</li>"
                
                decisions_html = ""
                if decisions_made:
                    for decision in decisions_made:
                        decisions_html += f"<li class='decision-item'>{decision}</li>\n"
                else:
                    decisions_html = "<li>No decisions were made this week.</li>"
                
                debates_html = ""
                if debate_topics:
                    for debate in debate_topics:
                        debates_html += f"<li class='debate-item'>{debate}</li>\n"
                else:
                    debates_html = "<li>No significant debates occurred this week.</li>"
                
                # Generate activity chart data
                sorted_dates = sorted(daily_message_count.keys())
                daily_message_counts = [daily_message_count[d] for d in sorted_dates]
                daily_participant_counts = [len([id for id in participant_days if day_str in participant_days[id]]) for day_str in sorted_dates]
                chart_labels = [datetime.strptime(d, '%Y-%m-%d').strftime('%m/%d') for d in sorted_dates]
            else:
                # If no messages, create empty placeholder summary
                weekly_focus_html = "<p>No messages found in this chat during the specified time period.</p>"
                bullet_points_html = "<li>No significant discussion points identified for this week.</li>"
                decisions_html = "<li>No decisions were made this week.</li>"
                debates_html = "<li>No significant debates occurred this week.</li>"
                
                # Add at least one day to the chart for proper rendering
                today = datetime.now().strftime('%Y-%m-%d')
                chart_labels = [datetime.now().strftime('%m/%d')]
                daily_message_counts = [0]
                daily_participant_counts = [0]
                print(f"No text messages found in the specified time period for chat: {chat_title}")
                print("Generating empty report with zero values.")
            
            total_messages = len(messages)
            
            # Generate HTML with styling inspired by fetch_github_data.py
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Chat Summary - {chat_title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
            max-width: 1200px;
            margin: 0 auto;
            position: relative;
            z-index: 1;
        }}
        
        .header {{
            display: flex;
            align-items: center;
            justify-content: flex-start;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid rgba(0, 255, 160, 0.3);
        }}
        
        .header h1 {{
            font-size: 24px;
            text-transform: uppercase;
            letter-spacing: 2px;
            flex-grow: 1;
        }}
        
        .date-range {{
            font-size: 18px;
            opacity: 0.7;
            margin-bottom: 5px;
        }}
        
        .stats-panel {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-box {{
            flex: 1;
            min-width: 200px;
            background-color: var(--panel);
            border: 1px solid rgba(0, 255, 160, 0.3);
            border-radius: 10px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            backdrop-filter: blur(5px);
            -webkit-backdrop-filter: blur(5px);
        }}
        
        .stat-value {{
            font-size: 32px;
            margin: 10px 0;
        }}
        
        .stat-label {{
            font-size: 14px;
            text-transform: uppercase;
            opacity: 0.7;
            letter-spacing: 1px;
        }}
        
        .summary {{
            background-color: var(--panel);
            border: 1px solid rgba(0, 255, 160, 0.3);
            border-radius: 10px;
            padding: 30px;
            margin-bottom: 30px;
            backdrop-filter: blur(5px);
            -webkit-backdrop-filter: blur(5px);
        }}
        
        .summary h2 {{
            color: var(--secondary);
            margin-bottom: 20px;
            font-size: 20px;
            letter-spacing: 1px;
        }}
        
        .summary h3 {{
            color: var(--warning);
            margin-top: 20px;
            margin-bottom: 15px;
            font-size: 18px;
            letter-spacing: 1px;
        }}
        
        .summary p {{
            line-height: 1.6;
            margin-bottom: 15px;
            font-size: 16px;
        }}
        
        .weekly-focus {{
            font-size: 1.2em;
            border-left: 3px solid var(--warning);
            padding-left: 15px;
            margin-bottom: 25px;
            color: var(--warning);
        }}
        
        .bullet-point {{
            margin-bottom: 15px;
            padding-left: 20px;
            position: relative;
        }}
        
        .bullet-point::before {{
            content: "•";
            position: absolute;
            left: 0;
            color: var(--warning);
        }}
        
        .decision-item {{
            padding-left: 15px;
            border-left: 3px solid var(--secondary);
            margin-bottom: 15px;
        }}
        
        .debate-item {{
            padding-left: 15px;
            border-left: 3px solid var(--primary);
            margin-bottom: 20px;
        }}
        
        .section-header {{
            color: var(--terminal-orange);
            margin-top: 30px;
            margin-bottom: 20px;
            font-size: 22px;
            letter-spacing: 2px;
            text-transform: uppercase;
            border-bottom: 1px dashed var(--terminal-orange);
            padding-bottom: 10px;
        }}
        
        .chart-container {{
            background-color: var(--panel);
            border: 1px solid rgba(0, 255, 160, 0.3);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            height: 400px;
            position: relative;
            backdrop-filter: blur(5px);
            -webkit-backdrop-filter: blur(5px);
        }}
        
        .credits {{
            text-align: center;
            margin-top: 50px;
            font-size: 12px;
            opacity: 0.5;
        }}
        
        .panel-title {{
            margin-bottom: 15px;
            font-size: 18px;
            letter-spacing: 1px;
            color: var(--terminal-orange);
        }}
        
        .most-active {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 20px;
        }}
        
        .user-card {{
            background-color: rgba(0, 255, 160, 0.1);
            border-radius: 8px;
            padding: 10px 15px;
            min-width: 130px;
        }}
        
        .user-name {{
            color: var(--warning);
            font-size: 14px;
            margin-bottom: 5px;
        }}
        
        .message-count {{
            font-size: 20px;
        }}
        
        @media (max-width: 768px) {{
            .stat-box {{
                min-width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>NERV TELEGRAM ANALYSIS SYSTEM</h1>
        </div>
        
        <div class="date-range">ANALYSIS PERIOD: {date_range}</div>
        
        <div class="stats-panel">
            <div class="stat-box">
                <div class="stat-label">CHAT TITLE</div>
                <div class="stat-value" style="font-size: 24px;">{chat_title}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">TOTAL MESSAGES</div>
                <div class="stat-value">{total_messages}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">UNIQUE PARTICIPANTS</div>
                <div class="stat-value">{unique_participants}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">ANALYSIS COMPLETED</div>
                <div class="stat-value" style="font-size: 20px;">{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="panel-title">ACTIVITY ANALYSIS</div>
            <canvas id="activityChart"></canvas>
        </div>
        
        <div class="summary">
            <div class="panel-title">WEEKLY ANALYSIS</div>
            
            <div class="section-header">WEEKLY FOCUS</div>
            {weekly_focus_html}
            
            <div class="section-header">KEY POINTS</div>
            <ul>
                {bullet_points_html}
            </ul>
            
            <div class="section-header">DECISIONS MADE</div>
            <ul>
                {decisions_html}
            </ul>
            
            <div class="section-header">TOPICS DEBATED</div>
            <ul>
                {debates_html}
            </ul>
        </div>
        
        <div class="credits">
            GENERATED BY NERV TELEGRAM ANALYSIS SYSTEM • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
    
    <script>
        // Activity Chart
        var ctx = document.getElementById('activityChart').getContext('2d');
        var activityChart = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {chart_labels},
                datasets: [
                    {{
                        label: 'Messages',
                        data: {daily_message_counts},
                        borderColor: '#00ffa0',
                        backgroundColor: 'rgba(0, 255, 160, 0.1)',
                        borderWidth: 2,
                        tension: 0.2,
                        fill: true
                    }},
                    {{
                        label: 'Participants',
                        data: {daily_participant_counts},
                        borderColor: '#ff5000',
                        backgroundColor: 'rgba(255, 80, 0, 0.1)',
                        borderWidth: 2,
                        tension: 0.2,
                        fill: true
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    x: {{
                        grid: {{
                            color: 'rgba(0, 255, 160, 0.1)'
                        }},
                        ticks: {{
                            color: '#00ffa0'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        grid: {{
                            color: 'rgba(0, 255, 160, 0.1)'
                        }},
                        ticks: {{
                            color: '#00ffa0'
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        labels: {{
                            color: '#00ffa0'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
            """
            
            # Create a unique filename based on chat title and ID
            report_filename = f"{chat_title.replace(' ', '_')}_{chat_id_formatted}.html"
            report_path = os.path.join(REPORTS_DIR, report_filename)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"Enhanced summary with statistics saved to {report_path}")

            # Add this report to our list for the index
            all_report_files.append({
                'filename': report_filename,
                'title': chat_title,
                'message_count': total_messages,
                'participant_count': unique_participants,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            print(f"Added report to index. Total reports so far: {len(all_report_files)}")
        except Exception as e:
            print(f"Error processing channel {channel_id}: {e}")

# Debug: Check if we have collected any reports
print(f"Total reports collected for index: {len(all_report_files)}")
for i, report in enumerate(all_report_files):
    print(f"Report {i+1}: {report['title']} - {report['filename']}")

# After processing all chats, generate the main index page with improved styling
index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NERV Telegram Analysis Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #00ffa0;
            --secondary: #ff5000;
            --warning: #ffcf00;
            --background: #0a0a0a;
            --panel: #101418;
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
            max-width: 1200px;
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
        
        .report-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .report-card {
            background: rgba(10, 10, 10, 0.5);
            border: 1px solid var(--primary);
            border-radius: 16px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }
        
        .report-card:hover {
            box-shadow: 0 0 20px rgba(0, 255, 160, 0.3);
            transform: translateY(-5px);
        }
        
        .report-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--primary);
            border-radius: 16px 16px 0 0;
        }
        
        .report-title {
            font-size: 1.3em;
            letter-spacing: 1px;
            margin-bottom: 15px;
            border-bottom: 1px dashed var(--primary);
            padding-bottom: 10px;
        }
        
        .report-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 20px;
            font-size: 0.9em;
        }
        
        .report-stat {
            display: flex;
            justify-content: space-between;
        }
        
        .report-stat-label {
            opacity: 0.7;
        }
        
        .report-stat-value {
            font-weight: bold;
            text-shadow: 0 0 5px var(--primary);
        }
        
        .report-date {
            font-size: 0.8em;
            text-align: right;
            opacity: 0.7;
            margin-bottom: 15px;
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
        
        .empty-message {
            text-align: center;
            padding: 40px 20px;
            font-size: 1.2em;
            opacity: 0.7;
            letter-spacing: 2px;
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
            <div class="nerv-subtitle">TELEGRAM ANALYSIS DASHBOARD</div>
        </div>
        
        <div class="report-grid">
"""

# Add each report to the grid
if all_report_files:
    for report in all_report_files:
        index_html += f"""
        <div class="report-card">
            <div class="report-title">{report['title']}</div>
            <div class="report-date">Generated: {report['date']}</div>
            <div class="report-stats">
                <div class="report-stat">
                    <div class="report-stat-label">MESSAGES:</div>
                    <div class="report-stat-value">{report['message_count']}</div>
                </div>
                <div class="report-stat">
                    <div class="report-stat-label">PARTICIPANTS:</div>
                    <div class="report-stat-value">{report['participant_count']}</div>
                </div>
            </div>
            <a href="{REPORTS_DIR}/{report['filename']}" class="eva-button">View Report</a>
        </div>
        """
else:
    index_html += """
        <div class="empty-message">
            No reports have been generated yet.
        </div>
    """

index_html += """
        </div>
        
        <footer>
            NERV TELEGRAM ANALYSIS SYSTEM v2.0 - Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
        </footer>
    </div>
</body>
</html>
"""

# Write the index HTML file
with open("telegram_reports_index.html", "w", encoding="utf-8") as f:
    f.write(index_html)
print("Index page created: telegram_reports_index.html") 