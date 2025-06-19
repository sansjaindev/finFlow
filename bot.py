# from telegram import Update
# from telegram.ext import (
# 	ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
# 	ConversationHandler, filters, JobQueue
# )
# from telegram.constants import ParseMode
# from supabase import create_client
# import os
# import re
# from datetime import datetime, timedelta, time
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# import random
# import pytz

# # Environment Variables
# BOT_TOKEN = os.getenv("BOT_TOKEN")
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# # Supabase Client
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# # States
# CATEGORY, AMOUNT, WALLET, NOTE, DATE = range(5)

# async def send_daily_reminder(app):
# 	# Replace this with your actual chat ID or maintain a list of users
# 	chat_id = int(os.getenv("CHAT_ID"))  # Replace with int, e.g., 123456789
# 	messages_list = ["📅 This is your daily 10 PM reminder to log your expenses!", "test"]
# 	random_msg = random.choice(messages_list)
# 	print('sending reminder now')
# 	try:
# 		await app.bot.send_message(
# 			chat_id=chat_id,
# 			text="sending message to you"
# 		)
# 	except Exception as e:
# 		print("Failed to send scheduled message:", e)

# # --- /start ---
# async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
# 	await update.message.reply_text(
# 		"👋 Hello! Use /inc to log income or /exp to log an expense.\n"
# 		"📝 Or send: `Food 250 UPI Lunch` or `Income 500000 Salary`\n"
# 		"🔍 Want to see entries? Try: `expenses on 2024-06-01`, `food`, `upi`, `income`"
# 	)

# # --- Income Entry Start ---
# async def income_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
# 	context.user_data["type"] = "income"
# 	await update.message.reply_text("Enter category for income:")
# 	return CATEGORY

# # --- Expense Entry Start ---
# async def expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
# 	context.user_data["type"] = "expense"
# 	await update.message.reply_text("Enter category for expense:")
# 	return CATEGORY

# # --- Step 1: Category ---
# async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
# 	context.user_data["category"] = update.message.text
# 	await update.message.reply_text("Enter amount:")
# 	return AMOUNT

# # --- Step 2: Amount ---
# async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
# 	try:
# 		context.user_data["amount"] = float(update.message.text)
# 	except ValueError:
# 		await update.message.reply_text("❌ Please enter a valid number.")
# 		return AMOUNT
# 	await update.message.reply_text("Enter wallet (e.g., UPI, Cash):")
# 	return WALLET

# # --- Step 3: Wallet ---
# async def get_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
# 	context.user_data["wallet"] = update.message.text
# 	await update.message.reply_text("Optional note (or type 'skip'):")
# 	return NOTE

# # --- Step 4: Note ---
# async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
# 	note = update.message.text
# 	if note.lower() == "skip":
# 		note = ""
	
# 	context.user_data["note"] = note
# 	await update.message.reply_text("Enter Date (YYYY-MM-DD) or type 'today':")
# 	return DATE

# async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
# 	date_input = update.message.text.strip()
# 	if date_input.lower() == "today":
# 		created_at = datetime.now().isoformat()

# 	elif date_input.lower() == "yesterday":
# 		created_at = (datetime.now() - timedelta(1)).isoformat()
	
# 	elif date_input.lower() == "day before yesterday":
# 		created_at = (datetime.now() - timedelta(2)).isoformat()

# 	else:
# 		try:
# 			created_at = datetime.strptime(date_input, '%Y-%m-%d').isoformat()
		
# 		except ValueError:
# 			await update.message.reply_text("❌ Invalid date format. Use YYYY-MM-DD or type 'today'.")
# 			return DATE


# 	user_id = update.effective_user.id
# 	amount = abs(context.user_data["amount"])
# 	if context.user_data["type"] == "expense":
# 		amount = -amount

# 	try:
# 		supabase.table("Expenses").insert({
# 			"user_id": user_id,
# 			"category": context.user_data["category"],
# 			"amount": amount,
# 			"wallet": context.user_data["wallet"],
# 			"note": context.user_data["note"],
# 			"created_at": created_at
# 		}).execute()

