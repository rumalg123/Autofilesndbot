import re
import os
from os import environ
from dotenv import load_dotenv
import pymongo
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Load environment variables from .env file
load_dotenv()

# --- Regular Expression & Helper Functions ---
id_pattern = re.compile(r'^.\d+$')
def is_enabled(value, default):
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

# --- Sensitive Settings (Always loaded from .env) ---
BOT_TOKEN = environ.get('BOT_TOKEN', '')
API_ID = int(environ.get('API_ID', '0'))
API_HASH = environ.get('API_HASH', '')
# MongoDB connection settings
DATABASE_URI = environ.get('DATABASE_URI', "")
DATABASE_NAME = environ.get('DATABASE_NAME', "PIRO")
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'FILES')

# --- Non-Sensitive Settings (Should be saved in DB if not available) ---
PORT = environ.get("PORT", "8000")
SESSION = environ.get('SESSION', 'Media_search')
UPSTREAM_REPO = environ.get('UPSTREAM_REPO', 'https://github.com/rumalg123/Autofilesndbot')
UPSTREAM_BRANCH = environ.get('UPSTREAM_BRANCH', 'master')
# Bot settings
CACHE_TIME = int(environ.get('CACHE_TIME', 300))
USE_CAPTION_FILTER = bool(environ.get('USE_CAPTION_FILTER', True))
PREMIUM_DURATION_DAYS = int(environ.get('PREMIUM_DURATION_DAYS', 30))
NON_PREMIUM_DAILY_LIMIT = int(environ.get('NON_PREMIUM_DAILY_LIMIT', 10))
MESSAGE_DELETE_SECONDS = int(environ.get('MESSAGE_DELETE_SECONDS', 300))

# --- New Premium Setting ---
DISABLE_PREMIUM_FOR_USERS = is_enabled(environ.get('DISABLE_PREMIUM_FOR_USERS', "False"), False)

# Bot images & videos
PICS = environ.get('PICS', 'https://graph.org/file/bdc720faf2ff35cf92563.jpg').split()
NOR_IMG = environ.get("NOR_IMG", "https://graph.org/file/bdc720faf2ff35cf92563.jpg")
MELCOW_VID = environ.get("MELCOW_VID", "https://graph.org/file/ea40f1b53dd3b6315c130.mp4")
SPELL_IMG = environ.get("SPELL_IMG", "https://graph.org/file/145e01158bf5ea3bc798b.jpg")

# Admins, Channels & Users
ADMINS = [int(admin) if id_pattern.search(admin) else admin
          for admin in environ.get('ADMINS', '').split()]
CHANNELS = [int(ch) if id_pattern.search(ch) else ch
            for ch in environ.get('CHANNELS', '0').split()]
auth_users = [int(user) if id_pattern.search(user) else user
              for user in environ.get('AUTH_USERS', '').split()]
AUTH_USERS = (auth_users + ADMINS) if auth_users else []
auth_channel = environ.get('AUTH_CHANNEL')
auth_grp = environ.get('AUTH_GROUP')
AUTH_CHANNEL = int(auth_channel) if auth_channel and id_pattern.search(auth_channel) else None
AUTH_GROUPS = [int(ch) for ch in auth_grp.split()] if auth_grp else None

support_chat_id = environ.get('SUPPORT_CHAT_ID')
reqst_channel = environ.get('REQST_CHANNEL_ID')
REQST_CHANNEL = int(reqst_channel) if reqst_channel and id_pattern.search(reqst_channel) else None
SUPPORT_CHAT_ID = environ.get('SUPPORT_CHAT_ID', '')
SUPPORT_CHAT_ID = int(support_chat_id) if support_chat_id and id_pattern.search(support_chat_id) else None

NO_RESULTS_MSG = bool(environ.get("NO_RESULTS_MSG", True))

# Others
DELETE_CHANNELS = [int(dch) if id_pattern.search(dch) else dch
                   for dch in environ.get('DELETE_CHANNELS', '0').split()]
