import os
import sys
import json
import pytz
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from anthropic import Anthropic
from dotenv import load_dotenv
import argparse
import re

# Configure logging and load environment variables
load_dotenv()

# Get Anthropic API key from environment
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("Error: ANTHROPIC_API_KEY environment variable is not set.")
    sys.exit(1)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate HTML summary from Telegram JSON data.')
    parser.add_argument('json_file', help='Path to the JSON file containing Telegram chat data')
    parser.add_argument('--output', default='offline_test.html', 
                        help='Output HTML file path (default: offline_test.html)')
    return parser.parse_args()

def load_telegram_data(json_file_path):
    """Load Telegram data from a JSON file."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"Error: File {json_file_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON data from {json_file_path}.")
        sys.exit(1)

def process_telegram_data(data):
    """Process Telegram data from JSON and prepare it for summarization."""
    # Extract metadata
    metadata = data.get('metadata', {})
    chat_title = metadata.get('chat_title', 'Unknown Chat')
    chat_id = metadata.get('chat_id', 'unknown_id')
    date_range = metadata.get('date_range', '')
    message_count = metadata.get('message_count', 0)
    
    # Extract messages
    raw_messages = data.get('messages', [])
    
    # Convert raw messages to format needed for summarization
    messages = []
    timestamps = []
    
    # First pass to collect timestamps and convert dates
    for msg in raw_messages:
        # Skip messages without text
        if not msg.get('text'):
            continue
        
        # Process timestamp
        try:
            timestamp = msg.get('timestamp')
            if timestamp:
                message_date = datetime.fromtimestamp(timestamp, pytz.UTC)
            else:
                message_date = datetime.strptime(msg.get('date', ''), '%Y-%m-%d %H:%M:%S %Z').replace(tzinfo=pytz.UTC)
            timestamps.append(message_date)
        except ValueError:
            # If date parsing fails, skip this message
            print(f"Warning: Could not parse date from {msg.get('date')}. Skipping.")
            continue
    
    # Determine latest date and one week before that
    if timestamps:
        latest_date = max(timestamps)
        one_week_ago = latest_date - timedelta(days=7)
        print(f"Latest message date: {latest_date.strftime('%Y-%m-%d')}")
        print(f"Filtering messages from: {one_week_ago.strftime('%Y-%m-%d')} to {latest_date.strftime('%Y-%m-%d')}")
    else:
        print("No valid message dates found. Processing all messages.")
        one_week_ago = datetime.datetime.min.replace(tzinfo=pytz.UTC)
    
    # Process messages again, filtering by date
    participants = set()
    daily_message_count = defaultdict(int)
    participant_days = defaultdict(set)
    
    # Second pass to filter and process messages
    for msg in raw_messages:
        # Skip messages without text
        if not msg.get('text'):
            continue
        
        # Process timestamp
        try:
            timestamp = msg.get('timestamp')
            if timestamp:
                message_date = datetime.fromtimestamp(timestamp, pytz.UTC)
            else:
                message_date = datetime.strptime(msg.get('date', ''), '%Y-%m-%d %H:%M:%S %Z').replace(tzinfo=pytz.UTC)
            
            # Skip messages older than one week
            if message_date < one_week_ago:
                continue
                
        except ValueError:
            # If date parsing fails, use current time
            print(f"Warning: Could not parse date from {msg.get('date')}. Using current time.")
            message_date = datetime.now(pytz.UTC)
        
        # Track participant and daily stats
        sender_id = msg.get('from_id')
        if sender_id:
            participants.add(sender_id)
            day_str = message_date.strftime('%Y-%m-%d')
            daily_message_count[day_str] += 1
            participant_days[sender_id].add(day_str)
        
        # Format messages for summarization
        sender_name = msg.get('first_name', 'Unknown')
        if msg.get('username'):
            sender_name += f" (@{msg.get('username')})"
            
        messages.append({
            'id': msg.get('id', 0),
            'date': message_date.strftime('%Y-%m-%d %H:%M:%S'),
            'sender_id': sender_id,
            'sender_name': sender_name,
            'text': msg.get('text', '')
        })
    
    # Update date range to reflect the filtered period
    if timestamps:
        filtered_date_range = f"{one_week_ago.strftime('%Y-%m-%d')} to {latest_date.strftime('%Y-%m-%d')}"
    else:
        filtered_date_range = date_range
    
    print(f"Filtered to {len(messages)} messages in the last week")
    
    return {
        'chat_title': chat_title,
        'chat_id': chat_id,
        'date_range': filtered_date_range,
        'messages': messages,
        'participants': participants,
        'daily_message_count': daily_message_count,
        'participant_days': participant_days
    }

def generate_summary(processed_data, anthropic_key):
    """Generate a summary of the Telegram chat using Claude 3.7."""
    messages = processed_data['messages']
    chat_title = processed_data['chat_title']
    
    if not messages:
        print("No messages to summarize.")
        return {
            'weekly_focus': "No messages found in this chat during the specified time period.",
            'bullet_points': [],
            'decisions_made': [],
            'topics_discussed': [],
            'thinking_mode': ""
        }
    
    # Format messages for the prompt
    formatted_messages = []
    for msg in messages:
        formatted_messages.append(f"[{msg['date']}] {msg['sender_name']}: {msg['text']}")
    
    message_text = "\n".join(formatted_messages)
    
    # New custom system prompt for L2 interoperability focus
    system_prompt = """You are an expert Ethereum Layer 2 core developer with extensive knowledge of interoperability efforts between Layer 2 protocols."""

    # New custom user prompt from user
    user_prompt = f"""Here are the Telegram discussions for this week:

