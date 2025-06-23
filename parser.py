import re
from datetime import datetime, timedelta
from config import IST

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


def parse_expense(text):
	dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
	date = dates[0] if dates else None
	if date:
		text = text.replace(date, "")

	# Handle "today", "yesterday", "day before yesterday" for dates
	date_keywords = {"today", "yesterday", "day before yesterday"}
	
	parts = text.strip().split()
	
	# Check for date keywords at the end
	extracted_date_keyword = None
	if parts and parts[-1].lower() in date_keywords:
		extracted_date_keyword = parts.pop(-1).lower()

	if len(parts) < 3:
		return None
		
	category = parts[0]
	try:
		amount = float(parts[1])
	except ValueError:
		return None
	wallet = parts[2]
	note = " ".join(parts[3:]) if len(parts) > 3 else ""

	# Override date if keyword was found
	if extracted_date_keyword:
		if extracted_date_keyword == "today":
			date = datetime.now(IST).strftime("%Y-%m-%d")
		elif extracted_date_keyword == "yesterday":
			date = (datetime.now(IST) - timedelta(1)).strftime("%Y-%m-%d")
		elif extracted_date_keyword == "day before yesterday":
			date = (datetime.now(IST) - timedelta(2)).strftime("%Y-%m-%d")

	return category, amount, wallet, note, date
