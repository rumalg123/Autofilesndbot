from pyrogram import Client, filters
from utils import temp
from pyrogram.types import Message
from database.users_chats_db import db
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import info

async def banned_users(_, client, message: Message):
    return (
        message.from_user is not None or not message.sender_chat
    ) and message.from_user.id in temp.BANNED_USERS

banned_user = filters.create(banned_users)

async def disabled_chat(_, client, message: Message):
    return message.chat.id in temp.BANNED_CHATS

disabled_group=filters.create(disabled_chat)


@Client.on_message(filters.private & banned_user & filters.incoming)
async def ban_reply(bot, message):
    user_id = message.from_user.id
    ban_status = await db.get_ban_status(user_id) # Renamed ban to ban_status for clarity
    try:
        await message.reply(f'<b>Sorry Dude, You are Banned to use Me.</b> \nBan Reason: {ban_status["ban_reason"]}')
    except InputUserDeactivated:
        logging.warning(f"User {user_id} (banned) is deactivated. Removing from DB.")
        await db.delete_user(user_id)
    except Exception as e:
        logging.error(f"Error sending ban reply to {user_id}: {e}", exc_info=True)

@Client.on_message(filters.group & disabled_group & filters.incoming)
async def grp_bd(bot, message):
    buttons = [[
        InlineKeyboardButton('🧩 𝖲𝖴𝖯𝖯𝖮𝖱𝖳 🧩', url=f"https://t.me/{info.SUPPORT_CHAT}")
    ]]
    reply_markup=InlineKeyboardMarkup(buttons)
    vazha = await db.get_chat(message.chat.id)
    k = await message.reply(
        text=f"<b>CHAT NOT ALLOWED 🐞</b>\n\nMy admins has restricted me from working here ! If you want to know more about it contact 𝖲𝖴𝖯𝖯𝖮𝖱𝖳 GROUP..\nReason : <code>{vazha['reason']}</code>.",
        reply_markup=reply_markup)
    try:
        await k.pin()
    except:
        pass
    await bot.leave_chat(message.chat.id)