MAX_B_TN = environ.get("MAX_B_TN", "10")
MAX_BTN = is_enabled(environ.get('MAX_BTN', "True"), True)
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', 0))
SUPPORT_CHAT = environ.get('SUPPORT_CHAT', 'Dramaxship')
P_TTI_SHOW_OFF = is_enabled(environ.get('P_TTI_SHOW_OFF', "True"), False)
IMDB = is_enabled(environ.get('IMDB', "False"), True)
AUTO_FFILTER = is_enabled(environ.get('AUTO_FFILTER', "True"), True)
AUTO_DELETE = is_enabled(environ.get('AUTO_DELETE', "True"), True)
SINGLE_BUTTON = is_enabled(environ.get('SINGLE_BUTTON', "True"), True)
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", '📂 <em>File Name</em>: <code>|{file_name}</code> \n\n🖇 <em>File Size</em>: <code>{file_size}</code> \n\n❤️‍🔥 <b>Join @kdramaworld_ongoing</b> \n Bot @filefilter001bot \n\n <b>Have A Nice Day 💖</b>')
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", '')
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", '🏷 𝖳𝗂𝗍𝗅𝖾: <a href={url}>{title}</a> \n🔮 𝖸𝖾𝖺𝗋: {year} \n⭐️ 𝖱𝖺𝗍𝗂𝗇𝗀𝗌: {rating}/ 10  \n🎭 𝖦𝖾𝗇𝖾𝗋𝗌: {genres} \n\n🎊 𝖯𝗈𝗐𝖾𝗋𝖾𝖽 𝖡𝗒 [『KDramaWorld』](t.me/kdramaworld_ongoing)')
LONG_IMDB_DESCRIPTION = is_enabled(environ.get("LONG_IMDB_DESCRIPTION", "False"), False)
SPELL_CHECK_REPLY = is_enabled(environ.get("SPELL_CHECK_REPLY", "True"), True)
MAX_LIST_ELM = environ.get("MAX_LIST_ELM", None)
INDEX_REQ_CHANNEL = int(environ.get('INDEX_REQ_CHANNEL', LOG_CHANNEL))
FILE_STORE_CHANNEL = [int(ch) for ch in environ.get('FILE_STORE_CHANNEL', '').split()]
MELCOW_NEW_USERS = is_enabled(environ.get('MELCOW_NEW_USERS', "False"), True)
PROTECT_CONTENT = is_enabled(environ.get('PROTECT_CONTENT', "False"), False)
PUBLIC_FILE_STORE = is_enabled(environ.get('PUBLIC_FILE_STORE', "False"), True)
KEEP_ORIGINAL_CAPTION = is_enabled(environ.get('KEEP_ORIGINAL_CAPTION', "True"), True)
POWERED_BY = environ.get("POWERED_BY", "@kdramaworld_ongoing")
SUPPORT_GROUP = environ.get("SUPPORT_GROUP", "https://t.me/kdramasmirrorchat")
SUPPORT_GROUP_USERNAME = environ.get("SUPPORT_GROUP_USERNAME", "@kdramasmirrorchat")
MAIN_CHANNEL = environ.get("MAIN_CHANNEL", "https://t.me/kdramaworld_ongoing")

# START_TEXT definition is moved after DISABLE_PREMIUM_FOR_USERS is loaded from CONFIG.
# START_TEXT = environ.get("START_TEXT", f"HELLO!! This bot offers a premium plan valid for 30 days with unlimited file retrievals. Free users can retrieve up to {NON_PREMIUM_DAILY_LIMIT} files per day. Check out /plans for more details.")

# A log string (for informational purposes)
LOG_STR = "Current Cusomized Configurations are:-\n"
LOG_STR += ("IMDB Results are enabled, Bot will be showing imdb details for your queries.\n" if IMDB
            else "IMBD Results are disabled.\n")
LOG_STR += ("P_TTI_SHOW_OFF found, users will be redirected to send /start to Bot PM instead of sending file directly.\n" if P_TTI_SHOW_OFF
            else "P_TTI_SHOW_OFF is disabled, files will be sent in PM instead of sending start.\n")
LOG_STR += ("SINGLE_BUTTON found, filename and file size will be shown in a single button instead of two separate buttons.\n" if SINGLE_BUTTON
            else "SINGLE_BUTTON is disabled, filename and file size will be shown as different buttons.\n")
LOG_STR += (f"CUSTOM_FILE_CAPTION enabled with value {CUSTOM_FILE_CAPTION}, your files will be sent along with this customized caption.\n" if CUSTOM_FILE_CAPTION
            else "No CUSTOM_FILE_CAPTION found, default file captions will be used.\n")
