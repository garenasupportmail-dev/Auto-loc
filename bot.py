import os, json, logging, threading, time, random
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

# ============ LOGGING ============
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============ FLASK (Render port fix) ============
flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health():
    return "BOT RUNNING", 200

def run_flask():
    try:
        port = int(os.environ.get('PORT', 5000))
        flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask error: {e}")

# ============ CONFIG ============
# Token is read from an environment variable ONLY.
# Set BOT_TOKEN in Render -> your service -> Environment -> Add Environment Variable.
# Never hardcode a real token in this file or paste it in chat.
BOT_TOKEN = os.environ.get('8499551746:AAHCgQJZDMvjmmh-IgvzmJ_jg9M0_6WKWOI')
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set.")

OWNER_ID = 8471373583
CHANNEL_USERNAME = "@KALYUGESCROWSERVICE"

ADMINS_FILE = "admins.json"
GROUPS_FILE = "groups.json"
MAX_ADMINS = 25

def load_json(fp, default):
    if os.path.exists(fp):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {fp}: {e}")
    return default

def save_json(fp, data):
    try:
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save {fp}: {e}")

admins = load_json(ADMINS_FILE, {})       # {"123456": "Name"}
groups = load_json(GROUPS_FILE, {})       # {"chat_id": {"locked": bool}}

START_TIME = datetime.now()

# ============ STYLISH FONTS ============
STYLISH = {
    'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅',
    'G': '𝐆', 'H': '𝐇', 'I': '𝐈', 'J': '𝐉', 'K': '𝐊', 'L': '𝐋',
    'M': '𝐌', 'N': '𝐍', 'O': '𝐎', 'P': '𝐏', 'Q': '𝐐', 'R': '𝐑',
    'S': '𝐒', 'T': '𝐓', 'U': '𝐔', 'V': '𝐕', 'W': '𝐖', 'X': '𝐗',
    'Y': '𝐘', 'Z': '𝐙',
    '0': '𝟎', '1': '𝟏', '2': '𝟐', '3': '𝟑', '4': '𝟒',
    '5': '𝟓', '6': '𝟔', '7': '𝟕', '8': '𝟖', '9': '𝟗'
}

def stylish(text):
    result = ""
    for char in text:
        if 'A' <= char.upper() <= 'Z' or '0' <= char <= '9':
            upper = char.upper()
            if upper in STYLISH:
                styled = STYLISH[upper]
                result += styled.lower() if char.islower() else styled
            else:
                result += char
        else:
            result += char
    return result

# ============ PREMIUM EMOJIS ============
PREMIUM_EMOJIS = {
    "verified":  {"id": "6246537187614005254", "fallback": "✅"},
    "eye":       {"id": "6035338338406242050", "fallback": "👁️"},
    "fire":      {"id": "4956222745814762495", "fallback": "🔥"},
    "heart":     {"id": "5783157259152397008", "fallback": "❤️"},
    "star":      {"id": "6244496562752331516", "fallback": "⭐"},
    "sparkle":   {"id": "6010338729640596556", "fallback": "✨"},
    "crown":     {"id": "5794422335599546668", "fallback": "👑"},
    "shield":    {"id": "6086778246882399112", "fallback": "🛡️"},
    "bolt":      {"id": "5791970059597386804", "fallback": "⚡"},
    "check":     {"id": "5977034395173715994", "fallback": "✅"},
    "cross":     {"id": "5977028203127113755", "fallback": "❌"},
    "warning":   {"id": "5463369591689987411", "fallback": "⚠️"},
    "info":      {"id": "5463371706332570811", "fallback": "ℹ️"},
    "wave":      {"id": "6134450255637642537", "fallback": "👋"},
    "lock":      {"id": "5433601609076586221", "fallback": "🔒"},
    "unlock":    {"id": "5434064563601421981", "fallback": "🔓"},
    "clock":     {"id": "5433854239052935880", "fallback": "🕒"},
    "megaphone": {"id": "6035432248717147837", "fallback": "📢"},
}
PREMIUM_NAMES = list(PREMIUM_EMOJIS.keys())

def get_emoji():
    name = random.choice(PREMIUM_NAMES)
    d = PREMIUM_EMOJIS[name]
    return f'<tg-emoji emoji-id="{d["id"]}">{d["fallback"]}</tg-emoji>'

def get_specific_emoji(name):
    d = PREMIUM_EMOJIS.get(name)
    if d:
        return f'<tg-emoji emoji-id="{d["id"]}">{d["fallback"]}</tg-emoji>'
    return "✨"

def decorate(text):
    lines = text.split('\n')
    out = []
    for line in lines:
        out.append(f"{get_emoji()} {line} {get_emoji()}" if line.strip() else line)
    return '\n'.join(out)