# 		await update.message.reply_text(
# 			f"✅ Saved {context.user_data['type']} ₹{abs(amount)} "
# 			f"under {context.user_data['category']} via {context.user_data['wallet']}"
# 			f"🗓️ {created_at[:10]} | 📝 {context.user_data['note']}"
# 		)
# 	except Exception as e:
# 		print("DB Insert Error:", e)
# 		await update.message.reply_text("❌ Failed to save. Please try again.")

# 	return ConversationHandler.END

# # --- /cancel ---
# async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
# 	await update.message.reply_text("❌ Cancelled.")
# 	return ConversationHandler.END

# # --- Parser for quick entry ---
# def parse_expense(text):
# 	dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
# 	date = dates[0] if dates else None
# 	if date:
# 		text = text.replace(date, "")
# 	parts = text.strip().split()
# 	if len(parts) < 3:
# 		return None
# 	category = parts[0]
# 	try:
# 		amount = float(parts[1])
# 	except ValueError:
# 		return None
# 	wallet = parts[2]
# 	note = " ".join(parts[3:]) if len(parts) > 3 else ""
# 	return category, amount, wallet, note, date


# # --- Handler for free-form insert or view ---
# async def free_form_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
# 	user_id = update.effective_user.id
# 	text = update.message.text.strip()
# 	text = update.message.text.strip().rstrip(".")


# 	# Check if it's a quick entry format (e.g., "Food 250 UPI Dinner")
# 	parsed = parse_expense(text)
# 	if parsed:
# 		category, amount, wallet, note, date_str = parsed
# 		try:
# 			created_at = (
# 				datetime.strptime(date_str, "%Y-%m-%d").isoformat()
# 				if date_str else datetime.now().isoformat()
# 			)
# 			# If category is not income/salary, treat it as expense
# 			final_amount = -abs(amount) if category.lower() not in ["income", "salary"] else abs(amount)

# 			supabase.table("Expenses").insert({
# 				"user_id": user_id,
# 				"category": category,
# 				"amount": final_amount,
# 				"wallet": wallet,
# 				"note": note,
# 				"created_at": created_at
# 			}).execute()

# 			await update.message.reply_text(
# 				f"✅ Saved *{category.title()}* ₹{abs(amount)} via *{wallet}*\n"
# 				f"🗓️ {created_at[:10]} | 📝 {note}",
# 				parse_mode=ParseMode.MARKDOWN
# 			)
# 		except Exception as e:
# 			print("Free-form insert error:", e)
# 			await update.message.reply_text("⚠️ Failed to save entry.")
# 		return

# 	# --- If not a quick-entry, fall back to view-query ---
# 	text = text.lower()
	
# 	if not text.startswith("show"):
# 		await update.message.reply_text("❌ Please start with 'Show ...'")
# 		return

# 	try:
# 		query = supabase.table("Expenses").select("*").eq("user_id", user_id)

# 		# 1. Ranged pattern
# 		pattern_range = r"show(?: all)?\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?\s*from (\d{4}-\d{2}-\d{2}) (?:to|till) (yesterday|today|\d{4}-\d{2}-\d{2})(?: via ([^0-9]+))?\.?$"

# 		# 2. All data (with optional category and wallet)
# 		pattern_all = r"show all\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?(?: via ([^0-9]+))?\.?$"

# 		# 3. Single-day pattern
# 		pattern_single = r"show(?: all)?\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?(?: for (today|yesterday|\d{4}-\d{2}-\d{2}))?(?: via ([^0-9]+))?\.?$"




# 		now = datetime.now()

# 		# --- Ranged Data ---
# 		if m := re.fullmatch(pattern_range, text):
# 			txn_type, category, start, end, wallet = m.groups()
# 			start_dt = datetime.strptime(start, "%Y-%m-%d")
# 			end_dt = (
# 				now - timedelta(days=1) if end == "yesterday"
# 				else now if end == "today"
# 				else datetime.strptime(end, "%Y-%m-%d")
# 			)