<telegram_discussions>
{message_text}
</telegram_discussions>

You are an expert Ethereum Layer 2 core developer with extensive knowledge of interoperability efforts between Layer 2 protocols. Your task is to analyze and summarize weekly Telegram discussions from the Ethereum Layer 2 Interoperability Working Group. This group focuses on advancing interoperability between Ethereum Layer 2s, as evidenced by their GitHub repository: https://github.com/ethereum/EIPs/tree/master/EIPS/eip-4844

Please analyze these discussions and create a summary following these steps:

1. Carefully read through all the Telegram discussions.

2. Wrap your detailed analysis inside <detailed_analysis> tags in your thinking block, performing the following tasks:
   a. List and categorize all technical topics mentioned in the discussions.
   b. For each topic, identify and quote 1-2 key statements that best represent the discussion.
   c. Rate the importance of each topic on a scale of 1-5.
   d. Determine the primary focus of the week's discussions, specifically related to Layer 2 interoperability.
   e. List the most important technical points that were raised.
   f. Identify any decisions that were made, counting them explicitly.
   g. Identify any technical debates that occurred, counting them explicitly, and note the arguments on each side.
   h. For each technical debate, list the pros and cons of each side.
   i. Count and list all unique participants in the discussion.
   j. Identify and quote any external resources or links mentioned.
   k. Provide a brief chronological breakdown of the discussion to track the flow of ideas.

