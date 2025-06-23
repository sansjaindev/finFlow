from telegram import Update
from telegram.ext import (
	ApplicationBuilder, CommandHandler, MessageHandler,
	ConversationHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from aiohttp import web
from operation import cancel, send_daily_reminder
from message_handler import (
    get_category, get_amount, get_note, get_date, get_wallet,
    get_update_id, get_update_data, confirm_update,
	get_delete_id, confirm_delete
)
from config import (
	BOT_TOKEN, WEBHOOK_PATH, WEBHOOK_URL, PORT,
    CATEGORY, AMOUNT, DATE, NOTE, WALLET,
    UPDATE_ID, UPDATE_DATA, UPDATE_CONFIRM,
	DELETE_ID, DELETE_CONFIRM
)
from entry_point import (
    start, income_command,
    expense_command, update_command,
	delete_command,
	get_update_free_form, get_delete_free_form,
	free_form_handler
)


# --- TELEGRAM + WEBHOOK SETUP ---
app = ApplicationBuilder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
	entry_points=[
		CommandHandler("inc", income_command),
		CommandHandler("exp", expense_command),
		CommandHandler("update", update_command),
		MessageHandler(filters.Regex(r"(?i)update transaction (\d+)$") & ~filters.COMMAND, get_update_free_form),
		CommandHandler("delete", delete_command),
		MessageHandler(filters.Regex(r"(?i)^delete transaction \d+$") & ~filters.COMMAND, get_delete_free_form),
],
	states={
		CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
		AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
		WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wallet)],
		NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_note)],
		DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
		UPDATE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_update_id)],
		UPDATE_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_update_data)],
		UPDATE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_update)],
		DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delete_id)],
		DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete)],
	},
	fallbacks=[CommandHandler("cancel", cancel)]
)

app.add_handler(CommandHandler("start", start))
app.add_handler(conv_handler)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_form_handler))

# --- Main ---
async def handle(request):
	data = await request.json()	
	update = Update.de_json(data, app.bot)
	await app.update_queue.put(update)
	return web.Response(text="OK")

async def main():
	await app.bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
	web_app = web.Application()
	web_app.router.add_post(WEBHOOK_PATH, handle)
	await app.initialize()
	await app.start()
	runner = web.AppRunner(web_app)
	await runner.setup()
	site = web.TCPSite(runner, "0.0.0.0", PORT)
	await site.start()
	print("Bot is running via webhook...")

	schedular = AsyncIOScheduler(timezone="Asia/Kolkata")
	schedular.add_job(send_daily_reminder, "cron", hour=22, minute=00, args=[app])
	schedular.start()
	await asyncio.Event().wait()

if __name__ == "__main__":
	asyncio.run(main())
