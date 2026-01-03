import logging
import os
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# ===================== CONFIG =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID_STR = os.environ.get("ADMIN_CHAT_ID")
ADMIN_CHAT_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR else 0
PRIVATE_CHANNEL_ID = -1003664993732

# ===================== STATES =====================
CHOOSING_LANGUAGE, AWAITING_NAME, AWAITING_PHONE, AWAITING_PAYMENT_PROOF, PENDING_APPROVAL = range(5)

# ===================== LOGGING =====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== ADMIN ACTIONS =====================
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_CHAT_ID:
        await query.answer("Unauthorized", show_alert=True)
        return

    await query.answer()
    data = query.data
    user_id = int(data.rsplit("_", 1)[-1])
    
    lang = context.user_data.get("language", "English")

    if data.startswith("adm_app"):
        try:
            invite = await context.bot.create_chat_invite_link(PRIVATE_CHANNEL_ID, member_limit=1)
            msg = (
                f"🎉 Approved!\nJoin here:\n{invite.invite_link}"
                if "English" in lang else f"🎉 ተፈቅዷል!\nበዚህ ሊንክ ይቀላቀሉ፦\n{invite.invite_link}"
            )
            await context.bot.send_message(user_id, msg)
            await query.edit_message_caption("✅ APPROVED & LINK SENT")
        except Exception as e:
            logger.error(f"Link error: {e}")
            await query.edit_message_caption("✅ APPROVED (But link failed - check bot permissions)")

    elif data.startswith("adm_rej"):
        msg = (
            "❌ Rejected. Please try again using /start."
            if "English" in lang else "❌ ውድቅ ተደርጓል። እባክዎ /start በመጠቀም እንደገና ይሞክሩ።"
        )
        await context.bot.send_message(user_id, msg)
        await query.edit_message_caption("❌ REJECTED")

# ===================== USER FLOW =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id == ADMIN_CHAT_ID:
        await update.message.reply_text("👋 Welcome Admin. You will receive payment proofs here.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Choose language / ቋንቋ ይምረጡ:",
        reply_markup=ReplyKeyboardMarkup(
            [["English 🇬🇧", "Amharic 🇪🇹"]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return CHOOSING_LANGUAGE

async def receive_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["language"] = update.message.text
    msg = "Enter full name:" if "English" in update.message.text else "እባክዎ ሙሉ ስምዎን ያስገቡ፦"
    await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
    return AWAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    lang = context.user_data.get("language", "English")
    btn = "Share Phone 📱" if "English" in lang else "ስልክ ቁጥር አጋራ 📱"
    
    await update.message.reply_text(
        "Share phone number:" if "English" in lang else "ስልክ ቁጥርዎን ያጋሩ፦",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(btn, request_contact=True)]], one_time_keyboard=True, resize_keyboard=True)
    )
    return AWAITING_PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.contact:
        await update.message.reply_text("Please use the button!")
        return AWAITING_PHONE

    context.user_data["phone"] = update.message.contact.phone_number
    lang = context.user_data.get("language", "English")

    # Integrated Payment Message
    if "English" in lang:
        payment_msg = (
            "💳 **Payment Details**\n"
            "Please deposit **300 Birr** using the options below. "
            "When finished, send a photo of the receipt 📸:\n\n"
            "CBE: `1000597069198` (Gaps International)\n"
            "Telebirr: `+251911691984` (Netsanet Fikre)"
        )
    else:
        payment_msg = (
            "💳 **የክፍያ ዝርዝር**\n"
            "እባክዎ **300 ብር** ከታች በተጠቀሱት አማራጮች ያስገቡ። "
            "ሲጨርሱ የደረሰኝ ፎቶ ይላኩ 📸፦\n\n"
            "ንግድ ባንክ (CBE)፦ `1000597069198` (Gaps International)\n"
            "ቴሌ ብር፦ `+251911691984` (Netsanet Fikre)"
        )

    await update.message.reply_text(payment_msg, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
    return AWAITING_PAYMENT_PROOF

async def receive_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("📸 Please send a photo!")
        return AWAITING_PAYMENT_PROOF

    user_id = update.effective_user.id
    name = context.user_data.get("name", "Unknown")
    phone = context.user_data.get("phone", "Unknown")
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"adm_app_{user_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"adm_rej_{user_id}")
    ]])
    
    # Send to Admin
    await context.bot.send_photo(
        ADMIN_CHAT_ID, 
        photo=update.message.photo[-1].file_id, 
        caption=f"🔔 NEW PAYMENT\nName: {name}\nPhone: {phone}\nID: {user_id}", 
        reply_markup=keyboard
    )
    
    lang = context.user_data.get("language", "English")
    msg = "👍 Submitted! Please wait for admin approval." if "English" in lang else "👍 ገብቷል! እባክዎ የአስተዳዳሪውን ማረጋገጫ ይጠብቁ።"
    await update.message.reply_text(msg)
    return PENDING_APPROVAL

async def pending_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "English")
    msg = "⏳ Still under review..." if "English" in lang else "⏳ ገና እየተረጋገጠ ነው።"
    await update.message.reply_text(msg)
    return PENDING_APPROVAL

# ===================== MAIN =====================
def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^adm_"))

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_language)],
            AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            AWAITING_PHONE: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_phone)],
            AWAITING_PAYMENT_PROOF: [MessageHandler(filters.PHOTO, receive_payment_proof)],
            PENDING_APPROVAL: [MessageHandler(filters.ALL & ~filters.COMMAND, pending_approval)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    app.add_handler(conv)
    
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()


