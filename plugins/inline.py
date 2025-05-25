import logging

from pyrogram import Client, emoji, enums
from pyrogram.errors.exceptions.bad_request_400 import QueryIdInvalid
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultCachedDocument, InlineQuery
from datetime import datetime, date, timedelta, time as dt_time # Added time for datetime.min.time()
from database.connections_mdb import active_connection
from database.ia_filterdb import get_search_results
from database.users_chats_db import db 
import info
from utils import is_subscribed, get_size, temp

logger = logging.getLogger(__name__)
cache_time = 0 if info.AUTH_USERS or info.AUTH_CHANNEL else info.CACHE_TIME

async def inline_users(query: InlineQuery):
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
                           switch_pm_text='Banned User', 
                           switch_pm_parameter="banned")
        return

    if info.AUTH_CHANNEL and not await is_subscribed(bot, query):
        await query.answer(results=[],
                           cache_time=0,
                           switch_pm_text='𝖸𝗈𝗎 𝖧𝖺𝗏𝖾 𝖳𝗈 𝖲𝗎𝖻𝗌𝖼𝗋𝗂𝖻𝖾 𝖬𝗒 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 𝖳𝗈 𝖴𝗌𝖾 𝖬𝖾 :)',
                           switch_pm_parameter="subscribe")
        return

    user_id = query.from_user.id
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, query.from_user.first_name or "Inline User")
    
    user_data = await db.get_user_data(user_id)
    owner_id = info.ADMINS[0] if info.ADMINS else None
    can_proceed_with_query = False 
    
    now_utc = datetime.utcnow()

    if owner_id and user_id == owner_id:
        can_proceed_with_query = True
    
    elif user_data and user_data.get('is_premium'):
        activation_date_val = user_data.get('premium_activation_date')
        if activation_date_val:
            activation_date = None
            if isinstance(activation_date_val, str):
                try:
                    activation_date = datetime.fromisoformat(activation_date_val)
                except ValueError:  
                    try: 
                        activation_date = datetime.fromtimestamp(float(activation_date_val))
                    except ValueError:
                         logger.error(f"Could not parse premium_activation_date string '{activation_date_val}' for user {user_id}")
            elif isinstance(activation_date_val, (int, float)): 
                activation_date = datetime.fromtimestamp(activation_date_val) 
            elif isinstance(activation_date_val, datetime):  
                 activation_date = activation_date_val

            if isinstance(activation_date, datetime): 
                expiry_date = activation_date + timedelta(days=info.PREMIUM_DURATION_DAYS)
                if now_utc > expiry_date: 
                    await db.update_premium_status(user_id, False)
                    try:
                        await bot.send_message(user_id, "Your premium subscription has expired. You are now on the free plan.")
                    except Exception as e:
                        logger.warning(f"Could not send premium expiry message to {user_id}: {e}")
                else:
                    can_proceed_with_query = True 
            else: 
                logger.error(f"User {user_id} has is_premium=True but invalid or unparsable premium_activation_date: {activation_date_val}")
        else: 
            logger.warning(f"User {user_id} has is_premium=True but no premium_activation_date. Treating as non-premium for this query.")
            
    if not can_proceed_with_query:
        current_user_data = await db.get_user_data(user_id) 
        
        daily_retrieval_count = 0 
        last_retrieval_date_obj = None

        if current_user_data:
            daily_retrieval_count = current_user_data.get('daily_retrieval_count', 0)
            last_retrieval_date_val = current_user_data.get('last_retrieval_date')

            if last_retrieval_date_val:
                if isinstance(last_retrieval_date_val, datetime): 
                    last_retrieval_date_obj = last_retrieval_date_val.date()
                elif isinstance(last_retrieval_date_val, date): 
                    last_retrieval_date_obj = last_retrieval_date_val
                elif isinstance(last_retrieval_date_val, str): 
                    try:
                        last_retrieval_date_obj = date.fromisoformat(last_retrieval_date_val.split('T')[0])
                    except ValueError:
                         try:
                             last_retrieval_date_obj = date.fromisoformat(last_retrieval_date_val)
                         except ValueError:
                             logger.error(f"Could not parse last_retrieval_date string '{last_retrieval_date_val}' for user {user_id}")
                else:
                    logger.error(f"Unknown format for last_retrieval_date: {last_retrieval_date_val} for user {user_id}")
        
        effective_count_for_today = daily_retrieval_count if last_retrieval_date_obj == now_utc.date() else 0
        
        if effective_count_for_today >= info.NON_PREMIUM_DAILY_LIMIT:
            await query.answer(results=[], 
                               cache_time=0, 
                               switch_pm_text=f"Daily file view limit ({info.NON_PREMIUM_DAILY_LIMIT}) reached. Upgrade for more.", 
                               switch_pm_parameter="premium_limit_inline")
            return 
        
    results = []
    if '|' in query.query:
        string, file_type = query.query.split('|', maxsplit=1)
        string = string.strip()
        file_type = file_type.strip().lower()
    else:
        string = query.query.strip()
        file_type = None

    search_chat_id = chat_id if chat_id else query.from_user.id 

    offset = int(query.offset or 0)
    reply_markup = get_reply_markup(query=string) 
    
    files, next_offset, total = await get_search_results(
                                                  search_chat_id, 
                                                  string,
                                                  file_type=file_type,
                                                  max_results=10, 
                                                  offset=offset)

    for file in files:
        title=file.file_name
        size=get_size(file.file_size)
        f_caption=file.caption
        if info.KEEP_ORIGINAL_CAPTION:
            pass
        elif info.CUSTOM_FILE_CAPTION:
            try:
                f_caption=info.CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
        if f_caption is None: 
            f_caption = f"<code>{title}</code>" if title else ""
            
        results.append(
            InlineQueryResultCachedDocument(
                title=file.file_name,
                document_file_id=file.file_id,
                caption=f_caption,
                parse_mode=enums.ParseMode.HTML, 
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
        switch_pm_text = f'{emoji.CROSS_MARK} 𝖭𝗈 𝖱𝖾𝗌𝗎𝗅𝗍𝗌 𝖥𝗈𝗎𝗇𝖽'
        if string:
            switch_pm_text += f' for "{string}"'

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




[end of plugins/inline.py]
