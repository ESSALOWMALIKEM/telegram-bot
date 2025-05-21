import logging
import json
import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import telegram.error # For broadcast error handling

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ADMIN_ID = 7877979174  # Bu esasy admin ID-si olaraq qalır
BOT_TOKEN = "7998830176:AAHsOkqkMjp-jlf46YjiXqDzFGQbsicRbmc" # Tokeninizi daxil edin
USERS_FILE = "users.json"
TEST_CODES_FILE = "test_codes.txt"
PROMO_FILE = "promocodes.json"
BOT_CONFIG_FILE = "bot_config.json" # Yeni konfiqurasiya faylı

active_orders = {}

# Faylların mövcudluğunu yoxlamaq və yaratmaq
def initialize_files():
    # Esasy adminin her zaman admin_ids siyahısında olmasını temin etmek üçün defolt konfiqurasiya
    default_bot_config = {
        "admin_ids": [ADMIN_ID],
        "start_message": {"text": None, "photo_id": None},
        "broadcast_in_progress": False # Yeni elave: yayim prosesini izlemek ucun
    }
    
    files_to_initialize = [
        (USERS_FILE, {}),
        (TEST_CODES_FILE, ""),
        (PROMO_FILE, {}),
        (BOT_CONFIG_FILE, default_bot_config)
    ]

    for file_path, default_content in files_to_initialize:
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding='utf-8') as f:
                if isinstance(default_content, dict):
                    json.dump(default_content, f, indent=4, ensure_ascii=False)
                else:
                    f.write(default_content)
        elif file_path == BOT_CONFIG_FILE: # Eger BOT_CONFIG_FILE movcuddursa, strukturunu yoxla
            try:
                with open(file_path, "r+", encoding='utf-8') as f:
                    config_data = json.load(f)
                    updated = False
                    if "admin_ids" not in config_data:
                        config_data["admin_ids"] = [ADMIN_ID]
                        updated = True
                    elif ADMIN_ID not in config_data["admin_ids"]:
                        config_data["admin_ids"].append(ADMIN_ID) # Esasy admini elave et
                        updated = True
                    
                    if "start_message" not in config_data:
                        config_data["start_message"] = {"text": None, "photo_id": None}
                        updated = True
                    if "broadcast_in_progress" not in config_data: # Yeni elave
                        config_data["broadcast_in_progress"] = False
                        updated = True

                    if updated:
                        f.seek(0)
                        json.dump(config_data, f, indent=4, ensure_ascii=False)
                        f.truncate()
            except json.JSONDecodeError: # Eger fayl korlanibsa, defolt deyerlerle yeniden yaz
                 with open(file_path, "w", encoding='utf-8') as f:
                    json.dump(default_bot_config, f, indent=4, ensure_ascii=False)


initialize_files()


