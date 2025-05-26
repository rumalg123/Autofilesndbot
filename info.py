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
START_TEXT = environ.get("START_TEXT", f"HELLO!! This bot offers a premium plan valid for 30 days with unlimited file retrievals. Free users can retrieve up to {NON_PREMIUM_DAILY_LIMIT} files per day. Check out /plans for more details.")

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
        "START_TEXT": START_TEXT,
        "PREMIUM_DURATION_DAYS": PREMIUM_DURATION_DAYS,
        "NON_PREMIUM_DAILY_LIMIT": NON_PREMIUM_DAILY_LIMIT,
        "MESSAGE_DELETE_SECONDS": MESSAGE_DELETE_SECONDS,
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
START_TEXT = CONFIG.get("START_TEXT")
PREMIUM_DURATION_DAYS = CONFIG.get("PREMIUM_DURATION_DAYS", PREMIUM_DURATION_DAYS)
NON_PREMIUM_DAILY_LIMIT = CONFIG.get("NON_PREMIUM_DAILY_LIMIT", NON_PREMIUM_DAILY_LIMIT)
MESSAGE_DELETE_SECONDS = CONFIG.get("MESSAGE_DELETE_SECONDS", MESSAGE_DELETE_SECONDS)

