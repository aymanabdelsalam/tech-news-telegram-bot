
import os
import feedparser
import telegram
import asyncio
import os # For environment variables and file operations
from bs4 import BeautifulSoup


# --- CONFIGURATION (from environment variables) ---
RSS_FEED_URL = os.environ.get('RSS_FEED_URL', 'http://feeds.feedburner.com/TechCrunch/')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
STATE_FILE = 'last_article_link.txt' # File to store the link of the last sent article

# --- 0. STATE MANAGEMENT ---
def get_last_sent_link():
    """Reads the last sent article link from the state file."""
    try:
        with open(STATE_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_last_sent_link(link):
    """Saves the last sent article link to the state file."""
    with open(STATE_FILE, 'w') as f:
        f.write(link)

# --- 1. FETCH LATEST NEWS ---
def fetch_latest_news(feed_url):
    """Fetches the latest news item from an RSS feed."""
    print(f"Fetching news from: {feed_url}")
    feed = feedparser.parse(feed_url)
    if not feed.entries:
        print("No entries found in the RSS feed.")
        return None
    latest_entry = feed.entries[0]
    print(f"Fetched article: {latest_entry.title} - Link: {latest_entry.link}")
    return {
        'title': latest_entry.title,
        'link': latest_entry.link,
        'description': latest_entry.get('summary', latest_entry.get('description', '')) # Get summary or description
    }


# --- 4. SUBMIT TO TELEGRAM ---
async def send_to_telegram(bot_token, chat_id, message):
    """Sends a message to a Telegram chat/channel. Returns True on success, False on failure."""
    if not bot_token or not chat_id:
        print("Error: Telegram Bot Token or Chat ID is not set.")
        return False
    try:
        bot = telegram.Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML', disable_web_page_preview=False)
        print("Message sent to Telegram successfully!")
        return True
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")
        return False

# --- MAIN WORKFLOW ---
async def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Critical Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured in environment variables.")
        return

    last_sent_link = get_last_sent_link()
    print(f"Last sent link: {last_sent_link}")

    news_item = fetch_latest_news(RSS_FEED_URL)
    if not news_item:
        return

    if news_item['link'] == last_sent_link:
        print("No new articles to send. The latest article is the same as the last one sent.")
        return

    # HTML CLEANING of the description
    raw_description = ""
# news_item['description']
    article_text_to_summarize = "" # Initialize
    if raw_description:
        soup = BeautifulSoup(raw_description, "html.parser")
        article_text_to_summarize = soup.get_text(separator=" ", strip=True)
        print(f"Cleaned text for summary (first 200 chars): {article_text_to_summarize[:200]}...")
    
    # Fallback if description was empty or resulted in empty cleaned text
    if not article_text_to_summarize:
        article_text_to_summarize = news_item['title'] # Fallback to title
        print("Description was empty or cleaned to empty, using article title for summary input.")

    arabic_summary = article_text_to_summarize

    # DEBUG: Print final Arabic summary before sending
    print(f"DEBUG: Final Arabic summary before sending to Telegram: {arabic_summary}")

    # Format and Send to Telegram
    # f"<b>{news_item['title']}</b>\n\n"
    message_to_send = (
        f"{arabic_summary}\n\n" # This should now be plain text
        f"<a href='{news_item['link']}'>اقرأ المزيد </a>"
    )

    send_success = await send_to_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message_to_send)

    if send_success:
        save_last_sent_link(news_item['link'])
        print(f"Successfully processed and sent article. Updated last sent link to: {news_item['link']}")
    else:
        print(f"Failed to send article '{news_item['title']}' to Telegram. State file not updated.")

if __name__ == '__main__':
    asyncio.run(main())
