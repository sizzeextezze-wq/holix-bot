import logging
import sqlite3
import uuid
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ⚙️ НАСТРОЙКИ
BOT_TOKEN = '8772485583:AAHm_9qeLQA1ldQ0REGnoAQlGbbw0w-Nf-w'
ADMIN_ID = 8414552583 # ВСТАВЬ СВОЙ TELEGRAM ID (узнать у @userinfobot)

REF_BONUS_DAYS = 5
BOT_USERNAME = 'HoliX_VPNbot'

# Польша (основная панель)
PL_API = 'http://pl2.h1cloud.net:25741/api'
PL_TOKEN = '16ac3a8d6ae547579d1a1cc2da138e6ecf320e80e77f454c8830ba8025f4ef11'
PL_INBOUND_TCP = 'ib_3b842feb11'
PL_INBOUND_GRPC = 'ib_758937ca4e'
PL_INBOUND_XHTTP = 'ib_604223be6f'

# Финляндия (нода)
FI_API = 'http://fi1.h1cloud.net:25148/api'
FI_TOKEN = '938d2b53d2794924ac388dc3d1c5dfb2c5912b4397874995a3b23fe0bfb7ec04'
FI_INBOUND_TCP = 'ib_052c2d9a45'
FI_INBOUND_GRPC = 'ib_a52022323b'
FI_INBOUND_XHTTP = 'ib_57d2be5908'


def headers(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def api_create(api, token, name, uuid_str, days, dev, gb, inbounds):
    try:
        r = requests.post(f'{api}/create', headers=headers(token), json={
            'name': name, 'uuid': uuid_str, 'days': days,
            'device_limit': dev, 'traffic_limit_gb': gb,
            'manual': True, 'channels': [], 'inbound_ids': inbounds
        }, timeout=15)
        if r.status_code in (200, 201):
            return True, r.text
        if r.status_code == 409:
            return True, 'exists'
        return False, r.text
    except Exception as e:
        return False, str(e)


def api_extend(api, token, name, days):
    try:
        r = requests.patch(f'{api}/clients/{name}', headers=headers(token),
                           json={'days': days}, timeout=10)
        return r.status_code == 200, r.text
    except Exception as e:
        return False, str(e)


def api_get(api, token, name):
    try:
        r = requests.get(f'{api}/clients/{name}', headers=headers(token), timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def create_everywhere(name, uuid_str, days=3, dev=1, gb=20):
    res = []
    pl_inb = [PL_INBOUND_TCP, PL_INBOUND_GRPC, PL_INBOUND_XHTTP]
    ok, _ = api_create(PL_API, PL_TOKEN, name, uuid_str, days, dev, gb, pl_inb)
    res.append(('PL', ok))
    fi_inb = [FI_INBOUND_TCP, FI_INBOUND_GRPC, FI_INBOUND_XHTTP]
    ok, _ = api_create(FI_API, FI_TOKEN, name, uuid_str, days, dev, gb, fi_inb)
    res.append(('FI', ok))
    return res


def extend_everywhere(name, days):
    res = []
    ok, _ = api_extend(PL_API, PL_TOKEN, name, days)
    res.append(('PL', ok))
    ok, _ = api_extend(FI_API, FI_TOKEN, name, days)
    res.append(('FI', ok))
    return res


def get_sub_url(name):
    data = api_get(PL_API, PL_TOKEN, name)
    if data:
        return data.get('subscription_url') or data.get('sub_url', '')
    return ''


def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        uuid TEXT, referred_by INTEGER, ref_count INTEGER DEFAULT 0,
        bonus_days INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()


def get_user(uid):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (uid,))
    row = c.fetchone()
    conn.close()
    return row


def add_user(uid, un, fn, uu, ref=None):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, uuid, referred_by) VALUES (?, ?, ?, ?, ?)',
              (uid, un, fn, uu, ref))
    conn.commit()
    conn.close()


