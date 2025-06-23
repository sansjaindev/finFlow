from telegram import Update
from telegram.ext import ConversationHandler, ContextTypes
from telegram.constants import ParseMode
from config import supabase
from datetime import datetime, timedelta
from config import AMOUNT, WALLET, NOTE, DATE, UPDATE_DATA, UPDATE_CONFIRM, IST
from parser import parse_expense


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

# --- Step 5: Date ---
async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
	date_input = update.message.text.strip()
	if date_input.lower() == "today":
		created_at = datetime.now(IST).isoformat()

	elif date_input.lower() == "yesterday":
		created_at = (datetime.now(IST) - timedelta(1)).isoformat()
	
	elif date_input.lower() == "day before yesterday":
		created_at = (datetime.now(IST) - timedelta(2)).isoformat()

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


# --- Step 1: Update ID ---
async def get_update_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
	context.user_data["update_id"] = update.message.text.strip()
	user_id = update.effective_user.id
	txn_id = context.user_data["update_id"]

	try:
		result = supabase.table("Expenses").select("*") \
			.eq("user_id", user_id).eq("id", txn_id).single().execute()

		data = result.data
		if not data:
			await update.message.reply_text("❌ Transaction not found. Please check the ID.")
			return ConversationHandler.END

		# Display transaction details to confirm
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
			f"✏️ Now enter the updated transaction (like: Food 1000 UPI Dinner)",
			parse_mode=ParseMode.MARKDOWN
		)
		return UPDATE_DATA
	
	except Exception as e:
		print("Error fetching transaction by ID:", e)
		await update.message.reply_text("⚠️ Failed to fetch transaction. Please try again later.")
		return ConversationHandler.END

# --- Step 2: Update Data ---
async def get_update_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
	parsed = parse_expense(update.message.text.strip())
	if not parsed:
		await update.message.reply_text("❌ Invalid format. Try like: Food 250 UPI Dinner")
		return UPDATE_DATA

	context.user_data["updated_data"] = parsed
	await update.message.reply_text("Are you sure you want to update this transaction? Reply with 'yes' to confirm or 'no' to cancel.")
	return UPDATE_CONFIRM

# --- Step 3: Confirm Update ---
async def confirm_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
	response = update.message.text.strip().lower()
	if response not in ["yes", "confirm", 'y', 'yeah']:
		await update.message.reply_text("❌ Update cancelled.")
		return ConversationHandler.END

	user_id = update.effective_user.id
	txn_id = context.user_data["update_id"]
	category, amount, wallet, note, date_str = context.user_data["updated_data"]

	created_at = (
		datetime.strptime(date_str, "%Y-%m-%d").isoformat() if date_str
		else datetime.now(IST).isoformat()
	)
	final_amount = -abs(amount) if category.lower() not in ["income", "salary"] else abs(amount)

	try:
		update_result = supabase.table("Expenses").update({
			"category": category,
			"amount": final_amount,
			"wallet": wallet,
			"note": note,
			"created_at": created_at
		}).eq("user_id", user_id).eq("id", int(txn_id)).execute()

		if not update_result.data:
			await update.message.reply_text("❌ Transaction not found or could not be updated.")
			return ConversationHandler.END

		display_date = created_at[:10]
		await update.message.reply_text(
			f"✅ Transaction updated:\n*{category.title()}* ₹{abs(final_amount)} via *{wallet}*\n🗓️ {display_date} | 📝 {note}",
			parse_mode=ParseMode.MARKDOWN
		)

	except Exception as e:
		print("Update error:", e)
		await update.message.reply_text("⚠️ Failed to update transaction.")

	return ConversationHandler.END