class Database:
    @staticmethod
    def read_db():
        try:
            with open(USERS_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @staticmethod
    def save_db(data):
        with open(USERS_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def read_test_codes():
        try:
            with open(TEST_CODES_FILE, "r", encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    @staticmethod
    def write_test_codes(code):
        with open(TEST_CODES_FILE, "w", encoding='utf-8') as f:
            f.write(code)

    @staticmethod
    def read_promos():
        try:
            with open(PROMO_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @staticmethod
    def write_promos(promos):
        with open(PROMO_FILE, "w", encoding='utf-8') as f:
            json.dump(promos, f, indent=4, ensure_ascii=False)

    @staticmethod
    def read_bot_config():
        try:
            with open(BOT_CONFIG_FILE, "r", encoding='utf-8') as f:
                config = json.load(f)
                if "admin_ids" not in config or ADMIN_ID not in config["admin_ids"]:
                    config["admin_ids"] = list(set(config.get("admin_ids", []) + [ADMIN_ID])) # Esasy admini daxil et
                if "start_message" not in config:
                    config["start_message"] = {"text": None, "photo_id": None}
                if "broadcast_in_progress" not in config:
                    config["broadcast_in_progress"] = False
                return config
        except (FileNotFoundError, json.JSONDecodeError):
            # Defolt deyerleri qaytar ve faylı yeniden yaratmağa cehd et
            default_config = {"admin_ids": [ADMIN_ID], "start_message": {"text": None, "photo_id": None}, "broadcast_in_progress": False}
            Database.save_bot_config(default_config) # Fayli defolt deyerlerle saxla
            return default_config


    @staticmethod
    def save_bot_config(data):
        # Esasy ADMIN_ID-nin her zaman admin_ids siyahisinda olmasini temin et
        if "admin_ids" in data:
            if ADMIN_ID not in data["admin_ids"]:
                data["admin_ids"].append(ADMIN_ID)
        else:
            data["admin_ids"] = [ADMIN_ID]
        
        with open(BOT_CONFIG_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

async def is_user_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID:  # Esasy admin
        return True
    bot_config = Database.read_bot_config()
    return user_id in bot_config.get("admin_ids", [])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id_str = str(user.id)
    user_id_int = user.id
    users = Database.read_db()
    bot_config = Database.read_bot_config() # Bot konfiqurasiyasını oxu

    # Referal emeliyyatı
    if context.args and context.args[0].isdigit():
        referrer_id_str = context.args[0]
        if referrer_id_str in users and user_id_str != referrer_id_str:
            if user_id_str not in users[referrer_id_str].get('referrals', []):
                users[referrer_id_str]['ref_count'] = users[referrer_id_str].get('ref_count', 0) + 1
                users[referrer_id_str].setdefault('referrals', []).append(user_id_str)
                
                try:
                    referrer_full_name = users[referrer_id_str].get('full_name', f"ID: {referrer_id_str}")
                    new_user_fullname = user.full_name or f"ID: {user_id_str}"
                    await context.bot.send_message(
                        chat_id=int(referrer_id_str),
                        text=f"🎉 Siziň çagyrygyňyz bilen täze ulanyjy ({new_user_fullname}) bota goşuldy.\nSiziň jemi referallaryňyz: {users[referrer_id_str]['ref_count']}"
                    )
                except Exception as e:
                    logger.error(f"Referal bildirişi gönderilemedi {referrer_id_str}: {e}")

    if user_id_str not in users:
        users[user_id_str] = {
            "keys": [],
            "ref_count": 0,
            "referrals": [],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "username": user.username or "",
            "full_name": user.full_name or ""
        }
    
    # İstifadəçinin adını və tam adını yeniləyin
    users[user_id_str]['username'] = user.username or users[user_id_str].get('username', '')
    users[user_id_str]['full_name'] = user.full_name or users[user_id_str].get('full_name', '')
    Database.save_db(users)

    if await is_user_admin(user_id_int):
        await show_admin_menu(update, context)
    else:
        await show_main_menu(update, user, context)


async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = Database.read_db()
    active_users = len([u for u in users if users[u].get('keys')])
    text = f"""🔧 Admin panel

👥 Jemi ulanyjylar: {len(users)}
✅ Aktiw ulanyjylar: {active_users}
🎁 Jemi referallar: {sum(u.get('ref_count', 0) for u in users.values())}"""

    keyboard = [
        [InlineKeyboardButton("📤 Test kody üýtget", callback_data="admin_change_test"), InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📩 Habar iber (Broadcast)", callback_data="admin_broadcast_options")],
        [InlineKeyboardButton("📦 Users bazasy", callback_data="admin_export")],
        [InlineKeyboardButton("🎟 Promokod goş", callback_data="admin_add_promo_prompt"), InlineKeyboardButton("🎟 Promokod poz", callback_data="admin_remove_promo_prompt")],
        [InlineKeyboardButton("⚙️ Başlangyç Habary Düzelt", callback_data="admin_set_start_msg_prompt")],
        [InlineKeyboardButton("👤 Adminleri Düzelt", callback_data="admin_manage_admins_menu")],
        [InlineKeyboardButton("🔙 Baş sahypa (User)", callback_data="main_menu_user_view")] # Adminin istifadeci menyusuna baxmasi ucun
    ]
    
    # `update` obyektinin message və ya callback_query olmasını yoxlayın
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif update.callback_query: # Eger callback_query ise, mesajı redaktə edin
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def main_menu_user_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adminin istifadəçi menyusunu görməsi üçün."""
    query = update.callback_query
    await query.answer()
    await show_main_menu(query, query.from_user, context) # query.from_user istifadeci kimi gosterir

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = Database.read_db()
    active_users = len([u for u in users if users[u].get('keys')])
    total_refs = sum(u.get('ref_count', 0) for u in users.values())

    text = f"""📊 *Bot statistikasy* 👥 Jemi ulanyjylar: {len(users)}
✅ Aktiw ulanyjylar: {active_users}
🎁 Jemi referallar: {total_refs}
🕒 Soňky aktivlik: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="admin_panel")]]),
        parse_mode="Markdown"
    )


async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return # Admin yoxlaması
    with open(USERS_FILE, "rb") as f:
        await update.callback_query.message.reply_document(f)


async def admin_add_promo_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    await update.callback_query.message.reply_text("🎟 Täze promokod we skidkany ýazyň (mysal üçin: PROMO10 10):")
    context.user_data["adding_promo"] = True

async def admin_remove_promo_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    promos = Database.read_promos()
    if not promos:
        await update.callback_query.message.reply_text("❌ Promokodlar ýok!")
        return

    keyboard = [[InlineKeyboardButton(f"{promo} ({promos[promo]}%)", callback_data=f"confirm_remove_promo_{promo}")] for promo in promos]
    keyboard.append([InlineKeyboardButton("🔙 Yza", callback_data="admin_panel")]) # Changed to go back to admin_panel
    await update.callback_query.edit_message_text( # edit_message_text istifade etdim
        "🎟 Pozmaly promokody saýlaň:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_remove_promo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    query = update.callback_query
    await query.answer()
    promo_code_to_remove = query.data.split("confirm_remove_promo_")[-1]
    
    promos = Database.read_promos()
    if promo_code_to_remove in promos:
        del promos[promo_code_to_remove]
        Database.write_promos(promos)
        await query.edit_message_text(f"✅ Promokod {promo_code_to_remove} pozuldy!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza (Promokodlar)", callback_data="admin_remove_promo_prompt")]]))
    else:
        await query.edit_message_text(f"❌ Promokod {promo_code_to_remove} tapylmady.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza (Promokodlar)", callback_data="admin_remove_promo_prompt")]]))


async def admin_change_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    await update.callback_query.message.reply_text("✏️ Täze test kody iberiň:")
    context.user_data["waiting_for_test"] = True

