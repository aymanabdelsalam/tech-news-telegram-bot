import nltk
import os

# --- NLTK Data Path Configuration ---
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
            print("This might indicate the pickle file is present but cannot be loaded, or it has internal dependencies that are missing (like 'punkt_tab').")
    else:
        print(f"ERROR: {full_path_to_pickle} NOT found.")
        # Also list contents of tokenizers/punkt if pickle not found (though we know it is from workflow logs)
        punkt_dir_path = os.path.join(nltk_custom_download_dir, 'tokenizers', 'punkt')
        if os.path.exists(punkt_dir_path):
            print(f"Contents of {punkt_dir_path}: {os.listdir(punkt_dir_path)}")
        else:
            print(f"{punkt_dir_path} does not exist.")
else:
    print(f"NLTK custom download directory {nltk_custom_download_dir} not found.")
print("--- End NLTK Setup ---")
# --- End NLTK Data Path Configuration ---

import feedparser
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from googletrans import Translator
import telegram
import asyncio
import os # For environment variables and file operations

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
        'description': latest_entry.get('summary', latest_entry.get('description', ''))
    }

# --- 2. SUMMARIZE NEWS ---
def summarize_text(text, num_sentences):
    if not text:
        print("No text to summarize.")
        return ""
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary_result = summarizer(parser.document, num_sentences)
    summary_text = " ".join([str(sentence) for sentence in summary_result])
    print(f"Summary: {summary_text}")
    return summary_text

# --- 3. TRANSLATE TEXT ---
def translate_text(text, dest_language):
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
    if not bot_token or not chat_id:
        print("Error: Telegram Bot Token or Chat ID is not set.")
        return
    try:
        bot = telegram.Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML', disable_web_page_preview=False)
        print("Message sent to Telegram successfully!")
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")

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

    article_text_to_summarize = news_item['description']
    if len(article_text_to_summarize.split()) < 20 and not news_item['description']: # If description is very short or empty
         # Attempt to fetch more content if description is too short - placeholder
        print("Description too short, using title as summary basis if description empty.")
        summary_input = news_item['title'] if not news_item['description'] else news_item['description']
    else:
        summary_input = article_text_to_summarize

    summary = summarize_text(summary_input, NUM_SENTENCES_SUMMARY)
    if not summary and summary_input: # If summarizer returns empty, use the input
        summary = summary_input
        print("Summarizer returned empty, using original input for summary.")


    if not summary:
        print("Failed to generate summary.")
        return

    arabic_summary = translate_text(summary, LANGUAGE_TO_TRANSLATE_TO)

    message_to_send = (
        f"<b>{news_item['title']}</b>\n\n"
        f"{arabic_summary}\n\n"
        f"<a href='{news_item['link']}'>اقرأ المزيد (Read More)</a>"
    )

    await send_to_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message_to_send)
    save_last_sent_link(news_item['link']) # Save after successful send
    print(f"Successfully processed and sent article. Updated last sent link to: {news_item['link']}")

if __name__ == '__main__':
    asyncio.run(main())
