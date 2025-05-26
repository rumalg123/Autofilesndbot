import asyncio
import logging
import os
import re
from typing import List
from typing import Union

import requests
import aiohttp # Added import
from bs4 import BeautifulSoup
from imdb import Cinemagoer
from pyrogram import enums
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from database.users_chats_db import db
import info

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BTN_URL_REGEX = re.compile(
    r"(\[([^\[]+?)]\((buttonurl|buttonalert):/{0,2}(.+?)(:same)?\))"
)

imdb = Cinemagoer() 

BANNED = {}
SMART_OPEN = '“'
SMART_CLOSE = '”'
START_CHAR = ('\'', '"', SMART_OPEN)

# temp db for banned 
class temp(object):
    BANNED_USERS = []
    BANNED_CHATS = []
    ME = None
    CURRENT=int(os.environ.get("SKIP", 2))
    CANCEL = False
    MELCOW = {}
    U_NAME = None
    B_NAME = None
    SETTINGS = {}
    FILES_IDS = {}

async def is_subscribed(bot, query):
    try:
        user = await bot.get_chat_member(info.AUTH_CHANNEL, query.from_user.id)
    except UserNotParticipant:
        pass
    except Exception as e:
        logger.exception(e)
    else:
        if user.status != enums.ChatMemberStatus.BANNED:
            return True

    return False

async def get_poster(query, bulk=False, id=False, file=None):
    if not id:
        query = (query.strip()).lower()
        title = query
        year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
        if year:
            year = list_to_str(year[:1])
            title = (query.replace(year, "")).strip()
        elif file is not None:
            year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1]) 
        else:
            year = None
        movieid = imdb.search_movie(title.lower(), results=10)
        if not movieid:
            return None
        if year:
            filtered=list(filter(lambda k: str(k.get('year')) == str(year), movieid))
            if not filtered:
                filtered = movieid
        else:
            filtered = movieid
        movieid=list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
        if not movieid:
            movieid = filtered
        if bulk:
            return movieid
        movieid = movieid[0].movieID
    else:
        movieid = query
    movie = imdb.get_movie(movieid)
    if movie.get("original air date"):
        date = movie["original air date"]
    elif movie.get("year"):
        date = movie.get("year")
    else:
        date = "N/A"
    plot = ""
    if not info.LONG_IMDB_DESCRIPTION:
        plot = movie.get('plot')
        if plot and len(plot) > 0:
            plot = plot[0]
    else:
        plot = movie.get('plot outline')
    if plot and len(plot) > 800:
        plot = plot[0:800] + "..."

    return {
        'title': movie.get('title'),
        'votes': movie.get('votes'),
        "aka": list_to_str(movie.get("akas")),
        "seasons": movie.get("number of seasons"),
        "box_office": movie.get('box office'),
        'localized_title': movie.get('localized title'),
        'kind': movie.get("kind"),
        "imdb_id": f"tt{movie.get('imdbID')}",
        "cast": list_to_str(movie.get("cast")),
        "runtime": list_to_str(movie.get("runtimes")),
        "countries": list_to_str(movie.get("countries")),
        "certificates": list_to_str(movie.get("certificates")),
        "languages": list_to_str(movie.get("languages")),
        "director": list_to_str(movie.get("director")),
        "writer":list_to_str(movie.get("writer")),
        "producer":list_to_str(movie.get("producer")),
        "composer":list_to_str(movie.get("composer")) ,
        "cinematographer":list_to_str(movie.get("cinematographer")),
        "music_team": list_to_str(movie.get("music department")),
        "distributors": list_to_str(movie.get("distributors")),
        'release_date': date,
        'year': movie.get('year'),
        'genres': list_to_str(movie.get("genres")),
        'poster': movie.get('full-size cover url'),
        'plot': plot,
        'rating': str(movie.get("rating")),
        'url':f'https://www.imdb.com/title/tt{movieid}'
    }

async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.x) # type: ignore[attr-defined]
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id}-Removed from Database, since deleted account.")
        return False, "Deleted"
    except UserIsBlocked:
        logging.info(f"{user_id} -Blocked the bot.")
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - PeerIdInvalid")
        return False, "Error"
    except Exception as e:
        return False, "Error"

async def broadcast_messages_group(chat_id, message):
    try:
        kd = await message.copy(chat_id=chat_id)
        try:
            await kd.pin()
        except:
            pass
        return True, "Succes"
    except FloodWait as e:
        await asyncio.sleep(e.x) # type: ignore[attr-defined]
        return await broadcast_messages_group(chat_id, message)
    except Exception as e:
        return False, "Error"

