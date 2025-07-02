from telegram import Update
from telegram.ext import ConversationHandler, ContextTypes
from telegram.constants import ParseMode
from datetime import datetime, timedelta
from config import (
	supabase,
    IST, 
    AMOUNT, WALLET, NOTE, DATE,
    UPDATE_DATA, UPDATE_CONFIRM,
    DELETE_CONFIRM,
    BUDGET_START_DATE, BUDGET_END_DATE,
	BUDGET_CATEGORY, BUDGET_WALLET, BUDGET_AMOUNT, BUDGET_DEFAULT
)
from parser import parse_expense
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup


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
	context.user_data["update_id"] = update.message.text.strip().split("_")[1]
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


# --- Step 1: Delete ID ---
async def get_delete_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
	context.user_data["delete_id"] = update.message.text.strip().split("_")[1]
	user_id = update.effective_user.id
	txn_id = context.user_data["delete_id"]

	try:
		result = supabase.table("Expenses").select("*").eq("user_id", user_id).eq("id", txn_id).single().execute()
		data = result.data

		if not data:
			await update.message.reply_text("❌ Transaction not found.")
			return ConversationHandler.END

		context.user_data["delete_data"] = data

		await update.message.reply_text(
			f"You are about to delete the following transaction:\n\n"
			f"🆔 ID {txn_id}\n"
			f"{'🟢 Income' if data['amount'] > 0 else '🔴 Expense'} ₹{abs(data['amount'])}\n"
			f"📂 {data['category']} | 💳 {data['wallet']}\n"
			f"🗓️ {data['created_at'][:10]} | 📝 {data.get('note', '')}\n\n"
			f"Are you sure? Reply with 'yes' to confirm or 'no' to cancel.",
			parse_mode=ParseMode.MARKDOWN
		)
		return DELETE_CONFIRM
	
	except Exception as e:
		print("Delete ID Fetch Error:", e)
		await update.message.reply_text("⚠️ Failed to fetch transaction.")
		return ConversationHandler.END

# --- Step 2: Confirm Delete
async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
	reply = update.message.text.strip().lower()
	if reply not in ["yes", "y", "confirm"]:
		await update.message.reply_text("❌ Deletion cancelled.")
		return ConversationHandler.END

	user_id = update.effective_user.id
	txn_id = context.user_data["delete_id"]

	try:
		delete_result = supabase.table("Expenses").delete().eq("user_id", user_id).eq("id", txn_id).execute()

		if not delete_result.data:
			await update.message.reply_text("⚠️ Transaction not found or already deleted.")
		else:
			await update.message.reply_text("✅ Transaction successfully deleted.")

	except Exception as e:
		print("Delete Error:", e)
		await update.message.reply_text("⚠️ Failed to delete transaction.")

	return ConversationHandler.END


async def budget_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	if query.data == "budget_view":
		print("Viewing budget")

	if query.data == "budget_add":
		await query.message.reply_text("📅 Enter budget start date (YYYY-MM-DD).")
		return BUDGET_START_DATE
	
	if query.data == "budger_remove":
		print("removing budget")

	return ConversationHandler.END

# --- Step 1: Budget Start Date ---
async def get_budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# query = update.callback_query
	# await query.answer()

	try:
		start_date = datetime.strptime(update.message.text.strip(), '%Y-%m-%d').isoformat()
		context.user_data["budget_start"] = str(start_date)
		await update.message.reply_text("📅 Enter budget end date (YYYY-MM-DD).")
		return BUDGET_END_DATE

	except Exception as e:
		await update.message.reply_text("❌ Invalid format. Use YYYY-MM-DD.")
		return BUDGET_START_DATE