LOG_STR += ("Long IMDB storyline enabled.\n" if LONG_IMDB_DESCRIPTION
            else "LONG_IMDB_DESCRIPTION is disabled, plot will be shorter.\n")
LOG_STR += ("Spell Check Mode is enabled, the bot will suggest related movies if a query is not found.\n" if SPELL_CHECK_REPLY
            else "SPELL_CHECK_REPLY mode is disabled.\n")
LOG_STR += (f"MAX_LIST_ELM found, long lists will be shortened to the first {MAX_LIST_ELM} elements.\n" if MAX_LIST_ELM
            else "Full list of casts and crew will be shown in the IMDB template; restrict them by adding a value to MAX_LIST_ELM.\n")
LOG_STR += f"Your current IMDB template is {IMDB_TEMPLATE}\n"
LOG_STR += f"Upstream Repo {UPSTREAM_REPO}\n"
LOG_STR += f"Upstream Branch {UPSTREAM_BRANCH}\n"
LOG_STR += f"Messages auto-delete after {MESSAGE_DELETE_SECONDS} seconds (if enabled for a chat).\n"

# --- MongoDB Configuration Management Functions ---

def connect_to_mongo():
    """Connect and return the MongoDB client, database, and collection."""
    client = pymongo.MongoClient(DATABASE_URI)
    db = client[DATABASE_NAME]
    collection = db["BOT_SETTINGS"]
    return client, db, collection

def load_config_from_db(collection):
    """Attempt to load configuration from database using a fixed _id."""
    config = collection.find_one({"_id": "config"})
    return config

def save_config_to_db(collection, config_data):
    """Upsert the configuration data so that it is stored in the database."""
    collection.replace_one({"_id": "config"}, config_data, upsert=True)

def get_config_data_from_env():
    """Gather the non-sensitive config data from the environment."""
    config_data = {
        "PORT": PORT,
        "SESSION": SESSION,
        "CACHE_TIME": CACHE_TIME,
        "USE_CAPTION_FILTER": USE_CAPTION_FILTER,
        "PICS": PICS,
        "NOR_IMG": NOR_IMG,
        "MELCOW_VID": MELCOW_VID,
        "SPELL_IMG": SPELL_IMG,
        "ADMINS": ADMINS,
        "CHANNELS": CHANNELS,
        "AUTH_USERS": AUTH_USERS,
        "AUTH_CHANNEL": AUTH_CHANNEL,
        "AUTH_GROUPS": AUTH_GROUPS,
        "REQST_CHANNEL": REQST_CHANNEL,
        "SUPPORT_CHAT_ID": SUPPORT_CHAT_ID,
        "NO_RESULTS_MSG": NO_RESULTS_MSG,
        "DELETE_CHANNELS": DELETE_CHANNELS,
        "MAX_B_TN": MAX_B_TN,
        "MAX_BTN": MAX_BTN,
        "LOG_CHANNEL": LOG_CHANNEL,
        "SUPPORT_CHAT": SUPPORT_CHAT,
        "P_TTI_SHOW_OFF": P_TTI_SHOW_OFF,
        "IMDB": IMDB,
        "AUTO_FFILTER": AUTO_FFILTER,
        "AUTO_DELETE": AUTO_DELETE,
        "SINGLE_BUTTON": SINGLE_BUTTON,
        "CUSTOM_FILE_CAPTION": CUSTOM_FILE_CAPTION,
        "BATCH_FILE_CAPTION": BATCH_FILE_CAPTION,
        "IMDB_TEMPLATE": IMDB_TEMPLATE,
        "LONG_IMDB_DESCRIPTION": LONG_IMDB_DESCRIPTION,
        "SPELL_CHECK_REPLY": SPELL_CHECK_REPLY,
        "MAX_LIST_ELM": MAX_LIST_ELM,
        "INDEX_REQ_CHANNEL": INDEX_REQ_CHANNEL,
        "FILE_STORE_CHANNEL": FILE_STORE_CHANNEL,
        "MELCOW_NEW_USERS": MELCOW_NEW_USERS,
        "PROTECT_CONTENT": PROTECT_CONTENT,
        "PUBLIC_FILE_STORE": PUBLIC_FILE_STORE,
        "KEEP_ORIGINAL_CAPTION": KEEP_ORIGINAL_CAPTION,
        "POWERED_BY": POWERED_BY,
        "SUPPORT_GROUP": SUPPORT_GROUP,
        "SUPPORT_GROUP_USERNAME": SUPPORT_GROUP_USERNAME,
        "MAIN_CHANNEL": MAIN_CHANNEL,
        "START_TEXT": environ.get("START_TEXT"), # Get from env, or None
        "PREMIUM_DURATION_DAYS": PREMIUM_DURATION_DAYS,
        "NON_PREMIUM_DAILY_LIMIT": NON_PREMIUM_DAILY_LIMIT,
        "MESSAGE_DELETE_SECONDS": MESSAGE_DELETE_SECONDS,
        "DISABLE_PREMIUM_FOR_USERS": DISABLE_PREMIUM_FOR_USERS,
    }
    return config_data

