import telebot
from telebot import types
import json
import os
import logging
import time

# Logging setup
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or '7588712034:AAGh-0ffrnS9Dq1e-8JK2l3A_uJWSHhOkcM'
bot = telebot.TeleBot(TOKEN)

# Telegram admin IDs
ADMIN_IDS = [7877979174]

# JSON file path
DATA_FILE = 'channels.json'

def load_data():
    """Load or create the channels.json file."""
    if not os.path.exists(DATA_FILE):
        initial_data = {
            "channels": [],
            "success_message": "🎉 Tebrikler! VPN Kodunuz: YOUR_VPN_CODE_HERE",
            "users": []
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(initial_data, file, ensure_ascii=False, indent=4)
        logger.info(f"{DATA_FILE} created.")
        return initial_data
    else:
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if "channels" not in data:
                    data["channels"] = []
                if "success_message" not in data:
                     data["success_message"] = "🎉 Tebrikler! VPN Kodunuz: YOUR_VPN_CODE_HERE"
                if "users" not in data:
                    data["users"] = []
                return data
        except json.JSONDecodeError:
            logger.error(f"{DATA_FILE} corrupted. Recreating.")
            try:
                 os.rename(DATA_FILE, f"{DATA_FILE}.bak")
                 logger.info(f"{DATA_FILE} backed up.")
            except OSError as e:
                 logger.error(f"Couldn't backup {DATA_FILE}: {e}")
            return load_data()
        except Exception as e:
            logger.error(f"Unexpected error loading {DATA_FILE}: {e}")
            return {"channels": [], "success_message": "🎉 Tebrikler! VPN Kodunuz: YOUR_VPN_CODE_HERE", "users": []}

def save_data(data):
    """Save data to channels.json."""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        logger.info(f"Data saved to {DATA_FILE}.")
    except Exception as e:
        logger.error(f"Error saving to {DATA_FILE}: {e}")

def add_user(user_id):
    """Add new user ID to the list if not exists."""
    data = load_data()
    if user_id not in data.get("users", []):
        data["users"].append(user_id)
        save_data(data)
        logger.info(f"New user added: {user_id}")

def escape_markdown(text):
    """Escape special Markdown characters."""
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(['\\' + char if char in escape_chars else char for char in text])

@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command."""
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "User"
    logger.info(f"User {user_id} used /start command.")

    add_user(user_id)

    data = load_data()
    channels = data.get("channels", [])

    markup = types.InlineKeyboardMarkup(row_width=1)

    if not channels:
        text = (
             f"𝐒𝐀𝐋𝐀𝐌 {user_name}🖐️\n\n"
             "📣 Şu anda sponsor kanal bulunmamaktadır. Daha sonra tekrar deneyin."
         )
        bot.send_message(message.chat.id, text)
    else:
        text = escape_markdown(
            f"𝐒𝐀𝐋𝐀𝐌 {user_name}🖐️\n\n"
            "📣𝐒𝐈𝐙 𝐀𝐒𝐀𝐊𝐃𝐀𝐊𝐘👇𝐕𝐈𝐏⚡𝐊𝐀𝐍𝐀𝐋𝐋𝐀𝐑𝐀 ⚜️𝐀𝐆𝐙𝐀 𝐁𝐎𝐋𝐌𝐀𝐊 𝐁𝐈𝐋𝐄𝐍 30 GUNLUK 𝐘𝐀𝐑𝐘𝐀𝐍 🔰𝐕𝐏𝐍 𝐊𝐎𝐃𝐔𝐍𝐘⚡ 𝐔𝐋𝐀𝐍𝐘𝐏 𝐁𝐈𝐋𝐄𝐑𝐒𝐈𝐍𝐈𝐙🔥"
        )
        for index, channel in enumerate(channels, 1):
            channel_username = channel.strip('@')
            if channel_username:
                 button = types.InlineKeyboardButton(f"Kanal {index}: {channel}", url=f"https://t.me/{channel_username}")
                 markup.add(button)
            else:
                 logger.warning(f"Invalid channel format in database: '{channel}'")

        button_check = types.InlineKeyboardButton("✅ AGZA BOLDUM / KODY AL", callback_data="check_subscription")
        markup.add(button_check)

        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="MarkdownV2")

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription(call):
    """Handle subscription check callback."""
    user_id = call.from_user.id
    logger.info(f"User {user_id} triggered subscription check.")

    bot.answer_callback_query(call.id, "Abonelikler kontrol ediliyor...")

    data = load_data()
    channels = data.get("channels", [])
    success_message_text = data.get("success_message", "🎉 Tebrikler! VPN Kodunuz: YOUR_VPN_CODE_HERE")

    if not channels:
         bot.edit_message_text("📢 Şu anda kontrol edilecek bir kanal bulunmuyor.", call.message.chat.id, call.message.message_id)
         return

    all_subscribed = True
    failed_channel = None

    for channel in channels:
        try:
            member = bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                all_subscribed = False
                failed_channel = channel
                logger.info(f"User {user_id} not subscribed to {channel}")
                break
        except telebot.apihelper.ApiTelegramException as e:
            if "user not found" in str(e).lower() or "user not participant" in str(e).lower():
                all_subscribed = False
                failed_channel = channel
                logger.info(f"User {user_id} not found in {channel}")
                break
            else:
                logger.error(f"API error checking user {user_id} in channel {channel}: {e}")
                all_subscribed = False
                failed_channel = channel
                break
        except Exception as e:
            logger.error(f"Unexpected error checking user {user_id} in channel {channel}: {e}")
            all_subscribed = False
            failed_channel = channel
            break

    if all_subscribed:
        bot.edit_message_text(
            escape_markdown(success_message_text),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None,
            parse_mode="MarkdownV2"
        )
        logger.info(f"User {user_id} subscribed to all channels. Success message sent.")
    else:
        error_text = escape_markdown("❌ KANALLARA AGZA BOLUN ‼")
        markup = types.InlineKeyboardMarkup(row_width=1)
        for index, channel in enumerate(channels, 1):
             channel_username = channel.strip('@')
             if channel_username:
                button = types.InlineKeyboardButton(f"Kanal {index}: {channel}", url=f"https://t.me/{channel_username}")
                markup.add(button)
        button_check = types.InlineKeyboardButton("✅ AGZA BOLDUM / KODY AL", callback_data="check_subscription")
        markup.add(button_check)

        bot.edit_message_text(
            error_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="MarkdownV2"
        )
        logger.info(f"User {user_id} not subscribed. Error message shown.")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Show all available commands"""
    user_id = message.from_user.id

    if user_id in ADMIN_IDS:
        help_text = """
🤖 *BOT KOMUTLARI* 🤖

👨‍💻 *Admin Komutları*:
/addch - Yeni kanal ekle
/delch - Kanal çıkar
/changevpn - VPN mesajını değiştir
/public - Kanallara duyuru gönder
/alert - Tüm kullanıcılara mesaj gönder
/help - Bu yardım mesajını göster

👤 *Kullanıcı Komutları*:
/start - Botu başlat
"""
    else:
        help_text = """
🤖 *BOT KOMUTLARI* 🤖

👤 *Kullanıcı Komutları*:
/start - Botu başlat
/help - Bu yardım mesajını göster
"""

    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['alert'])
