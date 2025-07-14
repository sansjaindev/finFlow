import re
from datetime import datetime, timedelta
from config import supabase
from parser import parse_expense, apply_multi_ilike
from telegram.ext import ConversationHandler, ContextTypes
from telegram.constants import ParseMode
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import os
import random
from config import IST
import pandas as pd
from io import BytesIO
from math import ceil

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

async def reset_default_budgets(app):
	CHAT_ID = int(os.getenv("CHAT_ID"))
	try:
		today = datetime.now(IST).date()

		response = supabase.table("Budgets") \
							.select("*") \
							.eq("is_default", True) \
							.eq("end_date", (today - timedelta(days=1)).isoformat()) \
							.execute()
		
		for budget in response.data:
			old_start = datetime.strptime(budget["start_date"], '%Y-%m-%d').date()
			old_end = datetime.strptime(budget["end_date"], '%Y-%m-%d').date()
			duration = (old_end - old_start).days + 1

			new_start = old_end + timedelta(days=1)
			new_end = new_start + timedelta(days=duration - 1)

			supabase.table("Budgets").insert({
				"user_id" : budget["user_id"],
				"start_date" : new_start.isoformat(),
				"end_date" : new_end.isoformat(),
				"amount" : budget["amount"],
				"wallets" : budget["wallets"],
				"categories" : budget["categories"],
				"is_default" : True,
				"created_at" : datetime.now(IST).isoformat()
			}).execute()

			await app.bot.send_message(
				chat_id=CHAT_ID,
				text="Default budget rolled over for use."
			)

			supabase.table("Budgets") \
					.update({"is_default" : False}) \
					.eq("id", budget["id"]) \
					.execute()

	except Exception as e:
		print("❌ Failed to roll over default budgets:", e)


async def handle_insert(update, context, user_id, parsed):
	category, amount, wallet, note, date_str = parsed

	try:
		created_at = (
			datetime.strptime(date_str, "%Y-%m-%d").isoformat() if date_str
			else datetime.now(IST).isoformat()
		)

		final_amount = -abs(amount) if category.lower() not in ["income", "salary", "bonus"] else abs(amount)
		
		supabase.table("Expenses").insert({
			"user_id": user_id,
			"category": category,
			"amount": final_amount,
			"wallet": wallet,
			"note": note,
			"created_at": created_at
		}).execute()

		await update.message.reply_text(
			f"✅ Saved *{category.title()}* ₹{abs(final_amount)} via *{wallet}*\n"
			f"🗓️ {created_at[:10]} | 📝 {note}",
			parse_mode=ParseMode.MARKDOWN
		)
	except Exception as e:
		print("Insert Error:", e)
		await update.message.reply_text("⚠️ Failed to save entry.")
	
	return


async def handle_update(update, context, user_id, text):
	match = re.match(r"update transaction (\d+)\s+with\s+(.+)", text, re.IGNORECASE)
	if match:
		txn_id = match.group(1).strip()
		txn_text = match.group(2).strip()
		parsed = parse_expense(txn_text)
		
		if parsed:
			category, amount, wallet, note, date_str = parsed
			created_at = (
				datetime.strptime(date_str, "%Y-%m-%d").isoformat() if date_str
				else datetime.now(IST).isoformat()
			)
			final_amount = -abs(amount) if category.lower() not in ["income", "salary"] else abs(amount)

			try:
				result = supabase.table("Expenses").update({
					"category": category,
					"amount": final_amount,
					"wallet": wallet,
					"note": note,
					"created_at": created_at
				}).eq("user_id", user_id).eq("id", txn_id).execute()

				if not result.data:
					await update.message.reply_text("❌ Transaction not found. Please check the ID.")
					return ConversationHandler.END

				await update.message.reply_text(
					f"✅ Updated *{category.title()}* ₹{abs(final_amount)} via *{wallet}*\n"
					f"🗓️ {created_at[:10]} | 📝 {note}",
					parse_mode=ParseMode.MARKDOWN
				)

			except Exception as e:
				print("Update Error:", e)
				await update.message.reply_text("⚠️ Failed to update transaction.")
		
		else:
			await update.message.reply_text("❌ Could not parse the update format. Use something like: `update transaction 32 with Food 250 UPI`")
		
		return


