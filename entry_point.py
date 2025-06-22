import re
from telegram import Update
from telegram.ext import ContextTypes
from config import CATEGORY, UPDATE_ID
from config import (
	supabase,
	UPDATE_DATA
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from parser import parse_expense
from operation import handle_insert, handle_update, handle_view

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

# --- Update Entry Start ---
async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
	await update.message.reply_text("Enter ID of the transaction you want to update:")
	return UPDATE_ID


# --- Handler to bridge free-form "update transaction ID" to conversation ---
async def get_update_free_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
	match = re.match(r"update transaction (\d+)$", update.message.text.strip(), re.IGNORECASE)
	if match:
		context.user_data["update_id"] = match.group(1).strip()
		user_id = update.effective_user.id
		txn_id = context.user_data["update_id"]

		try:
			result = supabase.table("Expenses").select("*") \
				.eq("user_id", user_id).eq("id", txn_id).single().execute()

			data = result.data
			if not data:
				await update.message.reply_text("❌ Transaction not found. Please check the ID.")
				return ConversationHandler.END

			amount = data["amount"]
			category = data["category"]
			wallet = data["wallet"]
			note = data.get("note", "")
			date = data.get("created_at", "")[:10]

			txntype = "🟢 Income" if amount > 0 else "🔴 Expense"

			await update.message.reply_text(
				f"📄 *Current Transaction Details:*\n"
				f"🆔 ID {txn_id}\n"
				f"{txntype} ₹{abs(amount)}\n"
				f"📂 {category} | 💳 {wallet}\n"
				f"🗓️ {date} | 📝 {note}\n\n"
				f"✏️ Now enter the updated transaction (like: `Food 1000 UPI Dinner`)",
				parse_mode=ParseMode.MARKDOWN
			)

			return UPDATE_DATA
		
		except Exception as e:
			print("Error fetching transaction by ID from free-form:", e)
			await update.message.reply_text("⚠️ Failed to fetch transaction. Please try again later.")
			return ConversationHandler.END
	return ConversationHandler.END

async def free_form_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	text = update.message.text.strip().rstrip(".")
	text_lower = text.lower()
	user_id = update.effective_user.id

	try:
		# --- 1. Check for Update Command ---
		if text_lower.startswith("update transaction"):
			await handle_update(update, context, user_id, text)
			return

		# --- 2. Check for Insert Format ---
		parsed = parse_expense(text)
		if parsed:
			await handle_insert(update, context, user_id, parsed)
			return

		# --- 3. Otherwise, assume View Request ---
		if text_lower.startswith("show"):
			await handle_view(update, context, user_id, text_lower)
			return

		# --- 4. Fallback if nothing matched ---
		await update.message.reply_text("❌ Unrecognized input. Please use 'Show ...', quick entry, or update format.")

	except Exception as e:
		print("Transaction Handler Error:", e)
		await update.message.reply_text("⚠️ Something went wrong while processing your request.")
