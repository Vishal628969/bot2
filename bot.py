import logging, os, asyncio, aiohttp, time, random, json
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

# === CONFIG ===
TOKEN = "8197397166:AAFiG9bwwpvxkvcId9_gPta2xUl428Vxv1g"
UPSTASH_URL = "https://in-humpback-7729.upstash.io"
UPSTASH_TOKEN = "AR4xAAIjcDE2NjU0YTFhYWU2MjE0Y2M5YWM1Y2UzNGZlODNiY2E5Y3AxMA"

OWNER = "🤖 *Bot by Vishal Prajapati*"

# === LOGGER ===
logging.basicConfig(level=logging.INFO)

# === CONVERSATION STATES ===
WAIT_TXT, WAIT_FILENAME = range(2)

# === START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 *Welcome to the Ultimate BIN Utility Bot!*\n\n"
        "🧾 /bin {bin} - Check a single BIN\n"
        "📂 /mbin - Bulk check BINs from a TXT file\n"
        "💳 /gen {bin} - Generate 1 card\n"
        "💳 /gen {bin} {amount} - Generate multiple cards\n\n"
        "📌 Format: `CARD|MM|YYYY|CVV`\n\n"
        f"{OWNER}",
        parse_mode="Markdown"
    )

# === /bin ===
async def bin_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: /bin 45717360")
        return

    bin_number = args[0]
    await update.message.reply_text(f"🔍 Checking BIN `{bin_number}`...", parse_mode="Markdown")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{UPSTASH_URL}/get/{bin_number}", headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}) as resp:
            data = await resp.json()

    if "result" in data:
        try:
            info = json.loads(data["result"]).get("value", {})
        except:
            await update.message.reply_text("❌ Invalid result format.")
            return

        reply = (
            f"✅ *BIN:* `{bin_number}`\n"
            f"🏦 *Bank:* {info.get('issuer', '-')}\n"
            f"💳 *Brand:* {info.get('brand', '-')}\n"
            f"🗂 *Category:* {info.get('category', '-')}\n"
            f"🏷 *Type:* {info.get('type', '-')}\n"
            f"🌍 *Country:* {info.get('country', '-')}\n"
            f"🌐 *Code:* {info.get('alpha_2', '-')}/{info.get('alpha_3', '-')}\n"
            f"📞 *Phone:* {info.get('bank_phone', '-')}\n"
            f"🔗 *Website:* {info.get('bank_url', '-')}\n\n"
            f"{OWNER}"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ BIN not found.")

# === /mbin ===
async def mbin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Please send the TXT file with BINs (one per line)...")
    return WAIT_TXT

async def mbin_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_path = f"binlist_{update.message.from_user.id}.txt"
    await file.download_to_drive(file_path)
    context.user_data["binfile"] = file_path
    await update.message.reply_text("✅ File received! Now send a name for the result file (without .txt):")
    return WAIT_FILENAME

async def mbin_receive_filename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    filename = update.message.text.strip()
    binfile = context.user_data.get("binfile")

    if not os.path.exists(binfile):
        await update.message.reply_text("❌ Upload failed. Please try again.")
        return ConversationHandler.END

    result_path = f"{filename}.txt"
    await update.message.reply_text("🔁 Processing BINs with ⚡️ speed...")

    with open(binfile, "r", encoding="utf-8") as f:
        bins = [line.strip() for line in f if line.strip()]

    checked = []

    async with aiohttp.ClientSession() as session:
        for i, bin in enumerate(bins, 1):
            try:
                async with session.get(f"{UPSTASH_URL}/get/{bin}", headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}) as resp:
                    res = await resp.json()
                    if "result" in res:
                        try:
                            info = json.loads(res["result"]).get("value", {})
                            line = f"{bin} ✅ {info.get('issuer', '-')}, {info.get('country', '-')}, {info.get('brand', '-')}, {info.get('type', '-')}"
                        except:
                            line = f"{bin} ❌ Invalid data"
                    else:
                        line = f"{bin} ❌ Not Found"
            except:
                line = f"{bin} ❌ Error"

            checked.append(line)
            if i % 10 == 0 or i == len(bins):
                await update.message.reply_text(f"📊 Checked {i}/{len(bins)}")

    with open(result_path, "w", encoding="utf-8") as f:
        f.write("\n".join(checked))

    await update.message.reply_document(document=open(result_path, "rb"), filename=result_path)
    os.remove(result_path)
    os.remove(binfile)
    return ConversationHandler.END

# === Card Gen with CVV & Expiry ===
def luhn_check(card):
    sum = 0
    alt = False
    for digit in reversed(card):
        d = int(digit)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        sum += d
        alt = not alt
    return sum % 10 == 0

def luhn_generate(bin_prefix, amount=1):
    cards = []
    while len(cards) < amount:
        card = bin_prefix + ''.join(random.choices("0123456789", k=16-len(bin_prefix)-1))
        for i in range(10):
            test_card = card + str(i)
            if luhn_check(test_card):
                cards.append(test_card)
                break
    return cards

def generate_expiry():
    month = str(random.randint(1, 12)).zfill(2)
    year = str(random.randint(datetime.now().year + 1, datetime.now().year + 6))
    return month, year

def generate_cvv():
    return ''.join(random.choices("0123456789", k=3))

async def gen_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: /gen 457173 or /gen 457173 5")
        return

    bin_prefix = args[0]
    amount = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1

    if len(bin_prefix) < 6 or amount > 1000:
        await update.message.reply_text("⚠️ Invalid BIN or too many cards (max 1000).")
        return

    cards = luhn_generate(bin_prefix, amount)
    full_cards = [f"{c}|{generate_expiry()[0]}|{generate_expiry()[1]}|{generate_cvv()}" for c in cards]

    if amount <= 10:
        text = "💳 *Generated Card(s):*\n" + "\n".join(f"`{c}`" for c in full_cards)
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        filename = f"cards_{bin_prefix}_{amount}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(full_cards))

        await update.message.reply_document(
            document=open(filename, "rb"),
            filename=filename,
            caption=f"📦 {amount} cards for BIN {bin_prefix}"
        )
        os.remove(filename)

# === HANDLERS ===
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bin", bin_check))
app.add_handler(CommandHandler("gen", gen_card))
app.add_handler(ConversationHandler(
    entry_points=[CommandHandler("mbin", mbin_start)],
    states={
        WAIT_TXT: [MessageHandler(filters.Document.TEXT, mbin_receive_file)],
        WAIT_FILENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, mbin_receive_filename)],
    },
    fallbacks=[],
))

# === RUN ===
if __name__ == "__main__":
    print("🤖 Bot is running...")
    app.run_polling()
