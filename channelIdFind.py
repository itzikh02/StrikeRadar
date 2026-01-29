import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

from dotenv import load_dotenv
load_dotenv()

# Your bot's API token
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def log_chat_id(update: Update, context):
    print(update.effective_chat.id)

# Create the bot application
application = Application.builder().token(BOT_TOKEN).build()

# Add a message handler
application.add_handler(MessageHandler(filters.ALL, log_chat_id))

# Run the bot
application.run_polling()