# ============ HELPERS ============
def is_owner(uid):
    return uid == OWNER_ID

def is_bot_admin(uid):
    return is_owner(uid) or str(uid) in admins

def group_entry(chat_id):
    cid = str(chat_id)
    if cid not in groups:
        groups[cid] = {"locked": False}
        save_json(GROUPS_FILE, groups)
    return groups[cid]

async def is_group_admin_or_bot_admin(update, context):
    uid = update.effective_user.id
    if is_bot_admin(uid):
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, uid)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

# ============ FORCE JOIN (green button) ============
async def not_member_msg(update, context):
    keyboard = [[InlineKeyboardButton(
        "✅ Join Group",
        url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
    )]]
    msg = (
        f"{get_specific_emoji('warning')} {stylish('JOIN REQUIRED')}\n\n"
        f"{get_specific_emoji('megaphone')} Please join {CHANNEL_USERNAME} first!"
    )
    await update.effective_message.reply_text(
        decorate(msg),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def check_channel_member(update, context):
    uid = update.effective_user.id
    if is_owner(uid):
        return True
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"Channel check failed for {uid}: {e}")
        return False

# ============ LOCK / UNLOCK ============
LOCKED_PERMS = ChatPermissions(
    can_send_messages=False, can_send_audios=False, can_send_documents=False,
    can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
    can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
    can_add_web_page_previews=False,
)
UNLOCKED_PERMS = ChatPermissions(
    can_send_messages=True, can_send_audios=True, can_send_documents=True,
    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
    can_add_web_page_previews=True,
)

