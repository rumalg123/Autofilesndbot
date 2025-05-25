import os
import logging
import random
import asyncio
import sys

from Script import script
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait, UserIsBlocked # Added UserIsBlocked
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified
from pyrogram.types import Message
from database.ia_filterdb import Media, get_file_details, unpack_new_file_id, get_bad_files
from database.users_chats_db import db
import info
from info import PREMIUM_DURATION_DAYS, NON_PREMIUM_DAILY_LIMIT 
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from database.connections_mdb import active_connection
import re
import json
import base64
import time
from datetime import datetime, timedelta, date, time as dt_time 

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) 
RESTART_FILE = "restart_msg.txt"

BATCH_FILES = {}

CMD = ["/", "."]

OWNER_ID = info.ADMINS[0] if info.ADMINS else None


async def check_user_access(client, message, user_id, *, increment: bool = False): # client is available here
    """Checks user access, handles premium status, and daily limits."""
    if OWNER_ID and user_id == OWNER_ID:
        return True, "Owner access: Unlimited"

    user_data = await db.get_user_data(user_id)

    if not user_data:
        # Use a placeholder name if message is None or from_user is None
        user_first_name = "User"
        if message and message.from_user:
            user_first_name = message.from_user.first_name
        await db.add_user(user_id, user_first_name)
        user_data = await db.get_user_data(user_id) # Reload user_data

    now_utc = datetime.utcnow() 

    if user_data.get('is_premium'):
        activation_date_val = user_data.get('premium_activation_date')
        if activation_date_val:
            activation_date = None
            if isinstance(activation_date_val, str):
                try:
                    activation_date = datetime.fromisoformat(activation_date_val)
                except ValueError:  
                    logger.error(f"Invalid premium_activation_date format for user {user_id}: {activation_date_val}")
            elif isinstance(activation_date_val, (int, float)): 
                activation_date = datetime.fromtimestamp(activation_date_val) 
            elif isinstance(activation_date_val, datetime):  
                activation_date = activation_date_val
            else:
                logger.error(f"Unknown premium_activation_date type for user {user_id}: {type(activation_date_val)}")

            if activation_date:  
                expiry_date = activation_date + timedelta(days=info.PREMIUM_DURATION_DAYS)
                if now_utc > expiry_date: 
                    await db.update_premium_status(user_id, False)
                    # Send PM directly to the user
                    try:
                        await client.send_message( # Use client.send_message
                            chat_id=user_id, 
                            text="Your premium subscription has expired. You are now on the free plan."
                        )
                    except UserIsBlocked:
                        logger.warning(f"User {user_id} has blocked the bot. Could not send premium expiry PM.")
                    except Exception as e:
                        logger.error(f"Failed to send premium expiry PM to {user_id}: {e}")
                    # Fall through to non-premium checks
                else:
                    return True, "Premium access" # Active premium
        else: # is_premium is True but no activation_date_val
             logger.warning(f"User {user_id} is_premium=True but no premium_activation_date. Treating as non-premium.")
             # Fall through to non-premium checks
    
    # Non-premium user logic (or expired/problematic premium)
    raw_last = user_data.get("last_retrieval_date")
    raw_count = user_data.get("daily_retrieval_count", 0)
    
    last_day = None
    if isinstance(raw_last, datetime):
        last_day = raw_last.date()
    elif isinstance(raw_last, str):
        try:
            last_day = date.fromisoformat(raw_last.split("T")[0])
        except ValueError: 
             try:
                 last_day = date.fromisoformat(raw_last)
             except ValueError:
                 logger.error(f"Invalid last_retrieval_date string format for user {user_id}: {raw_last}")
    elif isinstance(raw_last, date): 
        last_day = raw_last
    
    if last_day != now_utc.date(): 
        raw_count = 0

    if raw_count >= info.NON_PREMIUM_DAILY_LIMIT:
        limit_msg = f"You have reached your daily limit of {info.NON_PREMIUM_DAILY_LIMIT} file retrievals. Upgrade to premium for unlimited access."
        # The condition `user_data.get('is_premium') and 'expiry_date' in locals()` might be true if premium just expired in this call
        if 'expiry_date' in locals() and now_utc > expiry_date: # Check if premium expired in this same function call
            limit_msg = f"Your premium has expired and you have now reached your daily limit of {info.NON_PREMIUM_DAILY_LIMIT} file retrievals. Upgrade to premium for unlimited access."
        return False, limit_msg
    
    if increment:
        await db.increment_retrieval_count(user_id) 
    return True, "Non-premium access"


@Client.on_message(filters.command("addpremium") & filters.user(OWNER_ID if OWNER_ID else []))
async def add_premium_command(client, message):
    if not OWNER_ID:
        return await message.reply_text("Owner ID not configured.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: /addpremium <user_id>")
    try:
        user_id_to_add = int(message.command[1])
    except ValueError:
        return await message.reply_text("Invalid user ID format.")

    if not await db.is_user_exist(user_id_to_add):
        return await message.reply_text(
            f"User {user_id_to_add} not found in the database. They need to start the bot first.")

    await db.update_premium_status(user_id_to_add, True) 
    try:
        user_info = await client.get_users(user_id_to_add)
        user_mention = user_info.mention if user_info else f"`{user_id_to_add}`"
    except Exception:
        user_mention = f"`{user_id_to_add}`"

    await message.reply_text(f"Successfully upgraded {user_mention} to premium.")
    try:
        await client.send_message(user_id_to_add, "Congratulations! You have been upgraded to premium status.")
    except Exception:
        await message.reply_text(
            f"Could not notify user {user_mention} directly (they might have blocked the bot or not started a chat).")


@Client.on_message(filters.command("removepremium") & filters.user(OWNER_ID if OWNER_ID else []))
async def remove_premium_command(client, message):
    if not OWNER_ID:
        return await message.reply_text("Owner ID not configured.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: /removepremium <user_id>")
    try:
        user_id_to_remove = int(message.command[1])
    except ValueError:
        return await message.reply_text("Invalid user ID format.")

    if not await db.is_user_exist(user_id_to_remove):
        return await message.reply_text(f"User {user_id_to_remove} not found in the database.")

    await db.update_premium_status(user_id_to_remove, False)
    try:
        user_info = await client.get_users(user_id_to_remove)
        user_mention = user_info.mention if user_info else f"`{user_id_to_remove}`"
    except Exception:
        user_mention = f"`{user_id_to_remove}`"

    await message.reply_text(f"Successfully removed premium status from {user_mention}.")
    try:
        await client.send_message(user_id_to_remove, "Your premium status has been removed.")
    except Exception:
        await message.reply_text(f"Could not notify user {user_mention} directly.")


