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
	BUDGET_CATEGORY, BUDGET_WALLET, BUDGET_AMOUNT, BUDGET_DEFAULT,
	BUDGET_VIEW_CHOICE,
	DELETE_BUDGET_ID, DELETE_BUDGET_CONFIRM
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
	keyboard = InlineKeyboardMarkup([
		[
			InlineKeyboardButton("✅ Yes", callback_data="update_confirm"),
			InlineKeyboardButton("❌ No", callback_data="update_cancel")
		]
	])

	await update.message.reply_text(
		"Are you sure you want to update this transaction?",
		parse_mode=ParseMode.MARKDOWN,
		reply_markup=keyboard
	)

	return UPDATE_CONFIRM

# --- Step 3: Confirm Update ---
async def confirm_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()
	action = query.data

	if action == "update_cancel":
		await query.message.edit_text("❌ Update cancelled.")
		return ConversationHandler.END
	
	if action != "update_confirm":
		await query.message.edit_text("❌ Invalid action.")
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
			await update.message.edit_text("❌ Transaction not found or could not be updated.")
			return ConversationHandler.END

		display_date = created_at[:10]
		await query.message.edit_text(
			f"✅ Transaction updated:\n*{category.title()}* ₹{abs(final_amount)} via *{wallet}*\n🗓️ {display_date} | 📝 {note}",
			parse_mode=ParseMode.MARKDOWN
		)

	except Exception as e:
		print("Update error:", e)
		await query.message.edit_text("⚠️ Failed to update transaction.")

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

		keyboard = InlineKeyboardMarkup([
			[
				InlineKeyboardButton("✅ Yes", callback_data="delete_confirm"),
				InlineKeyboardButton("❌ No", callback_data="delete_cancel")
			]
		])

		await update.message.reply_text(
			f"You are about to delete the following transaction:\n\n"
			f"🆔 ID {txn_id}\n"
			f"{'🟢 Income' if data['amount'] > 0 else '🔴 Expense'} ₹{abs(data['amount'])}\n"
			f"📂 {data['category']} | 💳 {data['wallet']}\n"
			f"🗓️ {data['created_at'][:10]} | 📝 {data.get('note', '')}\n\n"
			f"Are you sure?",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=keyboard
		)
		return DELETE_CONFIRM
	
	except Exception as e:
		print("Delete ID Fetch Error:", e)
		await update.message.reply_text("⚠️ Failed to fetch transaction.")
		return ConversationHandler.END

# --- Step 2: Confirm Delete
async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()
	action = query.data

	if action == "delete_cancel":
		await query.message.edit_text("❌ Deletion cancelled.")
		return ConversationHandler.END
	
	if action != "delete_confirm":
		await query.message.edit_text("❌ Invalid action.")
		return ConversationHandler.END
	
	
	user_id = update.effective_user.id
	txn_id = context.user_data["delete_id"]

	try:
		delete_result = supabase.table("Expenses").delete().eq("user_id", user_id).eq("id", txn_id).execute()

		if not delete_result.data:
			await query.message.edit_text("⚠️ Transaction not found or already deleted.")
		else:
			await query.message.edit_text("✅ Transaction successfully deleted.")

	except Exception as e:
		print("Delete Error:", e)
		await query.message.edit_text("⚠️ Failed to delete transaction.")

	return ConversationHandler.END


async def budget_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	if query.data == "budget_view":
		keyboard = [
			[InlineKeyboardButton("📅 Active Budgets", callback_data="budget_view_active")],
			[InlineKeyboardButton("🗂️ All Budgets", callback_data="budget_view_all")]
		]
		
		await query.message.reply_text(
			"📊 *Which budgets do you want to view?*",
			parse_mode="Markdown",
			reply_markup=InlineKeyboardMarkup(keyboard)
		)

		return BUDGET_VIEW_CHOICE


	if query.data == "budget_add":
		await query.message.reply_text("📅 Enter budget start date (YYYY-MM-DD).")
		return BUDGET_START_DATE
	
	if query.data == "budget_remove":
		user_id = update.effective_user.id
		result = supabase.table("Budgets").select("id,start_date,end_date,amount") \
										.eq("user_id", user_id).execute()

		budgets = result.data
		if not budgets:
			await query.message.reply_text("ℹ️ No budgets to delete.")
			return ConversationHandler.END

		buttons = [
			[InlineKeyboardButton(f"{b['start_date']} → {b['end_date']} (₹{int(b['amount'])})", callback_data=f"delete_budget:{b['id']}")]
			for b in budgets
		]

		await query.message.reply_text(
			"🗑️ *Select a budget to delete:*",
			reply_markup=InlineKeyboardMarkup(buttons),
			parse_mode=ParseMode.MARKDOWN
		)

		return DELETE_BUDGET_ID

	return ConversationHandler.END

