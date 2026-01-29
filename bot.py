import os
import requests
import asyncio
import logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, ContextTypes, Defaults
from telegram.constants import ParseMode

# Load environment variables
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
LOCAL_API_URL = os.getenv("API_LOCAL_URL")
JSON_URL = os.getenv("JSON_URL")
INTERVAL = int(os.getenv("CHECK_INTERVAL", 30))

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Silence noisy network logs from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

# Global state to track risk
state = {"last_risk": None}


import json # Add this import at the top

def fetch_risk_data():
    """Fetch JSON data from URL or local file for testing."""
    # Check if JSON_URL in .env starts with 'http'
    if JSON_URL.startswith("http"):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(JSON_URL, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error fetching JSON from URL: {e}")
            return None
    else:
        # If it's not a URL, assume it's a local file path
        try:
            with open(JSON_URL, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error reading local JSON file: {e}")
            return None


async def check_risk_job(context: ContextTypes.DEFAULT_TYPE):
    """Function executed by the JobQueue every X seconds."""
    data = fetch_risk_data()
    if not data or "total_risk" not in data:
        return

    current_risk = data["total_risk"]["risk"]
    last_risk = state["last_risk"]

    # First run initialization
    if last_risk is None:
        state["last_risk"] = current_risk
        logging.info(f"Monitoring started. Initial risk: {current_risk}")
        return
    
    print(f"RISK: {current_risk}")

    # Check for change
    if current_risk != last_risk:
        emoji = "🔺" if current_risk > last_risk else "🔻"
        diff = current_risk - last_risk

        pentagon_detail = data.get("pentagon", {}).get("detail", "N/A")
        tankers_detail = data.get("tankers", {}).get("detail", "N/A")
        flighet_detail = data.get("flight", {}).get("detail", "N/A")
        polymarket_detail = data.get("polymarket", {}).get("detail", "N/A")
        weather_detail = data.get("weather", {}).get("detail", "N/A")

        message = (
            f"🚨 *Risk Level Update*\n\n"
            f"Current Level: `{current_risk}` {emoji} ({diff:+})\n"
            f"Previous Level: `{last_risk}`\n\n"
            f"📊 *Quick Stats:*\n"
            f"🍕 *Pentagon Pizza Meter*: {pentagon_detail}\n"
            f"📊 *Polymarket*: {polymarket_detail}\n"
            f"✈️ *Flights*: {flighet_detail}\n"
            f"🛢️ *Tankers*: {tankers_detail}\n"
            f"🌤️ *Weather*: {weather_detail}\n"
        )

        try:
            await context.bot.send_message(chat_id=CHAT_ID, text=message)
            logging.info(f"Notification sent. New level: {current_risk}")
        except Exception as e:
            logging.error(f"Telegram send error: {e}")


        state["last_risk"] = current_risk


async def main():
    """Manually start the application without Polling/Updater."""
    bot_defaults = Defaults(parse_mode=ParseMode.MARKDOWN)

    # Build the application
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .base_url(f"{LOCAL_API_URL}/bot")
        .defaults(bot_defaults)
        .build()
    )

    # Manual startup sequence (This bypasses polling entirely)
    async with application:
        await application.initialize()
        await application.start()

        # Start the recurring task
        application.job_queue.run_repeating(check_risk_job, interval=INTERVAL, first=1)

        logging.info("System is live. No polling active (Send-only mode).")
        # await application.bot.send_message(
        #     chat_id=CHAT_ID,
        #     text="🤖 Bot is now online and monitoring risk levels from [USStrikeRadar](https://usstrikeradar.com/) "
        #     )

        # Keep the event loop running
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot execution stopped.")
