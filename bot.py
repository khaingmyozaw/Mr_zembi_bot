import telebot
from telebot import types
import random
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
# Load environment variables from .env file
load_dotenv()

# Get token from environment variable
API_TOKEN = os.getenv('BOT_TOKEN')

if not API_TOKEN:
    print("Error: BOT_TOKEN not found in .env file.")
    exit(1)

# Initialize bot
bot = telebot.TeleBot(API_TOKEN)

# Mock database of VLESS/VMESS configurations
SERVER_CONFIGS = [
    "vless://uuid-1@127.0.0.1:443?security=reality&sni=google.com&fp=chrome&pbk=public-key&sid=short-id&type=grpc&serviceName=grpc#US_Server_1",
    "vmess://ew0KICAidiI6ICIyIiwNCiAgInBzIjogIkV4YW1wbGUiLA0KICAiYWRkIjogIjEyNy4wLjAuMSIsDQogICJwb3J0IjogIjQ0MyIsDQogICJpZCI6ICJ1dWlkIiwNCiAgImFpZCI6ICIwIiwNCiAgIm5ldCI6ICJ3cyIsDQogICJ0eXBlIjogIm5vbmUiLA0KICAiaG9zdCI6ICIiLA0KICAicGF0aCI6ICIvIiwNCiAgInRscyI6ICJ0bHMiDQp9",
    "vless://uuid-2@192.168.1.1:8080?security=none&type=ws&path=/ws#DE_Server_Fast"
]

# --- HANDLERS ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    # Create the main menu keyboard
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_get = types.KeyboardButton("🚀 Get Config")
    btn_status = types.KeyboardButton("📊 Server Status")
    btn_support = types.KeyboardButton("📞 Support")
    btn_about = types.KeyboardButton("ℹ️ About")
    
    markup.add(btn_get, btn_status, btn_support, btn_about)
    
    welcome_text = (
        f"👋 Hello {message.from_user.first_name}!\n\n"
        "I am a VLESS/VMESS distribution bot.\n"
        "Use the menu below to get a connection key."
    )
    
    bot.reply_to(message, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🚀 Get Config")
def send_config(message):
    # Select a random config
    config = random.choice(SERVER_CONFIGS)
    
    # Send with Markdown formatting so user can tap to copy
    response = (
        "🔑 <b>Here is your configuration:</b>\n\n"
        f"<code>{config}</code>\n\n"
        "<i>Click the code above to copy!</i>"
    )
    
    bot.reply_to(message, response, parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text == "📊 Server Status")
def server_status(message):
    bot.reply_to(message, "🟢 All servers are operational.\nLoad: 24%")

@bot.message_handler(func=lambda message: message.text == "ℹ️ About")
def about_bot(message):
    bot.reply_to(message, "Bot Version: 1.0\nBuilt with pyTelegramBotAPI 4.30.0")

# Handle all other text messages
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "⚠️ I don't understand that command. Please use the menu.")

# --- RUN ---
if __name__ == "__main__":
    print("Bot started...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Error: {e}")