# --- Yeni Admin İdarəetmə Funksiyaları ---
async def admin_manage_admins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("➕ Admin Goş", callback_data="admin_add_admin_prompt")],
        [InlineKeyboardButton("➖ Admin Poz", callback_data="admin_remove_admin_prompt")],
        [InlineKeyboardButton("📜 Admin Sanawy", callback_data="admin_list_admins")],
        [InlineKeyboardButton("🔙 Yza (Admin Panel)", callback_data="admin_panel")]
    ]
    await query.edit_message_text("Adminleri düzeltmek bölümi:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_add_admin_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("➕ Täze adminiň Telegram ID-syny ýazyň:")
    context.user_data["waiting_for_new_admin_id"] = True

async def admin_remove_admin_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    query = update.callback_query
    await query.answer()
    bot_config = Database.read_bot_config()
    admin_ids = bot_config.get("admin_ids", [])
    
    buttons = []
    for admin_id_val in admin_ids:
        if admin_id_val != ADMIN_ID:  # Esasy admini silmək olmaz
            try:
                user_chat = await context.bot.get_chat(admin_id_val)
                name = user_chat.full_name or f"ID: {admin_id_val}"
            except Exception:
                name = f"ID: {admin_id_val} (Ad tapylmady)"
            buttons.append([InlineKeyboardButton(f"➖ {name}", callback_data=f"confirm_remove_admin_{admin_id_val}")])
    
    if not buttons:
        await query.edit_message_text("Başga admin ýok.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="admin_manage_admins_menu")]]))
        return

    buttons.append([InlineKeyboardButton("🔙 Yza", callback_data="admin_manage_admins_menu")])
    await query.edit_message_text("Haýsy admini pozmaly?", reply_markup=InlineKeyboardMarkup(buttons))

async def confirm_remove_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    query = update.callback_query
    await query.answer()
    admin_id_to_remove = int(query.data.split("_")[-1])

    if admin_id_to_remove == ADMIN_ID:
        await query.edit_message_text("❌ Esasy admini pozup bilmersiňiz!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="admin_remove_admin_prompt")]]))
        return

    bot_config = Database.read_bot_config()
    if admin_id_to_remove in bot_config.get("admin_ids", []):
        bot_config["admin_ids"].remove(admin_id_to_remove)
        Database.save_bot_config(bot_config)
        await query.edit_message_text(f"✅ Admin {admin_id_to_remove} pozuldy!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="admin_remove_admin_prompt")]]))
        try:
            await context.bot.send_message(chat_id=admin_id_to_remove, text="ℹ️ Siziň admin ygtyýarlyklaryňyz aýryldy.")
        except Exception as e:
            logger.warning(f"Pozulan admine bildiriş gönderilemedi {admin_id_to_remove}: {e}")
    else:
        await query.edit_message_text(f"❌ Admin {admin_id_to_remove} tapylmady.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="admin_remove_admin_prompt")]]))

async def admin_list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    query = update.callback_query
    await query.answer()
    bot_config = Database.read_bot_config()
    admin_ids = bot_config.get("admin_ids", [ADMIN_ID])
    admin_list_text = "📜 Admin Sanawy:\n"
    for admin_id_val in admin_ids:
        try:
            user_chat = await context.bot.get_chat(admin_id_val)
            name = user_chat.full_name or f"ID: {admin_id_val}"
        except Exception:
            name = f"ID: {admin_id_val} (Ad tapylmady)"
        
        admin_list_text += f"- {name} ({admin_id_val})"
        if admin_id_val == ADMIN_ID:
            admin_list_text += " (Esasy Admin)\n"
        else:
            admin_list_text += "\n"
    await query.edit_message_text(admin_list_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="admin_manage_admins_menu")]]))

# --- Yeni Başlanğıc Mesajı Düzəltmə Funksiyaları ---
async def admin_set_start_msg_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    query = update.callback_query
    await query.answer()
    
    bot_config = Database.read_bot_config()
    current_text = bot_config.get("start_message", {}).get("text")
    current_photo_id = bot_config.get("start_message", {}).get("photo_id")
    
    current_text_display = current_text[:200] + '...' if current_text and len(current_text) > 200 else (current_text if current_text else "Bellenilmeyip")
    current_photo_display = "Hawa" if current_photo_id else "Ýok"

    msg = (
        "Başlangyç habary düzeltmek üçin:\n"
        "1. Diňe tekst: Täze teksti iberiň.\n"
        "2. Surat + Tekst: Suraty başlığı (caption) bilen birlikde iberiň.\n"
        "3. Suraty aýyrmak: /clearpicstart iberiň.\n"
        "4. Hemme zady aýyrmak (defolt): /clearfullstart iberiň.\n\n"
        f"Hazirki tekst: {current_text_display}\n"
        f"Hazirki surat: {current_photo_display}"
    )
    await query.message.reply_text(msg)
    context.user_data["setting_start_message"] = True

# --- Yeni Broadcast Funksiyaları ---
async def admin_broadcast_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    query = update.callback_query
    await query.answer()
    
    bot_config = Database.read_bot_config()
    if bot_config.get("broadcast_in_progress", False):
        await query.message.reply_text("❌ Bir ýaýlym eýýäm dowam edýär. Garaşmagyňyzy haýyş edýäris.")
        return

    keyboard = [
        [InlineKeyboardButton("📝 Diňe Tekst", callback_data="broadcast_text_only")],
        [InlineKeyboardButton("🖼️ Surat + Tekst", callback_data="broadcast_photo_text")],
        [InlineKeyboardButton("🔙 Yza (Admin Panel)", callback_data="admin_panel")]
    ]
    await query.edit_message_text("Ýaýlym habaryň görnüşini saýlaň:", reply_markup=InlineKeyboardMarkup(keyboard))

async def broadcast_text_only_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📨 Tekst ýaýlym habaryny iberiň:")
    context.user_data["broadcasting_type"] = "text_only"

async def broadcast_photo_text_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id): return
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🖼️ Suraty başlığı (caption) bilen birlikde iberiň:")
    context.user_data["broadcasting_type"] = "photo_text"
    # context.user_data["broadcast_photo_id"] = None # Lazım deyil, çünki şəkil və başlıq birlikdə göndəriləcək

async def _perform_broadcast(context: ContextTypes.DEFAULT_TYPE, admin_chat_id: int, text_message: str = None, photo_id: str = None, caption_message: str = None):
    bot_config = Database.read_bot_config()
    bot_config["broadcast_in_progress"] = True
    Database.save_bot_config(bot_config)

    users_db = Database.read_db()
    user_ids = list(users_db.keys())
    
    await context.bot.send_message(chat_id=admin_chat_id, text=f"📢 Ýaýlym başlaýar... {len(user_ids)} ulanyja iberilýär.")
    
    successful_sends = 0
    failed_sends = 0
    
    for user_id_str in user_ids:
        try:
            user_id_int = int(user_id_str)
            if photo_id:
                await context.bot.send_photo(chat_id=user_id_int, photo=photo_id, caption=caption_message, parse_mode="Markdown")
            elif text_message:
                await context.bot.send_message(chat_id=user_id_int, text=text_message, parse_mode="Markdown")
            successful_sends += 1
        except telegram.error.RetryAfter as e:
            logger.warning(f"Rate limit aşıldı: {user_id_int}. {e.retry_after} saniyə sonra yenidən cəhd edin.")
            await asyncio.sleep(e.retry_after)
            try:
                if photo_id:
                    await context.bot.send_photo(chat_id=user_id_int, photo=photo_id, caption=caption_message, parse_mode="Markdown")
                elif text_message:
                    await context.bot.send_message(chat_id=user_id_int, text=text_message, parse_mode="Markdown")
                successful_sends += 1
            except Exception as e_retry:
                logger.error(f"Yeniden cəhddən sonra {user_id_int} adresinə yayım göndərilə bilmədi: {e_retry}")
                failed_sends +=1
        except (telegram.error.BadRequest, telegram.error.ChatMigrated, telegram.error.Forbidden) as e:
            logger.error(f"{user_id_int} adresinə yayım göndərilə bilmədi (istifadəçi bloklamış və ya etibarsız ola bilər): {e}")
            failed_sends += 1
        except Exception as e:
            logger.error(f"{user_id_int} adresinə yayım göndərilərkən gözlənilməz bir xəta baş verdi: {e}")
            failed_sends += 1
        await asyncio.sleep(0.2) # Həddi aşmamaq üçün kiçik bir gecikmə (0.1-dən 0.2-yə artırıldı)
            
    await context.bot.send_message(chat_id=admin_chat_id, text=f"📢 Ýaýlym tamamlandy!\n✅ Üstünlikli iberildi: {successful_sends}\n❌ Şowsuz boldy: {failed_sends}")
    
    bot_config = Database.read_bot_config()
    bot_config["broadcast_in_progress"] = False
    Database.save_bot_config(bot_config)


