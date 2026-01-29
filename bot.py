import os
import asyncio
import logging
import time
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from telegram.ext import ApplicationBuilder, ContextTypes, Defaults
from telegram.constants import ParseMode

# Load environment variables
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
LOCAL_API_URL = os.getenv("API_LOCAL_URL")
INTERVAL = int(os.getenv("CHECK_INTERVAL", 30))

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Silence noisy logs
logging.getLogger("playwright").setLevel(logging.WARNING)

# Global state to track risk and browser instance
state = {
    "last_risk": None,
    "browser": None,
    "playwright": None
}

async def get_risk_value():
    """Uses Playwright to fetch the real-time risk from the UI gauge."""
    try:
        # Create a new incognito context for every check to ensure fresh data
        context = await state["browser"].new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        await page.goto("https://usstrikeradar.com/", wait_until="networkidle", timeout=30000)
        
        selector = "#gaugeValue"
        # Wait for the JS to replace '--' with the actual number
        await page.wait_for_function(
            "selector => document.querySelector(selector).innerText.trim() !== '--'",
            arg=selector,
            timeout=20000
        )
        
        raw_value = await page.inner_text(selector)
        # Clean the value (remove % and non-digits)
        clean_value = "".join(filter(str.isdigit, raw_value))
        
        await context.close() # Clean up the context (incognito tab)
        
        if clean_value:
            return int(clean_value)
        return None
    except Exception as e:
        logging.error(f"❌ Playwright Fetch Error: {e}")
        return None

async def check_risk_job(context: ContextTypes.DEFAULT_TYPE):
    """Function executed by the JobQueue every X seconds."""
    current_risk = await get_risk_value()
    
    if current_risk is None:
        return

    last_risk = state["last_risk"]

    # First run initialization
    if last_risk is None:
        state["last_risk"] = current_risk
        logging.info(f"📊 Monitoring started. Initial risk: {current_risk}%")
        return
    
    logging.info(f"🔍 Current Checked Risk: {current_risk}%")

    # Check for change
    if current_risk != last_risk:
        emoji = "🔺" if current_risk > last_risk else "🔻"
        diff = current_risk - last_risk

        message = (
            f"🚨 *Risk Level Update*\n\n"
            f"Current Level: `{current_risk}%` {emoji} ({diff:+}%)\n"
            f"Previous Level: `{last_risk}%`"
        )

        try:
            await context.bot.send_message(chat_id=CHAT_ID, text=message)
            logging.info(f"📩 Notification sent. New level: {current_risk}%")
        except Exception as e:
            logging.error(f"❌ Telegram send error: {e}")

        state["last_risk"] = current_risk

async def main():
    """Starts the bot and the Playwright browser."""
    # Start Playwright once
    state["playwright"] = await async_playwright().start()
    state["browser"] = await state["playwright"].chromium.launch(headless=True)
    
    bot_defaults = Defaults(parse_mode=ParseMode.MARKDOWN)

    # Build the application
    builder = ApplicationBuilder().token(TOKEN).defaults(bot_defaults)
    
    # Use local API URL if provided
    if LOCAL_API_URL:
        builder.base_url(f"{LOCAL_API_URL}/bot")
        
    application = builder.build()

    # Startup sequence
    async with application:
        await application.initialize()
        await application.start()

        # Start the recurring task
        application.job_queue.run_repeating(check_risk_job, interval=INTERVAL, first=1)

        logging.info("🚀 System is live. Monitoring usstrikeradar.com via Playwright.")

        # Keep the event loop running
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            # Cleanup on shutdown
            await state["browser"].close()
            await state["playwright"].stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("👋 Bot stopped.")