# Repository Analysis and Chat Summarization Tools

This repository contains a collection of tools for analyzing GitHub repositories and summarizing Telegram chat conversations with AI assistance.

## Overview

The repository contains three main scripts:

1. **fetch_github_data.py**: Analyzes GitHub repositories, generating reports about PRs, issues, and activity.
2. **telegram_chat_summary.py**: Fetches messages from Telegram channels and generates summaries using OpenAI.
3. **offline_telegram_summary.py**: Processes previously exported Telegram chat data from JSON files and generates summaries using Anthropic Claude.

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- A GitHub personal access token (for fetch_github_data.py)
- Telegram API credentials (for telegram_chat_summary.py)
- OpenAI API key (for fetch_github_data.py and telegram_chat_summary.py)
- Anthropic API key (for offline_telegram_summary.py)

### Environment Setup

1. **Create a Virtual Environment**
   ```bash
   python3 -m venv venv
   ```

2. **Activate the Virtual Environment**
   ```bash
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables**
   
   Create a `.env` file in the root directory with the following variables:

   ```
   # GitHub Analysis Variables
   GITHUB_TOKEN=ghp_yourgithubpersonalaccesstoken123456789
   REPOS=ethereum/EIPs,ethereum-optimism/optimism
   OPENAI_KEY=sk-youropenaikey123456789

   # Telegram Chat Summary Variables
   TELEGRAM_API_ID=123456
   TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
   TELEGRAM_CHANNEL_IDS=-1001723022155,-1001234567890,987654321

   # Offline Telegram Summary Variables
   ANTHROPIC_API_KEY=sk-ant-api03-youranthropic-apikey123456789
   ```

## Script Usage

### 1. GitHub Repository Analysis

This script analyzes GitHub repositories, generates HTML reports, and creates a dashboard for repository insights.

```bash
python fetch_github_data.py
```

The script will:
- Fetch open and closed PRs and issues from specified repositories
- Generate summaries using OpenAI
- Create HTML reports for each repository
- Build an index page linking to all reports

### 2. Telegram Chat Summary

This script connects to Telegram, fetches messages from specified channels, and generates summaries.

```bash
python telegram_chat_summary.py
```

Key features:
- Processes multiple Telegram channels (specified in TELEGRAM_CHANNEL_IDS)
- Generates summaries for each channel using OpenAI
- Creates HTML reports with visualizations of chat activity
- Creates an index page to access all reports

On first run, you'll need to authenticate your Telegram account with a verification code.

### 3. Offline Telegram Summary

This script processes previously exported Telegram chat data from JSON files without requiring Telegram API access.

```bash
python offline_telegram_summary.py path/to/chat_export.json --output path/to/output.html
```

For example:
```bash
python offline_telegram_summary.py reports/L2_Interop_Working_Group_n1002276686237_raw.json --output reports/l2_interop_analysis.html
```

Key features:
- Works with JSON files exported from telegram_chat_summary.py
- Generates summaries using Anthropic Claude
- Creates HTML reports with interactive visualizations
- Specialized for Ethereum Layer 2 interoperability analysis

## Example Usage

Here's a common workflow:

1. First, use `telegram_chat_summary.py` to fetch and export chat data to JSON files:
   ```bash
   python telegram_chat_summary.py
   ```

2. Then, use `offline_telegram_summary.py` to generate more detailed analysis using Claude:
   ```bash
   python offline_telegram_summary.py reports/YourChat_n123456789_raw.json --output reports/detailed_analysis.html
   ```

3. Separately, analyze GitHub repositories:
   ```bash
   python fetch_github_data.py
   ```

## Output Files

All scripts generate outputs in the `reports/` directory:
- HTML report files for each Telegram channel or GitHub repository
- JSON files containing raw chat data
- Index pages for easy navigation

## Troubleshooting

- **Telegram Authentication Issues**: Delete the `.session` file and try again
- **Missing Reports**: Check the environment variables are correctly set
- **API Rate Limits**: Add delays or reduce the date range in the scripts
- **Claude API Errors**: Verify your API key and check Anthropic's quota limits

## License

This project is licensed under the MIT License.
