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
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_KEY")
DAYS_TO_FETCH = 7  # Default to last 7 days of messages
MESSAGE_LIMIT = 2000  # Significantly increased to get more messages

# Define the output directory for reports
REPORTS_DIR = "reports"

# Ensure the reports directory exists
os.makedirs(REPORTS_DIR, exist_ok=True)

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
    print(f"Looking for channel ID: {TELEGRAM_CHANNEL_ID}")
    
    # Only try to get chat history if a chat ID is provided
    try:
        if TELEGRAM_CHANNEL_ID:
            print(f"Attempting to fetch messages from: {TELEGRAM_CHANNEL_ID}")
            
            # Get chat information
            chat = app.get_chat(TELEGRAM_CHANNEL_ID)
            chat_title = chat.title or chat.first_name or "Unknown Chat"
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
            for message in app.get_chat_history(TELEGRAM_CHANNEL_ID, limit=MESSAGE_LIMIT):
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
                Identify key topics discussed, any decisions made, and important information shared.
                Organize the summary by topics and include timestamps for key moments.
                
                CONVERSATION:
                {message_text}
                """
                
                print("Sending chat to OpenAI for summarization...")
                response = openai_client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes conversations clearly and concisely."},
                        {"role": "user", "content": summary_prompt}
                    ],
                    max_tokens=1000,  # Increased for more detailed summaries
                    temperature=0.3
                )
                
                # Extract summary
                summary = response.choices[0].message.content.strip()
                print("Summary received from OpenAI")
                
                # Process the summary to convert line breaks to HTML paragraphs
                formatted_summary = ""
                for line in summary.split('\n'):
                    if line.strip():
                        if line.strip().startswith('#'):  # Handle markdown style headers
                            header_level = len(line.split()[0].strip('#'))
                            header_text = ' '.join(line.split()[1:])
                            formatted_summary += f"<h{header_level}>{header_text}</h{header_level}>\n"
                        else:
                            formatted_summary += f"<p>{line}</p>\n"
                
                # Generate activity chart data
                sorted_dates = sorted(message_count_by_day.keys())
                daily_message_counts = [message_count_by_day[d] for d in sorted_dates]
                daily_participant_counts = [participant_count_by_day.get(d, 0) for d in sorted_dates]
                chart_labels = [datetime.strptime(d, '%Y-%m-%d').strftime('%m/%d') for d in sorted_dates]
                
                # Format the date range
                date_range = f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
                
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
            {formatted_summary}
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
                
                # Write to individual HTML file for each chat
                report_filename = f"{chat_title.replace(' ', '_')}.html"
                report_path = os.path.join(REPORTS_DIR, report_filename)
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"Enhanced summary with statistics saved to {report_path}")

                # Collect report filenames for index
                report_files = []
                report_files.append(report_filename)
            else:
                print("No text messages found in the specified time period.")
        else:
            print("No channel ID specified. Please set the TELEGRAM_CHANNEL_ID environment variable.")
    except Exception as e:
        print(f"Error: {e}")

# After processing all chats, generate the main index page
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Telegram Chat Summaries Index</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Share Tech Mono', monospace; background-color: #0a0a0a; color: #00ffa0; padding: 20px; }
        h1 { text-align: center; }
        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; }
        a { color: #00ffa0; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Telegram Chat Summaries</h1>
    <ul>
"""

for report_file in report_files:
    index_html += f"<li><a href='{REPORTS_DIR}/{report_file}'>{report_file.replace('_', ' ').replace('.html', '')}</a></li>\n"

index_html += """
    </ul>
</body>
</html>
"""

# Write the index HTML file
with open("telegram_reports_index.html", "w", encoding="utf-8") as f:
    f.write(index_html)
print("Index page created: telegram_reports_index.html") 