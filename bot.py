import logging
import os
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# ===================== CONFIG =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# Your Chapa Test Token
PAYMENT_PROVIDER_TOKEN = "6141645565:TEST:9DVSJVI3GuF2TlPiY8AT" 
ADMIN_ID_STR = os.environ.get("ADMIN_CHAT_ID")
ADMIN_CHAT_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR else 0
PRIVATE_CHANNEL_ID = -1003664993732

# ===================== STATES =====================
CHOOSING_LANGUAGE, AWAITING_NAME, AWAITING_PHONE, PENDING_PAYMENT = range(4)

# ===================== LOGGING =====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== PAYMENT HANDLERS =====================

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answers the PreCheckoutQuery (final confirmation before charging)"""
    query = update.pre_checkout_query
    # You can check internal inventory here if needed
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers after the user successfully pays via Chapa"""
    user_id = update.effective_user.id
    lang = context.user_data.get("language", "English")
    
    # Notify User
    msg = "✅ Payment Successful!" if "English" in lang else "✅ ክፍያው በተሳካ ሁኔታ ተጠናቅቋል!"
    await update.message.reply_text(msg)

    # Generate Link & Grant Access
    try:
        invite = await context.bot.create_chat_invite_link(PRIVATE_CHANNEL_ID, member_limit=1)
        link_msg = (
            f"🎉 Welcome! Join the channel here:\n{invite.invite_link}"
            if "English" in lang else f"🎉 እንኳን ደህና መጡ! ቻናሉን እዚህ ይቀላቀሉ፦\n{invite.invite_link}"
        )
        await update.message.reply_text(link_msg)
        
        # Notify Admin of automated success
        name = context.user_data.get("name", "Unknown")
        await context.bot.send_message(
            ADMIN_CHAT_ID, 
            f"💰 AUTOMATED PAYMENT SUCCESS\nUser: {name}\nID: {user_id}\nAmount: 300 ETB"
        )
    except Exception as e:
        logger.error(f"Invite Link Error: {e}")
        await update.message.reply_text("Error generating link. Please contact admin.")

# ===================== USER FLOW =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_CHAT_ID:
        await update.message.reply_text("👋 Welcome Admin. Payments are now automated!")
        return ConversationHandler.END

    await update.message.reply_text(
        "Choose language / ቋንቋ ይምረጡ:",
        reply_markup=ReplyKeyboardMarkup(
            [["English 🇬🇧", "Amharic 🇪🇹"]],
            one_time_keyboard=True, resize_keyboard=True
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

    # --- SEND AUTOMATED INVOICE ---
    title = "Channel Access" if "English" in lang else "የቻናል መግቢያ"
    description = "Access to the Private Channel" if "English" in lang else "የግል ቻናል መግቢያ ክፍያ"
    payload = f"user_{update.effective_user.id}_payment"
    currency = "ETB"
    price = 300 * 100  # 300.00 ETB (smallest unit is cents)
    prices = [LabeledPrice("Subscription", price)]

    await context.bot.send_invoice(
        update.effective_chat.id,
        title, description, payload,
        PAYMENT_PROVIDER_TOKEN,
        currency, prices
    )
    
    return PENDING_PAYMENT

# ===================== MAIN =====================
def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 1. Add Payment Specific Handlers (MUST be before ConversationHandler)
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # 2. Add Conversation Handler
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_language)],
            AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            AWAITING_PHONE: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_phone)],
            PENDING_PAYMENT: [MessageHandler(filters.ALL, lambda u, c: None)] # Wait for payment
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    app.add_handler(conv)
    
    print("Bot started with Automated Payments...")
    app.run_polling()

if __name__ == "__main__":
    main()