async def show_main_menu(update: Update, user: User, context: ContextTypes.DEFAULT_TYPE):
    bot_config = Database.read_bot_config()
    start_msg_config = bot_config.get("start_message", {})
    custom_text = start_msg_config.get("text")
    photo_id = start_msg_config.get("photo_id")

    default_text = f"""Salam, {user.full_name} 👋 

🔑 Açarlarym - düyməsinə bassanız, sizə pulsuz və ya pullu verilən kodları yadda saxlamağa kömək edəcək.
🎁 Referal - düyməsinə bassanız, dostlarınızı dəvət edərək pullu kod almaq imkanı əldə edəcəksiniz.
🆓 Test Kodu almaq - düyməsinə bassanız, sizin üçün Outline (ss://) kodu veriləcək.
💰 VPN Qiymətləri - düyməsinə bassanız, pullu VPN-ləri ala bilərsiniz.
🎟 Promokod - düyməsinə bassanız, promokod daxil etmek üçün bir yer açılacaq.

'Bildirişlər' - 'Уведомления' Açıq qoyun, çünki Test kodu yeniləndikdə bot vasitəsilə sizə vaxtında xəbər veriləcək."""

    text_to_send = custom_text if custom_text else default_text
    
    keyboard = [
        [InlineKeyboardButton("🔑 Açarlarym", callback_data="my_keys")],
        [InlineKeyboardButton("🎁 Referal", callback_data="referral"), InlineKeyboardButton("🆓 Test Kody Almak", callback_data="get_test")],
        [InlineKeyboardButton("💰 VPN Bahalary", callback_data="vpn_prices"), InlineKeyboardButton("🎟 Promokod", callback_data="use_promo")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    target_chat_id = update.effective_chat.id

    if update.callback_query: # Callback-dən çağırılırsa (məsələn, geri düyməsi)
        # Əvvəlki mesajı silib yenisini göndərmək daha təmiz görünə bilər
        try:
            await update.callback_query.message.delete()
        except Exception:
            pass # Mesaj artıq silinib və ya başqa bir səbəb

        if photo_id:
            try:
                await context.bot.send_photo(chat_id=target_chat_id, photo=photo_id)
                await context.bot.send_message(chat_id=target_chat_id, text=text_to_send, reply_markup=reply_markup, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Callback-də xüsusi başlanğıc şəkli göndərilərkən xəta: {e}")
                await context.bot.send_message(chat_id=target_chat_id, text=text_to_send, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=target_chat_id, text=text_to_send, reply_markup=reply_markup, parse_mode="Markdown")

    elif update.message: # /start əmrindən çağırılırsa
        if photo_id:
            try:
                await update.message.reply_photo(
                    photo=photo_id,
                    caption=text_to_send,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Xüsusi başlanğıc şəkli başlıqla göndərilərkən xəta: {e}")
                await update.message.reply_text(text_to_send, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text_to_send, reply_markup=reply_markup, parse_mode="Markdown")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_orders
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id_str = str(query.from_user.id)
    users = Database.read_db()

    if data == "admin_panel":
        if await is_user_admin(query.from_user.id):
            await show_admin_menu(query, context)
        else: # Eger admin deyilse, esas menyuya yönlendir
            await show_main_menu(query, query.from_user, context)
        return
        
    elif data == "main_menu": # Bu, istifadəçinin əsas menyusuna qayıtmaq üçündür
        # Admin əsas menyuya qayıtmaq istəyirsə, admin panelini göstər
        if await is_user_admin(query.from_user.id):
            await show_admin_menu(query, context) 
        else:
            await show_main_menu(query, query.from_user, context)
        return
    
    # ------ Button Handler-in qalan hissəsi (əvvəlki kimi) ------
    back_button = [[InlineKeyboardButton("🔙 Yza", callback_data="main_menu")]]
    if data == "my_keys":
        keys = users.get(user_id_str, {}).get("keys", [])
        text = "Siziň açarlaryňyz:" if keys else "Siziň açarlaryňyz ýok."
        key_buttons = [[InlineKeyboardButton(f"Açar {i+1}: ...{key[-10:]}", callback_data=f"show_one_key_{i}")] for i, key in enumerate(keys)]
        key_buttons.append([InlineKeyboardButton("🔙 Yza", callback_data="main_menu")])
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(key_buttons))

    elif data.startswith("show_one_key_"):
        key_index = int(data.split("_")[-1])
        keys = users.get(user_id_str, {}).get("keys", [])
        if 0 <= key_index < len(keys):
            await query.message.reply_text(f"`{keys[key_index]}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Açar Listesine", callback_data="my_keys")]]))
        else:
            await query.message.reply_text("Açar tapylmady.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Açar Listesine", callback_data="my_keys")]]))
        
    elif data == "referral":
        ref_link = f"https://t.me/{context.bot.username}?start={user_id_str}"
        ref_count = users.get(user_id_str, {}).get("ref_count", 0)
        text = f"""Siz 5 adam çagyryp platny kod alyp bilersiňiz 🎁 

Referal sylkaňyz: {ref_link}

Referal sanyňyz: {ref_count}"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(back_button)) # edit_message_text istifade etdim

    elif data == "get_test":
        test_kod = Database.read_test_codes()
        message_to_edit = await query.message.reply_text("Test Kodyňyz Ýasalýar...")
        await asyncio.sleep(1) # Daha qısa gecikmə
        await message_to_edit.edit_text(test_kod if test_kod else "Test kody ýok.", reply_markup=InlineKeyboardMarkup(back_button))

    elif data == "use_promo":
        await query.message.reply_text("🎟 Promokody ýazyň:") # Yeni mesaj olarak gonderilir
        context.user_data["waiting_for_promo"] = True
        
    elif data == "vpn_prices":
        base_prices = {
            "vpn_3": 20, "vpn_7": 40, "vpn_15": 100, "vpn_30": 130
        }
        discount = context.user_data.get("promo_discount_value", 0) # "promo_discount" yerine "promo_discount_value"
        
        prices_text = (
            "**Eger platny kod almakçy bolsaňyz aşakdaky knopka basyň we BOT arkaly admin'iň size ýazmagyna garaşyn📍**\n"
            "-----------------------------------------------\n"
            "🌍 **VPN adı: Shadowsocks**🛍️\n"
            "-----------------------------------------------\n"
        )
        
        price_lines = []
        for key, price in base_prices.items():
            days_text = key.split('_')[1]
            days_label = ""
            if days_text == "3": days_label = "3 Gün'lik"
            elif days_text == "7": days_label = "Hepdelik"
            elif days_text == "15": days_label = "15 Gün'lik"
            elif days_text == "30": days_label = "Aylık" # Düzəliş: Aylık Trafik yerinə Aylık

            original_price_text = f"{price} тмт"
            discounted_price = price * (1 - discount / 100)
            
            if discount > 0:
                price_lines.append(f"🕯️ {days_label}: <del>{original_price_text}</del> {discounted_price:.0f} тмт ({discount}% skidka!)")
            else:
                price_lines.append(f"🕯️ {days_label}: {original_price_text}")

        prices_text += "\n".join(price_lines)
        
        keyboard = []
        row = []
        for key, price in base_prices.items():
            final_price = price * (1 - discount / 100)
            button_text = f"📅 {key.split('_')[1]} gün - {final_price:.0f} 𝚃𝙼𝚃"
            if discount > 0:
                 button_text += " 🎉"
            button = InlineKeyboardButton(button_text, callback_data=key)
            row.append(button)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Yza", callback_data="main_menu")]) # Geri duymesi elave edildi
        await query.edit_message_text(text=prices_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("vpn_"):
        days = data.split("_")[1]
        user_info = query.from_user # user -> user_info (dəyişən adı)
        
        # Ödəniş məbləğini hesabla (promokod nəzərə alınaraq)
        base_prices = { "3": 20, "7": 40, "15": 100, "30": 130 }
        price = base_prices.get(days, 0)
        discount = context.user_data.get("promo_discount_value", 0)
        final_price = price * (1 - discount / 100)

        await context.bot.send_message(
            chat_id=user_info.id, # user -> user_info
            text=f"✅ {days} günlük kod saýlandy! Töleg: {final_price:.0f} TMT"
        )
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=user_info.id,
            text="⏳ Tiz wagtdan admin size ýazar."
        )
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=user_info.id,
            text="🚫 Eger admin'iň size ýazmagyny islemeýän bolsaňyz /stop ýazyp bilersiňiz."
        )
        admin_text = f"🆕 Täze sargyt:\n👤 Ulanyjy: {user_info.full_name} (@{user_info.username if user_info.username else 'N/A'}, {user_info.id})\n📆 Zakaz: {days} gün\n💰 Töleg: {final_price:.0f} TMT"
        if discount > 0:
            admin_text += f" (Promokod bilen: {discount}%)"

        # Adminlere bildiris gonder
        bot_cfg = Database.read_bot_config()
        admin_keyboard = [[InlineKeyboardButton("✅ Kabul etmek", callback_data=f"accept_{user_info.id}_{days}")]]
        for admin_user_id in bot_cfg.get("admin_ids", [ADMIN_ID]):
            try:
                await context.bot.send_message(
                    chat_id=admin_user_id, # ADMIN_ID -> admin_user_id
                    text=admin_text,
                    reply_markup=InlineKeyboardMarkup(admin_keyboard) # keyboard -> admin_keyboard
                )
            except Exception as e:
                logger.error(f"Admine ({admin_user_id}) sifaris bildirişi gönderilemedi: {e}")


    elif data.startswith("accept_"):
        # Yalniz adminler qebul ede biler
        if not await is_user_admin(query.from_user.id):
            await query.answer("Bu emeliyyat üçün icazeniz yoxdur.", show_alert=True)
            return

        _, target_id_str, days = data.split("_")
        target_id = int(target_id_str)
        active_orders[str(target_id)] = str(query.from_user.id) # Qəbul edən adminin ID-si
        active_orders[str(query.from_user.id)] = str(target_id) # Adminin kiminlə danışdığını bilməsi üçün

        # Digər adminlərdən "Kabul etmek" düyməsini sil
        bot_cfg = Database.read_bot_config()
        original_message_id = query.message.message_id
        for admin_user_id in bot_cfg.get("admin_ids", [ADMIN_ID]):
            if admin_user_id != query.from_user.id : # Qebul eden adminden basqa
                try:
                    # Bu hisse bir az murekkebdir, eger her admin oz mesajini redakte etmelidirse
                    # Sadelesdirmek ucun, sadece qebul eden admine cavab veririk
                    pass
                except Exception:
                    pass

        keyboard_close = [[InlineKeyboardButton("🚫 Zakazy ýapmak", callback_data=f"close_{target_id}")]]
        await query.edit_message_text( # edit_message_text
            text=f"✅ {target_id} ID-li ulanyjynyň zakazy sizin tarapyňyzdan kabul edildi! Indi oňa ýazyp bilersiňiz.\nUlanyja VPN koduny `ss://KOD` formatynda ýazyň.",
            reply_markup=InlineKeyboardMarkup(keyboard_close)
        )
        await context.bot.send_message(
            chat_id=target_id,
            text=f"✅ Zakazyňyz admin ({query.from_user.full_name}) tarapyndan kabul edildi! Admin bilen habarlaşyp bilersiňiz."
        )

    elif data.startswith("close_"):
        if not await is_user_admin(query.from_user.id): # Yalniz adminler baglaya biler
            current_order_admin = None
            target_id_to_find = data.split("_")[1]
            await query.answer("Bu emeliyyat üçün icazeniz yoxdur.", show_alert=True)
            return

        target_id_str = data.split("_")[1]
        admin_id_str = str(query.from_user.id)

        closed_by_admin = False
        if target_id_str in active_orders and active_orders[target_id_str] == admin_id_str: # Admin istifadeci ile olan chat-i baglayir
            del active_orders[target_id_str]
            if admin_id_str in active_orders: # Adminin de qeydini sil
                del active_orders[admin_id_str]
            closed_by_admin = True
            
        if closed_by_admin:
            await query.edit_message_text("✅ Zakaz ýapyldy!") # edit_message_text
            try:
                await context.bot.send_message(chat_id=int(target_id_str), text="🔒 Admin zakazy ýapdy!")
            except Exception as e:
                logger.info(f"Istifadeciye ({target_id_str}) chat baglandi bildirişi gönderilemedi: {e}")
        else:
            await query.answer("Bu zakaz sizin terefinizden idare edilmir ve ya artiq baglanib.", show_alert=True)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_orders
    user = update.effective_user
    user_id_int = user.id
    user_id_str = str(user.id)

    if not update.message: return
    text = update.message.text.strip() if update.message.text else ""
    photo = update.message.photo[-1] if update.message.photo else None
    
    current_admin_status = await is_user_admin(user_id_int)

    # --- Admin Girişləri üçün Xüsusi Vəziyyətlər ---
    if current_admin_status:
        # Test kodu gözlənilir
        if context.user_data.get("waiting_for_test"):
            if text:
                Database.write_test_codes(text)
                await update.message.reply_text("✅ Täze test kody üstünlikli ýatda saklandy!")
            else:
                await update.message.reply_text("❌ Test kodu boş bolup bilmez.")
            del context.user_data["waiting_for_test"]
            return

        # Promokod əlavə edilir
        if context.user_data.get("adding_promo"):
            if text:
                parts = text.split()
                if len(parts) == 2:
                    promo_code, discount_str = parts
                    try:
                        discount = int(discount_str)
                        if not (1 <= discount <= 100): raise ValueError
                        promos = Database.read_promos()
                        promos[promo_code.upper()] = discount
                        Database.write_promos(promos)
                        await update.message.reply_text(f"✅ Promokod: {promo_code.upper()} ({discount}%) üstünlikli goşuldy!")
                    except ValueError:
                        await update.message.reply_text("❌ Skidka 1-dan 100-e çenli aralykda bir san bolmaly. Format: KOD Faiz (məsələn, VPN25 25)")
                else:
                    await update.message.reply_text("❌ Nädogry format. Mysal: PROMO10 10")
            else:
                await update.message.reply_text("❌ Promokod melumatlari boş bolup bilmez.")
            del context.user_data["adding_promo"]
            return

        # Yeni admin ID-si gözlənilir
        if context.user_data.get("waiting_for_new_admin_id"):
            if text:
                try:
                    new_admin_id = int(text)
                    bot_config = Database.read_bot_config()
                    if new_admin_id not in bot_config.get("admin_ids", []):
                        bot_config.setdefault("admin_ids", []).append(new_admin_id)
                        Database.save_bot_config(bot_config)
                        await update.message.reply_text(f"✅ Admin {new_admin_id} üstünlikli goşuldy!")
                        try:
                            await context.bot.send_message(chat_id=new_admin_id, text="🎉 Siz admin edilip bellenildiňiz!")
                        except Exception as e:
                            logger.warning(f"Yeni admine ({new_admin_id}) bildiriş gönderilemedi: {e}")
                    else:
                        await update.message.reply_text(f"ℹ️ Ulanyjy {new_admin_id} eýýäm admin.")
                except ValueError:
                    await update.message.reply_text("❌ ID san bolmaly.")
            else:
                await update.message.reply_text("❌ Admin ID-si boş bolup bilmez.")
            del context.user_data["waiting_for_new_admin_id"]
            return

        # Başlanğıc mesajı düzəldilir
        if context.user_data.get("setting_start_message"):
            bot_config = Database.read_bot_config()
            start_msg_conf = bot_config.get("start_message", {"text": None, "photo_id": None})

            if text == "/clearpicstart":
                start_msg_conf["photo_id"] = None
                await update.message.reply_text("✅ Başlangyç habaryndaky surat aýryldy.")
            elif text == "/clearfullstart":
                start_msg_conf["text"] = None
                start_msg_conf["photo_id"] = None
                await update.message.reply_text("✅ Başlangyç habary (tekst we surat) doly aýryldy.")
            elif photo: # Admin şəkil göndərdi
                start_msg_conf["photo_id"] = photo.file_id
                if update.message.caption: # Şəklin başlığı varsa
                    start_msg_conf["text"] = update.message.caption
                    await update.message.reply_text("✅ Başlangyç habary (surat we tekst) üstünlikli ýatda saklandy!")
                else: # Şəklin başlığı yoxdursa, yalnız şəkli yadda saxla
                    # Sadece photo gonderilirse, text evvelki deyerini qoruyur
                    # Eger yalniz sekil gonderilerken evvelki texti silmek istenilirse: start_msg_conf["text"] = None
                    await update.message.reply_text("✅ Surat ýatda saklandy. Tekst ýoksa, öňki tekst saklanar.")
            elif text: # Admin yalnız mətn göndərdi
                start_msg_conf["text"] = text
                # Eger şəkil əvvəlcədən təyin edilmişdirsə və yalnız mətn göndərilirsə, şəkli silməyin
                # start_msg_conf["photo_id"] qalir - bu deyişmir
                await update.message.reply_text("✅ Başlangyç habaryň teksti üstünlikli ýatda saklandy!")
            else:
                await update.message.reply_text("❌ Düşnüksiz format. Tekst ýa-da surat+tekst (başlıq) iberiň.")
            
            bot_config["start_message"] = start_msg_conf
            Database.save_bot_config(bot_config)
            del context.user_data["setting_start_message"]
            return
        
        # Broadcast mesajı gözlənilir
        broadcasting_type = context.user_data.get("broadcasting_type")
        if broadcasting_type:
            if broadcasting_type == "text_only":
                if text:
                    await _perform_broadcast(context, admin_chat_id=user_id_int, text_message=text)
                else: await update.message.reply_text("❌ Tekst habar boş bolup bilmez.")
            elif broadcasting_type == "photo_text":
                if photo and update.message.caption: # Şəkil və başlıq birlikdə
                    await _perform_broadcast(context, admin_chat_id=user_id_int, photo_id=photo.file_id, caption_message=update.message.caption)
                elif photo and not update.message.caption:
                     await update.message.reply_text("❌ Surat üçin başlığı (caption) da iberiň.")
                elif not photo:
                     await update.message.reply_text("❌ Surat we başlığı (caption) birlikde iberiň.")
            del context.user_data["broadcasting_type"]
            return

    # --- İstifadəçi Promokod Girişi ---
    if context.user_data.get("waiting_for_promo"):
        if text:
            promo_code_input = text.upper()
            promos = Database.read_promos()
            if promo_code_input in promos:
                discount = promos[promo_code_input]
                context.user_data["promo_discount_code"] = promo_code_input # Promokodun özünü də yadda saxla
                context.user_data["promo_discount_value"] = discount # Əvvəlki "promo_discount" əvəzinə
                await update.message.reply_text(f"✅ Promokod '{promo_code_input}' ({discount}%) üstünlikli ulanıldı! VPN bahalary indi skidka bilen görkeziler.")
            else:
                await update.message.reply_text("❌ Bu promokod tapylmady ýa-da möhleti gutardy.")
        else:
             await update.message.reply_text("❌ Promokod boş bolup bilmez.")
        del context.user_data["waiting_for_promo"]
        return

    # --- Aktiv Sifarişlər üzrə Mesajlaşma ---
    if user_id_str in active_orders: # İstifadəçi adminlə danışır
        target_admin_id = active_orders[user_id_str]
        try:
            if photo:
                await context.bot.send_photo(chat_id=target_admin_id, photo=photo.file_id, caption=f"👤 {user.full_name} ({user_id_str}): {update.message.caption or 'Surat'}")
            elif text:
                await context.bot.send_message(chat_id=target_admin_id, text=f"👤 {user.full_name} ({user_id_str}): {text}")
        except Exception as e:
            logger.error(f"Adminden ({target_admin_id}) istifadeciye ({user_id_str}) mesaj gondererken xeta: {e}")
            await update.message.reply_text("❌ Admin bilen elaqe qurmaq mümkün olmadi. Biraz sonra yeniden cehd edin.")
        return

    # Admin aktiv sifarişdə olan istifadəçiyə yazır
    if current_admin_status and user_id_str in active_orders.values(): # Eger admin bir istifadecinin target_admin_id-sidirse
        # Hansı istifadəçi ilə danışdığını tapmaq
        target_user_id = None
        for u_id, adm_id in active_orders.items():
            if adm_id == user_id_str: # Adminin ID-si value olaraq saxlanılır
                target_user_id = u_id
                break
        
        if target_user_id:
            try:
                if photo:
                    await context.bot.send_photo(chat_id=target_user_id, photo=photo.file_id, caption=f"👮 Admin ({user.full_name}): {update.message.caption or 'Surat'}")
                elif text:
                    await context.bot.send_message(chat_id=target_user_id, text=f"👮 Admin ({user.full_name}): {text}")
                
                # Admin VPN açarı göndərirsə, onu istifadəçinin məlumat bazasına əlavə et
                if text and any(text.startswith(proto) for proto in ("ss://", "vmess://")):
                    users_db = Database.read_db()
                    users_db.setdefault(target_user_id, {"keys": [], "ref_count": 0, "referrals": [], "created_at": ""}) # Eger istifadeci yoxdursa (olmamalidir)
                    if "keys" not in users_db[target_user_id]: users_db[target_user_id]["keys"] = []
                    users_db[target_user_id]["keys"].append(text)
                    Database.save_db(users_db)
                    await update.message.reply_text(f"✅ Açar ulanyja ({target_user_id}) üstünlikli goşuldy we iberildi.")

            except Exception as e:
                logger.error(f"Adminden ({user_id_str}) istifadeciye ({target_user_id}) mesaj gondererken xeta: {e}")
                await update.message.reply_text(f"❌ Ulanyja ({target_user_id}) mesaj göndərmək mümkün olmadı. Bloklanmış ola bilər.")
            return

    # Normal istifadəçi tərəfindən göndərilən və açar olan mesajlar
    if not current_admin_status and any(text.startswith(proto) for proto in ("ss://", "vmess://")):
        users_db = Database.read_db()
        users_db.setdefault(user_id_str, {"keys": [], "ref_count": 0, "referrals": [], "created_at": ""})
        if "keys" not in users_db[user_id_str]: users_db[user_id_str]["keys"] = []
        users_db[user_id_str]["keys"].append(text)
        Database.save_db(users_db)
        await update.message.reply_text("✅ Açar üstünlikli ýatda saklandy!")
        return
        
    # Eger heç bir xüsusi vəziyyətə uyğun gəlmirsə və admin deyilsə, menyunu göstər
    # Bu, səhvən göndərilən mesajlara cavab verməmək üçün lazımdır
    # if not current_admin_status and not context.user_data and not (user_id_str in active_orders):
    # pass # Heç bir şey etmə və ya menyunu yenidən göstər
    # await show_main_menu(update, user, context) # Bu çoxlu mesaj göndərilməsinə səbəb ola bilər


async def vpn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Bu buýrugy diňe admin ulanýar!")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Ulanyş usuly: /vpn <id> <açar>")
        return

    target_id = args[0]
    key = " ".join(args[1:]).strip()

    if not any(key.startswith(proto) for proto in ("ss://", "vmess://")):
        await update.message.reply_text("❌ Açar formaty nädogry!")
        return

    users = Database.read_db()
    # Eger istifadeci yoxdursa, yarat (bu veziyyetde adeten olmalidir)
    users.setdefault(target_id, {"keys": [], "ref_count": 0, "referrals": [], "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    if "keys" not in users[target_id]: users[target_id]["keys"] = []
    
    users[target_id]["keys"].append(key)
    Database.save_db(users)

    await update.message.reply_text(f"✅ Açar üstünlikli goşuldy: {target_id}")
    try:
        await context.bot.send_message(chat_id=int(target_id), text=f"🔑 Size täze VPN açar berildi:\n`{key}`", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"VPN komutu ile açar gönderilemedi ({target_id}): {e}")
        await update.message.reply_text(f"⚠️ Açar {target_id} ID-li ulanyja iberilmedi (belki bloklanib).")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_orders
    user_id_str = str(update.effective_user.id)
    admin_id_associated = active_orders.pop(user_id_str, None) # İstifadəçinin qeydini sil və əlaqəli admini al
    if admin_id_associated:
        active_orders.pop(admin_id_associated, None) # Əlaqəli adminin qeydini də sil
        await update.message.reply_text("🔕 Admin bilen habarlaşma dayandyryldy.")
        try:
            await context.bot.send_message(chat_id=int(admin_id_associated), text=f"ℹ️ Ulanyjy ({update.effective_user.full_name}, {user_id_str}) sizin bilen habarlaşmany /stop etdi.")
        except Exception as e:
            logger.info(f"Stop komutu ile admine ({admin_id_associated}) bildiriş gönderilemedi: {e}")
    else:
        await update.message.reply_text("ℹ️ Hazirda admin bilen aktiv habarlaşma ýok.")


async def add_promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # /add_promo
    if not await is_user_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Bu buýrugy diňe admin ulanýar!")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Ullanmak: /add_promo <kod> <skidka_faizi>")
        return
    promo_code, discount_str = context.args
    try:
        discount = int(discount_str)
        if not (1 <= discount <= 100):
            raise ValueError("Faiz 1-100 aralığında olmalıdır.")
        promos = Database.read_promos()
        promos[promo_code.upper()] = discount # Kodu böyük hərflərlə yadda saxla
        Database.write_promos(promos)
        await update.message.reply_text(f"✅ Promokod: {promo_code.upper()} ({discount}%) üstünlikli goşuldy!")
    except ValueError as e:
        await update.message.reply_text(f"❌ Nädogry format: {e}. Skidka 1-dan 100-e çenli aralykda bir san bolmaly.")


async def remove_promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # /remove_promo
    if not await is_user_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Bu buýrugy diňe admin ulanýar!")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Ullanmak: /remove_promo <kod>")
        return
    promo_code_to_remove = context.args[0].upper() # Kodu böyük hərflərlə axtar
    promos = Database.read_promos()
    if promo_code_to_remove in promos:
        del promos[promo_code_to_remove]
        Database.write_promos(promos)
        await update.message.reply_text(f"✅ Promokod {promo_code_to_remove} pozuldy!")
    else:
        await update.message.reply_text(f"❌ Promokod '{promo_code_to_remove}' tapylmady!")


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("add_promo", add_promo_command)) # Komanda olaraq elave edildi
    application.add_handler(CommandHandler("remove_promo", remove_promo_command)) # Komanda olaraq elave edildi
    application.add_handler(CommandHandler("vpn", vpn_command))
    application.add_handler(CommandHandler("clearpicstart", message_handler)) # For start message editing
    application.add_handler(CommandHandler("clearfullstart", message_handler)) # For start message editing


    # Callback Query Handlers (Admin Panel and Submenus)
    application.add_handler(CallbackQueryHandler(show_admin_menu, pattern="^admin_panel$")) # admin_panel-e qayitmaq ucun
    application.add_handler(CallbackQueryHandler(main_menu_user_view_callback, pattern="^main_menu_user_view$"))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    
    # Broadcast Callbacks
    application.add_handler(CallbackQueryHandler(admin_broadcast_options, pattern="^admin_broadcast_options$"))
    application.add_handler(CallbackQueryHandler(broadcast_text_only_prompt, pattern="^broadcast_text_only$"))
    application.add_handler(CallbackQueryHandler(broadcast_photo_text_prompt, pattern="^broadcast_photo_text$"))
    
    application.add_handler(CallbackQueryHandler(admin_export, pattern="^admin_export$"))
    
    # Promo Callbacks (from admin panel)
    application.add_handler(CallbackQueryHandler(admin_add_promo_prompt, pattern="^admin_add_promo_prompt$"))
    application.add_handler(CallbackQueryHandler(admin_remove_promo_prompt, pattern="^admin_remove_promo_prompt$"))
    application.add_handler(CallbackQueryHandler(confirm_remove_promo_callback, pattern=r"^confirm_remove_promo_"))

    application.add_handler(CallbackQueryHandler(admin_change_test, pattern="^admin_change_test$"))

    # Admin Management Callbacks
    application.add_handler(CallbackQueryHandler(admin_manage_admins_menu, pattern="^admin_manage_admins_menu$"))
    application.add_handler(CallbackQueryHandler(admin_add_admin_prompt, pattern="^admin_add_admin_prompt$"))
    application.add_handler(CallbackQueryHandler(admin_remove_admin_prompt, pattern="^admin_remove_admin_prompt$"))
    application.add_handler(CallbackQueryHandler(confirm_remove_admin_callback, pattern=r"^confirm_remove_admin_"))
    application.add_handler(CallbackQueryHandler(admin_list_admins, pattern="^admin_list_admins$"))

    # Start Message Callbacks
    application.add_handler(CallbackQueryHandler(admin_set_start_msg_prompt, pattern="^admin_set_start_msg_prompt$"))

    # General Button Handler (should be one of the last callback handlers)
    application.add_handler(CallbackQueryHandler(button_handler)) # Butun diger callback-leri idare edir

    # Message Handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.PHOTO, message_handler)) # FOTO mesajlarini da message_handler-e yonlendirir

    logger.info("Bot başladıldı...")
    application.run_polling()

if __name__ == "__main__":
    main()
