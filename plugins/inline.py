import logging

from pyrogram import Client, emoji, enums
from pyrogram.errors.exceptions.bad_request_400 import QueryIdInvalid
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultCachedDocument, InlineQuery
from datetime import datetime, date, timedelta
from database.connections_mdb import active_connection
from database.ia_filterdb import get_search_results
from database.users_chats_db import db # Added db import
import info
from utils import is_subscribed, get_size, temp

logger = logging.getLogger(__name__)
cache_time = 0 if info.AUTH_USERS or info.AUTH_CHANNEL else info.CACHE_TIME

async def inline_users(query: InlineQuery):
    # if AUTH_USERS:
    #     if query.from_user and query.from_user.id in AUTH_USERS:
    #         return True
    #     else:
    #         return False
    if query.from_user and query.from_user.id not in temp.BANNED_USERS:
        return True
    return False

@Client.on_inline_query()
async def answer(bot, query):
    """𝖲𝗁𝗈𝗐 𝖲𝖾𝖺𝗋𝖼𝗁 𝖱𝖾𝗌𝗎𝗅𝗍𝗌 𝖥𝗈𝗋 𝖦𝗂𝗏𝖾𝗇 𝖨𝗇𝗅𝗂𝗇𝖾 𝖰𝗎𝖾𝗋𝗒"""
    chat_id = await active_connection(str(query.from_user.id))
    
    if not await inline_users(query):
        await query.answer(results=[],
                           cache_time=0,
                           switch_pm_text='Nothing Yet',
                           switch_pm_parameter="hehe")
        return

    if info.AUTH_CHANNEL and not await is_subscribed(bot, query):
        await query.answer(results=[],
                           cache_time=0,
                           switch_pm_text='𝖸𝗈𝗎 𝖧𝖺𝗏𝖾 𝖳𝗈 𝖲𝗎𝖻𝗌𝖼𝗋𝗂𝖻𝖾 𝖬𝗒 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 𝖳𝗈 𝖴𝗌𝖾 𝖬𝖾 :)',
                           switch_pm_parameter="subscribe")
        return

    user_id = query.from_user.id
    if not await db.is_user_exist(user_id):
        # Add user to DB if they don't exist, so get_user_data doesn't return None.
        # This can happen if a user uses inline mode before ever starting the bot.
        # Their first interaction would be here, so they need an entry.
        await db.add_user(user_id, query.from_user.first_name or "Inline User")
        # For a brand new user, user_data will be effectively empty for premium checks,
        # leading them to the non-premium path, which is correct.

    user_data = await db.get_user_data(user_id)
    owner_id = info.ADMINS[0] if info.ADMINS else None

    can_proceed_with_query = False # Flag to determine if user can see search results

    # 1. Owner Check
    if owner_id and user_id == owner_id:
        can_proceed_with_query = True
    
    # 2. Active Premium User Check
    elif user_data and user_data.get('is_premium'):
        activation_date_str = user_data.get('premium_activation_date')
        if activation_date_str:
            activation_date = None
            if isinstance(activation_date_str, str):
                try:
                    activation_date = datetime.fromisoformat(activation_date_str)
                except ValueError: 
                    try: # Fallback for older timestamp format if any
                        activation_date = datetime.fromtimestamp(float(activation_date_str))
                    except ValueError:
                         logger.error(f"Could not parse premium_activation_date string '{activation_date_str}' for user {user_id}")
            elif isinstance(activation_date_str, (int, float)): # Timestamp
                activation_date = datetime.fromtimestamp(activation_date_str)
            elif isinstance(activation_date_str, datetime): # Already a datetime object
                 activation_date = activation_date_str


            if isinstance(activation_date, datetime): 
                expiry_date = activation_date + timedelta(days=info.PREMIUM_DURATION_DAYS)
                if datetime.now() > expiry_date:
                    # Premium has expired
                    await db.update_premium_status(user_id, False)
                    try:
                        await bot.send_message(user_id, "Your premium subscription has expired. You are now on the free plan.")
                    except Exception as e:
                        logger.warning(f"Could not send premium expiry message to {user_id}: {e}")
                    # User is now non-premium; subsequent checks will apply non-premium logic.
                    # `can_proceed_with_query` remains False, will fall through to non-premium check.
                else:
                    can_proceed_with_query = True # Active premium user
            else: 
                logger.error(f"User {user_id} has is_premium=True but invalid or unparsable premium_activation_date: {activation_date_str}")
                # Treat as non-premium due to data issue; `can_proceed_with_query` remains False.
        else: 
            logger.warning(f"User {user_id} has is_premium=True but no premium_activation_date. Treating as non-premium for this query.")
            # `can_proceed_with_query` remains False.
            
    # 3. Non-Premium User Check (or expired premium, or premium with data issues)
    if not can_proceed_with_query:
        # Fetch user_data again in case it was modified (e.g., premium expired and status updated)
        current_user_data = await db.get_user_data(user_id) 
        
        daily_retrieval_count = 0 # Default if no data
        last_retrieval_date_obj = None

        if current_user_data:
            daily_retrieval_count = current_user_data.get('daily_retrieval_count', 0)
            last_retrieval_date_str = current_user_data.get('last_retrieval_date')

            if last_retrieval_date_str:
                if isinstance(last_retrieval_date_str, datetime): 
                    last_retrieval_date_obj = last_retrieval_date_str.date()
                elif isinstance(last_retrieval_date_str, date): 
                    last_retrieval_date_obj = last_retrieval_date_str
                elif isinstance(last_retrieval_date_str, str): # Stored as ISO string
                    try:
                        # Ensure to parse only the date part if it's a full ISO datetime string
                        last_retrieval_date_obj = date.fromisoformat(last_retrieval_date_str.split('T')[0])
                    except ValueError:
                         logger.error(f"Could not parse last_retrieval_date string '{last_retrieval_date_str}' for user {user_id}")
                else:
                    logger.error(f"Unknown format for last_retrieval_date: {last_retrieval_date_str} for user {user_id}")
        
        # If today's date matches the last retrieval, use the stored count. Otherwise, it's effectively 0 for today.
        effective_count_for_today = daily_retrieval_count if last_retrieval_date_obj == date.today() else 0
        
        # Check if this non-premium user has reached their daily view limit for inline queries.
        # Note: This count is for *viewing* results. Actual file retrieval count is handled in commands.py.
        if effective_count_for_today >= info.NON_PREMIUM_DAILY_LIMIT:
            await query.answer(results=[], 
                               cache_time=0, 
                               switch_pm_text=f"Daily file view limit ({info.NON_PREMIUM_DAILY_LIMIT}) reached. Upgrade for more.\nUse /plans command to view premium plans for unlimited access.", 
                               switch_pm_parameter="premium_limit_inline")
            return # User cannot proceed with this query
        
        # If under limit, they can proceed to see results for this query.
        # `can_proceed_with_query` remains False here, but we don't return, allowing search.
        # The actual increment of retrieval count happens when a file is *selected* from inline results (in commands.py).
        # This block is just to prevent showing results if already over limit.

    results = []
    if '|' in query.query:
        string, file_type = query.query.split('|', maxsplit=1)
        string = string.strip()
        file_type = file_type.strip().lower()
    else:
        string = query.query.strip()
        file_type = None

    offset = int(query.offset or 0)
    reply_markup = get_reply_markup(query=string)
    files, next_offset, total = await get_search_results(
                                                  chat_id,
                                                  string,
                                                  file_type=file_type,
                                                  max_results=10,
                                                  offset=offset)

    for file in files:
        title=file.file_name
        size=get_size(file.file_size)
        f_caption=file.caption
        if info.KEEP_ORIGINAL_CAPTION:
            try:
                f_caption = file.caption
            except:
                f_caption = f"<code>{title}</code>"
        elif info.CUSTOM_FILE_CAPTION:
            try:
                f_caption=info.CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
                f_caption=f_caption
        if f_caption is None:
            f_caption = f"{file.file_name}"
        results.append(
            InlineQueryResultCachedDocument(
                title=file.file_name,
                document_file_id=file.file_id,
                caption=f_caption,
                parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION else enums.ParseMode.DEFAULT,
                description=f'Size: {get_size(file.file_size)}\nType: {file.file_type}',
                reply_markup=reply_markup))

    if results:
        switch_pm_text = f"{emoji.FILE_FOLDER} Here are the results "
        if string:
            switch_pm_text += f" for {string}"
        try:
            await query.answer(results=results,
                           is_personal = True,
                           cache_time=cache_time,
                           switch_pm_text=switch_pm_text,
                           switch_pm_parameter="start",
                           next_offset=str(next_offset))
        except QueryIdInvalid:
            pass
        except Exception as e:
            logging.exception(str(e))
    else:
        if string: # string is the user's query
            switch_pm_text = f"No results found for '{string}'. Send a different keyword."
        else:
            switch_pm_text = "No results found. Send a different keyword."

        await query.answer(results=[],
                           is_personal = True,
                           cache_time=cache_time,
                           switch_pm_text=switch_pm_text,
                           switch_pm_parameter="okay")


def get_reply_markup(query):
    buttons = [
        [
            InlineKeyboardButton('🔎 𝖲𝖾𝖺𝗋𝖼𝗁 𝖠𝗀𝖺𝗂𝗇', switch_inline_query_current_chat=query),
            InlineKeyboardButton('⚡𝖴𝗉𝖽𝖺𝗍𝖾𝗌 ⚡', url=info.MAIN_CHANNEL)
        ]
        ]
    return InlineKeyboardMarkup(buttons)



