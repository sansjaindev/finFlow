from telegram import Update
from telegram.ext import (
	ApplicationBuilder, CommandHandler, MessageHandler,
	ConversationHandler, filters, CallbackQueryHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from aiohttp import web
from operation import cancel, send_daily_reminder, reset_default_budgets
from message_handler import (
    get_category, get_amount, get_note, get_date, get_wallet,
    get_update_id, get_update_data, confirm_update,
	get_delete_id, confirm_delete,
	budget_callback_handler,
	get_budget_start, get_budget_end, get_budget_wallet, get_budget_category, get_budget_amount, get_budget_default,
	get_budget_list, show_budget_details, 
)
from config import (
	BOT_TOKEN, WEBHOOK_PATH, WEBHOOK_URL, PORT,
    CATEGORY, AMOUNT, DATE, NOTE, WALLET,
    UPDATE_ID, UPDATE_DATA, UPDATE_CONFIRM,
	DELETE_ID, DELETE_CONFIRM,
	BUDGET_MENU, BUDGET_START_DATE, BUDGET_END_DATE, BUDGET_WALLET,  BUDGET_CATEGORY, BUDGET_AMOUNT, BUDGET_DEFAULT,
	BUDGET_VIEW_CHOICE,
)
from entry_point import (
    start, income_command,
    expense_command,
	get_update_free_form, get_delete_free_form,
	budget_command,
	free_form_handler
)


# --- TELEGRAM + WEBHOOK SETUP ---
app = ApplicationBuilder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
	entry_points=[
		CommandHandler("inc", income_command),
		CommandHandler("exp", expense_command),
		CommandHandler("budget", budget_command),	
		MessageHandler(filters.Regex(r"^/update_(\d+)$"), get_update_id),
		MessageHandler(filters.Regex(r"(?i)update transaction (\d+)$") & ~filters.COMMAND, get_update_free_form),
		MessageHandler(filters.Regex(r"^/delete_(\d+)$"), get_delete_id),
		MessageHandler(filters.Regex(r"(?i)^delete transaction \d+$") & ~filters.COMMAND, get_delete_free_form),
		MessageHandler(filters.Regex(r"^/vb_(\d+)$"), show_budget_details),
	],
	states={
		CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
		AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
		WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wallet)],
		NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_note)],
		DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
		UPDATE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_update_id)],
		UPDATE_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_update_data)],
		UPDATE_CONFIRM: [CallbackQueryHandler(confirm_update, pattern=r"^update_")],
		DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delete_id)],
		DELETE_CONFIRM: [CallbackQueryHandler(confirm_delete, pattern=r"^delete_")],
		BUDGET_MENU: [CallbackQueryHandler(budget_callback_handler, pattern=r"^budget_")],
		BUDGET_START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_budget_start)],
		BUDGET_END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_budget_end)],
		BUDGET_WALLET: [CallbackQueryHandler(get_budget_wallet, pattern=r"^budget_wallet:|^budget_wallet_done$")],
		BUDGET_CATEGORY: [CallbackQueryHandler(get_budget_category, pattern=r"^budget_category:|^budget_category_done$")],
		BUDGET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_budget_amount)],
		BUDGET_DEFAULT: [CallbackQueryHandler(get_budget_default, pattern=r"^budget_default_")],
		BUDGET_VIEW_CHOICE: [CallbackQueryHandler(get_budget_list, pattern=r"^budget_view_(active|all)$")],
	},
	fallbacks=[CommandHandler("cancel", cancel)],
	# per_message=True
)

app.add_handler(CommandHandler("start", start))
# app.add_handler(CallbackQueryHandler(budget_callback_handler, pattern=r"^budget_"))
# app.add_handler(CallbackQueryHandler(get_budget_list, pattern=r"^budget_view_(active|all)$"))
# app.add_handler(CallbackQueryHandler(show_budget_details, pattern=r"^budget_select:\d+$"))
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
	schedular.add_job(reset_default_budgets, "cron", hour=00, minute=00, args=[app])
	schedular.start()
	await asyncio.Event().wait()

if __name__ == "__main__":
	asyncio.run(main())
