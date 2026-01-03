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
# Using the token from your previous message
PAYMENT_PROVIDER_TOKEN = os.environ.get("PAYMENT_PROVIDER_TOKEN", "6141645565:TEST:9DVSJVI3GuF2TlPiY8AT") 
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
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = context.user_data.get("language", "English")
    
    msg = "✅ Payment Successful!" if "English" in lang else "✅ ክፍያው በተሳካ ሁኔታ ተጠናቅቋል!"
    await update.message.reply_text(msg)

    try:
        invite = await context.bot.create_chat_invite_link(PRIVATE_CHANNEL_ID, member_limit=1)
        link_msg = (
            f"🎉 Welcome! Join here:\n{invite.invite_link}"
            if "English" in lang else f"🎉 እንኳን ደህና መጡ! እዚህ ይቀላቀሉ፦\n{invite.invite_link}"
        )
        await update.message.reply_text(link_msg)
        
        name = context.user_data.get("name", "Unknown")
        await context.bot.send_message(
            ADMIN_CHAT_ID, 
            f"💰 PAID\nName: {name}\nID: {user_id}"
        )
    except Exception as e:
        logger.error(f"Invite Link Error: {e}")
        await update.message.reply_text("Error generating link. Contact admin.")

# ===================== USER FLOW =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_CHAT_ID:
        await update.message.reply_text("👋 Admin Mode.")
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
        await update.message.reply_text("Please use the 'Share Phone' button!")
        return AWAITING_PHONE

    context.user_data["phone"] = update.message.contact.phone_number
    lang = context.user_data.get("language", "English")
    
    logger.info(f"Generating invoice for user {update.effective_user.id}")

    # --- INVOICE DETAILS ---
    title = "Channel Access" if "English" in lang else "የቻናል መግቢያ"
    description = "Payment for Private Channel" if "English" in lang else "የግል ቻናል መግቢያ ክፍያ"
    payload = f"user_{update.effective_user.id}_subscription"
    currency = "ETB"
    price = 300 * 100  # 300.00 ETB
    prices = [LabeledPrice(title, price)]

    try:
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title=title,
            description=description,
            payload=payload,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency=currency,
            prices=prices,
            start_parameter="pay-for-access",
            # CRITICAL ADDITIONS FOR CHAPA:
            need_name=True,
            need_phone_number=True,
            send_phone_number_to_provider=True,
            is_flexible=False, # Set to False unless you have shipping options
            reply_markup=ReplyKeyboardRemove()
        )
        return PENDING_PAYMENT
    except Exception as e:
        logger.error(f"DETAILED INVOICE ERROR: {e}")
        error_msg = "Payment system error. Check your BotFather settings."
        await update.message.reply_text(error_msg)
        return ConversationHandler.END

# ===================== MAIN =====================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_language)],
            AWAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            # CHANGED: Explicitly handle contact and text separately
            AWAITING_PHONE: [
                MessageHandler(filters.CONTACT, receive_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)
            ],
            PENDING_PAYMENT: [MessageHandler(filters.ALL, lambda u, c: None)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
