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


def fetch_risk_data():
    """Fetch JSON data from the target website."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(JSON_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching JSON: {e}")
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

    # Check for change
    if current_risk != last_risk:
        emoji = "🔺" if current_risk > last_risk else "🔻"
        diff = current_risk - last_risk

        news_detail = data.get("news", {}).get("detail", "N/A")
        flight_detail = data.get("flight", {}).get("detail", "N/A")

        message = (
            f"🚨 *Risk Level Update*\n\n"
            f"Current Level: `{current_risk}` {emoji} ({diff:+})\n"
            f"Previous Level: `{last_risk}`\n\n"
            f"📊 *Quick Stats:*\n"
            f"📰 News: {news_detail}\n"
            f"✈️ Flights: {flight_detail}"
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
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text="🤖 Bot is now online and monitoring risk levels."
            )

        # Keep the event loop running
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot execution stopped.")