@Client.on_message(filters.command("plans") & filters.private)
async def plans_command(client: Client, message: Message):
    user_id = message.from_user.id
    user_data = await db.get_user_data(user_id) 

    plan_message_lines = [
        "✨ **Our Premium Plan** ✨\n",
        "🔹 **1-Month Plan:** $1 (30 days of unlimited access)\n",
        "💳 **Payment Link:** https://buymeacoffee.com/matthewmurdock001\n",
        "❗ **Important Payment Instructions:**",
        "1. After payment, send a confirmation message to @gunaya001contactbot.",
        "2. When paying on Buy Me a Coffee, please include your Telegram Username (e.g., @yourusername) AND your Telegram User ID in the message/note section.",
        "3. Send your Telegram Username and User ID also to @gunaya001contactbot after payment.\n",
        "---",
        "👤 **Your Current Status:**"
    ]
    
    now_utc = datetime.utcnow() 

    if user_data and user_data.get('is_premium'):
        plan_message_lines.append("✅ You are currently on the **Premium Plan**.")
        activation_date_val = user_data.get('premium_activation_date')
        if activation_date_val:
            activation_date = None
            if isinstance(activation_date_val, datetime):  
                activation_date = activation_date_val
            elif isinstance(activation_date_val, date) and not isinstance(activation_date_val, datetime): 
                activation_date = datetime.combine(activation_date_val, dt_time.min) 
            elif isinstance(activation_date_val, str):
                try:
                    activation_date = datetime.fromisoformat(activation_date_val)
                except ValueError:
                    try:  
                        activation_date = datetime.fromtimestamp(float(activation_date_val))
                    except ValueError:
                        logger.error(
                            f"Invalid premium_activation_date string format for user {user_id}: {activation_date_val}")
            elif isinstance(activation_date_val, (int, float)):  
                try:
                    activation_date = datetime.fromtimestamp(float(activation_date_val))
                except ValueError:
                    logger.error(
                        f"Invalid premium_activation_date timestamp format for user {user_id}: {activation_date_val}")

            if activation_date:
                expiry_date = activation_date + timedelta(days=PREMIUM_DURATION_DAYS)
                if now_utc > expiry_date: 
                    plan_message_lines.append("⚠️ Your premium subscription has expired.")
                else:
                    plan_message_lines.append(
                        f"🗓️ Your premium expires on: {expiry_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            else:
                plan_message_lines.append("Could not determine your premium activation date. Please contact support.")
        else:
            plan_message_lines.append("Premium status active, but activation date is missing. Please contact support.")
    else:
        plan_message_lines.append("🆓 You are currently on the **Free Plan**.")
        daily_limit = NON_PREMIUM_DAILY_LIMIT
        current_usage = 0
        if user_data:  
            current_usage = user_data.get('daily_retrieval_count', 0)
            last_retrieval_date_val = user_data.get('last_retrieval_date')
            retrieval_date_obj = None
            if isinstance(last_retrieval_date_val, datetime):
                retrieval_date_obj = last_retrieval_date_val.date()
            elif isinstance(last_retrieval_date_val, date):
                retrieval_date_obj = last_retrieval_date_val
            elif isinstance(last_retrieval_date_val, str): 
                 try:
                     retrieval_date_obj = date.fromisoformat(last_retrieval_date_val.split("T")[0])
                 except ValueError:
                     try:
                         retrieval_date_obj = date.fromisoformat(last_retrieval_date_val)
                     except ValueError:
                         logger.error(f"Invalid last_retrieval_date string format for user {user_id}: {last_retrieval_date_val}")


            if retrieval_date_obj != now_utc.date(): 
                current_usage = 0  
        plan_message_lines.append(f"File retrievals today: {current_usage}/{daily_limit}")

    await message.reply_text("\n".join(plan_message_lines), disable_web_page_preview=True)


@Client.on_message(filters.command("premiumusers") & filters.user(info.ADMINS))
async def list_premium_users_command(client: Client, message: Message):
    all_users = await db.get_all_users()
    premium_users_details = []
    now = datetime.utcnow() 

    for user_doc in all_users:
        if not user_doc.get('is_premium'):
            continue

        user_id = user_doc.get('id')
        name = "N/A"
        username = "N/A"

        try:
            user_info_obj = await client.get_users(int(user_id))
            if user_info_obj:
                name = user_info_obj.first_name or "N/A"
                username = f"@{user_info_obj.username}" if user_info_obj.username else "N/A"
        except Exception as e:
            logger.warning(f"Could not fetch info for user ID {user_id}: {e}")

        expiry_text = "Expiry: Unknown"
        act_val = user_doc.get('premium_activation_date')

        activation_date = None
        if isinstance(act_val, datetime):
            activation_date = act_val
        elif isinstance(act_val, date) and not isinstance(act_val, datetime):
            activation_date = datetime.combine(act_val, dt_time.min) 
        elif isinstance(act_val, str):
            try:
                activation_date = datetime.fromisoformat(act_val)
            except ValueError:
                try:
                    activation_date = datetime.fromtimestamp(float(act_val))
                except ValueError:
                    logger.error(
                        f"Invalid premium_activation_date for user {user_id}: {act_val}")
        elif isinstance(act_val, (int, float)):
            try:
                activation_date = datetime.fromtimestamp(act_val)
            except Exception:
                logger.error(
                    f"Invalid premium_activation_date timestamp for user {user_id}: {act_val}")

        if activation_date:
            expiry = activation_date + timedelta(days=info.PREMIUM_DURATION_DAYS)
            status = "Active" if now <= expiry else "Expired" 
            expiry_text = f"Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S UTC')} ({status})"
        else:
            expiry_text = "Expiry: No valid activation date"

        premium_users_details.append(
            f"ID: `{user_id}` | Name: {name} | User: {username} | {expiry_text}"
        )

    if not premium_users_details:
        await message.reply_text("No premium users found.")
        return

    header = "👑 **Premium Users List** 👑\n\n"
    body = "\n".join(premium_users_details)
    full_text = header + body

    if len(full_text) <= 4096:
        await message.reply_text(full_text, disable_web_page_preview=True)
    else:
        filename = "/tmp/premium_users.txt"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("Premium Users List\n\n" + body)

            await client.send_document(
                chat_id=message.chat.id,
                document=filename,
                caption="List of all premium users.",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error creating/sending premium users file: {e}")
            await message.reply_text("Error generating premium users list file.")
        finally:
            if os.path.exists(filename):
                os.remove(filename)


async def handle_start_no_args(client: Client, message: Message, user_id: int):
    buttons = [[
        InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ ➕', url=f"https://t.me/{temp.U_NAME}?startgroup=true")
    ], [
        InlineKeyboardButton('ᴏᴡɴᴇʀ', callback_data="owner_info"),
        InlineKeyboardButton('ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=f"https://t.me/{info.SUPPORT_CHAT}")
    ], [
        InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
        InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about'),
    ], [
        InlineKeyboardButton('ꜱᴇᴀʀᴄʜ ᴅʀᴀᴍᴀꜱ', switch_inline_query_current_chat='')
    ],
        [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_photo(
        photo=random.choice(info.PICS),
        caption=script.START_TXT.format(message.from_user.mention, info.NON_PREMIUM_DAILY_LIMIT),
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )

async def handle_start_invalid_args(client: Client, message: Message, user_id: int):
    buttons = [[
        InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ ➕', url=f"https://t.me/{temp.U_NAME}?startgroup=true")
    ], [
        InlineKeyboardButton('ᴏᴡɴᴇʀ', callback_data="owner_info"),
        InlineKeyboardButton('ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=f"https://t.me/{info.SUPPORT_CHAT}")
    ], [
        InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
        InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about'),
    ], [
        InlineKeyboardButton('ꜱᴇᴀʀᴄʜ ᴅʀᴀᴍᴀꜱ', switch_inline_query_current_chat='')
    ],
        [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_photo(
        photo=random.choice(info.PICS),
        caption=script.START_TXT.format(message.from_user.mention, info.NON_PREMIUM_DAILY_LIMIT),
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )

async def handle_start_force_subscribe(client: Client, message: Message, user_id: int, data: str):
    try:
        invite_link = await client.create_chat_invite_link(int(info.AUTH_CHANNEL))
    except ChatAdminRequired:
        logger.error("Make sure Bot is admin in Force Sub channel")
        await message.reply_text("Sorry, there's an issue with the bot configuration. Please try again later.")
        return
    btn = [
        [
            InlineKeyboardButton(
                "🤖 𝖩𝗈𝗂𝗇 𝖴𝗉𝖽𝖺𝗍𝖾𝗌 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 🤖", url=invite_link.invite_link
            )
        ]
    ]
    if data != "subscribe" and data != "send_all": 
        try:
            kk, file_id = data.split("_", 1)
            pre_for_cb = 'checksubp' if kk == 'filep' else 'checksub' 
            btn.append([InlineKeyboardButton("⟳ 𝖳𝗋𝗒 𝖠𝗀𝖺𝗂𝗇 ⟳", callback_data=f"{pre_for_cb}#{file_id}")])
        except (IndexError, ValueError):
            btn.append([InlineKeyboardButton("⟳ 𝖳𝗋𝗒 𝖠𝗀𝖺𝗂𝗇 ⟳",
                                             url=f"https://t.me/{temp.U_NAME}?start={data}")])
    await client.send_message(
        chat_id=user_id,
        text="**Please Join My Updates Channel to use this Bot!**",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.MARKDOWN
    )


async def handle_start_send_all(client: Client, message: Message, user_id: int, data: str):
    _, key, pre_type = data.split("_", 2)
    files = temp.FILES_IDS.get(key)
    if not files:
        await message.reply('<b><i>No such file exist.</b></i>')
        return

    for file_item in files:
        can_access, reason = await check_user_access(client, message, user_id, increment=False)
        if not can_access:
            await message.reply_text(f"Access denied for {file_item.file_name}: {reason}")
            return 

        ok, reason = await check_user_access(client, message, user_id, increment=True)
        if not ok:
            await message.reply_text(f"Access denied for {file_item.file_name}: {reason}")
            return 

        title = file_item.file_name
        size = get_size(file_item.file_size)
        f_caption = None
        original_caption = file_item.caption 

        if info.KEEP_ORIGINAL_CAPTION:
            f_caption = original_caption or title
        elif info.CUSTOM_FILE_CAPTION:
            try:
                f_caption = info.CUSTOM_FILE_CAPTION.format(
                    file_name=title or '',
                    file_size=size or '',
                    file_caption=original_caption or ''
                )
            except Exception as e:
                logger.exception(e)
                f_caption = original_caption or title
        if f_caption is None:
            f_caption = title

        await client.send_cached_media(
            chat_id=user_id,
            file_id=file_item.file_id,
            caption=f_caption,
            protect_content=True if pre_type == 'filep' else False,
            parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION or info.CUSTOM_FILE_CAPTION else enums.ParseMode.DEFAULT,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL)],
                                               [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")]])
        )
        await asyncio.sleep(1) 

async def handle_start_batch(client: Client, message: Message, user_id: int, data: str):
    sts = await message.reply("<b>Processing batch...</b>")
    batch_file_id_from_data = data.split("-", 1)[1] 
    msgs = BATCH_FILES.get(batch_file_id_from_data)
    file_path_local = None 

    if not msgs:
        try:
            file_path_local = await client.download_media(batch_file_id_from_data)
            if file_path_local:
                with open(file_path_local) as file_data_content: 
                    msgs = json.loads(file_data_content.read())
                BATCH_FILES[batch_file_id_from_data] = msgs
            else:
                raise Exception("Download failed, no path returned.")
        except FileNotFoundError:
            logger.error(f"Batch file (ID: {batch_file_id_from_data}) not found after attempting download.")
            await sts.edit("FAILED: Batch file definition not found.")
            return
        except json.JSONDecodeError:
            logger.error(f"Batch file (ID: {batch_file_id_from_data}) is not a valid JSON.")
            await sts.edit("FAILED: Batch file format error.")
            return
        except Exception as e:
            logger.error(f"Failed to load batch file (ID: {batch_file_id_from_data}): {e}", exc_info=True)
            await sts.edit("FAILED: Could not process batch file.")
            return
        finally:
            if file_path_local and os.path.exists(file_path_local):
                os.remove(file_path_local)


    if not msgs:
        await sts.edit("FAILED: Batch data unavailable.")
        return

    for msg_item_data in msgs: 
        can_access, reason = await check_user_access(client, message, user_id, increment=False)
        if not can_access:
            await message.reply_text(f"Access denied for file in batch: {reason} (File: {msg_item_data.get('title', 'N/A')})")
            return

        ok, reason = await check_user_access(client, message, user_id, increment=True)
        if not ok:
            await message.reply_text(f"Access denied for file in batch: {reason} (File: {msg_item_data.get('title', 'N/A')})")
            return

        title = msg_item_data.get("title")
        size = get_size(int(msg_item_data.get("size", 0)))
        f_caption = None
        original_caption = msg_item_data.get("caption")

        if info.KEEP_ORIGINAL_CAPTION:
            f_caption = original_caption or title
        elif info.BATCH_FILE_CAPTION:
            try:
                f_caption = info.BATCH_FILE_CAPTION.format(
                    file_name=title or '',
                    file_size=size or '',
                    file_caption=original_caption or ''
                )
            except Exception as e:
                logger.exception(e)
                f_caption = original_caption or title
        if f_caption is None:
            f_caption = title
            
        try:
            await client.send_cached_media(
                chat_id=user_id,
                file_id=msg_item_data.get("file_id"),
                caption=f_caption,
                protect_content=msg_item_data.get('protect', False),
                parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION or info.BATCH_FILE_CAPTION else enums.ParseMode.DEFAULT,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL)],
                                                   [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")]])
            )
        except FloodWait as e_flood: 
            await asyncio.sleep(e_flood.x) 
            logger.warning(f"Floodwait of {e_flood.x} sec.")
            await client.send_cached_media(
                chat_id=user_id,
                file_id=msg_item_data.get("file_id"),
                caption=f_caption,
                parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION or info.BATCH_FILE_CAPTION else enums.ParseMode.DEFAULT,
                protect_content=msg_item_data.get('protect', False),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL)],
                                                  [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")]])
            )
        except Exception as e_gen: 
            logger.warning(e_gen, exc_info=True)
            continue
        await asyncio.sleep(1)
    await sts.delete()

async def handle_start_dstore(client: Client, message: Message, user_id: int, data: str):
    sts = await message.reply("<b>Processing stored files...</b>")
    b_string = data.split("-", 1)[1]
    try:
        decoded = (base64.urlsafe_b64decode(b_string + "=" * (-len(b_string) % 4))).decode("ascii")
        f_msg_id, l_msg_id, f_chat_id, protect_str = decoded.split("_", 3) 
    except: 
        try: 
            f_msg_id, l_msg_id, f_chat_id = decoded.split("_", 2)
            protect_str = "/pbatch" if info.PROTECT_CONTENT else "batch"
        except:
            await sts.edit("Invalid DSTORE link format.")
            return


    async for dstore_msg_item_loop in client.iter_messages(int(f_chat_id), int(l_msg_id), int(f_msg_id)): 
        can_access, reason = await check_user_access(client, message, user_id, increment=False)
        if not can_access:
            await message.reply_text(f"Access denied for a file in stored batch: {reason}")
            return

        ok, reason = await check_user_access(client, message, user_id, increment=True)
        if not ok:
            await message.reply_text(f"Access denied for a file in stored batch: {reason}")
            return

        if dstore_msg_item_loop.media:
            media = getattr(dstore_msg_item_loop, dstore_msg_item_loop.media.value)
            f_caption = None
            original_caption_dstore = getattr(dstore_msg_item_loop, 'caption', '') 
            media_filename = getattr(media, 'file_name', '') 
            media_filesize = getattr(media, 'file_size', 0) 

            if info.KEEP_ORIGINAL_CAPTION:
                f_caption = original_caption_dstore or media_filename
            elif info.BATCH_FILE_CAPTION:
                try:
                    f_caption = info.BATCH_FILE_CAPTION.format(
                        file_name=media_filename,
                        file_size=get_size(media_filesize), 
                        file_caption=original_caption_dstore
                    )
                except Exception as e:
                    logger.exception(e)
                    f_caption = original_caption_dstore or media_filename
            if f_caption is None: 
                f_caption = media_filename
            
            try:
                await dstore_msg_item_loop.copy(user_id, caption=f_caption, protect_content=True if protect_str == "/pbatch" else False)
            except FloodWait as e_flood_dstore: 
                await asyncio.sleep(e_flood_dstore.x) 
                await dstore_msg_item_loop.copy(user_id, caption=f_caption, protect_content=True if protect_str == "/pbatch" else False)
            except Exception as e_dstore: 
                logger.exception(e_dstore)
                continue
        elif dstore_msg_item_loop.empty:
            continue
        else: 
            try:
                await dstore_msg_item_loop.copy(user_id, protect_content=True if protect_str == "/pbatch" else False)
            except FloodWait as e_flood_non_media: 
                await asyncio.sleep(e_flood_non_media.x) 
                await dstore_msg_item_loop.copy(user_id, protect_content=True if protect_str == "/pbatch" else False)
            except Exception as e_non_media: 
                logger.exception(e_non_media)
                continue
        await asyncio.sleep(1)
    await sts.delete()

async def handle_start_single_file(client: Client, message: Message, user_id: int, data: str, pre_param: str, file_id_param: str): 
    actual_file_id_to_send = None 
    actual_pre_to_send = pre_param 

    files_from_db = await get_file_details(file_id_param) 

    if not files_from_db:
        try:
            decoded_data_str = (base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii") 
            actual_pre_to_send, actual_file_id_to_send = decoded_data_str.split("_", 1)
            files_from_db = await get_file_details(actual_file_id_to_send)
            
            if files_from_db:
                can_access, reason = await check_user_access(client, message, user_id, increment=False)
                if not can_access:
                    await message.reply_text(reason)
                    return
                ok, reason = await check_user_access(client, message, user_id, increment=True)
                if not ok:
                    await message.reply_text(reason)
                    return
        except Exception:
            await message.reply('<b><i>No such file exist (error during decoding or final lookup).</b></i>')
            return

    if not files_from_db:
        await message.reply('<b><i>No such file exist.</b></i>')
        return

    if not actual_file_id_to_send: 
        actual_file_id_to_send = file_id_param

    db_file_entry_obj = files_from_db[0] 
    title = db_file_entry_obj.file_name
    size = get_size(db_file_entry_obj.file_size)
    f_caption = db_file_entry_obj.caption

    if info.KEEP_ORIGINAL_CAPTION:
        pass 
    elif info.CUSTOM_FILE_CAPTION:
        try:
            f_caption = info.CUSTOM_FILE_CAPTION.format(
                file_name=title or '',
                file_size=size or '',
                file_caption=f_caption or ''
            )
        except Exception as e:
            logger.exception(e)
    
    if f_caption is None:
        f_caption = title or ''


    await client.send_cached_media(
        chat_id=user_id,
        file_id=actual_file_id_to_send,
        caption=f_caption,
        parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION or info.CUSTOM_FILE_CAPTION else enums.ParseMode.DEFAULT,
        protect_content=True if actual_pre_to_send == 'filep' else False,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL)],
                                           [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")]])
    )


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [[
            InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ ➕', url=f"https://t.me/{temp.U_NAME}?startgroup=true")
        ], [
            InlineKeyboardButton('ᴏᴡɴᴇʀ', callback_data="owner_info"),
            InlineKeyboardButton('ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=f"https://t.me/{info.SUPPORT_CHAT}")
        ], [
            InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about')
        ], [
            InlineKeyboardButton('ꜱᴇᴀʀᴄʜ ᴅʀᴀᴍᴀꜱ', switch_inline_query_current_chat='')
        ],
            [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")], ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(
            script.START_TXT.format(message.from_user.mention if message.from_user else message.chat.title, info.NON_PREMIUM_DAILY_LIMIT), reply_markup=reply_markup)
        if not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            await client.send_message(info.LOG_CHANNEL,
                                      script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown"))
            await db.add_chat(message.chat.id, message.chat.title)
    
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(info.LOG_CHANNEL,
                                  script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention))

    user_id = message.from_user.id

    if len(message.command) == 1: 
        await handle_start_no_args(client, message, user_id)
        return

    data = message.command[1]
    
    if info.AUTH_CHANNEL and not await is_subscribed(client, message):
        await handle_start_force_subscribe(client, message, user_id, data)
        return
        
    if data in ["subscribe", "error", "okay", "help"]:
        await handle_start_invalid_args(client, message, user_id)
        return

    pre, file_id_check = "", data
    if '_' in data:
        try:
            pre, file_id_check = data.split('_', 1)
        except ValueError: 
            pass 

    is_direct_file_request = not (data.startswith("all") or data.split("-", 1)[0] in ["BATCH", "DSTORE"])

    if is_direct_file_request:
        can_access, reason = await check_user_access(client, message, user_id, increment=False)
        if not can_access:
            await message.reply_text(reason)
            return
        # Increment will be handled by handle_start_single_file if a file is sent.

    if data.startswith("all_"):
        await handle_start_send_all(client, message, user_id, data)
    elif data.startswith("BATCH-"):
        await handle_start_batch(client, message, user_id, data)
    elif data.startswith("DSTORE-"):
        await handle_start_dstore(client, message, user_id, data)
    else: 
        await handle_start_single_file(client, message, user_id, data, pre, file_id_check)


@Client.on_message(filters.command('channel') & filters.user(info.ADMINS))
async def channel_info(bot, message):
    """Send basic information of channel"""
    if isinstance(info.CHANNELS, (int, str)):
        channels = [info.CHANNELS]
    elif isinstance(info.CHANNELS, list):
        channels = info.CHANNELS
    else:
        raise ValueError("Unexpected type of CHANNELS")

    text = '📑 **Indexed channels/groups**\n'
    for channel in channels:
        chat = await bot.get_chat(channel)
        if chat.username:
            text += '\n@' + chat.username
        else:
            text += '\n' + chat.title or chat.first_name

    text += f'\n\n**Total:** {len(info.CHANNELS)}'

    if len(text) < 4096:
        await message.reply(text)
    else:
        file = 'Indexed channels.txt'
        with open(file, 'w') as f:
            f.write(text)
        await message.reply_document(file)
        os.remove(file)


@Client.on_message(filters.command('logs') & filters.user(info.ADMINS))
async def log_file(bot, message):
    """Send log file"""
    try:
        await message.reply_document('Logs.txt')
    except Exception as e:
        await message.reply(str(e))


@Client.on_message(filters.command('delete') & filters.user(info.ADMINS))
async def delete(bot, message):
    """Delete file from database"""
    reply = message.reply_to_message
    if reply and reply.media:
        msg = await message.reply("Processing...⏳", quote=True)
    else:
        await message.reply('Reply to file with /delete which you want to delete', quote=True)
        return 

    media = None 
    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None:
            break
    
    if media is None: 
        await msg.edit('This is not supported file format')
        return 

    file_id, file_ref = unpack_new_file_id(media.file_id)

    result = await Media.collection.delete_one({
        '_id': file_id,
    })
    if result.deleted_count:
        await msg.edit('File is successfully deleted from database')
    else:
        file_name = re.sub(r"([_\-.+])", " ", str(media.file_name))
        result = await Media.collection.delete_many({
            'file_name': file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
        })
        if result.deleted_count:
            await msg.edit('File is successfully deleted from database')
        else:
            result = await Media.collection.delete_many({
                'file_name': media.file_name, 
                'file_size': media.file_size,
                'mime_type': media.mime_type
            })
            if result.deleted_count:
                await msg.edit('File is successfully deleted from database')
            else:
                await msg.edit('File not found in database')


@Client.on_message(filters.command('deleteall') & filters.user(info.ADMINS))
async def delete_all_index(bot, message):
    await message.reply_text(
        'This will delete all indexed files.\nDo you want to continue??',
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="YES", callback_data="autofilter_delete"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="CANCEL", callback_data="close_data"
                    )
                ],
            ]
        ),
        quote=True,
    )


@Client.on_callback_query(filters.regex(r'^autofilter_delete'))
async def delete_all_index_confirm(bot, message):
    await Media.collection.drop()
    await message.answer('Support Us By Sharing The Channel And Bot')
    await message.message.edit('Succesfully Deleted All The Indexed Files.')


@Client.on_message(filters.command('settings'))
async def settings_cmd(client, message): 
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    grp_id = None
    title = None

    if chat_type == enums.ChatType.PRIVATE:
        grpid_conn = await active_connection(str(userid)) 
        if grpid_conn is not None:
            grp_id = grpid_conn
            try:
                chat = await client.get_chat(grpid_conn)
                title = chat.title
            except: 
                return await message.reply_text("Make sure I'm present in your group!!", quote=True)
        else:
            return await message.reply_text("I'm not connected to any groups!", quote=True)
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title
    else:
        return 

    if not grp_id or not title: 
        return await message.reply_text("Could not determine the group for settings.", quote=True)

    st = await client.get_chat_member(grp_id, userid)
    if not (
            st.status == enums.ChatMemberStatus.ADMINISTRATOR
            or st.status == enums.ChatMemberStatus.OWNER
            or str(userid) in info.ADMINS
    ):
        return 

    current_settings = await get_settings(grp_id) 

    buttons = [
        [
            InlineKeyboardButton('𝖥𝗂𝗅𝗍𝖾𝗋 𝖡𝗎𝗍𝗍𝗈𝗇', callback_data=f'setgs#button#{current_settings["button"]}#{grp_id}'),
            InlineKeyboardButton('𝖲𝗂𝗇𝗀𝗅𝖾 𝖡𝗎𝗍𝗍𝗈𝗇' if current_settings["button"] else '𝖣𝗈𝗎𝖻𝗅𝖾', callback_data=f'setgs#button#{current_settings["button"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('𝖥𝗂𝗅𝖾 𝖲𝖾𝗇𝖽 𝖬𝗈𝖽𝖾', callback_data=f'setgs#botpm#{current_settings["botpm"]}#{grp_id}'),
            InlineKeyboardButton('𝖬𝖺𝗇𝗎𝖺𝗅 𝖲𝗍𝖺𝗋𝗍' if current_settings["botpm"] else '𝖠𝗎𝗍𝗈 𝖲𝖾𝗇𝖽', callback_data=f'setgs#botpm#{current_settings["botpm"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('𝖯𝗋𝗈𝗍𝖾𝖼𝗍 𝖢𝗈𝗇𝗍𝖾𝗇𝗍', callback_data=f'setgs#file_secure#{current_settings["file_secure"]}#{grp_id}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if current_settings["file_secure"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#file_secure#{current_settings["file_secure"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('𝖨𝖬𝖣𝖻', callback_data=f'setgs#imdb#{current_settings["imdb"]}#{grp_id}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if current_settings["imdb"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#imdb#{current_settings["imdb"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('𝖲𝗉𝖾𝗅𝗅 𝖢𝗁𝖾𝖼𝗄', callback_data=f'setgs#spell_check#{current_settings["spell_check"]}#{grp_id}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if current_settings["spell_check"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#spell_check#{current_settings["spell_check"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖬𝖾𝗌𝗌𝖺𝗀𝖾', callback_data=f'setgs#welcome#{current_settings["welcome"]}#{grp_id}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if current_settings["welcome"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#welcome#{current_settings["welcome"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('𝖠𝗎𝗍𝗈 𝖣𝖾𝗅𝖾𝗍𝖾', callback_data=f'setgs#auto_delete#{current_settings["auto_delete"]}#{grp_id}'),
            InlineKeyboardButton('5 𝖬𝗂𝗇' if current_settings["auto_delete"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#auto_delete#{current_settings["auto_delete"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('𝖠𝗎𝗍𝗈-𝖥𝗂𝗅𝗍𝖾𝗋', callback_data=f'setgs#auto_ffilter#{current_settings["auto_ffilter"]}#{grp_id}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if current_settings["auto_ffilter"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#auto_ffilter#{current_settings["auto_ffilter"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('𝖬𝖺𝗑 𝖡𝗎𝗍𝗍𝗈𝗇𝗌', callback_data=f'setgs#max_btn#{current_settings["max_btn"]}#{grp_id}'),
            InlineKeyboardButton('10' if current_settings["max_btn"] else f'{info.MAX_B_TN}', callback_data=f'setgs#max_btn#{current_settings["max_btn"]}#{grp_id}')
        ],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        btn_open_options = [[
            InlineKeyboardButton("⬇ 𝖮𝗉𝖾𝗇 𝖧𝖾𝗋𝖾 ⬇", callback_data=f"opnsetgrp#{grp_id}"),
            InlineKeyboardButton("➡ 𝖮𝗉𝖾𝗇 𝗂𝗇 𝖯𝖬 ➡", callback_data=f"opnsetpm#{grp_id}")
        ]]
        await message.reply_text(
            text="<b>𝖣𝗈 𝖸𝗈𝗎 𝖶𝖺𝗇𝗍 𝖳𝗈 𝖮𝗉𝖾𝗇 𝖲𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝖧𝖾𝗋𝖾 ?</b>",
            reply_markup=InlineKeyboardMarkup(btn_open_options),
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=message.id
        )
    else: 
        await message.reply_text(
            text=f"<b>𝖢𝗁𝖺𝗇𝗀𝖾 𝖸𝗈𝗎𝗋 𝖲𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝖥𝗈𝗋 {title} 𝖠𝗌 𝖸𝗈𝗎𝗋 𝖶𝗂𝗌𝗁</b>",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=message.id
        )


@Client.on_message(filters.command("send") & filters.user(info.ADMINS))
async def send_msg_user(bot, message): # Renamed to send_msg_user
    if message.reply_to_message:
        target_id_str = message.text.split(" ", 1)[1] 
        try:
            user = await bot.get_users(target_id_str) 
            await message.reply_to_message.copy(int(user.id)) 
            await message.reply_text(f"<b>Your message has been successfully send to {user.mention}.</b>")
        except UserIsBlocked:
             await message.reply_text("<b>User has blocked the bot.</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error: {e}</b>")
    else:
        await message.reply_text(
            "<b>Use this command as a reply to any message using the target chat id. For eg: /send userid</b>")


@Client.on_message(filters.command("usend") & filters.user(info.ADMINS)) 
async def usend_msg(bot, message):
    if message.reply_to_message:
        target_id_str = message.text.split(" ", 1)[1]
        try:
            user = await bot.get_users(target_id_str)
            await message.reply_to_message.copy(int(user.id))
            await message.reply_text(f"<b>𝖸𝗈𝗎𝗋 𝖬𝖾𝗌𝗌𝖺𝗀𝖾 𝖧𝖺𝗌 𝖲𝗎𝖼𝖼𝖾𝗌𝗌𝖿𝗎𝗅𝗅𝗒 𝖲𝖾𝗇𝗍 𝖳𝗈 {user.mention}.</b>")
        except UserIsBlocked:
             await message.reply_text("<b>User has blocked the bot.</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error :- <code>{e}</code></b>")
    else:
        await message.reply_text("<b>Error𝖢𝗈𝗆𝗆𝖺𝗇𝖽 𝖨𝗇𝖼𝗈𝗆𝗉𝗅𝖾𝗍𝖾 ! Reply to a message.</b>")


@Client.on_message(filters.command("gsend") & filters.user(info.ADMINS))
async def send_chatmsg(bot, message):
    if message.reply_to_message:
        target_id_str = message.text.split(" ", 1)[1]
        try:
            chat = await bot.get_chat(target_id_str if not target_id_str.isnumeric() else int(target_id_str)) 
            await message.reply_to_message.copy(chat.id)
            await message.reply_text(f"<b>Your message has been successfully send to <code>{chat.id}</code>.</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error :- <code>{e}</code></b>")
    else:
        await message.reply_text("<b>Error𝖢𝗈𝗆𝗆𝖺𝗇𝖽 𝖨𝗇𝖼𝗈𝗆𝗉𝗅𝖾𝗍𝖾 ! Reply to a message.</b>")


@Client.on_message(filters.command("deletefiles") & filters.user(info.ADMINS))
async def deletemultiplefiles(bot, message):
    chat_type = message.chat.type
    if chat_type != enums.ChatType.PRIVATE:
        return await message.reply_text(
            f"<b>Hey {message.from_user.mention}, This command won't work in groups. It only works on my PM !</b>")
    
    try:
        keyword = message.text.split(" ", 1)[1]
    except IndexError: 
        return await message.reply_text(
            f"<b>Hey {message.from_user.mention}, Give me a keyword along with the command to delete files.</b>")
    
    k = await bot.send_message(chat_id=message.chat.id,
                               text=f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
    files, total = await get_bad_files(keyword) 
    
    if total == 0:
        return await k.edit_text(f"<b>No files found for query {keyword}. Nothing to delete.</b>")

    await k.edit_text(
        f"<b>Found {total} files for your query {keyword} !\n\nFile deletion process will start in 5 seconds !</b>")
    await asyncio.sleep(5)
    deleted_count = 0 
    async with lock: 
        try:
            for file_doc in files: 
                file_id = file_doc.file_id 
                file_name = file_doc.file_name 
                result = await Media.collection.delete_one({'_id': file_id}) 
                
                if result.deleted_count:
                    logger.info(f'File Found for your query {keyword}! Successfully deleted {file_name} from database.')
                    deleted_count += 1
                
                if deleted_count % 20 == 0:
                    await k.edit_text(f"<b>Process started for deleting files from DB. Successfully deleted {str(deleted_count)} files from DB for your query {keyword} !\n\nPlease wait...</b>")
        except Exception as e:
            logger.exception(e)
            await k.edit_text(f'Error: {e}') 
        else:
            await k.edit_text(f"<b>Process Completed for file deletion !\n\nSuccessfully deleted {str(deleted_count)} files from database for your query {keyword}.</b>")


async def allowed(_, __, message):
    if info.PUBLIC_FILE_STORE:
        return True
    if message.from_user and message.from_user.id in info.ADMINS:
        return True
    return False


@Client.on_message(filters.command(['link', 'plink']) & filters.create(allowed))
async def gen_link_s(bot, message):
    replied = message.reply_to_message
    if not replied:
        return await message.reply('Reply to a message to get a shareable link.')
    
    media_type = replied.media 
    if not media_type or media_type not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
        return await message.reply("Reply to a supported media (video, audio, document)")
        
    if message.has_protected_content and message.chat.id not in info.ADMINS: 
        return await message.reply("Cannot generate link for a message from a protected content chat if I'm not admin there.")

    media_obj = getattr(replied, media_type.value)
    if not media_obj or not hasattr(media_obj, 'file_id'):
         return await message.reply("Could not extract file_id from the media.")

    file_id, ref = unpack_new_file_id(media_obj.file_id)
    string = 'filep_' if message.text.lower().strip() == "/plink" else 'file_'
    string += file_id
    outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
    await message.reply(f"Here is your Link:\nhttps://t.me/{temp.U_NAME}?start={outstr}")


@Client.on_message(filters.command(['batch', 'pbatch']) & filters.create(allowed))
async def gen_link_batch(bot, message):
    if " " not in message.text:
        return await message.reply(
            "Use correct format.\nExample <code>/batch https://t.me/kdramaworld_ongoing/10 https://t.me/kdramaworld_ongoing/20</code>.")
    
    try:
        cmd, first_link, last_link = message.text.strip().split(" ", 2) 
    except ValueError:
        return await message.reply(
            "Use correct format.\nExample <code>/batch https://t.me/kdramaworld_ongoing/10 https://t.me/kdramaworld_ongoing/20</code>.")

    regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
    
    first_match = regex.match(first_link)
    if not first_match:
        return await message.reply('Invalid first link')
    f_chat_id_str = first_match.group(4)
    f_msg_id = int(first_match.group(5))
    f_chat_id = int(("-100" + f_chat_id_str)) if f_chat_id_str.isnumeric() else f_chat_id_str

    last_match = regex.match(last_link)
    if not last_match:
        return await message.reply('Invalid last link')
    l_chat_id_str = last_match.group(4)
    l_msg_id = int(last_match.group(5))
    l_chat_id = int(("-100" + l_chat_id_str)) if l_chat_id_str.isnumeric() else l_chat_id_str

    if f_chat_id != l_chat_id:
        return await message.reply("Chat IDs not matched.")
    
    try:
        chat = await bot.get_chat(f_chat_id) 
        chat_id = chat.id 
    except ChannelInvalid:
        return await message.reply(
            'This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        return await message.reply(f'Errors - {e}')

    sts = await message.reply("Generating link for your message.\nThis may take time depending upon number of messages")
    
    if chat_id in info.FILE_STORE_CHANNEL:
        protect_type_str = "pbatch" if cmd.lower().strip() == "/pbatch" else "batch"
        string_to_encode = f"{f_msg_id}_{l_msg_id}_{chat_id}_{protect_type_str}"
        b_64 = base64.urlsafe_b64encode(string_to_encode.encode("ascii")).decode().strip("=")
        return await sts.edit(f"Here is your link https://t.me/{temp.U_NAME}?start=DSTORE-{b_64}")

    FRMT = "Generating Link...\nTotal Messages: `{total}`\nDone: `{current}`\nRemaining: `{rem}`\nStatus: `{sts}`"
    outlist = []
    og_msg_count = 0 
    total_messages_to_iterate = abs(l_msg_id - f_msg_id) + 1 

    current_iterated_count = 0
    async for msg_item in bot.iter_messages(chat_id, l_msg_id, f_msg_id): 
        current_iterated_count +=1
        if msg_item.empty or msg_item.service:
            continue
        if not msg_item.media:
            continue
        
        try:
            media_type = msg_item.media
            file_obj = getattr(msg_item, media_type.value) 
            caption_html = getattr(msg_item, 'caption', None)
            if caption_html and hasattr(caption_html, "html"): 
                caption = caption_html.html
            elif isinstance(caption_html, str): 
                caption = caption_html
            else:
                caption = ""


            if file_obj:
                file_data_dict = { 
                    "file_id": file_obj.file_id,
                    "caption": caption,
                    "title": getattr(file_obj, "file_name", ""),
                    "size": file_obj.file_size,
                    "protect": cmd.lower().strip() == "/pbatch",
                }
                og_msg_count += 1
                outlist.append(file_data_dict)
        except Exception as e_inner: 
            logger.error(f"Error processing message {msg_item.id} in batch: {e_inner}", exc_info=True)
            pass 

        if not og_msg_count % 20: 
            try:
                await sts.edit(FRMT.format(total=total_messages_to_iterate, current=current_iterated_count, rem=(total_messages_to_iterate - current_iterated_count),
                                           sts="Saving Messages"))
            except FloodWait as e_flood_sts: 
                await asyncio.sleep(e_flood_sts.x) 
            except Exception: 
                pass 
                
    batch_file_name = f"batchmode_{message.from_user.id}.json" 
    try:
        with open(batch_file_name, "w+", encoding="utf-8") as out_file: 
            json.dump(outlist, out_file, indent=4) 
    except Exception as e:
        await sts.edit("Error saving batch data to file.")
        logger.error(f"Error writing batch file: {e}", exc_info=True)
        return

    try:
        post = await bot.send_document(info.LOG_CHANNEL, batch_file_name, file_name="Batch.json",
                                   caption="⚠️Generated for filestore.")
    except Exception as e:
        await sts.edit("Error sending batch file to log channel.")
        logger.error(f"Error sending batch file to log channel: {e}", exc_info=True)
        return
    finally:
        if os.path.exists(batch_file_name):
            os.remove(batch_file_name)
            
    file_id_final, ref = unpack_new_file_id(post.document.file_id) 
    await sts.edit(f"Here is your link\nContains `{og_msg_count}` files.\n https://t.me/{temp.U_NAME}?start=BATCH-{file_id_final}")


@Client.on_message(filters.command('alive', CMD))
async def check_alive(_, message):
    await message.reply_text("𝖡𝗎𝖽𝖽𝗒 𝖨𝖺𝗆 𝖠𝗅𝗂𝗏𝖾 :)")


@Client.on_message(filters.command("ping", CMD))
async def ping(_, message):
    start_t = time.time()
    rm = await message.reply_text("...........")
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    await rm.edit(f"𝖯𝗂𝗇𝗀!\n{time_taken_s:.3f} ms")


@Client.on_message(filters.command("restart") & filters.user(info.ADMINS) & filters.private)
async def restart_bot(client, message):
    restart_msg = await message.reply_text("♻️ **Restarting bot...**\n\n*Updating code and restarting. Please wait.*")

    if os.path.exists("Logs.txt"): 
        try:
            os.remove("Logs.txt")
        except OSError as e:
            logger.warning(f"Could not remove Logs.txt: {e}")


    with open(RESTART_FILE, "w") as f:
        f.write(f"{message.chat.id}|{restart_msg.id}")

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "update.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "Unknown update error"
            logger.error(f"Update failed: {error_msg}")
            await message.reply_text(f"❌ **Update failed!**\n\n`{error_msg}`")
            return
    except Exception as e:
        logger.error(f"Error during update: {e}")
        await message.reply_text(f"❌ **Update error!**\n\n`{str(e)}`")
        return

    logger.info("✅ Update successful. Restarting bot...")
    os.execl(sys.executable, sys.executable, *sys.argv)


async def update_restart_status(client):
    if os.path.exists(RESTART_FILE):
        with open(RESTART_FILE, "r") as f:
            data = f.read().strip().split("|")
        if len(data) == 2:
            chat_id, message_id = data
            try:
                await client.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=int(message_id),
                    text="✅ Successfully restarted! V1.0.2"
                )
            except Exception as e:
                logger.error(f"Failed to update restart message: {e}") # Changed print to logger.error
        try: 
            os.remove(RESTART_FILE)
        except OSError as e:
            logger.error(f"Could not remove restart file: {e}")

[end of plugins/commands.py]
