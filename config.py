import os
from supabase import create_client
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
UPDATE_ID, UPDATE_DATA, UPDATE_CONFIRM = range(20, 23)