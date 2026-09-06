import sqlite3
import random
from html import escape
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TOKEN = "YOUR_TOKEN"
DB = "santa.db"


# ------------------------------- DB INIT --------------------------------

def db():
    return sqlite3.connect(DB)


def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER UNIQUE,
        username TEXT,
        first_name TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS wishlist(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS userdata(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS pairs(
        user_id INTEGER UNIQUE,
        target_id INTEGER
    )""")

    conn.commit()
    conn.close()


init_db()


# ------------------------------- UTILS -----------------------------------

def get_or_create_user(update: Update):
    tg_id = update.effective_user.id
    username = update.effective_user.username
    first = update.effective_user.first_name

    conn = db()
    c = conn.cursor()

    c.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,))
    row = c.fetchone()

    if row:
        conn.close()
        return row[0]

    c.execute("INSERT INTO users(tg_id, username, first_name) VALUES (?,?,?)",
              (tg_id, username, first))
    conn.commit()
    uid = c.lastrowid
    conn.close()
    return uid


def get_user_count():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count


def get_wishlist(uid):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT text FROM wishlist WHERE user_id=?", (uid,))
    rows = c.fetchall()
    conn.close()
    return "\n".join([f"• {r[0]}" for r in rows]) if rows else "Нічого не додано."


def add_wishlist(uid, text):
    conn = db()
    c = conn.cursor()
    c.execute("INSERT INTO wishlist(user_id, text) VALUES (?,?)", (uid, text))
    conn.commit()
    conn.close()


def get_userdata(uid):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT text FROM userdata WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "Дані не вказані."


def set_userdata(uid, text):
    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM userdata WHERE user_id=?", (uid,))
    c.execute("INSERT INTO userdata(user_id, text) VALUES (?,?)", (uid, text))
    conn.commit()
    conn.close()


def get_pair(uid):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT target_id FROM pairs WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def save_pairs(pairs):
    conn = db()
    c = conn.cursor()

    c.execute("DELETE FROM pairs")
    for u, t in pairs.items():
        c.execute("INSERT INTO pairs(user_id, target_id) VALUES (?,?)", (u, t))

    conn.commit()
    conn.close()


# ------------------------------- KEYBOARDS -----------------------------------

def main_menu():
    kb = [
        [InlineKeyboardButton("🎁 Мій вішліст", callback_data="wishlist")],
        [InlineKeyboardButton("📦 Мої дані", callback_data="userdata")],
        [InlineKeyboardButton("🎅 Кому я дарую?", callback_data="target")],
    ]
    return InlineKeyboardMarkup(kb)


def back_btn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Повернутись", callback_data="back")]
    ])


# ------------------------------- HANDLERS -----------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_or_create_user(update)

    text = (
        "🎄 <b>Таємний Санта 2026</b>\n\n"
        f"👥 Учасників зараз: <b>{get_user_count()}</b>\n\n"
        "Оберіть дію:"
    )

    msg = await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="HTML")




async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "🎄 <b>Таємний Санта 2025</b>\n\n"
        f"👥 Учасників зараз: <b>{get_user_count()}</b>\n\n"
        "Оберіть дію:"
    )

    msg = await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="HTML")

    context.user_data["last_bot_message"] = msg.message_id
    context.user_data["mode"] = None



async def wishlist_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = get_or_create_user(update)
    wl = get_wishlist(uid)

    text = (
        "🎁 <b>Твій вішліст:</b>\n\n"
        f"{wl}\n\n"
        "📝 Надішли мені будь-яке повідомлення — додам у список."
    )

    msg = await query.edit_message_text(text, reply_markup=back_btn(), parse_mode="HTML")

    context.user_data["last_bot_message"] = msg.message_id
    context.user_data["mode"] = "wishlist"


async def wishlist_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("mode") != "wishlist":
        return

    uid = get_or_create_user(update)


    try:
        await update.message.delete()
    except Exception:
        pass


    add_wishlist(uid, update.message.text)


    wl = get_wishlist(uid)
    safe_wl = escape(wl)
    new_text = (
        "🎁 <b>Твій вішліст:</b>\n\n"
        f"{safe_wl}\n\n"
        "📝 Напиши нове повідомлення — додам у список."
    )

    bot_msg_id = context.user_data.get("last_bot_message")

    if bot_msg_id:
        try:

            msg = await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=bot_msg_id,
                text=new_text,
                reply_markup=back_btn(),
                parse_mode="HTML"
            )

            if hasattr(msg, "message_id"):
                context.user_data["last_bot_message"] = msg.message_id
            return
        except Exception as e:

            print("❌ wishlist edit_message_text error:", e)



async def userdata_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = get_or_create_user(update)
    data = get_userdata(uid)
    safe_data = escape(data)

    text = (
        "📦 <b>Твої дані для Нової Пошти:</b>\n\n"
        f"<pre>{safe_data}</pre>\n\n"
        "✏️ <b>Щоб оновити — надішли ОДНИМ повідомленням усі дані:</b>\n"
        "• ПІБ\n"
        "• Місто\n"
        "• Відділення/поштомат\n"
        "• Телефон\n\n"
        "Попередні дані буде повністю замінено."
    )

    msg = await query.edit_message_text(
        text,
        reply_markup=back_btn(),
        parse_mode="HTML"
    )

    context.user_data["mode"] = "userdata"
    context.user_data["last_bot_message"] = msg.message_id


async def userdata_save(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("mode") != "userdata":
        return

    uid = get_or_create_user(update)


    try:
        await update.message.delete()
    except Exception:
        pass


    text_in = update.message.text or ""
    lines = [l.strip() for l in text_in.splitlines() if l.strip()]

    bot_msg_id = context.user_data.get("last_bot_message")
    if not bot_msg_id:

        return

    if len(lines) < 4:

        new_text = (
            "⚠️ <b>Потрібно надіслати <u>усі 4 дані одним повідомленням</u>!</b>\n\n"
            "👉 Прізвище та імʼя\n"
            "👉 Телефон\n"
            "👉 Місто\n"
            "👉 Відділення/Поштомат\n\n"
            "Спробуй ще раз ⬆️"
        )
    else:

        lastname = lines[0]
        phone = lines[1]
        city = lines[2]
        branch = lines[3]


        set_userdata(uid, f"{lastname}\n{phone}\n{city}\n{branch}")


        new_text = (
            "📦 <b>Твої дані для Нової Пошти оновлено!</b>\n\n"
            f"👤 <b>ПІБ:</b> {escape(lastname)}\n"
            f"📱 <b>Телефон:</b> {escape(phone)}\n"
            f"🏙 <b>Місто:</b> {escape(city)}\n"
            f"🏤 <b>Відділення:</b> {escape(branch)}\n\n"
            "<i>Щоби змінити — просто надішли нове повідомлення з усіма даними.</i>"
        )


    try:
        msg = await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=bot_msg_id,
            text=new_text,
            parse_mode="HTML",
            reply_markup=back_btn()
        )
        if hasattr(msg, "message_id"):
            context.user_data["last_bot_message"] = msg.message_id
    except Exception as e:
        print("userdata edit error:", e)



async def target_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = get_or_create_user(update)
    target = get_pair(uid)

    if not target:
        await query.edit_message_text("❄️ Санта ще не розподілив подарунки.", reply_markup=back_btn())
        return

    conn = db()
    c = conn.cursor()
    c.execute("SELECT first_name FROM users WHERE id=?", (target,))
    row = c.fetchone()
    name = row[0] if row else "Невідомо"
    conn.close()

    wl = get_wishlist(target)
    data = get_userdata(target)

    safe_wl = escape(wl)
    safe_data = escape(data)

    text = (
        f"🎅 <b>Ти даруєш:</b>\n\n"
        f"👤 <b>{escape(name)}</b>\n\n"
        f"🎁 <b>Його побажання:</b>\n{safe_wl}" + f"\n\n📦 Його данні:\n<pre>{safe_data}</pre>\n\n"
    )

    await query.edit_message_text(text, reply_markup=back_btn(), parse_mode="HTML")



async def run_santa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()

    if len(users) < 2:
        await update.message.reply_text("Мало учасників!")
        return

    shuffled = users.copy()
    random.shuffle(shuffled)

    for i in range(len(users)):
        if users[i] == shuffled[i]:
            j = (i + 1) % len(users)
            shuffled[i], shuffled[j] = shuffled[j], shuffled[i]

    pairs = {users[i]: shuffled[i] for i in range(len(users))}
    save_pairs(pairs)


    conn = db()
    c = conn.cursor()
    for uid in users:
        c.execute("SELECT tg_id FROM users WHERE id=?", (uid,))
        row = c.fetchone()
        if not row:
            continue
        tg = row[0]
        try:
            await update.get_bot().send_message(tg, "🎅 Санта вже наближається! Подарунки розподілені!")
        except Exception:
            pass
    conn.close()

    await update.message.reply_text("Розподіл виконано!", reply_markup=back_btn())



async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.text:
        return

    mode = context.user_data.get("mode")

    if mode == "wishlist":
        await wishlist_add(update, context)
        return

    if mode == "userdata":
        await userdata_save(update, context)
        return


    return


# ------------------------------- APPLICATION -----------------------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run_santa", run_santa))

    app.add_handler(CallbackQueryHandler(back, pattern="back"))
    app.add_handler(CallbackQueryHandler(wishlist_menu, pattern="wishlist"))
    app.add_handler(CallbackQueryHandler(userdata_menu, pattern="userdata"))
    app.add_handler(CallbackQueryHandler(target_menu, pattern="target"))


    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    app.run_polling()


if __name__ == "__main__":
    main()