def initialize_configuration():
    """
    Load the configuration from MongoDB if it exists.
    Otherwise, load from the environment and save it for future use.
    """
    client, db, collection = connect_to_mongo()
    config = load_config_from_db(collection)
    if config:
        logger.info("Configuration loaded from database.")
        return config
    else:
        logger.info("No configuration found in database. Loading from environment variables...")
        config_data = get_config_data_from_env()
        config_data["_id"] = "config"
        save_config_to_db(collection, config_data)
        logger.info("Configuration saved to database.")
        return config_data

# Execute configuration loading at import time
CONFIG = initialize_configuration()

# Optionally, you can update your module-level variables from CONFIG.
PORT = CONFIG.get("PORT", PORT)
SESSION = CONFIG.get("SESSION", SESSION)
CACHE_TIME = CONFIG.get("CACHE_TIME", CACHE_TIME)
USE_CAPTION_FILTER = CONFIG.get("USE_CAPTION_FILTER", USE_CAPTION_FILTER)
PICS = CONFIG.get("PICS", PICS)
NOR_IMG = CONFIG.get("NOR_IMG", NOR_IMG)
MELCOW_VID = CONFIG.get("MELCOW_VID", MELCOW_VID)
SPELL_IMG = CONFIG.get("SPELL_IMG", SPELL_IMG)
ADMINS = CONFIG.get("ADMINS", ADMINS)
CHANNELS = CONFIG.get("CHANNELS", CHANNELS)
AUTH_USERS = CONFIG.get("AUTH_USERS", AUTH_USERS)
AUTH_CHANNEL = CONFIG.get("AUTH_CHANNEL", AUTH_CHANNEL)
AUTH_GROUPS = CONFIG.get("AUTH_GROUPS", AUTH_GROUPS)
REQST_CHANNEL = CONFIG.get("REQST_CHANNEL")
SUPPORT_CHAT_ID = CONFIG.get("SUPPORT_CHAT_ID", SUPPORT_CHAT_ID)
NO_RESULTS_MSG = CONFIG.get("NO_RESULTS_MSG")
DELETE_CHANNELS = CONFIG.get("DELETE_CHANNELS")
MAX_B_TN = CONFIG.get("MAX_B_TN", MAX_B_TN)
MAX_BTN = CONFIG.get("MAX_BTN", MAX_BTN)
LOG_CHANNEL = CONFIG.get("LOG_CHANNEL")
SUPPORT_CHAT = CONFIG.get("SUPPORT_CHAT")
P_TTI_SHOW_OFF = CONFIG.get("P_TTI_SHOW_OFF")
IMDB_TEMPLATE = CONFIG.get("IMDB_TEMPLATE")
AUTO_FFILTER = CONFIG.get("AUTO_FFILTER")
AUTO_DELETE = CONFIG.get("AUTO_DELETE")
SINGLE_BUTTON = CONFIG.get("SINGLE_BUTTON")
CUSTOM_FILE_CAPTION = CONFIG.get("CUSTOM_FILE_CAPTION")
BATCH_FILE_CAPTION = CONFIG.get("BATCH_FILE_CAPTION")
LONG_IMDB_DESCRIPTION = CONFIG.get("LONG_IMDB_DESCRIPTION")
IMDB = CONFIG.get("IMDB")
SPELL_CHECK_REPLY = CONFIG.get("SPELL_CHECK_REPLY")
MAX_LIST_ELM = CONFIG.get("MAX_LIST_ELM")
INDEX_REQ_CHANNEL = CONFIG.get("INDEX_REQ_CHANNEL")
FILE_STORE_CHANNEL = CONFIG.get("FILE_STORE_CHANNEL")
MELCOW_NEW_USERS = CONFIG.get("MELCOW_NEW_USERS")
PROTECT_CONTENT = CONFIG.get("PROTECT_CONTENT")
PUBLIC_FILE_STORE = CONFIG.get("PUBLIC_FILE_STORE")
KEEP_ORIGINAL_CAPTION = CONFIG.get("KEEP_ORIGINAL_CAPTION")
POWERED_BY = CONFIG.get("POWERED_BY")
SUPPORT_GROUP = CONFIG.get("SUPPORT_GROUP")
SUPPORT_GROUP_USERNAME = CONFIG.get("SUPPORT_GROUP_USERNAME")
MAIN_CHANNEL = CONFIG.get("MAIN_CHANNEL")
# START_TEXT is now defined below, after DISABLE_PREMIUM_FOR_USERS is loaded