# --- Step 1: Budget Start Date ---
async def get_budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

	all_wallets = supabase.table("Expenses") \
								.select("wallet") \
								.eq("user_id", user_id) \
								.execute()
	
	all_categories = supabase.table("Expenses") \
								.select("category") \
								.eq("user_id", user_id) \
								.execute()
	
	all_wallets = sorted({txn["wallet"] for txn in all_wallets.data if txn.get("wallet")})
	all_categories = sorted({txn["category"] for txn in all_categories.data if txn.get("category")})

	if not wallets or set(wallets) == set(all_wallets):
		wallets = ["__ALL__"]

	if not categories or set(categories) == set(all_categories):
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


async def get_budget_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	user_id = update.effective_user.id
	today = datetime.now(IST).date()

	try:
		result = supabase.table("Budgets") \
							.select("*") \
							.eq("user_id", user_id) \
							.execute()
		
		budgets = result.data

		if query.data == "budget_view_active":
			budgets = [b for b in budgets if datetime.strptime(b["start_date"], '%Y-%m-%d').date() <= today <= datetime.strptime(b["end_date"], '%Y-%m-%d').date()]

		if not budgets:
			await query.message.reply_text("ℹ️ No budgets found for your selection.")
			return ConversationHandler.END
		
		context.user_data["budget_list"] = {str(b["id"]): b for b in budgets}

		message = "📋 *Your Budgets:*\n\n"
		for b in budgets:
			message += (
				f"🗓️ {b['start_date']} → {b['end_date']} | ₹{int(b['amount'])}\n"
				f"🔗 View Budget: /vb\_{b['id']}\n"
				f"🗑️ Delete Budget /db\_{b['id']}\n\n"
			)
		
		await query.message.reply_text(message.strip(), parse_mode="Markdown")
		return ConversationHandler.END

	except Exception as e:
		await query.message.reply_text("⚠️ Failed to fetch budgets. Try again later.")
		return ConversationHandler.END


async def show_budget_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user_id = update.effective_user.id
	text = update.message.text.strip()
	budget_id = text.split("_")[1]
	
	try:
		result = supabase.table("Budgets") \
							.select("*") \
							.eq("user_id", user_id) \
							.eq("id", int(budget_id)) \
							.single() \
							.execute()
		
		budget = result.data

		if not budget:
			await update.message.reply_text("❌ Budget not found.")
			return ConversationHandler.END

		start = datetime.strptime(budget["start_date"], '%Y-%m-%d')
		end = datetime.strptime(budget["end_date"], '%Y-%m-%d')
		amount = float(budget["amount"])
		days_total = (end - start).days + 1
		today = datetime.now(IST).date()
		days_passed = (today - start.date()).days + 1 if start.date() <= today <= end.date() else days_total

		txns = supabase.table("Expenses") \
			.select("amount,created_at,wallet,category") \
			.eq("user_id", update.effective_user.id) \
			.gte("created_at", start.isoformat()) \
			.lte("created_at", end.isoformat()) \
			.lt("amount", 0) \
			.execute()
		
		txns = [
			t for t in txns.data
			if (budget["wallets"][0] == "__ALL__" or t["wallet"] in budget["wallets"])
			and (budget["categories"][0] == "__ALL__" or t["category"] in budget["categories"])
		]

		spent = abs(sum(float(t["amount"]) for t in txns))
		remaining = amount - spent
		avg_daily = spent / days_passed if days_passed > 0 else 0
		optimal_daily = amount / days_total if days_total > 0 else 0

		msg = (
			f"📊 *Budget Status for*\n"
			f"👛 *Wallets: {', '.join(['ALL'] if budget.get('wallets')[0] == '__ALL__' else budget.get('wallets', []))}*\n"
			f"📂 *Categories: {', '.join(['ALL'] if budget.get('categories')[0] == '__ALL__' else budget.get('categories', []))}*\n"
			f"🗓️ *{start.date()} → {end.date()}*:\n\n"
			f"💰 Budgeted: ₹{amount}\n"
			f"💸 Spent: ₹{spent:.2f}\n"
			f"💼 Remaining: ₹{remaining:.2f}\n"
			f"📈 Daily Spend Avg: ₹{avg_daily:.2f}\n"
			f"✅ Optimal Daily: ₹{optimal_daily:.2f}\n"
			f"📈 *Predicted Total Spend* : ₹{(avg_daily * days_total):.0f}"
		)

		if today <= end.date():
			if avg_daily * days_total > amount:
				msg += " ❗\n\n⚠️ *You’re on track to exceed your budget.*"
			elif remaining < amount * 0.2:
				msg += "\n\n⚠️ *You’re close to exhausting your budget.*"
			else:
				msg += "\n\n✅ *You're within budget.*"

		await update.message.reply_text(msg, parse_mode="Markdown")

	except Exception as e:
		print("Budget stats error:", e)
		await update.message.reply_text("❌ Failed to compute budget statistics.")

	return ConversationHandler.END