# 			query = query.gte("created_at", start_dt.replace(hour=0, minute=0, second=0).isoformat()) \
# 						.lte("created_at", end_dt.replace(hour=23, minute=59, second=59).isoformat())

# 			if txn_type == "income":
# 				query = query.gt("amount", 0)
# 			elif txn_type == "expenses":
# 				query = query.lt("amount", 0)

# 			if category:
# 				query = apply_multi_ilike(query, "category", category)
# 			if wallet:
# 				query = apply_multi_ilike(query, "wallet", wallet)


# 		# --- All data ---
# 		elif m := re.fullmatch(pattern_all, text):
# 			txn_type, category, wallet = m.groups()

# 			if txn_type == "income":
# 				query = query.gt("amount", 0)
# 			elif txn_type == "expenses":
# 				query = query.lt("amount", 0)

# 			if category:
# 				query = apply_multi_ilike(query, "category", category)
# 			if wallet:
# 				query = apply_multi_ilike(query, "wallet", wallet)




# 		# --- Single Day (or default to today) ---
# 		elif m := re.fullmatch(pattern_single, text):
# 			txn_type, category, date_str, wallet = m.groups()

# 			if not date_str or date_str == "today":
# 				target_date = now
# 			elif date_str == "yesterday":
# 				target_date = now - timedelta(days=1)
# 			else:
# 				target_date = datetime.strptime(date_str, "%Y-%m-%d")

# 			start_dt = target_date.replace(hour=0, minute=0, second=0)
# 			end_dt = target_date.replace(hour=23, minute=59, second=59)

# 			query = query.gte("created_at", start_dt.isoformat()).lte("created_at", end_dt.isoformat())

# 			if txn_type == "income":
# 				query = query.gt("amount", 0)
# 			elif txn_type == "expenses":
# 				query = query.lt("amount", 0)

# 			if category:
# 				query = apply_multi_ilike(query, "category", category)
# 			if wallet:
# 				query = apply_multi_ilike(query, "wallet", wallet)


# 		else:
# 			await update.message.reply_text(
# 				"❌ Unrecognized format.\n"
# 				"Try:\n"
# 				"• `Show expenses`\n"
# 				"• `Show income of salary for yesterday`\n"
# 				"• `Show all transactions`\n"
# 				"• `Show expenses of food from 2025-06-01 to 2025-06-10`"
# 			)
# 			return

# 		# --- Execute query ---
# 		data = query.order("created_at", desc=True).execute().data

# 		if not data:
# 			await update.message.reply_text("ℹ️ No transactions found.")
# 			return

# 		message = f"📊 *Transactions:*\n\n"
# 		for txn in data:
# 			sign = "🟢 Income" if txn["amount"] > 0 else "🔴 Expense"
# 			message += (
# 				f"{sign} ₹{abs(txn['amount'])}\n"
# 				f"📂 {txn['category']} | 💳 {txn['wallet']}\n"
# 				f"🗓️ {txn.get('created_at', '')[:10]} | 📝 {txn.get('note', '')}\n\n"
# 			)

# 		await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

# 	except Exception as e:
# 		print("Free-form error:", e)
# 		await update.message.reply_text("⚠️ Could not process request.")


# def apply_multi_ilike(query, field, value_string):
# 	values = [v.strip() for v in value_string.split(",") if v.strip()]
# 	if not values:
# 		return query
# 	if len(values) == 1:
# 		return query.ilike(field, f"%{values[0]}%")

# 	# Build Supabase 'or' string
# 	conditions = [f"{field}.ilike.%{v}%" for v in values]
# 	joined = ",".join(conditions)
# 	return query.or_(joined)

# # --- Main ---
# def main():
# 	app = ApplicationBuilder().token(BOT_TOKEN).build()

# 	conv_handler = ConversationHandler(
# 		entry_points=[
# 			CommandHandler("inc", income_command),
# 			CommandHandler("exp", expense_command),
# 		],
# 		states={
# 			CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
# 			AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
# 			WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wallet)],
# 			NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_note)],
# 			DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
# 		},
# 		fallbacks=[CommandHandler("cancel", cancel)],
# 	)

