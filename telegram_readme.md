# Telegram Chat Summarizer

This script fetches messages from a Telegram chat, uses ChatGPT to generate a summary, and creates an HTML report called "EA.html".

## Prerequisites

- Python 3.7 or higher
- A Telegram API key (API ID and API Hash)
- An OpenAI API key
- The Telegram chat must be accessible to your Telegram account

## Setup

1. Clone this repository or download the script file.

2. Install the required Python packages:

```bash
pip install telethon python-dotenv openai pillow
```

3. Create a `.env` file in the same directory as the script with the following content:

```
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash
TELEGRAM_PHONE=your_phone_number
TELEGRAM_CHAT_NAME=name_or_username_of_chat
OPENAI_KEY=your_openai_api_key
```

### Getting Telegram API Credentials

To obtain your Telegram API credentials:

1. Visit https://my.telegram.org/auth
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application
5. Copy the API ID and API Hash to your `.env` file

## Usage

Run the script using:

```bash
python telegram_chat_summary.py
```

The first time you run the script, you will be prompted to enter the confirmation code sent to your Telegram account.

By default, the script will:
- Fetch messages from the last 7 days
- Summarize them using ChatGPT (GPT-4o model)
- Generate an "EA.html" file with the summary

## Customization

You can modify the following variables at the top of the script:

- `OUTPUT_HTML`: The name of the generated HTML file (default: "EA.html")
- `DAYS_TO_FETCH`: Number of days of chat history to fetch (default: 7)

## Output

The script generates an HTML file (EA.html by default) that contains:

- A title with the chat name
- The date range for the messages
- A summary of the chat organized by topics
- Timestamp of when the report was generated

## Troubleshooting

- If you get authentication errors, delete the `telegram_session.session` file and run the script again.
- If no messages are found, check that the chat name is correct and that your account has access to that chat.
- For API rate limiting issues, try increasing the delay between requests or reduce the number of days to fetch.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 