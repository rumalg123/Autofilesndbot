import os
import logging
import random
import asyncio
import sys

from Script import script
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified
from pyrogram.types import Message  # Added Message
from database.ia_filterdb import Media, get_file_details, unpack_new_file_id, get_bad_files
from database.users_chats_db import db
#from info import CHANNELS, ADMINS, AUTH_CHANNEL, LOG_CHANNEL, PICS, BATCH_FILE_CAPTION, CUSTOM_FILE_CAPTION, SUPPORT_CHAT, PROTECT_CONTENT, REQST_CHANNEL, SUPPORT_CHAT_ID, MAX_B_TN, FILE_STORE_CHANNEL, PUBLIC_FILE_STORE, KEEP_ORIGINAL_CAPTION, initialize_configuration
import info
from info import PREMIUM_DURATION_DAYS, NON_PREMIUM_DAILY_LIMIT  # Added
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from database.connections_mdb import active_connection
import re
import json
import base64
import time
from datetime import datetime, timedelta, date  # Added date

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
RESTART_FILE = "restart_msg.txt"

BATCH_FILES = {}

CMD = ["/", "."]

OWNER_ID = info.ADMINS[0] if info.ADMINS else None


async def check_user_access(client, message, user_id, *, increment: bool = False):
    """Checks user access, handles premium status, and daily limits."""
    if info.DISABLE_PREMIUM:
        return True, "Premium disabled"
    if OWNER_ID and user_id == OWNER_ID:
        return True, "Owner access: Unlimited"

    user_data = await db.get_user_data(user_id)
    #last = user_data.get('last_retrieval_date')
    #count = user_data.get('daily_retrieval_count', 0)

    if not user_data:
        name = message.from_user.first_name if message and message.from_user else f"User {user_id}"
        await db.add_user(user_id, name)
        user_data = await db.get_user_data(user_id)  # ← re-load here!

    # Check for premium status
    if user_data.get('is_premium'):
        activation_date_val = user_data.get('premium_activation_date')
        if activation_date_val:
            activation_date = None
            if isinstance(activation_date_val, str):
                try:
                    activation_date = datetime.fromisoformat(activation_date_val)
                except ValueError:  # Handle cases where date might be in old format or corrupted
                    # Log error or handle as invalid premium state
                    logger.error(f"Invalid premium_activation_date format for user {user_id}: {activation_date_val}")
                    # Fall through to non-premium logic by not setting activation_date
            elif isinstance(activation_date_val, (int, float)):  # Assuming timestamp
                activation_date = datetime.fromtimestamp(activation_date_val)
            elif isinstance(activation_date_val, datetime):  # Already a datetime object
                activation_date = activation_date_val
            else:
                logger.error(f"Unknown premium_activation_date type for user {user_id}: {type(activation_date_val)}")
                # Fall through

            if activation_date:  # If date was successfully parsed
                expiry_date = activation_date + timedelta(days=info.PREMIUM_DURATION_DAYS)
                if datetime.now() > expiry_date:
                    await db.update_premium_status(user_id, False)
                    if message:  # Ensure message object is available to reply
                        try:
                            await message.reply_text(
                                "Your premium subscription has expired. You are now on the free plan.")
                        except Exception as e:
                            logger.error(f"Failed to send premium expiry message to {user_id}: {e}")
                    # Proceed to non-premium check for this session
                else:
                    # Premium is active
                    #await db.increment_retrieval_count(user_id)  # Track usage for premium users
                    return True, "Premium access"
        # If activation_date_val is None or parsing failed, or if premium expired, fall through to non-premium logic

    # Non-premium user logic (or expired premium, or premium with issues)
    raw_last = user_data.get("last_retrieval_date")
    raw_count = user_data.get("daily_retrieval_count", 0)
    if isinstance(raw_last, datetime):
        last_day = raw_last.date()
    elif isinstance(raw_last, str):
        # isoformat or full-datetime string
        last_day = date.fromisoformat(raw_last.split("T")[0])
    elif isinstance(raw_last, date):
        last_day = raw_last
    else:
        last_day = None
    if last_day != date.today():
        raw_count = 0


    if raw_count >= info.NON_PREMIUM_DAILY_LIMIT:
        limit_msg = f"You have reached your daily limit of {info.NON_PREMIUM_DAILY_LIMIT} file retrievals. Upgrade to premium for unlimited access.\nUse /plans command to view premium plans for unlimited access."
        # Check if premium had just expired in this same call
        if user_data.get(
                'is_premium') and 'expiry_date' in locals() and datetime.now() > expiry_date:  # expiry_date would be defined if premium was checked
            limit_msg = f"Your premium has expired and you have now reached your daily limit of {info.NON_PREMIUM_DAILY_LIMIT} file retrievals. Upgrade to premium for unlimited access.\nUse /plans command to view premium plans for unlimited access."
        return False, limit_msg
    if increment:
        new_count = await db.increment_retrieval_count(user_id)
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
        # Optionally add the user if they don't exist, or instruct the owner to have the user start the bot first.
        # For now, let's assume the user must exist.
        return await message.reply_text(
            f"User {user_id_to_add} not found in the database. They need to start the bot first.")

    await db.update_premium_status(user_id_to_add, True)
    # Fetch user's first name to make the message more personal
    try:
        user_info = await client.get_users(user_id_to_add)
        user_mention = user_info.mention if user_info else f"`{user_id_to_add}`"
    except Exception:
        user_mention = f"`{user_id_to_add}`"

    # Log the premium status addition
    admin_id = message.from_user.id
    admin_mention = message.from_user.mention
    log_message_text = (f"➕ **Premium Status Added** ➕\n\n"
                        f"👤 **User:** {user_mention} (`{user_id_to_add}`)\n"
                        f"👑 **Admin:** {admin_mention} (`{admin_id}`)\n"
                        f"⏰ **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    try:
        await client.send_message(chat_id=info.LOG_CHANNEL, text=log_message_text)
    except Exception as e:
        logger.error(f"Failed to send premium add log to LOG_CHANNEL: {e}")

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

    # Log the premium status removal
    admin_id = message.from_user.id
    admin_mention = message.from_user.mention
    log_message_text = (f"➖ **Premium Status Removed** ➖\n\n"
                        f"👤 **User:** {user_mention} (`{user_id_to_remove}`)\n"
                        f"👑 **Admin:** {admin_mention} (`{admin_id}`)\n"
                        f"⏰ **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    try:
        await client.send_message(chat_id=info.LOG_CHANNEL, text=log_message_text)
    except Exception as e:
        logger.error(f"Failed to send premium remove log to LOG_CHANNEL: {e}")

    await message.reply_text(f"Successfully removed premium status from {user_mention}.")
    try:
        await client.send_message(user_id_to_remove, "Your premium status has been removed.")
    except Exception:
        await message.reply_text(f"Could not notify user {user_mention} directly.")


@Client.on_message(filters.command("plans") & filters.private)
async def plans_command(client: Client, message: Message):
    if info.DISABLE_PREMIUM:
        await message.reply_text("Premium features are currently disabled.")
        return
    user_id = message.from_user.id
    user_data = await db.get_user_data(user_id)  # Returns None if user not found

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

    if user_data and user_data.get('is_premium'):
        plan_message_lines.append("✅ You are currently on the **Premium Plan**.")
        activation_date_val = user_data.get('premium_activation_date')
        if activation_date_val:
            activation_date = None
            # Robust date parsing
            if isinstance(activation_date_val, datetime):  # Already a datetime object (preferred)
                activation_date = activation_date_val
            elif isinstance(activation_date_val, date) and not isinstance(activation_date_val,
                                                                          datetime):  # if it's just a date object
                activation_date = datetime.combine(activation_date_val, datetime.min.time())
            elif isinstance(activation_date_val, str):
                try:
                    activation_date = datetime.fromisoformat(activation_date_val)
                except ValueError:
                    try:  # Attempt to parse older timestamp format if isoformat fails
                        activation_date = datetime.fromtimestamp(float(activation_date_val))
                    except ValueError:
                        logger.error(
                            f"Invalid premium_activation_date string format for user {user_id}: {activation_date_val}")
            elif isinstance(activation_date_val, (int, float)):  # Timestamp
                try:
                    activation_date = datetime.fromtimestamp(float(activation_date_val))
                except ValueError:
                    logger.error(
                        f"Invalid premium_activation_date timestamp format for user {user_id}: {activation_date_val}")

            if activation_date:
                expiry_date = activation_date + timedelta(days=PREMIUM_DURATION_DAYS)
                if datetime.now() > expiry_date:
                    plan_message_lines.append("⚠️ Your premium subscription has expired.")
                    # Consider calling db.update_premium_status(user_id, False) if not handled elsewhere reliably
                else:
                    plan_message_lines.append(
                        f"🗓️ Your premium expires on: {expiry_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            else:
                plan_message_lines.append("Could not determine your premium activation date. Please contact support.")
        else:
            plan_message_lines.append("Premium status active, but activation date is missing. Please contact support.")
    else:
        plan_message_lines.append("🆓 You are currently on the **Free Plan**.")
        #Optional: Show current usage for free tier
        daily_limit = NON_PREMIUM_DAILY_LIMIT
        current_usage = 0
        if user_data:  # User might be new and not in db yet, or db.get_user_data might return None
            current_usage = user_data.get('daily_retrieval_count', 0)
            # Ensure last_retrieval_date is today for the count to be relevant
            last_retrieval_date_val = user_data.get('last_retrieval_date')
            retrieval_date_obj = None
            if isinstance(last_retrieval_date_val, datetime):
                retrieval_date_obj = last_retrieval_date_val.date()
            elif isinstance(last_retrieval_date_val, date):
                retrieval_date_obj = last_retrieval_date_val
            if retrieval_date_obj != date.today():
                current_usage = 0  # Reset if not today
        plan_message_lines.append(f"File retrievals today: {current_usage}/{daily_limit}")

    await message.reply_text("\n".join(plan_message_lines), disable_web_page_preview=True)


# @Client.on_message(filters.command("premiumusers") & filters.user(info.ADMINS))
# async def list_premium_users_command(client: Client, message: Message):
#     await message.reply_chat_action(enums.ChatAction.TYPING)
#     all_users_cursor = await db.get_all_users()
#     premium_users_details = []
#
#     # Get current time once for expiry checks
#     now = datetime.now()
#
#     async for user_doc in all_users_cursor:  # Iterate using async for
#         if user_doc.get('is_premium'):
#             user_id = user_doc.get('id')  # In the DB, it's 'id', not '_id' for user documents
#             name = "N/A"
#             username = "N/A"
#
#             try:
#                 # Ensure user_id is an int for get_users
#                 user_info_obj = await client.get_users(int(user_id))
#                 if user_info_obj:
#                     name = user_info_obj.first_name or "N/A"
#                     username = f"@{user_info_obj.username}" if user_info_obj.username else "N/A"
#             except Exception as e:
#                 logger.warning(f"Could not fetch info for user ID {user_id}: {e}")
#
#             expiry_text = "Expiry: Unknown"
#             activation_date_val = user_doc.get('premium_activation_date')
#
#             if activation_date_val:
#                 activation_date = None
#                 if isinstance(activation_date_val, datetime):
#                     activation_date = activation_date_val
#                 elif isinstance(activation_date_val, date) and not isinstance(activation_date_val, datetime):
#                     activation_date = datetime.combine(activation_date_val, datetime.min.time())
#                 elif isinstance(activation_date_val, str):
#                     try:
#                         activation_date = datetime.fromisoformat(activation_date_val)
#                     except ValueError:
#                         try:
#                             activation_date = datetime.fromtimestamp(float(activation_date_val))
#                         except ValueError:
#                             logger.error(
#                                 f"Invalid premium_activation_date string for user {user_id} in premiumusers: {activation_date_val}")
#                 elif isinstance(activation_date_val, (int, float)):
#                     try:
#                         activation_date = datetime.fromtimestamp(float(activation_date_val))
#                     except ValueError:
#                         logger.error(
#                             f"Invalid premium_activation_date timestamp for user {user_id} in premiumusers: {activation_date_val}")
#
#                 if activation_date:
#                     expiry_date = activation_date + timedelta(days=PREMIUM_DURATION_DAYS)
#                     status = "Expired" if now > expiry_date else "Active"
#                     expiry_text = f"Expires: {expiry_date.strftime('%Y-%m-%d %H:%M:%S UTC')} ({status})"
#                 else:
#                     expiry_text = "Expiry: Invalid activation date"
#             else:
#                 expiry_text = "Expiry: No activation date"
#
#             premium_users_details.append(f"ID: `{user_id}` | Name: {name} | User: {username} | {expiry_text}")
#
#     if not premium_users_details:
#         reply_message_text = "No premium users found."
#     else:
#         reply_message_text = "👑 **Premium Users List** 👑\n\n" + "\n".join(premium_users_details)
#
#     if len(reply_message_text) > 4096:
#         try:
#             with open("premium_users.txt", "w", encoding="utf-8") as f:
#                 # Use the raw list for the file content for better readability
#                 file_content = "Premium Users List\n\n" + "\n".join(premium_users_details)
#                 f.write(file_content)
#             await message.reply_document("premium_users.txt", caption="List of all premium users.")
#             if os.path.exists("premium_users.txt"):  # Ensure file exists before removing
#                 os.remove("premium_users.txt")
#         except Exception as e:
#             logger.error(f"Error creating or sending premium users file: {e}")
#             await message.reply_text("Error generating premium users list file.")
#     else:
#         await message.reply_text(reply_message_text, disable_web_page_preview=True)

@Client.on_message(filters.command("premiumusers") & filters.user(info.ADMINS))
async def list_premium_users_command(client: Client, message: Message):
    # Indicate typing action
    #await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    # Fetch all users (returns a list)
    all_users = await db.get_all_users()
    premium_users_details = []

    now = datetime.utcnow()

    for user_doc in all_users:
        if not user_doc.get('is_premium'):
            continue

        user_id = user_doc.get('id')
        name = "N/A"
        username = "N/A"

        # Try to fetch their Telegram info
        try:
            user_info_obj = await client.get_users(int(user_id))
            if user_info_obj:
                name = user_info_obj.first_name or "N/A"
                username = f"@{user_info_obj.username}" if user_info_obj.username else "N/A"
        except Exception as e:
            logger.warning(f"Could not fetch info for user ID {user_id}: {e}")

        # Determine expiry
        expiry_text = "Expiry: Unknown"
        act_val = user_doc.get('premium_activation_date')

        activation_date = None
        if isinstance(act_val, datetime):
            activation_date = act_val
        elif isinstance(act_val, date) and not isinstance(act_val, datetime):
            activation_date = datetime.combine(act_val, datetime.min.time())
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

    # Build reply
    if not premium_users_details:
        await message.reply_text("No premium users found.")
        return

    header = "👑 **Premium Users List** 👑\n\n"
    body = "\n".join(premium_users_details)
    full_text = header + body

    # Telegram message limit is 4096 chars
    if len(full_text) <= 4096:
        await message.reply_text(full_text, disable_web_page_preview=True)
    else:
        # Write to a temp file and send as document
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


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [[
            InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ ➕', url=f"https://t.me/{temp.U_NAME}?startgroup=true")
        ], [
            InlineKeyboardButton('ᴏᴡɴᴇʀ', callback_data="owner_info"),
            InlineKeyboardButton('Request Group', url=f"https://t.me/{info.SUPPORT_CHAT}")
        ], [
            InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about')
        ], [
            InlineKeyboardButton('ꜱᴇᴀʀᴄʜ ᴅʀᴀᴍᴀꜱ', switch_inline_query_current_chat='')
        ],
            #[InlineKeyboardButton("🔞 Adult Content Channel", url="https://t.me/eseoaOF")],
            [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")], ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(
            script.START_TXT.format(message.from_user.mention if message.from_user else message.chat.title, info.NON_PREMIUM_DAILY_LIMIT), reply_markup=reply_markup)
        await asyncio.sleep(2)
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

    if len(message.command) != 2:
        buttons = [[
            InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ ➕', url=f"https://t.me/{temp.U_NAME}?startgroup=true")
        ], [
            InlineKeyboardButton('ᴏᴡɴᴇʀ', callback_data="owner_info"),
            InlineKeyboardButton('Request Group', url=f"https://t.me/{info.SUPPORT_CHAT}")
        ], [
            InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about'),
        ], [
            InlineKeyboardButton('ꜱᴇᴀʀᴄʜ ᴅʀᴀᴍᴀꜱ', switch_inline_query_current_chat='')
        ],
            #[InlineKeyboardButton("🔞 Adult Content Channel", url="https://t.me/eseoaOF")],
            [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=random.choice(info.PICS),
            caption=script.START_TXT.format(message.from_user.mention, info.NON_PREMIUM_DAILY_LIMIT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        # No file access here, so no check_user_access needed yet
        return  # Exit if it's just a /start command without arguments

    # From here, message.command[1] is expected to exist.
    # This is where file access logic begins, so place check_user_access upfront for single file logic.
    # For multi-file logic (batch, all), the check will be inside their loops.

    data = message.command[1]
    try:
        pre, file_id_check = data.split('_', 1)
    except:
        file_id_check = data  # data itself is the file_id or another command like "BATCH-xxx"
        pre = ""

    # Only apply general access check if it's potentially a direct file request
    # BATCH, DSTORE, and "all" will have checks inside their loops
    is_direct_file_request = not (data.startswith("all") or data.split("-", 1)[0] in ["BATCH", "DSTORE"])

    if is_direct_file_request:
        can_access, reason = await check_user_access(client, message, user_id,increment=False)
        if not can_access:
            await message.reply_text(reason)
            return
    if is_direct_file_request:
        can_access, reason = await check_user_access(client, message, user_id,increment=True)
        if not can_access:
            await message.reply_text(reason)
            return

    if info.AUTH_CHANNEL and not await is_subscribed(client, message):
        try:
            invite_link = await client.create_chat_invite_link(int(info.AUTH_CHANNEL))
        except ChatAdminRequired:
            logger.error("Make sure Bot is admin in Force Sub channel")
        btn = [
            [
                InlineKeyboardButton(
                    "🤖 𝖩𝗈𝗂𝗇 𝖴𝗉𝖽𝖺𝗍𝖾𝗌 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 🤖", url=invite_link.invite_link
                )
            ]
        ]

        if message.command[1] != "subscribe" or message.command[1] != "send_all":
            try:
                kk, file_id = message.command[1].split("_", 1)
                pre = 'checksubp' if kk == 'filep' else 'checksub'
                btn.append([InlineKeyboardButton("⟳ 𝖳𝗋𝗒 𝖠𝗀𝖺𝗂𝗇 ⟳", callback_data=f"{pre}#{file_id}")])
            except (IndexError, ValueError):
                btn.append([InlineKeyboardButton("⟳ 𝖳𝗋𝗒 𝖠𝗀𝖺𝗂𝗇 ⟳",
                                                 url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}")])
        await client.send_message(
            chat_id=user_id,
            text="**Please Join My Updates Channel to use this Bot!**",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return  # Stop further processing if force sub is triggered

    if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay",
                                                            "help"]:  # these are not file requests
        buttons = [[
            InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ ➕', url=f"https://t.me/{temp.U_NAME}?startgroup=true")
        ], [
            InlineKeyboardButton('ᴏᴡɴᴇʀ', callback_data="owner_info"),
            InlineKeyboardButton('Request Group', url=f"https://t.me/{info.SUPPORT_CHAT}")
        ], [
            InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about')
        ], [
            InlineKeyboardButton('ꜱᴇᴀʀᴄʜ ᴅʀᴀᴍᴀꜱ', switch_inline_query_current_chat='')

        ],
            #[InlineKeyboardButton("🔞 Adult Content Channel", url="https://t.me/eseoaOF")],
            [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=random.choice(info.PICS),
            caption=script.START_TXT.format(message.from_user.mention, info.NON_PREMIUM_DAILY_LIMIT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    # data = message.command[1] # already defined
    # try: # already defined
    #     pre, file_id = data.split('_', 1)
    # except:
    #     file_id = data
    #     pre = ""

    if data.startswith("all"):
        _, key, pre_type = data.split("_", 2)  # pre_type to avoid conflict with outer 'pre'
        files = temp.FILES_IDS.get(key)
        if not files:
            await message.reply('<b><i>No such file exist.</b></i>')
            return  # Added return

        for file_item in files:  # Renamed to file_item
            # Access check for each file in the "all" list
            can_access, reason = await check_user_access(client, message, user_id,increment=False)
            if not can_access:
                await message.reply_text(f"Access denied for {file_item.file_name}: {reason}")
                return
                #continue  # Skip this file
            title = file_item.file_name
            size = get_size(file_item.file_size)
            f_caption = None
            f_caption = None
            if info.KEEP_ORIGINAL_CAPTION:
                try:
                    f_caption = file_item.caption
                except:
                    f_caption = file_item.file_name
            elif info.CUSTOM_FILE_CAPTION:
                try:
                    f_caption = info.CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                                file_size='' if size is None else size,
                                                                file_caption='' if getattr(file_item, 'caption',
                                                                                           None) is None else file_item.caption)
                except:
                    f_caption = getattr(file_item, 'caption', file_item.file_name)  # Fallback
            if f_caption is None:
                f_caption = f"{file_item.file_name}"
            ok, reason = await check_user_access(client, message, user_id, increment=True)
            if not ok:
                await message.reply_text(f"Access denied for {file_item.file_name}: {reason}")
                return
            await client.send_cached_media(
                chat_id=user_id,
                file_id=file_item.file_id,
                caption=f_caption,
                protect_content=True if pre_type == 'filep' else False,  # Use pre_type
                parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION else enums.ParseMode.DEFAULT,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL)],
                                                   [InlineKeyboardButton("🍺 Buy Me A Beer",
                                                                         url="https://buymeacoffee.com/matthewmurdock001")],
                                                   ]),
            )
        return  # Added return after processing "all"

    if data.split("-", 1)[0] == "BATCH":
        sts = await message.reply("<b>Processing batch...</b>")
        batch_file_id = data.split("-", 1)[1]  # Renamed to batch_file_id
        msgs = BATCH_FILES.get(batch_file_id)
        if not msgs:
            # file_id was from pre, file_id = data.split('_', 1) or file_id = data
            # This part of the code seems to have a bug if `data` was "BATCH-somebatchfileid",
            # then `file_id` would be undefined here.
            # It should use `batch_file_id` for downloading.
            download_target_id = batch_file_id
            try:
                file_path = await client.download_media(download_target_id)
                if file_path:  # download_media returns path on success
                    with open(file_path) as file_data:
                        msgs = json.loads(file_data.read())
                    os.remove(file_path)
                    BATCH_FILES[batch_file_id] = msgs  # Store with the correct ID
                else:
                    raise Exception("Download failed, no path returned.")
            except FileNotFoundError:
                logger.error(f"Batch file (ID: {download_target_id}) not found after attempting download.")
                await sts.edit("FAILED: Batch file definition not found.")
                return
            except json.JSONDecodeError:
                logger.error(f"Batch file (ID: {download_target_id}) is not a valid JSON.")
                await sts.edit("FAILED: Batch file format error.")
                if file_path and os.path.exists(file_path):  # Clean up if download happened but was invalid
                    os.remove(file_path)
                return
            except Exception as e:
                logger.error(f"Failed to load batch file (ID: {download_target_id}): {e}", exc_info=True)
                await sts.edit("FAILED: Could not process batch file.")
                if 'file_path' in locals() and file_path and os.path.exists(file_path):  # Clean up
                    os.remove(file_path)
                return

        if not msgs:  # Check again if msgs could not be loaded
            await sts.edit("FAILED: Batch data unavailable.")
            return

        for msg_item in msgs:  # Renamed to msg_item
            # Access check for each file in BATCH
            can_access, reason = await check_user_access(client, message, user_id, increment=False)
            if not can_access:
                await message.reply_text(
                    f"Access denied for file in batch: {reason} (File: {msg_item.get('title', 'N/A')})")
                return


            title = msg_item.get("title")
            size = get_size(int(msg_item.get("size", 0)))
            f_caption = None
            if info.KEEP_ORIGINAL_CAPTION:
                try:
                    f_caption = msg_item.get("caption")
                except:
                    f_caption = msg_item.get("title")
            elif info.BATCH_FILE_CAPTION:
                try:
                    f_caption = info.BATCH_FILE_CAPTION.format(file_name='' if title is None else title,
                                                               file_size='' if size is None else size,
                                                               file_caption='' if msg_item.get(
                                                                   "caption") is None else msg_item.get("caption"))
                except Exception as e:
                    logger.exception(e)
                    f_caption = msg_item.get("caption", title)  # Fallback
            if f_caption is None:
                f_caption = f"{title}"
            ok, reason = await check_user_access(client, message, user_id, increment=True)
            if not ok:
                await message.reply_text(
                    f"Access denied for file in batch: {reason} (File: {msg_item.get('title', 'N/A')})")
                return
            try:
                await client.send_cached_media(
                    chat_id=user_id,
                    file_id=msg_item.get("file_id"),
                    caption=f_caption,
                    protect_content=msg_item.get('protect', False),
                    parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION else enums.ParseMode.DEFAULT,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL)],
                         [InlineKeyboardButton("🍺 Buy Me A Beer",
                                               url="https://buymeacoffee.com/matthewmurdock001")],
                         ]),
                )
            except FloodWait as e:
                await asyncio.sleep(e.x)
                logger.warning(f"Floodwait of {e.x} sec.")
                await client.send_cached_media(
                    chat_id=user_id,
                    file_id=msg_item.get("file_id"),
                    caption=f_caption,
                    parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION else enums.ParseMode.DEFAULT,
                    protect_content=msg_item.get('protect', False),
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL)],
                         [InlineKeyboardButton("🍺 Buy Me A Beer",
                                               url="https://buymeacoffee.com/matthewmurdock001")],
                         ]),
                )
            except Exception as e:
                logger.warning(e, exc_info=True)
                continue
            await asyncio.sleep(1)
        await sts.delete()
        return  # Added return

    elif data.split("-", 1)[0] == "DSTORE":
        sts = await message.reply("<b>Processing stored files...</b>")
        b_string = data.split("-", 1)[1]
        decoded = (base64.urlsafe_b64decode(b_string + "=" * (-len(b_string) % 4))).decode("ascii")
        try:
            f_msg_id, l_msg_id, f_chat_id, protect = decoded.split("_", 3)
        except:
            f_msg_id, l_msg_id, f_chat_id = decoded.split("_", 2)
            protect = "/pbatch" if info.PROTECT_CONTENT else "batch"
        diff = int(l_msg_id) - int(f_msg_id)
        async for dstore_msg_item in client.iter_messages(int(f_chat_id), int(l_msg_id), int(f_msg_id)):  # Renamed
            # Access check for each file in DSTORE
            can_access, reason = await check_user_access(client, message, user_id,increment=False)
            if not can_access:
                # Cannot easily get file name here before copying, so generic message
                await message.reply_text(f"Access denied for a file in stored batch: {reason}")
                return
            ok, reason = await check_user_access(client, message, user_id, increment=True)
            if not ok:
                await message.reply_text(f"Access denied for a file in stored batch: {reason}")
                return
            if dstore_msg_item.media:
                media = getattr(dstore_msg_item, dstore_msg_item.media.value)
                f_caption = None
                if info.KEEP_ORIGINAL_CAPTION:
                    try:
                        f_caption = getattr(dstore_msg_item, 'caption', '')
                    except:
                        f_caption = getattr(media, 'file_name', '')
                elif info.BATCH_FILE_CAPTION:  # Using BATCH_FILE_CAPTION for DSTORE as well
                    try:
                        f_caption = info.BATCH_FILE_CAPTION.format(file_name=getattr(media, 'file_name', ''),
                                                                   file_size=getattr(media, 'file_size', 0),
                                                                   file_caption=getattr(dstore_msg_item, 'caption', ''))
                    except Exception as e:
                        logger.exception(e)
                        f_caption = getattr(dstore_msg_item, 'caption', '')
                else:  # Fallback
                    file_name = getattr(media, 'file_name', '')
                    f_caption = getattr(dstore_msg_item, 'caption', file_name)
                try:
                    await dstore_msg_item.copy(user_id, caption=f_caption,
                                               protect_content=True if protect == "/pbatch" else False)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await dstore_msg_item.copy(user_id, caption=f_caption,
                                               protect_content=True if protect == "/pbatch" else False)
                except Exception as e:
                    logger.exception(e)
                    continue
            elif dstore_msg_item.empty:
                continue
            else:  # Non-media message
                try:
                    await dstore_msg_item.copy(user_id, protect_content=True if protect == "/pbatch" else False)
                except FloodWait as e:
                    await asyncio.sleep(e.x)
                    await dstore_msg_item.copy(user_id, protect_content=True if protect == "/pbatch" else False)
                except Exception as e:
                    logger.exception(e)
                    continue
            await asyncio.sleep(1)
        await sts.delete()
        return  # Added return

    # This is the final block for single file requests (direct or base64 encoded)
    # The user access check was already performed if is_direct_file_request was true.
    # If it was a BATCH/DSTORE/all, it would have returned by now.

    actual_file_id = None
    actual_pre = pre  # Use the 'pre' from initial parsing of 'data'

    files_ = await get_file_details(file_id_check)  # Use file_id_check from initial parsing
    if not files_:
        try:
            # Attempt to decode if it wasn't a direct match
            decoded_data = (base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")
            actual_pre, actual_file_id = decoded_data.split("_", 1)
            files_ = await get_file_details(actual_file_id)  # Try fetching with decoded ID
        except Exception:  # Includes ValueError from split, or BinasciiError
            await message.reply('<b><i>No such file exist (error during decoding or final lookup).</b></i>')
            return

    if not files_:
        await message.reply('<b><i>No such file exist.</b></i>')
        return

    # If we reached here, files_ is populated, either from direct file_id_check or decoded actual_file_id
    # The access check for direct file_id_check (is_direct_file_request) was done at the top.
    # If it was a decoded one, the check might not have been done if it didn't look like a direct request initially.
    # However, the current structure of check at the top should cover it if it's not BATCH/DSTORE/all.

    # Let's ensure actual_file_id and actual_pre are set correctly for sending
    if not actual_file_id:  # If not set by decoding block, it means original file_id_check was used
        actual_file_id = file_id_check
        # 'actual_pre' is already 'pre'

    # Send the file using 'actual_file_id' and 'actual_pre'
    db_file_entry = files_[0]  # Assuming get_file_details returns a list
    title = db_file_entry.file_name
    size = get_size(db_file_entry.file_size)
    f_caption = db_file_entry.caption  # Original caption from DB

    # Apply custom caption logic
    if info.KEEP_ORIGINAL_CAPTION:
        # f_caption is already what we want
        pass
    elif info.CUSTOM_FILE_CAPTION:
        try:
            f_caption = info.CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                        file_size='' if size is None else size,
                                                        file_caption='' if f_caption is None else f_caption)
        except Exception as e:
            logger.exception(e)
            # Keep original f_caption if template fails

    if f_caption is None:  # Fallback if all else fails
        f_caption = f"{title}"

    await client.send_cached_media(
        chat_id=user_id,
        file_id=actual_file_id,
        caption=f_caption,
        parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION or info.CUSTOM_FILE_CAPTION else enums.ParseMode.DEFAULT,
        # Adjusted condition
        protect_content=True if actual_pre == 'filep' else False,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL)],
                                           # [InlineKeyboardButton("🔞 Adult Content Channel",
                                           #                       url="https://t.me/eseoaOF")],
                                           [InlineKeyboardButton("🍺 Buy Me A Beer",
                                                                 url="https://buymeacoffee.com/matthewmurdock001")],
                                           ]),
    )


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

    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None:
            break
    else:
        await msg.edit('This is not supported file format')

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
async def settings(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                return await message.reply_text("Make sure I'm present in your group!!", quote=True)

        else:
            return await message.reply_text("I'm not connected to any groups!", quote=True)


    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title

    else:
        return None

    st = await client.get_chat_member(grp_id, userid)
    if (
            st.status != enums.ChatMemberStatus.ADMINISTRATOR
            and st.status != enums.ChatMemberStatus.OWNER
            and str(userid) not in info.ADMINS
    ):
        return None

    settings = await get_settings(grp_id)

    try:
        if settings['max_btn']:
            settings = await get_settings(grp_id)
    except KeyError:
        await save_group_settings(grp_id, 'max_btn', False)
        settings = await get_settings(grp_id)

    if settings is not None:
        buttons = [
            [
                InlineKeyboardButton(
                    '𝖥𝗂𝗅𝗍𝖾𝗋 𝖡𝗎𝗍𝗍𝗈𝗇',
                    callback_data=f'setgs#button#{settings["button"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '𝖲𝗂𝗇𝗀𝗅𝖾 𝖡𝗎𝗍𝗍𝗈𝗇' if settings["button"] else '𝖣𝗈𝗎𝖻𝗅𝖾',
                    callback_data=f'setgs#button#{settings["button"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖥𝗂𝗅𝖾 𝖲𝖾𝗇𝖽 𝖬𝗈𝖽𝖾',
                    callback_data=f'setgs#botpm#{settings["botpm"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '𝖬𝖺𝗇𝗎𝖺𝗅 𝖲𝗍𝖺𝗋𝗍' if settings["botpm"] else '𝖠𝗎𝗍𝗈 𝖲𝖾𝗇𝖽',
                    callback_data=f'setgs#botpm#{settings["botpm"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖯𝗋𝗈𝗍𝖾𝖼𝗍 𝖢𝗈𝗇𝗍𝖾𝗇𝗍',
                    callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ 𝖮𝗇' if settings["file_secure"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖨𝖬𝖣𝖻',
                    callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ 𝖮𝗇' if settings["imdb"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖲𝗉𝖾𝗅𝗅 𝖢𝗁𝖾𝖼𝗄',
                    callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ 𝖮𝗇' if settings["spell_check"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖬𝖾𝗌𝗌𝖺𝗀𝖾',
                    callback_data=f'setgs#welcome#{settings["welcome"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ 𝖮𝗇' if settings["welcome"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#welcome#{settings["welcome"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖠𝗎𝗍𝗈 𝖣𝖾𝗅𝖾𝗍𝖾',
                    callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '5 𝖬𝗂𝗇' if settings["auto_delete"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖠𝗎𝗍𝗈-𝖥𝗂𝗅𝗍𝖾𝗋',
                    callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ 𝖮𝗇' if settings["auto_ffilter"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖬𝖺𝗑 𝖡𝗎𝗍𝗍𝗈𝗇𝗌',
                    callback_data=f'setgs#max_btn#{settings["max_btn"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '10' if settings["max_btn"] else f'{info.MAX_B_TN}',
                    callback_data=f'setgs#max_btn#{settings["max_btn"]}#{grp_id}',
                ),
            ],
        ]

        btn = [[
            InlineKeyboardButton("⬇ 𝖮𝗉𝖾𝗇 𝖧𝖾𝗋𝖾 ⬇", callback_data=f"opnsetgrp#{grp_id}"),
            InlineKeyboardButton("➡ 𝖮𝗉𝖾𝗇 𝗂𝗇 𝖯𝖬 ➡", callback_data=f"opnsetpm#{grp_id}")
        ]]

        reply_markup = InlineKeyboardMarkup(buttons)
        if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            await message.reply_text(
                text="<b>𝖣𝗈 𝖸𝗈𝗎 𝖶𝖺𝗇𝗍 𝖳𝗈 𝖮𝗉𝖾𝗇 𝖲𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝖧𝖾𝗋𝖾 ?</b>",
                reply_markup=InlineKeyboardMarkup(btn),
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
async def send_msg(bot, message):
    if message.reply_to_message:
        target_id = message.text
        command = ["/send"]
        out = "Users Saved In DB Are:\n\n"
        for cmd in command:
            if cmd in target_id:
                target_id = target_id.replace(cmd, "")
        success = False
        try:
            user = await bot.get_users(target_id)
            users = await db.get_all_users()
            async for usr in users:
                out += f"{usr['id']}"
                out += '\n'
            if str(user.id) in str(out):
                await message.reply_to_message.copy(int(user.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>Your message has been successfully send to {user.mention}.</b>")
            else:
                await message.reply_text("<b>This user didn't started this bot yet !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error: {e}</b>")
    else:
        await message.reply_text(
            "<b>Use this command as a reply to any message using the target chat id. For eg: /send userid</b>")


@Client.on_message(filters.command('set_template'))
async def save_template(client, message):
    sts = await message.reply("Checking template")
    userid = message.from_user.id if message.from_user else None
    if not userid:
        await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title

    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
            st.status != enums.ChatMemberStatus.ADMINISTRATOR
            and st.status != enums.ChatMemberStatus.OWNER
            and str(userid) not in info.ADMINS
    ):
        return

    if len(message.command) < 2:
        await sts.edit("No Input!!")
    template = message.text.split(" ", 1)[1]
    await save_group_settings(grp_id, 'template', template)
    await sts.edit(f"Successfully changed template for {title} to\n\n{template}")


# @Client.on_message((filters.command(["request", "Request"]) | filters.regex("#request") | filters.regex("#Request")) & filters.group)
# async def requests(bot, message):
#     if REQST_CHANNEL is None or SUPPORT_CHAT_ID is None: return # Must add REQST_CHANNEL and SUPPORT_CHAT_ID to use this feature
#     if message.from_user:
#         reporter = str(message.from_user.id)
#         mention = str(message.from_user.mention)
#     elif message.sender_chat:
#         reporter = str(message.sender_chat.id)
#         mention = str(message.sender_chat.mention)
#     else:
#         await message.reply_text("<b>Unable to process the request: Missing user or channel information.</b>")
#         return
#     success = True
#     if message.reply_to_message and SUPPORT_CHAT_ID == message.chat.id:
#         chat_id = message.chat.id
#         #reporter = str(message.from_user.id)
#         #mention = message.from_user.mention
#         #success = True
#         content = message.reply_to_message.text
#         try:
#             if REQST_CHANNEL is not None:
#                 btn = [[
#                         InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.reply_to_message.link}"),
#                         InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
#                       ]]
#                 reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
#                 success = True
#             elif len(content) >= 3:
#                 for admin in ADMINS:
#                     btn = [[
#                         InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.reply_to_message.link}"),
#                         InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
#                       ]]
#                     reported_post = await bot.send_message(chat_id=admin, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
#                     success = True
#             else:
#                 if len(content) < 3:
#                     await message.reply_text("<b>You must type about your request [Minimum 3 Characters]. Requests can't be empty.</b>")
#             if len(content) < 3:
#                 success = False
#         except Exception as e:
#             await message.reply_text(f"Error: {e}")
#             pass
#
#     elif SUPPORT_CHAT_ID == message.chat.id:
#         chat_id = message.chat.id
#         reporter = str(message.from_user.id)
#         mention = message.from_user.mention
#         success = True
#         content = message.text
#         keywords = ["#request", "/request", "#Request", "/Request"]
#         for keyword in keywords:
#             if keyword in content:
#                 content = content.replace(keyword, "")
#         try:
#             if REQST_CHANNEL is not None and len(content) >= 3:
#                 btn = [[
#                         InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.link}"),
#                         InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
#                       ]]
#                 reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
#                 success = True
#             elif len(content) >= 3:
#                 for admin in ADMINS:
#                     btn = [[
#                         InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.link}"),
#                         InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
#                       ]]
#                     reported_post = await bot.send_message(chat_id=admin, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
#                     success = True
#             else:
#                 if len(content) < 3:
#                     await message.reply_text("<b>You must type about your request [Minimum 3 Characters]. Requests can't be empty.</b>")
#             if len(content) < 3:
#                 success = False
#         except Exception as e:
#             await message.reply_text(f"Error: {e}")
#             pass
#
#     else:
#         success = False
#
#     if success:
#         btn = [[
#                 InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{reported_post.link}")
#               ]]
#         await message.reply_text("<b>Your request has been added! Please wait for some time.</b>", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(
    (filters.command(["request", "Request"]) | filters.regex("#request") | filters.regex("#Request"))
    & filters.group
)
async def requests(bot, message):
    # Preliminary check: Ensure that SUPPORT_CHAT_ID and REQST_CHANNEL are defined when required.
    if info.REQST_CHANNEL is None or info.SUPPORT_CHAT_ID is None:
        return

    reported_post = None

    # Safely retrieve the reporter and mention
    if message.from_user:
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
    elif message.sender_chat:
        await message.reply_text("<b>Anonymous users or channels cannot request. Please use original user profile</b>")
        return
        # Fallback for channel posts or anonymous messages
        #reporter = str(message.sender_chat.id)
        #mention = message.sender_chat.title
    else:
        await message.reply_text("<b>Unable to process the request: Missing user or channel information.</b>")
        return

    success = True
    # Depending on the context of the message, determine the content and handle accordingly:
    if message.reply_to_message and info.SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        content = message.reply_to_message.text
        try:
            if len(content) < 3:
                await message.reply_text(
                    "<b>You must type about your request [Minimum 3 Characters]. Requests can't be empty.</b>")
                success = False
            elif info.REQST_CHANNEL is not None:
                btn = [[
                    InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.reply_to_message.link}"),
                    InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
                ]]
                reported_post = await bot.send_message(
                    chat_id=info.REQST_CHANNEL,
                    text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            else:
                # Optionally send to ADMINS if REQST_CHANNEL is not defined
                for admin in info.ADMINS:
                    btn = [[
                        InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.reply_to_message.link}"),
                        InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
                    ]]
                    reported_post = await bot.send_message(
                        chat_id=admin,
                        text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            return

    elif info.SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        content = message.text
        # Remove keywords before processing
        for keyword in ["#request", "/request", "#Request", "/Request"]:
            content = content.replace(keyword, "")
        try:
            if len(content) < 3:
                await message.reply_text(
                    "<b>You must type about your request [Minimum 3 Characters]. Requests can't be empty.</b>")
                return
            if info.REQST_CHANNEL is not None:
                btn = [[
                    InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.link}"),
                    InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
                ]]
                reported_post = await bot.send_message(
                    chat_id=info.REQST_CHANNEL,
                    text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            else:
                for admin in info.ADMINS:
                    btn = [[
                        InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.link}"),
                        InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
                    ]]
                    reported_post = await bot.send_message(
                        chat_id=admin,
                        text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            return

    else:
        # If message context doesn't match expected sources, simply exit
        return

    # Acknowledge successful request submission
    # if success:
    #     if reported_post is None:
    #         # If reported_post was never assigned, handle the error gracefully.
    #         await message.reply_text("Error: Unable to process your request. Please try again later.")
    #         return
    #     btn = [[
    #         InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{reported_post.link}")
    #     ]]
    #     await message.reply_text("<b>Your request has been added! Please wait for some time.</b>", reply_markup=InlineKeyboardMarkup(btn))


@Client.on_message(filters.command("usend") & filters.user(info.ADMINS))
async def send_msg(bot, message):
    if message.reply_to_message:
        target_id = message.text.split(" ", 1)[1]
        out = "Users Saved In DB Are:\n\n"
        success = False
        try:
            user = await bot.get_users(target_id)
            users = await db.get_all_users()
            async for usr in users:
                out += f"{usr['id']}"
                out += '\n'
            if str(user.id) in str(out):
                await message.reply_to_message.copy(int(user.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>𝖸𝗈𝗎𝗋 𝖬𝖾𝗌𝗌𝖺𝗀𝖾 𝖧𝖺𝗌 𝖲𝗎𝖼𝖼𝖾𝗌𝗌𝖿𝗎𝗅𝗅𝗒 𝖲𝖾𝗇𝗍 𝖳𝗈 {user.mention}.</b>")
            else:
                await message.reply_text("<b>An Error Occurred !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error :- <code>{e}</code></b>")
    else:
        await message.reply_text("<b>Error𝖢𝗈𝗆𝗆𝖺𝗇𝖽 𝖨𝗇𝖼𝗈𝗆𝗉𝗅𝖾𝗍𝖾 !</b>")


@Client.on_message(filters.command("send") & filters.user(info.ADMINS))
async def send_msg(bot, message):
    if message.reply_to_message:
        target_id = message.text.split(" ", 1)[1]
        out = "Users Saved In DB Are:\n\n"
        success = False
        try:
            user = await bot.get_users(target_id)
            users = await db.get_all_users()
            async for usr in users:
                out += f"{usr['id']}"
                out += '\n'
            if str(user.id) in str(out):
                await message.reply_to_message.copy(int(user.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>Your message has been successfully send to {user.mention}.</b>")
            else:
                await message.reply_text("<b>This user didn't started this bot yet !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error: {e}</b>")
    else:
        await message.reply_text(
            "<b>Use this command as a reply to any message using the target chat id. For eg: /send userid</b>")


@Client.on_message(filters.command("gsend") & filters.user(info.ADMINS))
async def send_chatmsg(bot, message):
    if message.reply_to_message:
        target_id = message.text.split(" ", 1)[1]
        out = "Chats Saved In DB Are:\n\n"
        success = False
        try:
            chat = await bot.get_chat(target_id)
            chats = await db.get_all_chats()
            async for cht in chats:
                out += f"{cht['id']}"
                out += '\n'
            if str(chat.id) in str(out):
                await message.reply_to_message.copy(int(chat.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>Your message has been successfully send to <code>{chat.id}</code>.</b>")
            else:
                await message.reply_text("<b>An Error Occurred !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error :- <code>{e}</code></b>")
    else:
        await message.reply_text("<b>Error𝖢𝗈𝗆𝗆𝖺𝗇𝖽 𝖨𝗇𝖼𝗈𝗆𝗉𝗅𝖾𝗍𝖾 !</b>")


@Client.on_message(filters.command("deletefiles") & filters.user(info.ADMINS))
async def deletemultiplefiles(bot, message):
    chat_type = message.chat.type
    if chat_type != enums.ChatType.PRIVATE:
        return await message.reply_text(
            f"<b>Hey {message.from_user.mention}, This command won't work in groups. It only works on my PM !</b>")
    else:
        pass
    try:
        keyword = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text(
            f"<b>Hey {message.from_user.mention}, Give me a keyword along with the command to delete files.</b>")
    k = await bot.send_message(chat_id=message.chat.id,
                               text=f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
    files, total = await get_bad_files(keyword)
    await k.edit_text(
        f"<b>Found {total} files for your query {keyword} !\n\nFile deletion process will start in 5 seconds !</b>")
    await asyncio.sleep(5)
    deleted = 0
    for file in files:
        await k.edit_text(
            f"<b>Process started for deleting files from DB. Successfully deleted {str(deleted)} files from DB for your query {keyword} !\n\nPlease wait...</b>")
        file_ids = file.file_id
        file_name = file.file_name
        result = await Media.collection.delete_one({
            '_id': file_ids,
        })
        if result.deleted_count:
            logger.info(f'File Found for your query {keyword}! Successfully deleted {file_name} from database.')
        deleted += 1
    await k.edit_text(
        text=f"<b>Process Completed for file deletion !\n\nSuccessfully deleted {str(deleted)} files from database for your query {keyword}.</b>")


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
    file_type = replied.media
    if file_type not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
        return await message.reply("Reply to a supported media")
    if message.has_protected_content and message.chat.id not in info.ADMINS:
        return await message.reply("okDa")
    file_id, ref = unpack_new_file_id((getattr(replied, file_type.value)).file_id)
    string = 'filep_' if message.text.lower().strip() == "/plink" else 'file_'
    string += file_id
    outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
    await message.reply(f"Here is your Link:\nhttps://t.me/{temp.U_NAME}?start={outstr}")


@Client.on_message(filters.command(['batch', 'pbatch']) & filters.create(allowed))
async def gen_link_batch(bot, message):
    if " " not in message.text:
        return await message.reply(
            "Use correct format.\nExample <code>/batch https://t.me/kdramaworld_ongoing/10 https://t.me/kdramaworld_ongoing/20</code>.")
    links = message.text.strip().split(" ")
    if len(links) != 3:
        return await message.reply(
            "Use correct format.\nExample <code>/batch https://t.me/kdramaworld_ongoing/10 https://t.me/kdramaworld_ongoing/20</code>.")
    cmd, first, last = links
    regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
    match = regex.match(first)
    if not match:
        return await message.reply('Invalid link')
    f_chat_id = match.group(4)
    f_msg_id = int(match.group(5))
    if f_chat_id.isnumeric():
        f_chat_id = int(("-100" + f_chat_id))
    match = regex.match(last)
    if not match:
        return await message.reply('Invalid link')
    l_chat_id = match.group(4)
    l_msg_id = int(match.group(5))
    if l_chat_id.isnumeric():
        l_chat_id = int(("-100" + l_chat_id))

    if f_chat_id != l_chat_id:
        return await message.reply("Chat ids not matched.")
    try:
        chat_id = (await bot.get_chat(f_chat_id)).id
    except ChannelInvalid:
        return await message.reply(
            'This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        return await message.reply(f'Errors - {e}')

    sts = await message.reply("Generating link for your message.\nThis may take time depending upon number of messages")
    if chat_id in info.FILE_STORE_CHANNEL:
        string = f"{f_msg_id}_{l_msg_id}_{chat_id}_{cmd.lower().strip()}"
        b_64 = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
        return await sts.edit(f"Here is your link https://t.me/{temp.U_NAME}?start=DSTORE-{b_64}")

    FRMT = "Generating Link...\nTotal Messages: `{total}`\nDone: `{current}`\nRemaining: `{rem}`\nStatus: `{sts}`"

    outlist = []

    # file store without db channel
    og_msg = 0
    tot = 0
    async for msg in bot.iter_messages(f_chat_id, l_msg_id, f_msg_id):
        tot += 1
        if msg.empty or msg.service:
            continue
        if not msg.media:
            # only media messages supported.
            continue
        try:
            file_type = msg.media
            file = getattr(msg, file_type.value)
            caption = getattr(msg, 'caption', '')
            if caption and not isinstance(caption, str) and hasattr(caption, "html"):
                caption = caption.html

            if file:
                file = {
                    "file_id": file.file_id,
                    "caption": caption,
                    "title": getattr(file, "file_name", ""),
                    "size": file.file_size,
                    "protect": cmd.lower().strip() == "/pbatch",
                }

                og_msg += 1
                outlist.append(file)
        except:
            pass
        if not og_msg % 20:
            try:
                await sts.edit(FRMT.format(total=l_msg_id - f_msg_id, current=tot, rem=((l_msg_id - f_msg_id) - tot),
                                           sts="Saving Messages"))
            except:
                pass
    with open(f"batchmode_{message.from_user.id}.json", "w+", encoding="utf-8") as out:
        out.write(json.dumps(outlist))
    post = await bot.send_document(info.LOG_CHANNEL, f"batchmode_{message.from_user.id}.json", file_name="Batch.json",
                                   caption="⚠️Generated for filestore.")
    os.remove(f"batchmode_{message.from_user.id}.json")
    file_id, ref = unpack_new_file_id(post.document.file_id)
    await sts.edit(f"Here is your link\nContains `{og_msg}` files.\n https://t.me/{temp.U_NAME}?start=BATCH-{file_id}")


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


# @Client.on_message(filters.command("restart") & filters.user(info.ADMINS) &filters.private)
# async def restart_bot(client, message):
#     status_msg = await message.reply_text("🔄 Updating code from UPSTREAM_REPO...")
#     proc = await asyncio.create_subprocess_exec(
#         sys.executable, "update.py",
#         stdout=asyncio.subpr, stderr=STDOUT
#     )
#     stdout, _ = await proc.communicate()
#     # Send a message and capture the returned message object
#     restart_msg = await message.reply_text("♻️ Restarting bot... Please wait.")
#     # Save the chat id and message id to a file (using a delimiter, e.g., "|")
#     with open(RESTART_FILE, "w") as f:
#         f.write(f"{message.chat.id}|{restart_msg.id}")
#     # Wait a moment to ensure the message is sent
#     await asyncio.sleep(2)
#     # Restart the current process (Docker will auto-restart the container)
#     os.execl(sys.executable, sys.executable, *sys.argv)

@Client.on_message(filters.command("restart") & filters.user(info.ADMINS) & filters.private)
async def restart_bot(client, message):
    # Notify user about restart
    restart_msg = await message.reply_text("♻️ **Restarting bot...**\n\n*Updating code and restarting. Please wait.*")

    if os.path.exists("Logs.txt"):
        os.remove("Logs.txt")

    # Save chat and message ID for later status update
    with open(RESTART_FILE, "w") as f:
        f.write(f"{message.chat.id}|{restart_msg.id}")

    # Run update.py to fetch latest code
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "update.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            logger.error(f"Update failed: {error_msg}")
            await message.reply_text(f"❌ **Update failed!**\n\n`{error_msg}`")
            return
    except Exception as e:
        logger.error(f"Error during update: {e}")
        await message.reply_text(f"❌ **Update error!**\n\n`{str(e)}`")
        return

    # Restart the bot process
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
                print("Failed to update restart message:", e)
        os.remove(RESTART_FILE)