# 	app.add_handler(CommandHandler("start", start))
# 	app.add_handler(conv_handler)
# 	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_form_handler))

# 	daily_reminder_time = time(hour=2, minute=13, second=0, tzinfo=pytz.timezone("Asia/Kolkata"))
# 	# Scheduler setup
# 	app.job_queue.run_daily(
# 		send_daily_reminder, # The callback function
# 		time=daily_reminder_time, # The time of day to run
# 		days=(0, 1, 2, 3, 4, 5, 6), # Run every day of the week (Monday=0 to Sunday=6)
# 		name='Daily Expense Reminder', # A name for the job (optional, for logging/debugging)
# 	)
# 	print("Daily reminder scheduled for 10 PM IST using JobQueue.")

# 	app.run_polling()


# if __name__ == "__main__":
# 	main()





from telegram import Update
from telegram.ext import (
	ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
	ConversationHandler, filters
)
from telegram.constants import ParseMode
from supabase import create_client
import os
import re
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import random
import asyncio
from aiohttp import web

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 8080))

# Supabase Client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# States
CATEGORY, AMOUNT, WALLET, NOTE, DATE = range(5)

async def send_daily_reminder(app):
	CHAT_ID = int(os.getenv("CHAT_ID"))
	messages_list = ["📅 This is your daily 10 PM reminder to log your expenses!", "💡 Time to track today's money moves!",
		"🔁 Don’t forget to record your expenses before bed!",]
	random_msg = random.choice(messages_list)
	try:
		await app.bot.send_message(
			chat_id=CHAT_ID,
			text=random_msg
		)
	except Exception as e:
		print("Failed to send scheduled message:", e)


# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
	await update.message.reply_text(
		"👋 Hello! Use /inc to log income or /exp to log an expense.\n"
		"📝 Or send: `Food 250 UPI Lunch` or `Income 500000 Salary`\n"
		"🔍 Want to see entries? Try: `expenses on 2024-06-01`, `food`, `upi`, `income`"
	)

# --- Income Entry Start ---
async def income_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
	context.user_data["type"] = "income"
	await update.message.reply_text("Enter category for income:")
	return CATEGORY

# --- Expense Entry Start ---
async def expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
	context.user_data["type"] = "expense"
	await update.message.reply_text("Enter category for expense:")
	return CATEGORY

# --- Step 1: Category ---
async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
	context.user_data["category"] = update.message.text
	await update.message.reply_text("Enter amount:")
	return AMOUNT

# --- Step 2: Amount ---
async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
	try:
		context.user_data["amount"] = float(update.message.text)
	except ValueError:
		await update.message.reply_text("❌ Please enter a valid number.")
		return AMOUNT
	await update.message.reply_text("Enter wallet (e.g., UPI, Cash):")
	return WALLET

# --- Step 3: Wallet ---
async def get_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
	context.user_data["wallet"] = update.message.text
	await update.message.reply_text("Optional note (or type 'skip'):")
	return NOTE

# --- Step 4: Note ---
async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
	note = update.message.text
	if note.lower() == "skip":
		note = ""
	
	context.user_data["note"] = note
	await update.message.reply_text("Enter Date (YYYY-MM-DD) or type 'today':")
	return DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
	date_input = update.message.text.strip()
	if date_input.lower() == "today":
		created_at = datetime.now().isoformat()

	elif date_input.lower() == "yesterday":
		created_at = (datetime.now() - timedelta(1)).isoformat()
	
	elif date_input.lower() == "day before yesterday":
		created_at = (datetime.now() - timedelta(2)).isoformat()

	else:
		try:
			created_at = datetime.strptime(date_input, '%Y-%m-%d').isoformat()
		
		except ValueError:
			await update.message.reply_text("❌ Invalid date format. Use YYYY-MM-DD or type 'today'.")
			return DATE


	user_id = update.effective_user.id
	amount = abs(context.user_data["amount"])
	if context.user_data["type"] == "expense":
		amount = -amount

	try:
		supabase.table("Expenses").insert({
			"user_id": user_id,
			"category": context.user_data["category"],
			"amount": amount,
			"wallet": context.user_data["wallet"],
			"note": context.user_data["note"],
			"created_at": created_at
		}).execute()

		await update.message.reply_text(
			f"✅ Saved {context.user_data['type']} ₹{abs(amount)} "
			f"under {context.user_data['category']} via {context.user_data['wallet']}"
			f"🗓️ {created_at[:10]} | 📝 {context.user_data['note']}"
		)
	except Exception as e:
		print("DB Insert Error:", e)
		await update.message.reply_text("❌ Failed to save. Please try again.")

	return ConversationHandler.END

