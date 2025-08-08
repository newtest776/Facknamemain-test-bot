import logging
import asyncio
import nest_asyncio
import os
from aiohttp import web  # aiohttp ইম্পোর্ট করা হয়েছে
from faker import Faker

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
)

# Pydroid3 বা অন্যান্য পরিবেশের জন্য nest_asyncio প্রয়োগ
nest_asyncio.apply()

# --- লগিং কনফিগারেশন ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING) # httpx এর অতিরিক্ত লগ বন্ধ করা

# --- মূল কনফিগারেশন ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables")

PORT = int(os.getenv("PORT", 8443))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("No WEBHOOK_URL found in environment variables")

# --- ConversationHandler ও অন্যান্য কনস্ট্যান্ট ---
(SELECTING_ACTION, SELECTING_COUNTRY, SELECTING_GENDER) = range(3)
SUPPORTED_LOCALES = { "🇺🇸 USA": "en_US", "🇬🇧 UK": "en_GB", "🇮🇳 India": "en_IN", "🇩🇪 Germany": "de_DE", "🇧🇩 Bangladesh": "bn_BD" }
USE_FOOTER_AD = True

# --- Helper Functions (generate_profile_text, create_pagination_keyboard) ---
def generate_profile_text(locale_code="en_US", gender="random"):
    custom_faker = Faker(locale_code)
    name = (custom_faker.name_male() if gender == "male" else
            custom_faker.name_female() if gender == "female" else
            custom_faker.name())
    profile = (
        "➖➖➖** FAKE IDENTITY CARD **➖➖➖\n\n"
        f"👤 **Name**\n`{name}`\n\n"
        f"📧 **Email**\n`{custom_faker.email()}`\n\n"
        f"📍 **Address**\n`{custom_faker.address()}`\n\n"
        f"🏢 **Occupation**\n`{custom_faker.job()}`\n\n"
        "➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖"
    )
    if USE_FOOTER_AD:
        profile += "\n*Sponsored by Example.com*"
    return profile

def create_pagination_keyboard(current_index, total_profiles):
    row = []
    if current_index > 0:
        row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"paginate:prev:{current_index}"))
    row.append(InlineKeyboardButton(f"❌ Close", callback_data="paginate:close:0"))
    if current_index < total_profiles - 1:
        row.append(InlineKeyboardButton("Next ▶️", callback_data=f"paginate:next:{current_index}"))
    return InlineKeyboardMarkup([row])

# --- কমান্ড ও Callback হ্যান্ডলার (start, help, stats, conversations, etc.) ---
# (আপনার আগের কোডের এই অংশগুলো অপরিবর্তিত থাকবে)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (f"👋 **Hi {user.first_name}!**\n\nWelcome to the **Advanced Fake Profile Generator**.\n"
                    "👇 Choose an option below to get started!")
    keyboard = [
        [InlineKeyboardButton("🚀 Generate Profile", callback_data="main_generate")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="main_settings"), InlineKeyboardButton("❓ Help", callback_data="main_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = ("**Available Commands:**\n\n"
                 "🔹 /generate `<amount>` - Generate fake profiles.\n"
                 "🔹 /settings - Set your defaults.\n"
                 "🔹 /stats - View your generation stats.\n"
                 "🔹 /help - Show this help message.")
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("<< Back to Menu", callback_data="main_start")]])
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(help_text, parse_mode="Markdown", reply_markup=reply_markup)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = context.user_data.get('generation_count', 0)
    await update.message.reply_text(f"📊 You have generated a total of **{count}** profiles!", parse_mode="Markdown")

async def generate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = 1
    if context.args and context.args[0].isdigit():
        amount = min(int(context.args[0]), 10)
    context.user_data["amount"] = amount
    
    keyboard = [[InlineKeyboardButton(name, callback_data=name)] for name in SUPPORTED_LOCALES.keys()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "Please select a country:"

    if update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    return SELECTING_COUNTRY

async def select_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data["locale_name_temp"] = query.data
    keyboard = [[InlineKeyboardButton("👨 Male", callback_data="male"), InlineKeyboardButton("👩‍🦰 Female", callback_data="female"), InlineKeyboardButton("🎲 Random", callback_data="random")]]
    await query.edit_message_text(text="Great! Now, select a gender:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_GENDER

async def select_gender_and_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data["gender_temp"] = query.data
    amount = context.user_data.get("amount", 1)
    editable_message = query.message
    
    await editable_message.edit_text(text="🌍 Finding a new identity...")
    await asyncio.sleep(0.5); await editable_message.edit_text(text="🔍 Searching records...")
    await asyncio.sleep(0.5); await editable_message.edit_text(text="✅ Identity found! Preparing profile(s)...")
    await asyncio.sleep(0.5)
    
    locale_name = context.user_data.get("locale_name_temp"); locale_code = SUPPORTED_LOCALES[locale_name]
    gender = context.user_data.get("gender_temp")
    current_stats = context.user_data.get('generation_count', 0); context.user_data['generation_count'] = current_stats + amount
    
    if amount == 1:
        profile_text = generate_profile_text(locale_code, gender)
        await editable_message.edit_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("<< Back to Menu", callback_data="main_start")]]))
    else:
        profiles = [generate_profile_text(locale_code, gender) for _ in range(amount)]
        context.user_data['profiles'] = profiles
        keyboard = create_pagination_keyboard(0, amount)
        await editable_message.edit_text(text=f"**Profile 1 of {amount}**\n\n{profiles[0]}", reply_markup=keyboard, parse_mode="Markdown")
    return ConversationHandler.END