async def search_gagala(text): # Changed to async def
    usr_agent = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/61.0.3163.100 Safari/537.36'
        }
    text = text.replace(" ", '+')
    url = f'https://www.google.com/search?q={text}'
    async with aiohttp.ClientSession() as session: # Use aiohttp.ClientSession
        async with session.get(url, headers=usr_agent) as response: # Use async with session.get
            response.raise_for_status() # Check for HTTP errors
            html_content = await response.text() # await response.text()
    soup = BeautifulSoup(html_content, 'html.parser') # html_content instead of response.text
    titles = soup.find_all( 'h3' )
    return [title.getText() for title in titles]


async def get_settings(group_id):
    settings = temp.SETTINGS.get(group_id)
    if not settings:
        settings = await db.get_settings(group_id)
        temp.SETTINGS[group_id] = settings
    return settings
    
async def save_group_settings(group_id, key, value):
    current = await get_settings(group_id)
    current[key] = value
    temp.SETTINGS[group_id] = current
    await db.update_settings(group_id, current)
    
def get_size(size):
    """Get size in readable format"""

    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def split_list(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]  

def get_file_id(msg: Message):
    if msg.media:
        for message_type in (
            "photo",
            "animation",
            "audio",
            "document",
            "video",
            "video_note",
            "voice",
            "sticker"
        ):
            obj = getattr(msg, message_type)
            if obj:
                setattr(obj, "message_type", message_type)
                return obj

def extract_user(message: Message) -> Union[int, str]:
    """extracts the user from a message"""
    user_id = None
    user_first_name = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_first_name = message.reply_to_message.from_user.first_name

    elif len(message.command) > 1:
        if (
            len(message.entities) > 1 and
            message.entities[1].type == enums.MessageEntityType.TEXT_MENTION
        ):
           
            required_entity = message.entities[1]
            user_id = required_entity.user.id
            user_first_name = required_entity.user.first_name
        else:
            user_id = message.command[1]
            # don't want to make a request -_-
            user_first_name = user_id
        try:
            user_id = int(user_id)
        except ValueError:
            pass
    else:
        user_id = message.from_user.id
        user_first_name = message.from_user.first_name
    return (user_id, user_first_name)

def list_to_str(k):
    if not k:
        return "N/A"
    elif len(k) == 1:
        return str(k[0])
    elif info.MAX_LIST_ELM:
        k = k[:int(info.MAX_LIST_ELM)]
        return ' '.join(f'{elem}, ' for elem in k)
    else:
        return ' '.join(f'{elem}, ' for elem in k)

def last_online(from_user):
    time = ""
    if from_user.is_bot:
        time += "🤖 Bot :("
    elif from_user.status == enums.UserStatus.RECENTLY:
        time += "Recently"
    elif from_user.status == enums.UserStatus.LAST_WEEK:
        time += "Within the last week"
    elif from_user.status == enums.UserStatus.LAST_MONTH:
        time += "Within the last month"
    elif from_user.status == enums.UserStatus.LONG_AGO:
        time += "A long time ago :("
    elif from_user.status == enums.UserStatus.ONLINE:
        time += "Currently Online"
    elif from_user.status == enums.UserStatus.OFFLINE:
        time += from_user.last_online_date.strftime("%a, %d %b %Y, %H:%M:%S")
    return time


def split_quotes(text: str) -> List:
    if not any(text.startswith(char) for char in START_CHAR):
        return text.split(None, 1)
    counter = 1  # ignore first char -> is some kind of quote
    while counter < len(text):
        if text[counter] == "\\":
            counter += 1
        elif text[counter] == text[0] or (text[0] == SMART_OPEN and text[counter] == SMART_CLOSE):
            break
        counter += 1
    else:
        return text.split(None, 1)

    # 1 to avoid starting quote, and counter is exclusive so avoids ending
    key = remove_escapes(text[1:counter].strip())
    # index will be in range, or `else` would have been executed and returned
    rest = text[counter + 1:].strip()
    if not key:
        key = text[0] + text[0]
    return list(filter(None, [key, rest]))

def gfilterparser(text, keyword):
    if "buttonalert" in text:
        text = (text.replace("\n", "\\n").replace("\t", "\\t"))
    buttons = []
    note_data = ""
    prev = 0
    i = 0
    alerts = []
    for match in BTN_URL_REGEX.finditer(text):
        # Check if btnurl is escaped
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        # if even, not escaped -> create button
        if n_escapes % 2 == 0:
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
            if match.group(3) == "buttonalert":
                # create a thruple with button label, url, and newline status
                if bool(match.group(5)) and buttons:
                    buttons[-1].append(InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"gfilteralert:{i}:{keyword}"
                    ))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"gfilteralert:{i}:{keyword}"
                    )])
                i += 1
                alerts.append(match.group(4))
            elif bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                ))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                )])

        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    else:
        note_data += text[prev:]

    try:
        return note_data, buttons, alerts
    except:
        return note_data, buttons, None