PREMIUM_DURATION_DAYS = CONFIG.get("PREMIUM_DURATION_DAYS", PREMIUM_DURATION_DAYS)
NON_PREMIUM_DAILY_LIMIT = CONFIG.get("NON_PREMIUM_DAILY_LIMIT", NON_PREMIUM_DAILY_LIMIT)
MESSAGE_DELETE_SECONDS = CONFIG.get("MESSAGE_DELETE_SECONDS", MESSAGE_DELETE_SECONDS)
DISABLE_PREMIUM_FOR_USERS = CONFIG.get("DISABLE_PREMIUM_FOR_USERS", DISABLE_PREMIUM_FOR_USERS)

# Define START_TEXT based on whether premium is disabled
if DISABLE_PREMIUM_FOR_USERS:
    _default_start_text = "Hello! Welcome to our bot. Enjoy unlimited access to all features."
else:
    _default_start_text = f"HELLO!! This bot offers a premium plan valid for 30 days with unlimited file retrievals. Free users can retrieve up to {NON_PREMIUM_DAILY_LIMIT} files per day. Check out /plans for more details."

START_TEXT = environ.get("START_TEXT", _default_start_text)
# If START_TEXT was loaded from DB (via CONFIG), and it's not the placeholder from env, use it.
# Otherwise, use the dynamically generated one.
# This allows user to override with their own START_TEXT from .env even if premium is disabled.
# However, the default behavior if START_TEXT is not in .env is to use the conditional one.
# A bit complex: if user explicitly sets START_TEXT in .env, that takes precedence.
# If they don't, then the conditional logic (_default_start_text) applies.
# CONFIG.get("START_TEXT") might be None if it was never set in DB or .env initially.
# Let's simplify: The environment variable always takes precedence if set.
# If not set in env, then the conditional default is used.
# And this whole block (environ.get or conditional) is what gets stored in DB if nothing was there.

# Re-evaluation for START_TEXT based on CONFIG and then conditional default:
# 1. Try to get START_TEXT from environment (highest priority for fresh start)
# 2. If not in env, try to get from CONFIG (loaded from DB)
# 3. If not in CONFIG (e.g. first run, or not saved before), then use the conditional default.

# Let's refine the logic for START_TEXT initialization:
# The module-level START_TEXT will be what's used by the bot.
# It should reflect the env var if present, else the DB value if present, else the conditional default.

# Initial value from environment (could be None)
_env_start_text = environ.get('START_TEXT')

if _env_start_text: # User explicitly set it in .env
    START_TEXT = _env_start_text
elif CONFIG.get("START_TEXT"): # It was in the database
    START_TEXT = CONFIG.get("START_TEXT")
else: # Not in .env and not in DB, so use conditional default
    if DISABLE_PREMIUM_FOR_USERS:
        START_TEXT = "Hello! Welcome to our bot. Enjoy unlimited access to all features."
    else:
        START_TEXT = f"HELLO!! This bot offers a premium plan valid for 30 days with unlimited file retrievals. Free users can retrieve up to {NON_PREMIUM_DAILY_LIMIT} files per day. Check out /plans for more details."

# Ensure START_TEXT is part of the config to be saved back if it was determined by conditional logic
if "START_TEXT" not in CONFIG or CONFIG["START_TEXT"] is None: # If it wasn't in DB or was None
    CONFIG["START_TEXT"] = START_TEXT # This ensures the dynamically chosen START_TEXT is saved if it was default

