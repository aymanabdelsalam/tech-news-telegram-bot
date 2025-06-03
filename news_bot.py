import feedparser
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from googletrans import Translator
import telegram
import asyncio
import os
from bs4 import BeautifulSoup # For HTML cleaning

# --- NLTK Data Path Configuration ---
# This ensures NLTK looks in the directory where we downloaded 'punkt' in the GitHub Action.
print("--- Python Script: NLTK Setup ---")
nltk_custom_download_dir = '/home/runner/nltk_data'
if os.path.exists(nltk_custom_download_dir):
    if nltk_custom_download_dir not in nltk.data.path:
        nltk.data.path.insert(0, nltk_custom_download_dir) # Ensure it's searched first
    print(f"NLTK data path configured: {nltk.data.path}")

    # Check for the specific punkt tokenizer path and english.pickle
    punkt_english_pickle_path_str = f'tokenizers/punkt/english.pickle'
    full_path_to_pickle = os.path.join(nltk_custom_download_dir, punkt_english_pickle_path_str)
    
    print(f"Checking for: {full_path_to_pickle}")
    if os.path.exists(full_path_to_pickle):
        print(f"SUCCESS: Found {full_path_to_pickle}")
        try:
            # Attempt to load it directly to see if NLTK can access it
            print(f"Attempting nltk.data.load('{punkt_english_pickle_path_str}')...")
            loaded_resource = nltk.data.load(punkt_english_pickle_path_str)
            print(f"Successfully loaded '{punkt_english_pickle_path_str}' with nltk.data.load(). Type: {type(loaded_resource)}")
        except Exception as e:
            print(f"ERROR trying to nltk.data.load('{punkt_english_pickle_path_str}'): {e}")
    else:
        print(f"ERROR: {full_path_to_pickle} NOT found.")
else:
    print(f"NLTK custom download directory {nltk_custom_download_dir} not found.")
print("--- End NLTK Setup ---")
# --- End NLTK Data Path Configuration ---


# --- CONFIGURATION (from environment variables) ---
RSS_FEED_URL = os.environ.get('RSS_FEED_URL', 'http://feeds.feedburner.com/TechCrunch/')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
NUM_SENTENCES_SUMMARY = 3
LANGUAGE_TO_TRANSLATE_TO = 'ar'
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

# --- 2. SUMMARIZE NEWS ---
def summarize_text(text, num_sentences):
    """Summarizes the given plain text."""
    if not text:
        print("No text to summarize.")
        return ""
    # Assuming 'text' is plain text now
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary_result = summarizer(parser.document, num_sentences)
    summary_text = " ".join([str(sentence) for sentence in summary_result])
    print(f"Summary (from plain text): {summary_text}")
    return summary_text

# --- 3. TRANSLATE TEXT ---
def translate_text(text, dest_language):
    """Translates plain text to the destination language."""
    if not text:
        print("No text to translate.")
        return ""
    try:
        translator = Translator()
        translation = translator.translate(text, dest=dest_language)
        translated_text = translation.text
        print(f"Translated text ({dest_language}): {translated_text}")
        return translated_text
    except Exception as e:
        print(f"Error during translation: {e}")
        return f"Translation failed for: {text[:50]}..." # Fallback

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
    raw_description = news_item['description']
    article_text_to_summarize = "" # Initialize
    if raw_description:
        soup = BeautifulSoup(raw_description, "html.parser")
        article_text_to_summarize = soup.get_text(separator=" ", strip=True)
        print(f"Cleaned text for summary (first 200 chars): {article_text_to_summarize[:200]}...")
    
    # Fallback if description was empty or resulted in empty cleaned text
    if not article_text_to_summarize:
        article_text_to_summarize = news_item['title'] # Fallback to title
        print("Description was empty or cleaned to empty, using article title for summary input.")

    # Summarization
    if len(article_text_to_summarize.split()) < 10: # Adjusted minimum length for meaningful summary
        summary = article_text_to_summarize # Use directly if too short
        print("Cleaned text too short, using it directly as summary.")
    else:
        summary = summarize_text(article_text_to_summarize, NUM_SENTENCES_SUMMARY)
    
    if not summary: # Ensure summary is not empty after summarization attempt
        print("Summarizer returned empty, using original cleaned text or title as fallback summary.")
        summary = article_text_to_summarize # Fallback to the cleaned text (or title if description was empty)

    # DEBUG: Print final summary before translation
    print(f"DEBUG: Final summary before translation: {summary}")

    # Translation
    arabic_summary = translate_text(summary, LANGUAGE_TO_TRANSLATE_TO)
    if not arabic_summary or "Translation failed" in arabic_summary: # Check if translation actually failed
        print("Translation failed or resulted in error message. Sending English summary if available, or a notice.")
        if summary and "Translation failed" not in summary : # Avoid sending "Translation failed" as the message
             arabic_summary = f"Original Summary (English):\n{summary}" # Fallback to English summary
        else:
             arabic_summary = "Summary processing error."


    # DEBUG: Print final Arabic summary before sending
    print(f"DEBUG: Final Arabic summary before sending to Telegram: {arabic_summary}")

    # Format and Send to Telegram
    message_to_send = (
        f"<b>{news_item['title']}</b>\n\n"
        f"{arabic_summary}\n\n" # This should now be plain text
        f"<a href='{news_item['link']}'>اقرأ المزيد (Read More)</a>"
    )

    send_success = await send_to_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message_to_send)

    if send_success:
        save_last_sent_link(news_item['link'])
        print(f"Successfully processed and sent article. Updated last sent link to: {news_item['link']}")
    else:
        print(f"Failed to send article '{news_item['title']}' to Telegram. State file not updated.")

if __name__ == '__main__':
    asyncio.run(main())