def parser(text, keyword):
    if "buttonalert" in text:
        text = (text.replace("\n", "\\n").replace("\t", "\\t"))
    buttons = []
    note_data = ""
    prev = 0
    i = 0
    alerts = []
    for match in BTN_URL_REGEX.finditer(text):
        # Check if btnurl is escaped
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        # if even, not escaped -> create button
        if n_escapes % 2 == 0:
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
            if match.group(3) == "buttonalert":
                # create a thruple with button label, url, and newline status
                if bool(match.group(5)) and buttons:
                    buttons[-1].append(InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}"
                    ))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}"
                    )])
                i += 1
                alerts.append(match.group(4))
            elif bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                ))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                )])

        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    else:
        note_data += text[prev:]

    try:
        return note_data, buttons, alerts
    except:
        return note_data, buttons, None

def remove_escapes(text: str) -> str:
    res = ""
    is_escaped = False
    for counter in range(len(text)):
        if is_escaped:
            res += text[counter]
            is_escaped = False
        elif text[counter] == "\\":
            is_escaped = True
        else:
            res += text[counter]
    return res


async def check_user_access(client, message, user_id, *, increment: bool = False): # client is available here
    """Checks user access, handles premium status, and daily limits."""
    # OWNER_ID, PREMIUM_DURATION_DAYS, NON_PREMIUM_DAILY_LIMIT are from info
    # db is from database.users_chats_db
    # datetime, date, timedelta from datetime
    # UserIsBlocked from pyrogram.errors (if client.send_message is used directly here)
    
    if info.ADMINS and user_id == info.ADMINS[0]: # Assuming OWNER_ID is the first admin
        return True, "Owner access: Unlimited"

    user_data = await db.get_user_data(user_id)

    if not user_data or not user_data.get('id'): # Check if user_data is minimal or user not fully added
        # This case indicates user might not exist or was added with placeholder by get_user_data/increment_retrieval_count
        # Let's try to add them more formally if message context is available
        user_first_name = "User"
        user_username = None
        if message and message.from_user:
            user_first_name = message.from_user.first_name if message.from_user.first_name else "User"
            user_username = message.from_user.username
        
        # Check again if user exists after attempting to get data, to avoid re-adding if get_user_data added a placeholder
        if not await db.is_user_exist(user_id):
             await db.add_user(user_id, user_first_name, user_username, name=user_first_name)
             logger.info(f"User {user_id} was not found or was partial, re-added/updated via check_user_access.")
        user_data = await db.get_user_data(user_id) # Reload user_data

    now_utc = datetime.utcnow()

    if user_data.get('is_premium'):
        expiration_date = user_data.get('premium_expiration_date')
        
        if expiration_date:
            if isinstance(expiration_date, str):
                try:
                    expiration_date = datetime.fromisoformat(expiration_date)
                except ValueError:
                    logger.error(f"Invalid premium_expiration_date string format for user {user_id}: {expiration_date}")
                    expiration_date = None # Treat as invalid
            
            if isinstance(expiration_date, datetime):
                if now_utc > expiration_date:
                    logger.info(f"Premium expired for user {user_id} on {expiration_date}. Downgrading.")
                    await db.update_premium_status(user_id, False) 
                    user_data['is_premium'] = False # Reflect change locally
                    try:
                        await client.send_message(
                            chat_id=user_id,
                            text="Your premium subscription has expired. You are now on the free plan."
                        )
                    except UserIsBlocked:
                        logger.warning(f"User {user_id} has blocked the bot. Could not send premium expiry PM.")
                    except Exception as e:
                        logger.error(f"Failed to send premium expiry PM to {user_id}: {e}")
                    # Fall through to non-premium checks for the current request
                else:
                    return True, "Premium access"  # Active premium
            else: # Not a datetime object after potential parsing
                logger.error(f"User {user_id} has is_premium=True but premium_expiration_date is not a valid datetime: {expiration_date}. Treating as non-premium.")
                # Fall through to non-premium checks
        else:  # is_premium is True but no premium_expiration_date
            logger.warning(f"User {user_id} is_premium=True but no premium_expiration_date. Treating as non-premium.")
            # Fall through to non-premium checks

    # Non-premium user logic (or expired/problematic premium)
    # Use last_retrieval_date and daily_retrieval_count from user_data
    raw_last = user_data.get("last_retrieval_date")
    raw_count = user_data.get("daily_retrieval_count", 0)

    last_day = None
    if isinstance(raw_last, datetime):
        last_day = raw_last.date()
    elif isinstance(raw_last, str):
        try:
            last_day = date.fromisoformat(raw_last.split("T")[0]) # Handle ISO format string
        except ValueError:
            try:
                last_day = date.fromisoformat(raw_last) # Handle date string
            except ValueError:
                logger.error(f"Invalid last_retrieval_date string format for user {user_id}: {raw_last}")
    elif isinstance(raw_last, date): # Handle if it's already a date object
        last_day = raw_last
    
    if last_day != now_utc.date(): # If last retrieval was not today, reset count
        raw_count = 0

    if raw_count >= info.NON_PREMIUM_DAILY_LIMIT:
        limit_msg = f"You have reached your daily limit of {info.NON_PREMIUM_DAILY_LIMIT} file retrievals. Send /plan to see available plans and upgrade to premium."
        # This part is tricky: if premium just expired *within this function call*, we need to convey that.
        # The user_data['is_premium'] = False would have been set above.
        if not user_data.get('is_premium') and user_data.get('premium_expiration_date') and isinstance(user_data.get('premium_expiration_date'), datetime) and now_utc > user_data.get('premium_expiration_date'):
             limit_msg = f"Your premium has expired and you have now reached your daily limit of {info.NON_PREMIUM_DAILY_LIMIT} file retrievals. Send /plan to see available plans and upgrade to premium."
        return False, limit_msg

    if increment:
        await db.increment_retrieval_count(user_id)
    return True, "Non-premium access"