async def handle_view(update, context, user_id, text):
	try:
		query = supabase.table("Expenses").select("*").eq("user_id", user_id)

		pattern_range = r"show(?: all)?\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?\s*from (\d{4}-\d{2}-\d{2}) (?:to|till) (yesterday|today|\d{4}-\d{2}-\d{2})(?: via ([^0-9]+))?\.?$"
		pattern_all = r"show all\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?(?: via ([^0-9]+))?\.?$"
		pattern_single = r"show(?: all)?\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?(?: for (today|yesterday|\d{4}-\d{2}-\d{2}))?(?: via ([^0-9]+))?\.?$"

		now = datetime.now(IST)

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
				target_date = now - timedelta(1)
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
		data = query.order("created_at", desc=False).execute().data

		if not data:
			await update.message.reply_text("ℹ️ No transactions found.")
			return

		# message = f"📊 *Transactions:*\n\n"
		# total_income = 0
		# total_expense = 0
		# for txn in data:
		# 	amt = txn["amount"]
		# 	if amt > 0:
		# 		sign = "🟢 Income"
		# 		total_income += amt

		# 	else:
		# 		sign = "🔴 Expense"
		# 		total_expense += abs(amt)

		# 	message += (
		# 		f"🆔 ID {txn['id']}\n"
		# 		f"{sign} ₹{abs(amt)}\n"
		# 		f"📂 {txn['category']} | 💳 {txn['wallet']}\n"
		# 		f"🗓️ {txn.get('created_at', '')[:10]} | 📝 {txn.get('note', '')}\n"
		# 		f"📝 Update : /update\_{txn['id']}\n"
		# 		f"❌ Delete  : /delete\_{txn['id']}\n\n"
		# 		# f"/update\_{txn['id']} | /delete\_{txn['id']}\n\n"
		# 	)
		
		# net_total = total_income - total_expense

		# summary = ["📈 *Summary:*\n"]

		# if "transactions" in text or "transaction" in text or ("income" not in text and ("expense" not in text or "expenses" not in text)):
		# 	summary.append(f"🟢 Total Income   : ₹{total_income:.2f}")
		# 	summary.append(f"🔴 Total Expenses : ₹{total_expense:.2f}")
		# 	summary.append(f"🧾 Net: ₹{net_total:.2f}")

		# elif "income" in text:
		# 	summary.append(f"🟢 Total Income : ₹{total_income:.2f}")
			
		# elif "expenses" in text:
		# 	summary.append(f"🔴 Total Expenses : ₹{total_expense:.2f}")

		# message += "\n" + "\n".join(summary)	

		# await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

		# context.user_data.pop("pagination", None)
		# context.user_data.pop("pagination_gen", None)

		gen = context.user_data.get("pagination_data", {}).get("gen", 0) + 1
		context.user_data["pagination_data"] = {
			"data" : data,
			"gen" : gen
		}
		await paginate_data(update, context, page=1, gen=gen)

	except Exception as e:
		print("Free-form error:", e)
		await update.message.reply_text("⚠️ Could not process request.")

async def paginate_data(update, context, page=1, gen=None):
	paginated_data = context.user_data.get("pagination_data", {})
	data = paginated_data["data"]
	current_gen = paginated_data.get("gen")

	if gen is None:
		gen = current_gen

	total_txns = len(data)

	for per_page in range(4, 2, -1):
		if total_txns %  per_page == 0:
			break
	
	total_pages = ceil(total_txns / per_page)

	start = (page - 1) * per_page
	end = start + per_page
	page_data = data[start:end]

	message = f"📊 *Transactions:*\n\n"
	total_income = 0
	total_expense = 0
	for txn in page_data:
		amt = txn["amount"]
		if amt > 0:
			sign = "🟢 Income"
			total_income += amt

		else:
			sign = "🔴 Expense"
			total_expense += abs(amt)

		message += (
			f"🆔 ID {txn['id']}\n"
			f"{sign} ₹{abs(amt)}\n"
			f"📂 {txn['category']} | 💳 {txn['wallet']}\n"
			f"🗓️ {txn.get('created_at', '')[:10]} | 📝 {txn.get('note', '')}\n"
			f"📝 Update : /update\_{txn['id']}\n"
			f"❌ Delete  : /delete\_{txn['id']}\n\n"
			# f"/update\_{txn['id']} | /delete\_{txn['id']}\n\n"
		)
	
	buttons = []
	if page > 1:
		buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_gen{gen}_{page - 1}"))

	if page < total_pages:
		buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"page_gen{gen}_{page + 1}"))

	if update.message:
		await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup([buttons]), parse_mode=ParseMode.MARKDOWN)
	
	elif update.callback_query:
		await update.callback_query.message.edit_text(message, reply_markup=InlineKeyboardMarkup([buttons]), parse_mode=ParseMode.MARKDOWN)