# --- Step 2: Budget End Date ---
async def get_budget_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
	try:
		end_date = datetime.strptime(update.message.text.strip(), '%Y-%m-%d').isoformat()
		start_date = context.user_data["budget_start"]

		if end_date <= start_date:
			await update.message.reply_text("⚠️ End date must be after start date. Try again:")
			return BUDGET_END_DATE
		
		context.user_data["budget_end"] = str(end_date)
		user_id = update.effective_user.id

		try:
			result = supabase.table("Expenses") \
							.select("wallet") \
							.eq("user_id", user_id) \
							.execute()
			
			wallets = list({txn["wallet"] for txn in result.data if txn.get("wallet")})
			wallets.sort()

			if not wallets:
				wallets = ["UPI", "Cash", "Card"]
			
			buttons = [[InlineKeyboardButton(w, callback_data=f"budget_wallet:{w}")] for w in wallets]
			buttons.append([InlineKeyboardButton("✅ Done", callback_data="budget_wallet_done")])
			await update.message.reply_text("💳 Select wallet(s) to apply budget to:", reply_markup=InlineKeyboardMarkup(buttons))
			context.user_data["budget_wallets"] = []
			return BUDGET_WALLET
		
		except Exception as e:
			await update.message.reply_text("⚠️ Failed to fetch wallets. Try again.")
			return ConversationHandler.END
	
	except Exception as e:
		await update.message.reply_text("❌ Invalid format. Use YYYY-MM-DD.")
		return BUDGET_END_DATE

# --- Step 3: Buget Wallets ---
async def get_budget_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	if query.data == "budget_wallet_done":
		user_id = update.effective_user.id
		try:
			result = supabase.table("Expenses") \
				.select("category") \
				.eq("user_id", user_id) \
				.execute()
			
			categories = list({txn["category"] for txn in result.data if txn.get("category")})
			categories.sort()

			if not categories:
				categories = ["Food", "Travel", "Health"]\
				
			buttons = [[InlineKeyboardButton(c, callback_data=f"budget_category:{c}")] for c in categories]
			buttons.append([InlineKeyboardButton("✅ Done", callback_data="budget_category_done")])
			
			await query.message.reply_text("📂 Select category(s) to apply budget to:", reply_markup=InlineKeyboardMarkup(buttons))
			context.user_data["budget_categories"] = []
			return BUDGET_CATEGORY



		except Exception as e:
			print("Error fetching categories:", e)
			await query.message.reply_text("⚠️ Failed to fetch categories. Try again.")
			return ConversationHandler.END


	wallet = query.data.split(":")[1]
	if wallet not in context.user_data["budget_wallets"]:
		context.user_data["budget_wallets"].append(wallet)

	await query.message.reply_text(f"✔️ Added wallet: {wallet}")
	return BUDGET_WALLET

# --- Step 4: Budget Categories ---
async def get_budget_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	if query.data == "budget_category_done":
		await query.message.reply_text("💰 Now enter the budget amount:")
		return BUDGET_AMOUNT

	category = query.data.split(":")[1]
	if category not in context.user_data["budget_categories"]:
		context.user_data["budget_categories"].append(category)

	await query.message.reply_text(f"✔️ Added category: {category}")
	return BUDGET_CATEGORY

# --- Step 5: Budget Amount ---
async def get_budget_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
	try:
		amount = float(update.message.text.strip())
		context.user_data["budget_amount"] = amount

		keyboard = InlineKeyboardMarkup([
			[InlineKeyboardButton("Yes ✅", callback_data="budget_default_yes"),
			 InlineKeyboardButton("No ❌", callback_data="budget_default_no")]
		])
		await update.message.reply_text("Do you want to make this a default budget?", reply_markup=keyboard)
		return BUDGET_DEFAULT
	except:
		await update.message.reply_text("❌ Please enter a valid number.")
		return BUDGET_AMOUNT

# --- Budget Default ---
async def get_budget_default(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	is_default = query.data.endswith("yes")

	user_id = update.effective_user.id
	start_date = context.user_data["budget_start"],
	end_date = context.user_data["budget_end"],
	wallets = context.user_data.get("budget_wallets", [])
	categories = context.user_data.get("budget_categories", [])
	amount = context.user_data["budget_amount"]

	if not wallets:
		wallets = ["__ALL__"]

	if not categories:
		categories = ["__ALL__"]


	# Save to Supabase (replace with actual code)
	try:
		response = supabase.table("Budgets").insert({
			"user_id" : user_id,
			"start_date" : start_date,
			"end_date" : end_date,
			"amount" : amount,
			"wallets" : wallets,
			"categories" : categories,
			"is_default" : is_default,
			"created_at" : datetime.now(IST).isoformat()
		}).execute()

		await update.callback_query.message.reply_text("✅ Budget saved successfully!")	
	
	except Exception as e:
		print("Error saving budget:", e)
		await update.callback_query.message.reply_text("❌ Failed to save budget. Please try again later.")

	return ConversationHandler.END