def alert_users(message):
    """Send message to all users (Admin only)"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Bu komutu kullanma yetkiniz yok.")
        return

    bot.reply_to(message, "📢 Tüm kullanıcılara göndermek istediğiniz mesajı yazın:")
    bot.register_next_step_handler(message, process_alert_message)

def process_alert_message(message):
    """Process the alert message to send to all users"""
    alert_text = message.text
    admin_id = message.from_user.id

    data = load_data()
    users = data.get("users", [])

    if not users:
        bot.reply_to(message, "ℹ️ Henüz kayıtlı kullanıcı yok.")
        return

    msg = bot.reply_to(message, f"📢 {len(users)} kullanıcıya mesaj gönderiliyor...")

    success_count = 0
    failed_count = 0

    for user_id in users:
        try:
            bot.send_message(user_id, alert_text)
            success_count += 1
            time.sleep(0.1)  # Flood önleme
        except Exception as e:
            logger.error(f"Kullanıcı {user_id} mesaj gönderilemedi: {e}")
            failed_count += 1

    report = f"""
✅ Mesaj gönderme tamamlandı:

Başarılı: {success_count}
Başarısız: {failed_count}
"""
    bot.edit_message_text(report, msg.chat.id, msg.message_id)

@bot.message_handler(commands=['addch'])
def add_channel(message):
    """Add channel (Admin)"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Bu komutu kullanma yetkiniz yok.")
        return

    bot.reply_to(message, "➕ Eklemek istediğiniz kanalın @kullanıcı adını yazın (Örnek: @kanal_adi):")
    bot.register_next_step_handler(message, process_add_channel)

def process_add_channel(message):
    """Process channel addition"""
    new_channel = message.text.strip()
    user_id = message.from_user.id

    if not new_channel.startswith("@"):
        bot.reply_to(message, "❌ Geçersiz format! @kanal_adi şeklinde girin.")
        return

    data = load_data()

    try:
        bot.get_chat(new_channel)
    except Exception as e:
        bot.reply_to(message, f"❌ Kanal bulunamadı veya erişilemiyor: {e}")
        return

    if new_channel not in data["channels"]:
        data["channels"].append(new_channel)
        save_data(data)
        bot.reply_to(message, f"✅ {new_channel} başarıyla eklendi.")
    else:
        bot.reply_to(message, f"ℹ️ {new_channel} zaten listede var.")