# --- /cancel ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
	await update.message.reply_text("❌ Cancelled.")
	return ConversationHandler.END

# --- Parser for quick entry ---
def parse_expense(text):
	dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
	date = dates[0] if dates else None
	if date:
		text = text.replace(date, "")
	parts = text.strip().split()
	if len(parts) < 3:
		return None
	category = parts[0]
	try:
		amount = float(parts[1])
	except ValueError:
		return None
	wallet = parts[2]
	note = " ".join(parts[3:]) if len(parts) > 3 else ""
	return category, amount, wallet, note, date


# --- Handler for free-form insert or view ---
async def free_form_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user_id = update.effective_user.id
	text = update.message.text.strip()
	text = update.message.text.strip().rstrip(".")

	# Check if it's a quick entry format
	parsed = parse_expense(text)
	if parsed:
		category, amount, wallet, note, date_str = parsed
		try:
			created_at = (
				datetime.strptime(date_str, "%Y-%m-%d").isoformat()
				if date_str else datetime.now().isoformat()
			)
			
			final_amount = -abs(amount) if category.lower() not in ["income", "salary"] else abs(amount)

			supabase.table("Expenses").insert({
				"user_id": user_id,
				"category": category,
				"amount": final_amount,
				"wallet": wallet,
				"note": note,
				"created_at": created_at
			}).execute()

			await update.message.reply_text(
				f"✅ Saved *{category.title()}* ₹{abs(amount)} via *{wallet}*\n"
				f"🗓️ {created_at[:10]} | 📝 {note}",
				parse_mode=ParseMode.MARKDOWN
			)
		except Exception as e:
			print("Free-form insert error:", e)
			await update.message.reply_text("⚠️ Failed to save entry.")
		return

	# --- If not a quick-entry, fall back to view-query ---
	text = text.lower()
	
	if not text.startswith("show"):
		await update.message.reply_text("❌ Please start with 'Show ...'")
		return

	try:
		query = supabase.table("Expenses").select("*").eq("user_id", user_id)

		pattern_range = r"show(?: all)?\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?\s*from (\d{4}-\d{2}-\d{2}) (?:to|till) (yesterday|today|\d{4}-\d{2}-\d{2})(?: via ([^0-9]+))?\.?$"
		pattern_all = r"show all\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?(?: via ([^0-9]+))?\.?$"
		pattern_single = r"show(?: all)?\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?(?: for (today|yesterday|\d{4}-\d{2}-\d{2}))?(?: via ([^0-9]+))?\.?$"

		now = datetime.now()

		# --- Ranged Data ---
		if m := re.fullmatch(pattern_range, text):
			txn_type, category, start, end, wallet = m.groups()
			start_dt = datetime.strptime(start, "%Y-%m-%d")
			end_dt = (
				now - timedelta(days=1) if end == "yesterday"
				else now if end == "today"
				else datetime.strptime(end, "%Y-%m-%d")
			)

			query = query.gte("created_at", start_dt.replace(hour=0, minute=0, second=0).isoformat()) \
						.lte("created_at", end_dt.replace(hour=23, minute=59, second=59).isoformat())

			if txn_type == "income":
				query = query.gt("amount", 0)
			elif txn_type == "expenses":
				query = query.lt("amount", 0)

			if category:
				query = apply_multi_ilike(query, "category", category)
			if wallet:
				query = apply_multi_ilike(query, "wallet", wallet)


		# --- All data ---
		elif m := re.fullmatch(pattern_all, text):
			txn_type, category, wallet = m.groups()

			if txn_type == "income":
				query = query.gt("amount", 0)
			elif txn_type == "expenses":
				query = query.lt("amount", 0)

			if category:
				query = apply_multi_ilike(query, "category", category)
			if wallet:
				query = apply_multi_ilike(query, "wallet", wallet)


		# --- Single Day (or default to today) ---
		elif m := re.fullmatch(pattern_single, text):
			txn_type, category, date_str, wallet = m.groups()

			if not date_str or date_str == "today":
				target_date = now
			elif date_str == "yesterday":
				target_date = now - timedelta(days=1)
			else:
				target_date = datetime.strptime(date_str, "%Y-%m-%d")

			start_dt = target_date.replace(hour=0, minute=0, second=0)
			end_dt = target_date.replace(hour=23, minute=59, second=59)

			query = query.gte("created_at", start_dt.isoformat()).lte("created_at", end_dt.isoformat())

			if txn_type == "income":
				query = query.gt("amount", 0)
			elif txn_type == "expenses":
				query = query.lt("amount", 0)

			if category:
				query = apply_multi_ilike(query, "category", category)
			if wallet:
				query = apply_multi_ilike(query, "wallet", wallet)


		else:
			await update.message.reply_text(
				"❌ Unrecognized format.\n"
				"Try:\n"
				"• `Show expenses`\n"
				"• `Show income of salary for yesterday`\n"
				"• `Show all transactions`\n"
				"• `Show expenses of food from 2025-06-01 to 2025-06-10`"
			)
			return


		# --- Execute query ---
		data = query.order("created_at", desc=True).execute().data

		if not data:
			await update.message.reply_text("ℹ️ No transactions found.")
			return

		message = f"📊 *Transactions:*\n\n"
		total_income = 0
		total_expense = 0
		for txn in data:
			amt = txn["amount"]
			if amt > 0:
				sign = "🟢 Income"
				total_income += amt

			else:
				sign = "🔴 Expense"
				total_expense += abs(amt)

			message += (
				f"{sign} ₹{abs(amt)}\n"
				f"📂 {txn['category']} | 💳 {txn['wallet']}\n"
				f"🗓️ {txn.get('created_at', '')[:10]} | 📝 {txn.get('note', '')}\n\n"
			)
		
		net_total = total_income - total_expense

		summary = ["📈 *Summary:*\n"]

		if "transactions" in text or "transaction" in text or ("income" not in text and ("expense" not in text or "expenses" not in text)):
			summary.append(f"🟢 Total Income   : ₹{total_income:.2f}")
			summary.append(f"🔴 Total Expenses : ₹{total_expense:.2f}")
			summary.append(f"🧾 Net: ₹{net_total:.2f}")

		elif "income" in text:
			summary.append(f"🟢 Total Income : ₹{total_income:.2f}")
			
		elif "expenses" in text:
			summary.append(f"🔴 Total Expenses : ₹{total_expense:.2f}")

		message += "\n" + "\n".join(summary)	

		await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

	except Exception as e:
		print("Free-form error:", e)
		await update.message.reply_text("⚠️ Could not process request.")

def apply_multi_ilike(query, field, value_string):
	values = [v.strip() for v in value_string.split(",") if v.strip()]
	if not values:
		return query
	if len(values) == 1:
		return query.ilike(field, f"%{values[0]}%")

	# Build Supabase 'or' string
	conditions = [f"{field}.ilike.%{v}%" for v in values]
	joined = ",".join(conditions)
	return query.or_(joined)

# --- TELEGRAM + WEBHOOK SETUP ---
app = ApplicationBuilder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
	entry_points=[CommandHandler("inc", income_command), CommandHandler("exp", expense_command)],
	states={
		CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
		AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
		WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wallet)],
		NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_note)],
		DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)]
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