# The above logic for START_TEXT needs to be part of the `initialize_configuration` or happen just after it.
# The current placement is fine, as CONFIG is already populated.
# The key is that `START_TEXT` as a global variable in `info.py` is correctly set.

# Let's simplify the START_TEXT definition logic to be clearer and ensure it's correctly
# reflected in the CONFIG for saving if it was derived.

# Define default based on premium status (used if no specific START_TEXT is provided by user)
if DISABLE_PREMIUM_FOR_USERS:
    DEFAULT_CONDITIONAL_START_TEXT = "Hello! Welcome to our bot. Enjoy unlimited access to all features."
else:
    DEFAULT_CONDITIONAL_START_TEXT = f"HELLO!! This bot offers a premium plan valid for 30 days with unlimited file retrievals. Free users can retrieve up to {NON_PREMIUM_DAILY_LIMIT} files per day. Check out /plans for more details."

# 1. Get from environment (highest priority)
# 2. Else, get from DB (via CONFIG)
# 3. Else, use the conditional default
START_TEXT = environ.get('START_TEXT') or CONFIG.get('START_TEXT') or DEFAULT_CONDITIONAL_START_TEXT

# If START_TEXT was derived from DEFAULT_CONDITIONAL_START_TEXT (i.e., not set in env or DB),
# make sure this derived value is updated in the CONFIG object so it can be saved to DB if it's new.
if not environ.get('START_TEXT') and not CONFIG.get('START_TEXT'):
    CONFIG['START_TEXT'] = START_TEXT


# The global START_TEXT variable is now correctly set.
# The `get_config_data_from_env` function also needs to be aware of this.
# When `get_config_data_from_env` is called, `DISABLE_PREMIUM_FOR_USERS` (from env) is known.
# So, `START_TEXT` in `get_config_data_from_env` should also reflect this logic.

# This is getting complicated because of the order of operations and desire for env > db > default.
# Let's make sure `CONFIG` accurately reflects the `START_TEXT` to be used and potentially saved.

# Final simplified approach for setting the global START_TEXT:
# The module-level variables (like DISABLE_PREMIUM_FOR_USERS, NON_PREMIUM_DAILY_LIMIT)
# are already set from CONFIG (which loaded from DB or env).
# So we can use them directly to define START_TEXT.

if DISABLE_PREMIUM_FOR_USERS:
    _default_start_text_val = "Hello! Welcome to our bot. Enjoy unlimited access to all features."
else:
    _default_start_text_val = f"HELLO!! This bot offers a premium plan valid for 30 days with unlimited file retrievals. Free users can retrieve up to {NON_PREMIUM_DAILY_LIMIT} files per day. Check out /plans for more details."

# Use the START_TEXT from environment if provided, otherwise use the one from CONFIG (which might be from DB),
# otherwise use the just-defined default conditional text.
# This order ensures: ENV > DB > Conditional Default for the *runtime value* of START_TEXT.
START_TEXT = environ.get('START_TEXT') or CONFIG.get('START_TEXT', _default_start_text_val)

# Now, we also need to ensure that `get_config_data_from_env` provides a *default* START_TEXT
# that is conditional, in case it's the first time and nothing is in .env or DB.
# And that `CONFIG["START_TEXT"]` (when initially populated from env or later when saving) is correct.

# Let's adjust `get_config_data_from_env` first, then ensure the module level var is set correctly.
# This is because `initialize_configuration` calls `get_config_data_from_env` if DB is empty.

# The change in `get_config_data_from_env` to include `START_TEXT` conditionally was removed.
# It should be: `environ.get("START_TEXT", _conditional_default_based_on_env_DISABLE_PREMIUM)`

# The current global `START_TEXT` is derived from `environ.get("START_TEXT")` (initial value at top of file)
# or (if that was None) from `CONFIG.get("START_TEXT")`.
# This is not quite right.

# Let's try again for clarity for the global `START_TEXT` variable:
# By this point, DISABLE_PREMIUM_FOR_USERS and NON_PREMIUM_DAILY_LIMIT global vars are set from CONFIG.

if DISABLE_PREMIUM_FOR_USERS:
    _default_start_text_runtime = "Hello! Welcome to our bot. Enjoy unlimited access to all features."
