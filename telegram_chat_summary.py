from pyrogram import Client
from openai import OpenAI
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
from collections import Counter
import pytz

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
            end_date = datetime.now()
            start_date = end_date - timedelta(days=DAYS_TO_FETCH)
            
            print(f"Fetching messages from {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Stats counters
            messages = []
            participants = set()
            message_count_by_day = Counter()
            participant_count_by_day = {}
            
            # Track messages by day
            current_day = None
            day_participants = set()
            
            # Progress tracking
            print(f"Fetching up to {MESSAGE_LIMIT} messages... this may take a while.")
            msg_counter = 0
            filtered_counter = 0
            
            # Fetch messages with increased limit
            for message in app.get_chat_history(channel_id, limit=MESSAGE_LIMIT):
                msg_counter += 1
                
                # Show progress
                if msg_counter % 100 == 0:
                    print(f"Processed {msg_counter} messages, collected {len(messages)} in time range...")
                
                # Skip messages before our date range - convert to UTC for consistent comparison
                message_date = message.date.replace(tzinfo=pytz.UTC)
                start_date_utc = start_date.replace(tzinfo=pytz.UTC)
                
                if message_date < start_date_utc:
                    filtered_counter += 1
                    continue
                    
                # Check if we're on a new day
                message_day = message_date.strftime('%Y-%m-%d')
                if message_day != current_day:
                    if current_day is not None:
                        # Save the participants for the previous day
                        participant_count_by_day[current_day] = len(day_participants)
                    # Reset for new day
                    current_day = message_day
                    day_participants = set()
                
                # Count this message for the day
                message_count_by_day[message_day] += 1
                
                # Track participants
                if message.from_user:
                    sender_id = message.from_user.id
                    participants.add(sender_id)
                    day_participants.add(sender_id)
                
                # Only collect text messages for summarization
                if message.text:
                    sender_name = message.from_user.first_name if message.from_user else "Unknown"
                    messages.append({
                        'id': message.id,
                        'date': message_date.strftime('%Y-%m-%d %H:%M:%S'),
                        'sender_id': message.from_user.id if message.from_user else 'Unknown',
                        'sender_name': sender_name,
                        'text': message.text
                    })
            
            # Save the last day's participants
            if current_day is not None:
                participant_count_by_day[current_day] = len(day_participants)
            
            # Stats calculations
            total_messages = len(messages)
            unique_participants = len(participants)
            
            print(f"Total messages processed: {msg_counter}")
            print(f"Messages filtered out (before {start_date.date()}): {filtered_counter}")
            print(f"Successfully collected {total_messages} messages from {unique_participants} participants")
            print(f"Messages by day: {dict(message_count_by_day)}")
            
            # Format the date range
            date_range = f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
            
            # Always generate a report, even if no messages found
            formatted_summary = ""
            core_themes_html = ""
            decisions_html = ""
            general_summary_html = ""
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
                
                summary_prompt = f"""
                Summarize the following Telegram chat conversation from the past week. 
                Your summary must include these specific sections:
                
                1. THREE CORE THEMES: Identify and list exactly 3 main themes/topics of discussion, even if there were more.
                   For each theme, provide a brief description and relevant details.
                
                2. DECISIONS MADE: Explicitly list any decisions that were made during the discussions.
                   Format each decision clearly with bullet points. If no clear decisions were made, state that.
                
                3. GENERAL SUMMARY: Organize the rest of the summary by topics and include timestamps for key moments.
                
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
                core_themes_lines = []
                decisions_lines = []
                general_summary_lines = []
                
                for line in summary.split('\n'):
                    line_lower = line.lower()
                    
                    # Detect section headers
                    if "core theme" in line_lower or "three core theme" in line_lower:
                        current_section = "core_themes"
                        continue
                    elif "decision" in line_lower and ("made" in line_lower or "reached" in line_lower):
                        current_section = "decisions"
                        continue
                    elif "general summary" in line_lower or "summary" in line_lower and current_section in ["core_themes", "decisions"]:
                        current_section = "general_summary"
                        continue
                    
                    # Add line to appropriate section if not empty
                    if line.strip():
                        if current_section == "core_themes":
                            core_themes_lines.append(line)
                        elif current_section == "decisions":
                            decisions_lines.append(line)
                        elif current_section == "general_summary":
                            general_summary_lines.append(line)
                        else:
                            # If no section has been identified yet, add to general summary
                            general_summary_lines.append(line)
                
                # Format each section
                for line in core_themes_lines:
                    if line.strip():
                        if line.strip().startswith('#'):  # Handle markdown style headers
                            header_level = len(line.split()[0].strip('#'))
                            header_text = ' '.join(line.split()[1:])
                            core_themes_html += f"<h{header_level}>{header_text}</h{header_level}>\n"
                        elif line.strip().startswith(('1.', '2.', '3.')):  # Handle numbered list items
                            core_themes_html += f"<p class='theme-item'>{line}</p>\n"
                        else:
                            core_themes_html += f"<p>{line}</p>\n"
                
                for line in decisions_lines:
                    if line.strip():
                        if line.strip().startswith('#'):  # Handle markdown style headers
                            header_level = len(line.split()[0].strip('#'))
                            header_text = ' '.join(line.split()[1:])
                            decisions_html += f"<h{header_level}>{header_text}</h{header_level}>\n"
                        elif line.strip().startswith(('•', '-', '*')):  # Handle bullet points
                            decisions_html += f"<p class='decision-item'>{line}</p>\n"
                        else:
                            decisions_html += f"<p>{line}</p>\n"
                
                for line in general_summary_lines:
                    if line.strip():
                        if line.strip().startswith('#'):  # Handle markdown style headers
                            header_level = len(line.split()[0].strip('#'))
                            header_text = ' '.join(line.split()[1:])
                            general_summary_html += f"<h{header_level}>{header_text}</h{header_level}>\n"
                        else:
                            general_summary_html += f"<p>{line}</p>\n"
                
                # If any section is empty, add a default message
                if not core_themes_html:
                    core_themes_html = "<p>No clear themes were identified in the conversation.</p>"
                if not decisions_html:
                    decisions_html = "<p>No clear decisions were identified in the conversation.</p>"
                if not general_summary_html:
                    general_summary_html = "<p>No additional details were provided in the summary.</p>"
                
                formatted_summary = core_themes_html + decisions_html + general_summary_html
                
                # Generate activity chart data
                sorted_dates = sorted(message_count_by_day.keys())
                daily_message_counts = [message_count_by_day[d] for d in sorted_dates]
                daily_participant_counts = [participant_count_by_day.get(d, 0) for d in sorted_dates]
                chart_labels = [datetime.strptime(d, '%Y-%m-%d').strftime('%m/%d') for d in sorted_dates]
            else:
                # If no messages, create empty placeholder summary
                formatted_summary = "<p>No messages found in this chat during the specified time period.</p>"
                # Add at least one day to the chart for proper rendering
                today = datetime.now().strftime('%Y-%m-%d')
                chart_labels = [datetime.now().strftime('%m/%d')]
                daily_message_counts = [0]
                daily_participant_counts = [0]
                print(f"No text messages found in the specified time period for chat: {chat_title}")
                print("Generating empty report with zero values.")
            
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
        
        .theme-item {{
            padding-left: 15px;
            border-left: 3px solid var(--warning);
            margin-bottom: 20px;
        }}
        
        .decision-item {{
            padding-left: 15px;
            border-left: 3px solid var(--secondary);
            margin-bottom: 15px;
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
            <div class="panel-title">CONVERSATION SUMMARY</div>
            
            <div class="section-header">THREE CORE THEMES</div>
            {core_themes_html}
            
            <div class="section-header">DECISIONS MADE</div>
            {decisions_html}
            
            <div class="section-header">GENERAL SUMMARY</div>
            {general_summary_html}
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