3. Based on your analysis, create a summary with the following structure:

   <weekly_focus>
   [One sentence describing the main focus of the week's discussions, specifically related to Layer 2 interoperability]
   </weekly_focus>

   <summary_points>
   - [First key technical point of the week's discussions]
   - [Second key technical point of the week's discussions]
   - [Third key technical point of the week's discussions]
   </summary_points>

   <decisions>
   [List any technical decisions made related to the discussions. If no decisions were made, state "No formal decisions were made this week."]
   </decisions>

   <topics_discussed>
   [For each significant topic discussed:
    <topic>[Technical topic]</topic>
    <details>[Brief, technical description of the discussion]</details>
   ]
   </topics_discussed>

Important guidelines:
- Use exact technical terms as they appear in the discussions. Do not paraphrase technical concepts.
- Be specific and avoid vague statements. Your summary should reflect deep involvement in the discussions.
- If no significant discussions occurred in a particular week, simply state that no significant discussions took place.
- Focus on the most important and technically relevant information, particularly related to Layer 2 interoperability.
- Ensure your language reflects expertise in Ethereum Layer 2 development and familiarity with the ongoing interoperability efforts.

Remember, your goal is to provide a concise yet technically accurate summary that captures the essence of the week's Layer 2 interoperability discussions. Your summary should be useful for participants of the chat to refresh their memory and for other stakeholders to stay informed about the progress of Layer 2 interoperability efforts.

Your final output should consist only of the summary with the structure outlined above and should not duplicate or rehash any of the analysis work you did in the <detailed_analysis> section.
"""
    
    print("Sending chat to Claude 3.7 for summarization...")
    try:
        anthropic_client = Anthropic(api_key=anthropic_key)
        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20240620",  # Using Claude 3.5 Sonnet
            max_tokens=4000,
            temperature=0.3,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        summary = response.content[0].text
        print("Summary received from Claude")
        
        # Process the summary to extract sections using regex
        # Extract thinking section
        thinking_mode = ""
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', summary, re.DOTALL)
        if thinking_match:
            thinking_mode = thinking_match.group(1).strip()
            # Remove the thinking section from the main summary
            summary = re.sub(r'<thinking>.*?</thinking>', '', summary, flags=re.DOTALL).strip()
        
        # Extract detailed analysis (which should be inside the thinking section)
        detailed_analysis = ""
        analysis_match = re.search(r'<detailed_analysis>(.*?)</detailed_analysis>', thinking_mode, re.DOTALL)
        if analysis_match:
            detailed_analysis = analysis_match.group(1).strip()
        
        # Extract main sections using regex with the new tag structure
        weekly_focus_match = re.search(r'<weekly_focus>(.*?)</weekly_focus>', summary, re.DOTALL)
        weekly_focus = weekly_focus_match.group(1).strip() if weekly_focus_match else "No specific focus identified for this week."
        
        # Extract summary points (bullet points)
        bullet_points = []
        summary_points_match = re.search(r'<summary_points>(.*?)</summary_points>', summary, re.DOTALL)
        if summary_points_match:
            points_text = summary_points_match.group(1).strip()
            for line in points_text.split('\n'):
                line = line.strip()
                if line.startswith('- '):
                    # Remove the leading dash to avoid redundant bullets
                    cleaned_point = line[2:].strip()
                    bullet_points.append(cleaned_point)
        
        # Extract decisions
        decisions_made = []
        decisions_match = re.search(r'<decisions>(.*?)</decisions>', summary, re.DOTALL)
        if decisions_match:
            decisions_text = decisions_match.group(1).strip()
            if "No formal decisions" not in decisions_text and "No decisions" not in decisions_text:
                for line in decisions_text.split('\n'):
                    line = line.strip()
                    if line and line.startswith('- '):
                        decisions_made.append(line)
        
        # Extract topics discussed
        topics_discussed = []
        topics_match = re.search(r'<topics_discussed>(.*?)</topics_discussed>', summary, re.DOTALL)
        if topics_match:
            topics_text = topics_match.group(1).strip()
            
            # Find all topic/details pairs
            topic_matches = re.finditer(r'<topic>(.*?)</topic>\s*<details>(.*?)</details>', topics_text, re.DOTALL)
            for topic_match in topic_matches:
                topic = topic_match.group(1).strip()
                details = topic_match.group(2).strip()
                topics_discussed.append({
                    'topic': topic,
                    'details': details
                })
        
        return {
            'weekly_focus': weekly_focus,
            'bullet_points': bullet_points,
            'decisions_made': decisions_made,
            'topics_discussed': topics_discussed,
            'thinking_mode': thinking_mode,
            'detailed_analysis': detailed_analysis
        }
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return {
            'weekly_focus': "Error generating summary.",
            'bullet_points': [],
            'decisions_made': [],
            'topics_discussed': [],
            'thinking_mode': "",
            'detailed_analysis': ""
        }

def generate_html(processed_data, summary_data, output_file):
    """Generate an HTML report of the Telegram chat."""
    chat_title = processed_data['chat_title']
    chat_id = processed_data['chat_id']
    date_range = processed_data['date_range']
    participants = processed_data['participants']
    daily_message_count = processed_data['daily_message_count']
    participant_days = processed_data['participant_days']
    messages = processed_data['messages']
    
    # Format summary sections as HTML
    weekly_focus_html = f"<p class='weekly-focus'>{summary_data['weekly_focus']}</p>" if summary_data['weekly_focus'] else "<p>No specific focus identified for this week.</p>"
    
    bullet_points_html = ""
    if summary_data['bullet_points']:
        for point in summary_data['bullet_points']:
            bullet_points_html += f"<li class='bullet-point'>{point}</li>\n"
    else:
        bullet_points_html = "<li>No significant discussion points identified for this week.</li>"
    
    decisions_html = ""
    if summary_data['decisions_made']:
        for decision in summary_data['decisions_made']:
            decisions_html += f"<li class='decision-item'>{decision}</li>\n"
    else:
        decisions_html = "<li>No decisions were made this week.</li>"
    
    # Generate HTML for topics discussed - new format
    topics_html = ""
    if summary_data['topics_discussed']:
        for topic_item in summary_data['topics_discussed']:
            topics_html += f"""
            <div class="topic-card">
                <h3 class="topic-title">{topic_item['topic']}</h3>
                <p class="topic-details">{topic_item['details']}</p>
            </div>
            """
    else:
        topics_html = "<p>No significant topics were discussed this week.</p>"
    
    # Add thinking mode section if available
    thinking_html = ""
    if summary_data.get('thinking_mode'):
        thinking_html = f"""
        <div class="section-header">THINKING PROCESS</div>
        <div class="thinking-box">
            <pre>{summary_data['thinking_mode']}</pre>
        </div>
        """
    
    # Add detailed analysis section if available
    analysis_html = ""
    if summary_data.get('detailed_analysis'):
        analysis_html = f"""
        <div class="section-header">DETAILED ANALYSIS</div>
        <div class="analysis-box">
            <pre>{summary_data['detailed_analysis']}</pre>
        </div>
        """
    
    # Generate activity chart data
    sorted_dates = sorted(daily_message_count.keys())
    daily_message_counts = [daily_message_count[d] for d in sorted_dates]
    
    # Calculate daily participant counts
    daily_participant_counts = []
    for day_str in sorted_dates:
        day_participants = sum(1 for user_id in participant_days if day_str in participant_days[user_id])
        daily_participant_counts.append(day_participants)
    
    chart_labels = [datetime.strptime(d, '%Y-%m-%d').strftime('%m/%d') for d in sorted_dates]
    
    # Fallback for empty data
    if not chart_labels:
        chart_labels = [datetime.now().strftime('%m/%d')]
        daily_message_counts = [0]
        daily_participant_counts = [0]
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Layer 2 Interoperability Chat Summary - {chat_title}</title>
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
            --thinking-bg: #0f1f1a;
            --analysis-bg: #151a1f;
            --topic-card-bg: rgba(0, 255, 160, 0.05);
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
        
        .topic-card {{
            background-color: var(--topic-card-bg);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 3px solid var(--primary);
        }}
        
        .topic-title {{
            color: var(--warning);
            margin-bottom: 10px;
            font-size: 18px;
        }}
        
        .topic-details {{
            line-height: 1.6;
            font-size: 16px;
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
        
        .thinking-box {{
            background-color: var(--thinking-bg);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 25px;
            max-height: 500px;
            overflow-y: auto;
            border-left: 3px solid var(--secondary);
        }}
        
        .thinking-box pre {{
            white-space: pre-wrap;
            font-family: 'Share Tech Mono', monospace;
            font-size: 14px;
            line-height: 1.5;
        }}
        
        .analysis-box {{
            background-color: var(--analysis-bg);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 25px;
            max-height: 500px;
            overflow-y: auto;
            border-left: 3px solid var(--warning);
        }}
        
        .analysis-box pre {{
            white-space: pre-wrap;
            font-family: 'Share Tech Mono', monospace;
            font-size: 14px;
            line-height: 1.5;
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
            <h1>LAYER 2 INTEROPERABILITY ANALYSIS</h1>
        </div>
        
        <div class="date-range">ANALYSIS PERIOD: {date_range}</div>
        
        <div class="stats-panel">
            <div class="stat-box">
                <div class="stat-label">CHAT TITLE</div>
                <div class="stat-value" style="font-size: 24px;">{chat_title}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">TOTAL MESSAGES</div>
                <div class="stat-value">{len(messages)}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">UNIQUE PARTICIPANTS</div>
                <div class="stat-value">{len(participants)}</div>
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
            
            <div class="section-header">TOPICS DISCUSSED</div>
            <div class="topics-container">
                {topics_html}
            </div>
            
            {analysis_html}
            
            {thinking_html}
        </div>
        
        <div class="credits">
            GENERATED BY LAYER 2 INTEROPERABILITY ANALYSIS SYSTEM • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
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
    
    # Write HTML to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Offline summary generated and saved to: {output_file}")

def main():
    """Main function to process JSON and generate HTML."""
    args = parse_arguments()
    
    print(f"Loading Telegram data from: {args.json_file}")
    telegram_data = load_telegram_data(args.json_file)
    
    print("Processing Telegram data...")
    processed_data = process_telegram_data(telegram_data)
    
    print("Generating summary...")
    summary_data = generate_summary(processed_data, ANTHROPIC_API_KEY)
    
    print("Generating HTML report...")
    generate_html(processed_data, summary_data, args.output)
    
    print(f"Process complete. HTML report saved to: {args.output}")

if __name__ == "__main__":
    main() 