async def lock_cmd(update, context):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text(decorate("This only works inside a group."), parse_mode=ParseMode.HTML)
        return
    if not await is_group_admin_or_bot_admin(update, context):
        await update.message.reply_text(decorate(f"{get_specific_emoji('cross')} Admins only!"), parse_mode=ParseMode.HTML)
        return
    try:
        await context.bot.set_chat_permissions(update.effective_chat.id, LOCKED_PERMS)
        group_entry(update.effective_chat.id)["locked"] = True
        save_json(GROUPS_FILE, groups)
        msg = f"{get_specific_emoji('lock')} {stylish('GROUP LOCKED')}\n\nOnly admins can send messages now."
        await update.message.reply_text(decorate(msg), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Lock failed: {e}")
        await update.message.reply_text(
            decorate(f"{get_specific_emoji('warning')} Failed to lock — make sure the bot is an admin with 'Restrict Members' permission."),
            parse_mode=ParseMode.HTML
        )

async def unlock_cmd(update, context):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text(decorate("This only works inside a group."), parse_mode=ParseMode.HTML)
        return
    if not await is_group_admin_or_bot_admin(update, context):
        await update.message.reply_text(decorate(f"{get_specific_emoji('cross')} Admins only!"), parse_mode=ParseMode.HTML)
        return
    try:
        await context.bot.set_chat_permissions(update.effective_chat.id, UNLOCKED_PERMS)
        group_entry(update.effective_chat.id)["locked"] = False
        save_json(GROUPS_FILE, groups)
        msg = f"{get_specific_emoji('unlock')} {stylish('GROUP UNLOCKED')}\n\nEveryone can send messages again."
        await update.message.reply_text(decorate(msg), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Unlock failed: {e}")
        await update.message.reply_text(
            decorate(f"{get_specific_emoji('warning')} Failed to unlock — make sure the bot is an admin with 'Restrict Members' permission."),
            parse_mode=ParseMode.HTML
        )

# ============ TIME ============
async def time_cmd(update, context):
    now = datetime.now()
    uptime = now - START_TIME
    hours, rem = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(rem, 60)
    msg = (
        f"{get_specific_emoji('clock')} {stylish('BOT TIME')}\n\n"
        f"Current: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Uptime: {hours}h {minutes}m {seconds}s"
    )
    await update.message.reply_text(decorate(msg), parse_mode=ParseMode.HTML)

# ============ ADMIN PANEL (owner only) ============
async def addadmin_cmd(update, context):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text(decorate(f"{get_specific_emoji('cross')} Owner only!"), parse_mode=ParseMode.HTML)
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(decorate("Usage: /addadmin USER_ID"), parse_mode=ParseMode.HTML)
        return
    if len(admins) >= MAX_ADMINS:
        await update.message.reply_text(decorate(f"{get_specific_emoji('warning')} Max {MAX_ADMINS} admins reached."), parse_mode=ParseMode.HTML)
        return
    target = context.args[0]
    try:
        chat = await context.bot.get_chat(int(target))
        name = chat.first_name or chat.username or target
    except Exception:
        name = target
    admins[target] = name
    save_json(ADMINS_FILE, admins)
    await update.message.reply_text(
        decorate(f"{get_specific_emoji('check')} {name} ({target}) added as bot admin. ({len(admins)}/{MAX_ADMINS})"),
        parse_mode=ParseMode.HTML
    )

async def removeadmin_cmd(update, context):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text(decorate(f"{get_specific_emoji('cross')} Owner only!"), parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(decorate("Usage: /removeadmin USER_ID"), parse_mode=ParseMode.HTML)
        return
    target = context.args[0]
    if target in admins:
        removed = admins.pop(target)
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text(decorate(f"{get_specific_emoji('check')} {removed} ({target}) removed."), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(decorate("That user is not a bot admin."), parse_mode=ParseMode.HTML)

async def adminlist_cmd(update, context):
    if not is_bot_admin(update.effective_user.id):
        await update.message.reply_text(decorate(f"{get_specific_emoji('cross')} Admins only!"), parse_mode=ParseMode.HTML)
        return
    body = "\n".join([f"{get_specific_emoji('shield')} {name} — {uid}" for uid, name in admins.items()]) or "No bot admins added yet."
    msg = f"{get_specific_emoji('crown')} {stylish('ADMIN PANEL')} ({len(admins)}/{MAX_ADMINS})\n\n{body}"
    await update.message.reply_text(decorate(msg), parse_mode=ParseMode.HTML)

# ============ BROADCAST ============
async def broadcast_cmd(update, context):
    if not is_bot_admin(update.effective_user.id):
        await update.message.reply_text(decorate(f"{get_specific_emoji('cross')} Admins only!"), parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(decorate("Usage: /broadcast <message>"), parse_mode=ParseMode.HTML)
        return
    text = " ".join(context.args)
    sent, failed = 0, 0
    await update.message.reply_text(decorate(f"{get_specific_emoji('bolt')} Broadcasting to {len(groups)} groups..."), parse_mode=ParseMode.HTML)
    for chat_id in list(groups.keys()):
        try:
            await context.bot.send_message(
                chat_id=int(chat_id),
                text=decorate(f"{get_specific_emoji('megaphone')} {stylish('ANNOUNCEMENT')}\n\n{text}"),
                parse_mode=ParseMode.HTML
            )
            sent += 1
        except Exception as e:
            logger.warning(f"Broadcast to {chat_id} failed: {e}")
            failed += 1
    await update.message.reply_text(decorate(f"{get_specific_emoji('check')} Sent: {sent} | {get_specific_emoji('cross')} Failed: {failed}"), parse_mode=ParseMode.HTML)

# ============ TRACK GROUPS ============
async def track_group(update, context):
    if update.effective_chat and update.effective_chat.type in ("group", "supergroup"):
        group_entry(update.effective_chat.id)

# ============ START ============
async def start_cmd(update, context):
    uid = update.effective_user.id
    if update.effective_chat.type == "private":
        if not is_bot_admin(uid) and not await check_channel_member(update, context):
            await not_member_msg(update, context)
            return
        msg = (
            f"{get_specific_emoji('wave')} {stylish('WELCOME')}\n\n"
            f"{get_specific_emoji('lock')} /lock - Lock this group\n"
            f"{get_specific_emoji('unlock')} /unlock - Unlock this group\n"
            f"{get_specific_emoji('clock')} /time - Bot time & uptime\n"
        )
        if is_bot_admin(uid):
            msg += (
                f"\n{get_specific_emoji('crown')} {stylish('ADMIN PANEL')}\n"
                f"/addadmin USER_ID\n/removeadmin USER_ID\n/adminlist\n/broadcast <message>\n"
            )
        await update.message.reply_text(decorate(msg), parse_mode=ParseMode.HTML)
    else:
        await track_group(update, context)
        await update.message.reply_text(
            decorate(f"{get_specific_emoji('wave')} Bot active here. Admins can use /lock and /unlock."),
            parse_mode=ParseMode.HTML
        )

# ============ ERROR HANDLER ============
async def error_handler(update, context):
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)

# ============ MAIN ============
def main():
    logger.info("Starting bot...")
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info(f"Flask health server started on port {os.environ.get('PORT', '5000')}")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("time", time_cmd))
    app.add_handler(CommandHandler("lock", lock_cmd))
    app.add_handler(CommandHandler("unlock", unlock_cmd))
    app.add_handler(CommandHandler("addadmin", addadmin_cmd))
    app.add_handler(CommandHandler("removeadmin", removeadmin_cmd))
    app.add_handler(CommandHandler("adminlist", adminlist_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_error_handler(error_handler)

    logger.info(f"Owner ID: {OWNER_ID}")
    logger.info(f"Channel: {CHANNEL_USERNAME}")

    while True:
        try:
            app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Polling crashed: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
