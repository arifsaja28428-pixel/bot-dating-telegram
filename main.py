import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import date, datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==================== DUMMY WEB SERVER UNTUK RENDER FREE TIER ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot Active")

def run_dummy_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

# Jalankan server HTTP kecil di thread terpisah
threading.Thread(target=run_dummy_server, daemon=True).start()
# =================================================================================

# ==================== PENGATURAN BOT ====================
TOKEN = "8872474814:AAExby0Bw7KFCR5KyTptAwhd62czO9dlx_8"
ADMIN_ID = 8670588012
MAX_DAILY_SEARCH = 100

ADMIN_USERNAME = "@brobro2612"
PAYMENT_DETAILS = (
    "💳 **PILIHAN PEMBAYARAN VIP (1 BULAN)**\n\n"
    "• **DANA :** `085703333939` (a.n. Arif)\n"
    "💰 **Harga VIP:** Rp10.000 / 30 Hari"
)
# ========================================================

logging.basicConfig(level=logging.INFO)

waiting_queue = []
pairs = {}
all_users = set()

user_search_count = {}
user_last_search_date = {}
vip_users = {}


def is_user_vip(user_id: int) -> bool:
    if user_id in vip_users:
        expiry_date = vip_users[user_id]
        if datetime.now() < expiry_date:
            return True
        else:
            del vip_users[user_id]
            return False
    return False