async def pagination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    action, direction, current_index_str = query.data.split(':'); current_index = int(current_index_str)
    if direction == "close": await query.delete_message(); return
    profiles = context.user_data.get('profiles', [])
    if not profiles: await query.edit_message_text("Sorry, the profile list has expired."); return
    new_index = current_index + 1 if direction == "next" else current_index - 1
    total_profiles = len(profiles); keyboard = create_pagination_keyboard(new_index, total_profiles)
    await query.edit_message_text(text=f"**Profile {new_index + 1} of {total_profiles}**\n\n{profiles[new_index]}", reply_markup=keyboard, parse_mode="Markdown")

async def settings_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    default_locale = context.user_data.get("locale_name", "Not Set")
    default_gender = context.user_data.get("gender", "Not Set")
    text = f"**Your Settings**\nDefault Country: {default_locale}\nDefault Gender: {default_gender}\n\nWhat to do?"
    keyboard = [[InlineKeyboardButton("Change Country", callback_data="s_change_country")], [InlineKeyboardButton("Change Gender", callback_data="s_change_gender")], [InlineKeyboardButton("<< Back to Menu", callback_data="main_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else: await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return SELECTING_ACTION

async def settings_change_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton(name, callback_data=name)] for name in SUPPORTED_LOCALES.keys()]
    await query.edit_message_text("Select your new default country:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_COUNTRY

async def settings_save_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data["locale_name"] = query.data
    await query.edit_message_text(f"Default country set to: {query.data}\nRedirecting...")
    await asyncio.sleep(1); return await settings_start(update, context)

async def settings_change_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton("👨 Male", callback_data="male"), InlineKeyboardButton("👩‍🦰 Female", callback_data="female")]]
    await query.edit_message_text("Select your new default gender:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_GENDER

async def settings_save_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data["gender"] = query.data
    await query.edit_message_text(f"Default gender set to: {query.data}\nRedirecting...")
    await asyncio.sleep(1); return await settings_start(update, context)

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    data = query.data
    if data == "main_start": return await start(update, context)
    if data == "main_generate": return await generate_start(update, context)
    if data == "main_settings": return await settings_start(update, context)
    if data == "main_help": return await help_command(update, context)

# --- নতুন main() ফাংশন এবং ওয়েব সার্ভার সেটআপ ---
async def main() -> None:
    # PTB অ্যাপ্লিকেশন তৈরি করা
    application = Application.builder().token(TOKEN).build()

    # কথোপকথন ও অন্যান্য হ্যান্ডলার যোগ করা
    main_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(main_menu_handler, pattern="^main_generate$"), CommandHandler("generate", generate_start)],
        states={
            SELECTING_COUNTRY: [CallbackQueryHandler(select_country, pattern=f"^{'|'.join(SUPPORTED_LOCALES.keys())}$")],
            SELECTING_GENDER: [CallbackQueryHandler(select_gender_and_generate, pattern="^(male|female|random)$")],
        },
        fallbacks=[CommandHandler("start", start)], per_message=False
    )
    settings_conv = ConversationHandler(
        entry_points=[CommandHandler("settings", settings_start), CallbackQueryHandler(main_menu_handler, pattern="^main_settings$")],
        states={
            SELECTING_ACTION: [CallbackQueryHandler(settings_change_country, pattern="^s_change_country$"), CallbackQueryHandler(settings_change_gender, pattern="^s_change_gender$"), CallbackQueryHandler(start, pattern="^main_start$")],
            SELECTING_COUNTRY: [CallbackQueryHandler(settings_save_country, pattern=f"^{'|'.join(SUPPORTED_LOCALES.keys())}$")],
            SELECTING_GENDER: [CallbackQueryHandler(settings_save_gender, pattern="^(male|female)$")],
        },
        fallbacks=[CommandHandler("settings", settings_start)], per_message=False
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(main_conv)
    application.add_handler(settings_conv)
    application.add_handler(CallbackQueryHandler(pagination_handler, pattern="^paginate:"))
    application.add_handler(CallbackQueryHandler(main_menu_handler, pattern="^main_"))

    # PTB এর অভ্যন্তরীণ কাজগুলো শুরু করার জন্য এটি জরুরি
    await application.initialize()
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")

    # --- aiohttp ওয়েব সার্ভার তৈরি করা ---
    # Uptime Robot এর জন্য হেলথ চেক রুট
    async def health(_: web.Request) -> web.Response:
        return web.Response(text="I am alive!")

    # Telegram থেকে আসা অনুরোধ হ্যান্ডেল করার রুট
    async def telegram(request: web.Request) -> web.Response:
        await application.update_queue.put(Update.de_json(await request.json(), application.bot))
        return web.Response()

    # aiohttp অ্যাপ তৈরি করা এবং রুটগুলো যোগ করা
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_post(f"/{TOKEN}", telegram)

    # ওয়েব সার্ভার রান করা
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()

    logging.info(f"Web server started on port {PORT}")

    # PTB অ্যাপ্লিকেশনটি চালু রাখা
    await application.start()
    
    # সার্ভারটি অনির্দিষ্টকালের জন্য চলতে থাকবে
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