else:
    _default_start_text_runtime = f"HELLO!! This bot offers a premium plan valid for 30 days with unlimited file retrievals. Free users can retrieve up to {NON_PREMIUM_DAILY_LIMIT} files per day. Check out /plans for more details."

# Priority:
# 1. Value from environment variable `START_TEXT` (if set by user for this run)
# 2. Value from database `CONFIG['START_TEXT']` (if it exists from previous runs)
# 3. Conditionally determined default `_default_start_text_runtime`
_env_start_text_for_runtime = environ.get('START_TEXT') # This is the original env value for START_TEXT
_db_start_text_for_runtime = CONFIG.get('START_TEXT') # This is what was loaded from DB for START_TEXT

if _env_start_text_for_runtime is not None:
    START_TEXT = _env_start_text_for_runtime
elif _db_start_text_for_runtime is not None:
    START_TEXT = _db_start_text_for_runtime
else:
    START_TEXT = _default_start_text_runtime

# And ensure this resolved START_TEXT is what `CONFIG` holds if it needs to be saved.
# This means if `START_TEXT` was resolved to `_default_start_text_runtime`,
# `CONFIG['START_TEXT']` should be updated to this value if it wasn't already set from env/db.
# This is handled by `save_config_to_db` which saves the entire `CONFIG` dict.
# We need to ensure `CONFIG['START_TEXT']` is correctly populated before saving.

# If CONFIG was loaded from DB, CONFIG['START_TEXT'] is already what it should be (or None).
# If CONFIG was from `get_config_data_from_env`, then `START_TEXT` key in that dict needs to be correct.

# This requires fixing `get_config_data_from_env` for `START_TEXT`
# and then ensuring the global `START_TEXT` is correctly set *after* `CONFIG` is finalized.

# The most straightforward way:
# 1. All other config vars are loaded (including DISABLE_PREMIUM_FOR_USERS).
# 2. Then, determine START_TEXT based on them and env/db priority.
# 3. Update CONFIG['START_TEXT'] with this final value so it's saved correctly.

# Current global vars are set. Now set START_TEXT for runtime & update CONFIG for saving.
if DISABLE_PREMIUM_FOR_USERS:
    final_default_start_text = "Hello! Welcome to our bot. Enjoy unlimited access to all features."
else:
    final_default_start_text = f"HELLO!! This bot offers a premium plan valid for 30 days with unlimited file retrievals. Free users can retrieve up to {NON_PREMIUM_DAILY_LIMIT} files per day. Check out /plans for more details."

# Determine runtime START_TEXT
runtime_start_text = environ.get('START_TEXT') # Env var for START_TEXT specifically
if runtime_start_text is None:
    runtime_start_text = CONFIG.get('START_TEXT') # DB value for START_TEXT
    if runtime_start_text is None:
        runtime_start_text = final_default_start_text # Fallback to conditional

START_TEXT = runtime_start_text
CONFIG['START_TEXT'] = runtime_start_text # Ensure CONFIG has the final version to be saved

# Define the global START_TEXT variable based on priority:
# 1. Environment variable `START_TEXT` (user-defined override)
# 2. Value from `CONFIG['START_TEXT']` (database persisted value)
# 3. Conditional default based on `DISABLE_PREMIUM_FOR_USERS`

# First, determine the conditional default:
if DISABLE_PREMIUM_FOR_USERS: # This global var is already set from CONFIG
    # Takes two arguments, but the second one (daily limit) is ignored in the text.
    _conditional_default_start_text = "Hello {0}! Welcome to our bot. All features are fully available to you."
else:
    # Takes two arguments: {0} for user mention, {1} for the daily limit.
    _conditional_default_start_text = f"HELLO {{0}}!! This bot offers a premium plan valid for 30 days with unlimited file retrievals. Free users can retrieve up to {{1}} files per day. Check out /plans for more details."

# Now, apply priority:
_env_value = environ.get('START_TEXT') # Raw value from .env for START_TEXT
_db_value = CONFIG.get('START_TEXT')   # Value from DB for START_TEXT

if _env_value is not None:
    START_TEXT = _env_value
elif _db_value is not None:
    START_TEXT = _db_value
else:
    START_TEXT = _conditional_default_start_text

# Ensure that the CONFIG dictionary (which might be saved to DB)
# reflects the final START_TEXT value that was determined.
CONFIG['START_TEXT'] = START_TEXT