def check_and_update_quota(user_id: int) -> bool:
    today = date.today()

    if is_user_vip(user_id):
        return True

    last_date = user_last_search_date.get(user_id)
    if last_date != today:
        user_last_search_date[user_id] = today
        user_search_count[user_id] = 0

    current_count = user_search_count.get(user_id, 0)
    if current_count >= MAX_DAILY_SEARCH:
        return False

    user_search_count[user_id] = current_count + 1
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    all_users.add(user_id)

    reply_keyboard = [["🔍 Cari Pasangan", "❌ Berhenti Obrolan"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

    status_vip = "🌟 VIP Member (Unlimited)" if is_user_vip(user_id) else f"🎁 Gratis ({MAX_DAILY_SEARCH} pencarian/hari)"

    welcome_text = (
        "👋 **Selamat datang di Anonymous Dating Bot!**\n\n"
        "Di sini kamu bisa ngobrol anonim dengan pengguna lain secara acak.\n"
        "Identitas dan username kamu dijamin 100% aman dan rahasia.\n\n"
        f"📊 **Status Akun:** {status_vip}\n\n"
        "Tekan **🔍 Cari Pasangan** untuk mulai mencari teman obrolan!"
    )
    await update.message.reply_text(welcome_text, reply_markup=markup, parse_mode="Markdown")


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    all_users.add(user_id)

    if user_id in pairs:
        await update.message.reply_text("⚠️ Kamu sedang dalam obrolan! Ketik /stop atau tekan '❌ Berhenti Obrolan' terlebih dahulu.")
        return

    if user_id in waiting_queue:
        await update.message.reply_text("⏳ Kamu sudah masuk dalam antrean pencarian. Mohon tunggu...")
        return

    if not check_and_update_quota(user_id):
        limit_text = (
            f"🚫 **KUOTA PENCARIAN HARIAN HABIS!**\n\n"
            f"Kamu telah mencapai batas {MAX_DAILY_SEARCH} pencarian gratis untuk hari ini. Kuota akan di-reset otomatis besok.\n\n"
            f"{PAYMENT_DETAILS}\n\n"
            f"👉 **CARA KONFIRMASI PEMBAYARAN:**\n"
            f"1. Salin ID Telegram kamu di bawah ini (cukup tekan angkanya).\n"
            f"2. Kirim bukti transfer beserta ID kamu ke Admin: {ADMIN_USERNAME}\n\n"
            f"🆔 **ID TELEGRAM KAMU:** `{user_id}`"
        )
        await update.message.reply_text(limit_text, parse_mode="Markdown")
        return

    if is_user_vip(user_id):
        exp_date = vip_users[user_id].strftime("%d-%m-%Y")
        info_kuota = f" (🌟 VIP s/d {exp_date})"
    else:
        sisa = MAX_DAILY_SEARCH - user_search_count.get(user_id, 0)
        info_kuota = f" (Sisa gratis hari ini: {sisa})"

    if waiting_queue:
        partner_id = waiting_queue.pop(0)

        if partner_id == user_id:
            waiting_queue.append(user_id)
            await update.message.reply_text(f"⏳ Mencari pasangan yang cocok...{info_kuota}")
            return

        pairs[user_id] = partner_id
        pairs[partner_id] = user_id

        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 **Pasangan ditemukan!**\nSilakan mulai mengobrol secara anonim."
        )
        await context.bot.send_message(
            chat_id=partner_id,
            text="🎉 **Pasangan ditemukan!**\nSilakan mulai mengobrol secara anonim."
        )
    else:
        waiting_queue.append(user_id)
        await update.message.reply_text(f"🔎 Sedang mencari pasangan obrolan...{info_kuota}")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in waiting_queue:
        waiting_queue.remove(user_id)
        await update.message.reply_text("🛑 Pencarian pasangan dibatalkan.")
        return

    if user_id in pairs:
        partner_id = pairs.pop(user_id, None)
        if partner_id and partner_id in pairs:
            del pairs[partner_id]
            await context.bot.send_message(
                chat_id=partner_id,
                text="❌ **Teman obrolanmu telah mengakhiri percakapan.**\nTekan **🔍 Cari Pasangan** untuk mencari teman baru."
            )
        await update.message.reply_text("❌ **Kamu telah mengakhiri percakapan.**")
    else:
        await update.message.reply_text("ℹ️ Kamu tidak sedang dalam obrolan.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    all_users.add(user_id)
    text = update.message.text

    if text == "🔍 Cari Pasangan":
        await search(update, context)
        return
    elif text == "❌ Berhenti Obrolan":
        await stop(update, context)
        return

    if user_id in pairs:
        partner_id = pairs[user_id]
        try:
            await context.bot.copy_message(
                chat_id=partner_id,
                from_chat_id=user_id,
                message_id=update.message.message_id
            )
        except Exception:
            await update.message.reply_text("⚠️ Gagal mengirim pesan. Pasangan mungkin telah memblokir bot.")
    else:
        await update.message.reply_text("ℹ️ Kamu belum terhubung. Tekan **🔍 Cari Pasangan** untuk mencari teman obrolan.")


async def set_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        target_id = int(context.args[0])
        expiry_date = datetime.now() + timedelta(days=30)
        vip_users[target_id] = expiry_date

        formatted_date = expiry_date.strftime("%d-%m-%Y")
        await update.message.reply_text(
            f"✅ **Berhasil!** User ID `{target_id}` diaktifkan sebagai VIP selama **30 Hari** (Aktif s/d {formatted_date}).",
            parse_mode="Markdown"
        )

        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"🎉 **Selamat! Akun kamu telah diaktifkan menjadi VIP Member.**\n\n"
                f"⏰ **Masa Aktif:** 30 Hari (s/d {formatted_date})\n"
                f"🚀 **Manfaat:** Bebas mencari pasangan obrolan tanpa batas harian!"
            )
        )
    except Exception:
        await update.message.reply_text("⚠️ **Format Salah!** Gunakan: `/vip ID_USER` (contoh: `/vip 987654321`)", parse_mode="Markdown")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg_text = update.message.text.replace("/bc ", "").strip()
    if not msg_text or msg_text == "/bc":
        await update.message.reply_text("⚠️ **Format Salah!** Gunakan: `/bc Isi pesan iklan`", parse_mode="Markdown")
        return

    success_count = 0
    fail_count = 0
    for target_user_id in list(all_users):
        try:
            await context.bot.send_message(chat_id=target_user_id, text=msg_text)
            success_count += 1
        except Exception:
            fail_count += 1

    await update.message.reply_text(
        f"📢 **Laporan Iklan (Broadcast):**\n"
        f"✅ Berhasil dikirim ke: {success_count} pengguna\n"
        f"❌ Gagal/Diblokir: {fail_count} pengguna"
    )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("bc", broadcast))
    app.add_handler(CommandHandler("vip", set_vip))

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("🤖 Bot Dating Anonim Berhasil Dijalankan!")
    app.run_polling()


if __name__ == "__main__":
    main()