def add_bonus(uid, days):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('UPDATE users SET bonus_days = bonus_days + ?, ref_count = ref_count + 1 WHERE user_id = ?',
              (days, uid))
    conn.commit()
    conn.close()


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Пробный доступ (3 дня)", callback_data="trial")],
        [InlineKeyboardButton("💳 Купить подписку", callback_data="buy")],
        [InlineKeyboardButton("🔗 Реферальная программа", callback_data="ref")],
        [InlineKeyboardButton("📱 Подключиться", callback_data="connect")],
        [InlineKeyboardButton("💬 Поддержка", url="https://t.me/holiX_Sup")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref = None
    if context.args and context.args[0].startswith('ref_'):
        try:
            ref = int(context.args[0].replace('ref_', ''))
        except:
            pass

    existing = get_user(user.id)
    if not existing:
        new_uuid = str(uuid.uuid4())
        add_user(user.id, user.username, user.first_name, new_uuid, ref)
        name = f'tg_{user.id}'
        create_everywhere(name, new_uuid, days=3, dev=1, gb=20)

        if ref and ref != user.id:
            add_bonus(ref, REF_BONUS_DAYS)
            extend_everywhere(f'tg_{ref}', REF_BONUS_DAYS)
            try:
                await context.bot.send_message(ref,
                    f"🎉 По твоей ссылке пришёл друг!\n💰 +{REF_BONUS_DAYS} дней к подписке.")
            except:
                pass

    text = (f"👋 Привет, {user.first_name}!\n\n"
            f"⚡ HoliX VPN\n\n🚀 Быстрый VPN без границ\n♾ Безлимит\n🛡 Без логов\n🌍 6 локаций\n\n"
            f"🎁 Первые 3 дня — бесплатно!\n\nВыбери действие 👇")

    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu())


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = f'tg_{q.from_user.id}'

    if q.data == "trial":
        sub = get_sub_url(name)
        txt = f"🎁 Твой пробный доступ!\n\n📱 Ссылка:\n{sub}\n\nСкачай Happ (Android) или Incy (iPhone)." if sub else "🎁 Пробный доступ\n\nНапиши @holiX_Sup"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Как подключиться", callback_data="connect")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")]]))

    elif q.data == "buy":
        await q.edit_message_text(
            "💳 Тарифы:\n⚡ 70₽ • 🚀 150₽ • 🔥 350₽ • 👑 599₽\n\nНапиши @holiX_Sup",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Связаться", url="https://t.me/holiX_Sup")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back")]]))

    elif q.data == "ref":
        u = q.from_user
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{u.id}"
        ud = get_user(u.id)
        rc = ud[5] if ud else 0
        bn = ud[6] if ud else 0
        await q.edit_message_text(
            f"🔗 Реф-программа\n\n+{REF_BONUS_DAYS} дней за друга!\n\nТвоя ссылка:\n{link}\n\n👥 Приглашено: {rc}\n🎁 Бонусов: +{bn} дней",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back")]]))

    elif q.data == "connect":
        sub = get_sub_url(name)
        txt = "📱 Скачай Happ (Android) или Incy (iPhone)\n\nВставь ссылку → Connect\n\n"
        if sub:
            txt += f"🔗 {sub}"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="back")]]))

    elif q.data == "back":
        await start(update, context)


async def myref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{u.id}"
    ud = get_user(u.id)
    rc = ud[5] if ud else 0
    bn = ud[6] if ud else 0
    await update.message.reply_text(f"🔗 {link}\n\n👥 {rc}\n🎁 +{bn} дней")


async def admin_extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("/extend USER_ID DAYS")
        return
    try:
        uid, days = int(args[0]), int(args[1])
        res = extend_everywhere(f'tg_{uid}', days)
        txt = '\n'.join([f'{p}: {"✅" if ok else "❌"}' for p, ok in res])
        await update.message.reply_text(f"Результат:\n{txt}")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myref", myref))
    app.add_handler(CommandHandler("extend", admin_extend))
    app.add_handler(CallbackQueryHandler(button))
    print("✅ Бот запущен")
    app.run_polling()


if __name__ == '__main__':
    main()
