import re
from datetime import datetime, timedelta
from config import supabase
from parser import parse_expense, apply_multi_ilike
from telegram.ext import ConversationHandler, ContextTypes
from telegram.constants import ParseMode
from telegram import Update
import os
import random
from config import IST
import pandas as pd
from io import BytesIO

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


async def handle_insert(update, context, user_id, parsed):
	category, amount, wallet, note, date_str = parsed

	try:
		created_at = (
			datetime.strptime(date_str, "%Y-%m-%d").isoformat() if date_str
			else datetime.now(IST).isoformat()
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
				f"🆔 ID {txn['id']}\n"
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