@bot.message_handler(commands=['delch'])
def remove_channel(message):
    """Remove channel (Admin)"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Bu komutu kullanma yetkiniz yok.")
        return

    bot.reply_to(message, "➖ Çıkarmak istediğiniz kanalın @kullanıcı adını yazın:")
    bot.register_next_step_handler(message, process_remove_channel)

def process_remove_channel(message):
    """Process channel removal"""
    channel_to_remove = message.text.strip()
    data = load_data()

    if channel_to_remove in data["channels"]:
        data["channels"].remove(channel_to_remove)
        save_data(data)
        bot.reply_to(message, f"✅ {channel_to_remove} başarıyla çıkarıldı.")
    else:
        bot.reply_to(message, f"ℹ️ {channel_to_remove} listede bulunamadı.")

@bot.message_handler(commands=['changevpn'])
def change_success_message(message):
    """Change success message (Admin)"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Bu komutu kullanma yetkiniz yok.")
        return

    bot.reply_to(message, "🔑 Yeni başarı mesajını yazın (Markdown desteklenir):")
    bot.register_next_step_handler(message, process_change_success_message)

def process_change_success_message(message):
    """Process success message change"""
    new_message = message.text.strip()
    data = load_data()
    data["success_message"] = new_message
    save_data(data)
    bot.reply_to(message, "✅ Başarı mesajı güncellendi.")

@bot.message_handler(commands=['public'])
def public_to_channels(message):
    """Send announcement to channels (Admin)"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Bu komutu kullanma yetkiniz yok.")
        return

    data = load_data()
    channels = data.get("channels", [])

    if not channels:
        bot.reply_to(message, "ℹ️ Hiç kanal bulunmamaktadır.")
        return

    text = """
💁‍♂ 𝗩𝗣𝗡-𝗗𝗔𝗡 𝗞𝗢𝗦𝗘𝗡𝗬𝗔𝗡 𝗔𝗚𝗭𝗔𝗟𝗔𝗥
𝗕𝗢𝗧𝗬𝗠𝗬𝗭𝗔 𝗧𝗔𝗭𝗘𝗝𝗘 𝟭𝟬-𝗚𝗨𝗡𝗟𝗜𝗞
𝗦𝗘𝗥𝗩𝗘𝗥𝗟𝗔𝗥 𝗚𝗢𝗬𝗬𝗢𝗟𝗗𝗬 💥

🚀 𝗔𝗡𝗗𝗥𝗢𝗜𝗗 - 𝗜𝗢𝗦 - 𝗣𝗖 - 𝗪𝗘
𝗧𝗘𝗟𝗘𝗚𝗥𝗔𝗠 𝗣𝗥𝗢𝗫𝗬🤗
🫵 𝗦𝗜𝗭 𝗦𝗔𝗬𝗟𝗔𝗣 𝗔𝗟𝗬𝗣 𝗕𝗜𝗟𝗘𝗥𝗦𝗜𝗡𝗜𝗭 🔥
"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    bot_username = bot.get_me().username
    markup.add(types.InlineKeyboardButton("Android 🇹🇲", url=f"https://t.me/{bot_username}?start=android"))
    markup.add(types.InlineKeyboardButton("Ios 🇹🇲", url=f"https://t.me/{bot_username}?start=ios"))
    markup.add(types.InlineKeyboardButton("Windows 🇹🇲", url=f"https://t.me/{bot_username}?start=windows"))
    markup.add(types.InlineKeyboardButton("Telegram Proxy 🇹🇲", url=f"https://t.me/{bot_username}?start=proxy"))

    msg = bot.reply_to(message, f"📢 {len(channels)} kanala duyuru gönderiliyor...")

    success_count = 0
    failed_count = 0

    for channel in channels:
        try:
            bot.send_message(channel, text, reply_markup=markup)
            success_count += 1
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Kanal {channel} mesaj gönderilemedi: {e}")
            failed_count += 1

    report = f"""
✅ Duyuru gönderme tamamlandı:

Başarılı: {success_count}
Başarısız: {failed_count}
"""
    bot.edit_message_text(report, msg.chat.id, msg.message_id)

@bot.message_handler(func=lambda message: True)
def handle_unknown_commands(message):
    """Handle unknown commands"""
    user_id = message.from_user.id
    text = message.text

    if text.startswith('/'):
        logger.info(f"User {user_id} sent unknown command: {text}")

        for admin_id in ADMIN_IDS:
            try:
                forward_text = f"⚠️ Bilinmeyen komut:\n\nKullanıcı ID: {user_id}\nKomut: {text}"
                bot.send_message(admin_id, forward_text)
            except Exception as e:
                logger.error(f"Admin {admin_id} mesaj iletilemedi: {e}")

        bot.reply_to(message, "⛔ Bilinmeyen komut. /help komutunu kullanarak mevcut komutları görebilirsiniz.")

# Start the bot
logger.info("Bot başlatılıyor...")
try:
    bot.polling(none_stop=True)
except Exception as e:
    logger.error(f"Bot hatası: {e}")