async def get_budget_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()
	budget_id = query.data.split(":")[1]
	context.user_data["delete_budget_id"] = budget_id

	user_id = update.effective_user.id
	result = supabase.table("Budgets").select("*").eq("user_id", user_id).eq("id", budget_id).single().execute()
	budget = result.data

	if not budget:
		await query.message.reply_text("❌ Budget not found.")
		return ConversationHandler.END

	context.user_data["delete_budget_data"] = budget

	confirm_markup = InlineKeyboardMarkup([
		[InlineKeyboardButton("✅ Yes", callback_data="delete_budget_confirm"),
		 InlineKeyboardButton("❌ No", callback_data="delete_budget_cancel")]
	])

	await query.message.reply_text(
		f"Are you sure you want to delete this budget?\n\n"
		f"🗓️ {budget['start_date']} → {budget['end_date']} | ₹{int(budget['amount'])}",
		reply_markup=confirm_markup
	)
	return DELETE_BUDGET_CONFIRM

async def confirm_delete_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	if query.data == "delete_budget_cancel":
		await query.message.edit_text("❌ Budget deletion cancelled.")
		return ConversationHandler.END

	if query.data != "delete_budget_confirm":
		await query.message.edit_text("❌ Invalid action.")
		return ConversationHandler.END

	budget_id = context.user_data["delete_budget_id"]
	user_id = update.effective_user.id

	try:
		delete_result = supabase.table("Budgets").delete().eq("user_id", user_id).eq("id", budget_id).execute()
		
		if not delete_result.data:
			await query.message.edit_text("⚠️ Budget not found or already deleted.")
		else:
			await query.message.edit_text("✅ Budget successfully deleted.")

	except Exception as e:
		print("Error deleting budget:", e)
		await query.message.edit_text("⚠️ Failed to delete budget. Please try again later.")

	return ConversationHandler.END

async def delete_budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
	budget_id = update.message.text.strip().split("_")[1]
	user_id = update.effective_user.id

	result = supabase.table("Budgets").select("*").eq("user_id", user_id).eq("id", budget_id).single().execute()
	budget = result.data

	if not budget:
		await update.message.reply_text("❌ Budget not found.")
		return ConversationHandler.END

	context.user_data["delete_budget_id"] = budget_id
	context.user_data["delete_budget_data"] = budget

	keyboard = InlineKeyboardMarkup([
		[InlineKeyboardButton("✅ Yes", callback_data="delete_budget_confirm"),
		 InlineKeyboardButton("❌ No", callback_data="delete_budget_cancel")]
	])

	await update.message.reply_text(
		f"Are you sure you want to delete this budget?\n\n"
		f"🗓️ {budget['start_date']} → {budget['end_date']} | ₹{int(budget['amount'])}",
		reply_markup=keyboard
	)

	return DELETE_BUDGET_CONFIRM