async def navigate_transaction_pages(update: Update, context: ContextTypes.DEFAULT_TYPE):
	try:
		query = update.callback_query
		await query.answer()
		data = query.data
		match = re.match(r"^page_gen(\d+)_(\d+)$", data)

		if not match:
			await query.message.reply_text("⚠️ Invalid navigation request.")
			return
		
		gen_clicked = int(match.group(1))
		page = int(match.group(2))

		current_gen = context.user_data.get("pagination_data", {}).get("gen", -1)

		
		if gen_clicked != current_gen:
			await query.message.reply_text("⚠️ This message has expired. Please request the transactions again.")
			return
			
		await paginate_data(update, context, page=page, gen=gen_clicked)
		
	except Exception as e:
		print("Pagination error:", e)
		await update.callback_query.message.reply_text("⚠️ Could not load page.")


async def handle_reports(update, context, user_id, text):
	try:
		query = supabase.table("Expenses").select("*").eq("user_id", user_id)

		pattern_range_report = r"generate (?:a )?report for(?: all)?\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?\s*from (\d{4}-\d{2}-\d{2}) (?:to|till) (yesterday|today|\d{4}-\d{2}-\d{2})(?: via ([^0-9]+))?\.?$"
		pattern_all_report = r"generate (?:a )?report for all\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?(?: via ([^0-9]+))?\.?$"
		pattern_single_report = r"generate (?:a )?report for(?: all)?\s*(income|expenses|transactions)?(?: of ([^0-9]+?))?(?: for (today|yesterday|\d{4}-\d{2}-\d{2}))?(?: via ([^0-9]+))?\.?$"

		now = datetime.now(IST)

		# --- Ranged Data ---
		if m := re.fullmatch(pattern_range_report, text):
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
		elif m := re.fullmatch(pattern_all_report, text):
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
		elif m := re.fullmatch(pattern_single_report, text):
			txn_type, category, date_str, wallet = m.groups()

			if not date_str or date_str == "today":
				target_date = now
			elif date_str == "yesterday":
				target_date = now - timedelta(1)
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
		
		data = query.order("created_at", desc=True).execute().data

		if not data:
			await update.message.reply_text("ℹ️ No transactions found.")
			return
		
		
		t_created_at = []
		t_type = []
		t_cat = []
		t_amt = []
		t_wallet = []
		t_note = []

		for txn in data:
			t_created_at.append(txn['created_at'])
			t_type.append("Income" if txn['amount'] > 0 else "Expense")
			t_cat.append(txn['category'])
			t_amt.append(abs(txn['amount']))
			t_wallet.append(txn['wallet'])
			t_note.append(txn['note'])

		file_data = pd.DataFrame({
			'Date': t_created_at,
			'Transaction Type': t_type,
			'Category': t_cat,
			'Amount': t_amt,
			'Wallet': t_wallet,
			'Note': t_note
		})
		
		excel_buffer = BytesIO()
		file_data.to_excel(excel_buffer, index=False)
		excel_buffer.seek(0)

		await update.message.reply_document(document=excel_buffer, filename="transactions.xlsx")
		
	except Exception as e:
		print("Free-form error:", e)
		await update.message.reply_text("⚠️ Could not process request.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
	await update.message.reply_text("❌ Cancelled.")
	return ConversationHandler.END