def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

async def is_chat_admin_or_bot_admin(client, chat_id, user_id) -> bool:
    """Checks if a user is an admin/owner of a chat or a bot admin."""
    if user_id in info.ADMINS: # Bot Admin check
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
    except Exception as e:
        # Log the error but don't propagate; if user isn't found or other issue, they're not admin.
        logger.warning(f"Could not determine chat admin status for user {user_id} in chat {chat_id}: {e}")
    return False

def generate_file_caption(original_caption: str, title: str, size: str, is_batch: bool = False) -> str:
    """
    Generates a file caption based on system settings (KEEP_ORIGINAL_CAPTION, CUSTOM_FILE_CAPTION, BATCH_FILE_CAPTION).
    """
    f_caption = None
    
    # Ensure inputs are strings, provide defaults if None
    original_caption = original_caption or ""
    title = title or ""
    size = size or ""

    if info.KEEP_ORIGINAL_CAPTION:
        f_caption = original_caption if original_caption else title
    else:
        caption_template_to_use = info.BATCH_FILE_CAPTION if is_batch else info.CUSTOM_FILE_CAPTION
        if caption_template_to_use:
            try:
                f_caption = caption_template_to_use.format(
                    file_name=title,
                    file_size=size,
                    file_caption=original_caption 
                )
            except Exception as e:
                logger.error(f"Error formatting caption (is_batch={is_batch}): {e}", exc_info=True)
                # Fallback to original caption or title if formatting fails
                f_caption = original_caption if original_caption else title
        else: # No custom/batch template, but KEEP_ORIGINAL_CAPTION is also false
            f_caption = title # Default to title

    # Final fallback if f_caption is still None or empty string after logic
    if not f_caption:
        f_caption = title
        
    return f_caption

async def send_message_to_user(client, user_id: int, text: str, reply_markup=None, **kwargs) -> bool:
    """
    Sends a message to a user, handling UserIsBlocked and other common exceptions.
    Returns True if message was sent successfully, False otherwise.
    Additional kwargs are passed to client.send_message.
    """
    try:
        await client.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            **kwargs
        )
        return True
    except UserIsBlocked:
        logger.warning(f"User {user_id} has blocked the bot. Could not send message.")
    except InputUserDeactivated:
        logger.warning(f"User {user_id} is deactivated. Could not send message.")
        # Consider deleting user from DB here if appropriate for the bot's logic
        # await db.delete_user(user_id) 
    except PeerIdInvalid:
        logger.warning(f"User ID {user_id} is invalid (PeerIdInvalid). Could not send message.")
    except Exception as e:
        logger.error(f"Failed to send message to user {user_id}: {e}", exc_info=True)
    return False

async def send_all(bot, userid, files, ident):
    for file in files:
        f_caption = file.caption
        title = file.file_name
        size = get_size(file.file_size)
        if info.KEEP_ORIGINAL_CAPTION:
            try:
                f_caption = file.caption
            except:
                f_caption = f"{title}"
        elif info.CUSTOM_FILE_CAPTION:
            try:
                f_caption = info.CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                        file_size='' if size is None else size,
                                                        file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                print(e)
                f_caption = f_caption
        if f_caption is None:
            f_caption = f"{title}"
        await bot.send_cached_media(
            chat_id=userid,
            file_id=file.file_id,
            caption=f_caption,
            parse_mode=enums.ParseMode.HTML,
            protect_content=True if ident == "filep" else False,
            reply_markup=InlineKeyboardMarkup( [ [ InlineKeyboardButton('⚔️ Main Channel ⚔️', url="https://t.me/kdramaworld_ongoing") ] ] ))



[end of utils.py]
