import asyncio

from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, PeerIdInvalid # Added PeerIdInvalid for more specific exception handling
from pyrogram.errors.exceptions.bad_request_400 import MessageTooLong
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from Script import script
from database.ia_filterdb import Media
from database.users_chats_db import db
import info
from utils import get_size, temp, get_settings


@Client.on_message(filters.new_chat_members & filters.group)
async def save_group(client, message): # Renamed bot to client
    new_member_ids = [member.id for member in message.new_chat_members] # Renamed r_j_check to new_member_ids, u to member
    if temp.ME in new_member_ids:
        if not await db.get_chat(message.chat.id):
            total_members = await client.get_chat_members_count(message.chat.id) # Renamed total to total_members
            added_by_mention = message.from_user.mention if message.from_user else "Anonymous" # Renamed r_j to added_by_mention
            await client.send_message(info.LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total_members, added_by_mention))
            await db.add_chat(message.chat.id, message.chat.title)
        if message.chat.id in temp.BANNED_CHATS:
            buttons = [[
                InlineKeyboardButton(' 𝖲𝗎𝗉𝗉𝗈𝗋𝗍 ', url=f"https://t.me/{info.SUPPORT_CHAT}")
            ]]
            reply_markup = InlineKeyboardMarkup(buttons)
            chat_not_allowed_message = await message.reply( # Renamed k to chat_not_allowed_message
                text='<b>CHAT NOT ALLOWED 🐞\n\nMy admins has restricted me from working here ! If you want to know more about it contact support..</b>',
                reply_markup=reply_markup,
            )

            try:
                await chat_not_allowed_message.pin() # Use new variable name
            except ChatAdminRequired:
                pass # Bot may not have pin rights
            except Exception: # Catch other potential errors during pinning
                pass
            await client.leave_chat(message.chat.id)
            return
        buttons = [[
            InlineKeyboardButton(' 𝖲𝖴𝖯𝖯𝖮𝖱𝖳 ', url=f"https://t.me/{info.SUPPORT_CHAT}"),
            InlineKeyboardButton(' Main Channel ', url=info.MAIN_CHANNEL)
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(
            text=f"<b>Thankyou For Adding Me In {message.chat.title} ❣️\n\nIf you have any questions & doubts about using me contact Support.</b>",
            reply_markup=reply_markup)
    else:
        settings = await get_settings(message.chat.id)
        if settings["welcome"]:
            for new_member in message.new_chat_members: # Renamed u to new_member
                # If a welcome message already exists (e.g., from a previous new member in a quick succession of joins),
                # try to delete it before sending a new one. This avoids multiple welcome messages.
                if temp.MELCOW.get('welcome') is not None:
                    try:
                        await (temp.MELCOW['welcome']).delete()
                    except Exception: # Catch if the message was already deleted or other errors
                        pass 
                temp.MELCOW['welcome'] = await message.reply_video(
                                                 video=info.MELCOW_VID,
                                                 caption=(script.MELCOW_ENG.format(new_member.mention, message.chat.title)),
                                                 reply_markup=InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(' 𝖲𝖴𝖯𝖯𝖮𝖱𝖳 ', url=f"https://t.me/{info.SUPPORT_CHAT}"),
            InlineKeyboardButton(' Main Channel ', url=info.MAIN_CHANNEL)
        ]]
                                                 ),
                                                 parse_mode=enums.ParseMode.HTML
                )
                
        if settings["auto_delete"]:
            await asyncio.sleep(600) # Consider making this duration configurable
            if 'welcome' in temp.MELCOW and temp.MELCOW['welcome']:
                try:
                    await temp.MELCOW['welcome'].delete()
                except Exception:
                    pass # Message might have been manually deleted


@Client.on_message(filters.command('leave') & filters.user(info.ADMINS))
async def leave_a_chat(client, message): # Renamed bot to client
    if len(message.command) == 1:
        return await message.reply('Give me a chat id or username.')
    
    chat_id_or_username_to_leave = message.command[1] # Renamed chat
    target_chat_id = None # Initialize target_chat_id

    try:
        target_chat_id = int(chat_id_or_username_to_leave) # Try converting to int first
    except ValueError:
        target_chat_id = chat_id_or_username_to_leave # If not int, assume it's a username string
    
    try:
        buttons = [[
            InlineKeyboardButton(' 𝖲𝖴𝖯𝖯𝖮𝖱𝖳 ', url=f"https://t.me/{info.SUPPORT_CHAT}"),
            InlineKeyboardButton(' 𝖴𝗉𝖽𝖺𝗍𝖾𝗌 ', url=info.MAIN_CHANNEL)
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.send_message(
            chat_id=target_chat_id,
            text='<b>Hello Friends, \nMy admin has told me to leave from group so I go! If you wanna add me again contact my 𝖲𝖴𝖯𝖯𝖮𝖱𝖳 GROUP.</b>',
            reply_markup=reply_markup,
        )
        await client.leave_chat(target_chat_id)
        await message.reply(f"Successfully left the chat `{target_chat_id}`")
    except PeerIdInvalid:
        await message.reply(f"Error: Invalid chat ID or username: `{chat_id_or_username_to_leave}`.")
    except Exception as e:
        await message.reply(f'Error leaving chat {chat_id_or_username_to_leave}: {e}')

@Client.on_message(filters.command('disable') & filters.user(info.ADMINS))
async def disable_chat(client, message): # Renamed bot to client
    if len(message.command) == 1:
        return await message.reply('Give me a chat id to disable.')
    
    command_parts = message.text.split(None, 2) # Renamed r to command_parts
    chat_id_str = command_parts[1] # Renamed chat to chat_id_str
    reason = command_parts[2] if len(command_parts) > 2 else "No reason Provided"

    try:
        target_chat_id = int(chat_id_str) # Renamed chat_ to target_chat_id
    except ValueError:
        return await message.reply('Invalid Chat ID format. Please provide a numeric Chat ID.')
        
    chat_status_details = await db.get_chat(target_chat_id) # Renamed cha_t to chat_status_details
    if not chat_status_details:
        return await message.reply("Chat Not Found In DB.")
    if chat_status_details.get('is_disabled', False): # Use .get for safety
        return await message.reply(f"This chat is already disabled:\nReason: <code>{chat_status_details.get('reason', 'N/A')}</code>")
    
    await db.disable_chat(target_chat_id, reason)
    if target_chat_id not in temp.BANNED_CHATS: # Ensure it's added only if not already present (though disable_chat implies it wasn't)
        temp.BANNED_CHATS.append(target_chat_id)
    await message.reply('Chat Successfully Disabled.')
    
    try:
        buttons = [[
            InlineKeyboardButton(' 𝖲𝖴𝖯𝖯𝖮𝖱𝖳  ', url=f"https://t.me/{info.SUPPORT_CHAT}"),
            InlineKeyboardButton(' 𝖴𝗉𝖽𝖺𝗍𝖾𝗌 ', url=info.MAIN_CHANNEL)
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.send_message(
            chat_id=target_chat_id, 
            text=f'<b>𝖧𝖾𝗅𝗅𝗈 𝖥𝗋𝗂𝖾𝗇𝖽𝗌, \n𝖬𝗒 𝖺𝖽𝗆𝗂𝗇 𝗁𝖺𝗌 𝖽𝗂𝗌𝖺𝖻𝗅𝖾𝖽 𝗆𝖾 𝖿𝗈𝗋 𝗍𝗁𝗂𝗌 𝗀𝗋𝗈𝗎𝗉! 𝖨𝖿 𝗒𝗈𝗎 𝗐𝖺𝗇𝗍 𝗍𝗈 𝗄𝗇𝗈𝗐 𝗆𝗈𝗋𝖾, 𝖼𝗈𝗇𝗍𝖺𝖼𝗍 𝗆𝗒 𝗌𝗎𝗉𝗉𝗈𝗋𝗍 𝗀𝗋𝗈𝗎𝗉.</b> \nReason: <code>{reason}</code>', # Modified message to reflect disable, not leave
            reply_markup=reply_markup
        )
        await client.leave_chat(target_chat_id) # Bot leaves after disabling
    except PeerIdInvalid:
        await message.reply(f"Error: Could not send disable notification or leave chat `{target_chat_id}`. Invalid chat ID.")
    except Exception as e:
        await message.reply(f"Error during post-disable actions for chat {target_chat_id}: {e}")


@Client.on_message(filters.command('enable') & filters.user(info.ADMINS))
async def re_enable_chat(client, message): # Renamed bot to client
    if len(message.command) == 1:
        return await message.reply('Give me a chat id to enable.')
    
    chat_id_str = message.command[1] # Renamed chat to chat_id_str
    try:
        target_chat_id = int(chat_id_str) # Renamed chat_ to target_chat_id
    except ValueError:
        return await message.reply('Invalid Chat ID format. Please provide a numeric Chat ID.')
        
    chat_status_details = await db.get_chat(target_chat_id) # Renamed sts to chat_status_details
    if not chat_status_details:
        return await message.reply("Chat Not Found In DB!")
    if not chat_status_details.get('is_disabled', False): # Use .get for safety
        return await message.reply('This chat is not currently disabled.')
        
    await db.re_enable_chat(target_chat_id)
    if target_chat_id in temp.BANNED_CHATS: # Ensure it's removed if present
        temp.BANNED_CHATS.remove(target_chat_id)
    await message.reply("Chat Successfully Re-enabled.")


@Client.on_message(filters.command('stats') & filters.incoming)
async def get_ststs(bot, message): # Parameter name 'bot' kept as is, can be client
    rju = await message.reply('Fetching stats...')
    total_users = await db.total_users_count()
    totl_chats = await db.total_chat_count()
    files = await Media.count_documents()
    size = await db.get_db_size()
    free = 536870912 - size
    size = get_size(size)
    free = get_size(free)
    await rju.edit(script.STATUS_TXT.format(files, total_users, totl_chats, size, free))

@Client.on_message(filters.command('invite') & filters.user(info.ADMINS))
async def gen_invite(bot, message): # Parameter name 'bot' kept as is
    if len(message.command) == 1:
        return await message.reply('Give me a chat id')
    chat_id_str = message.command[1] # Renamed chat to chat_id_str
    try:
        target_chat_id = int(chat_id_str) # Renamed chat to target_chat_id
    except ValueError:
        return await message.reply('Give Me A Valid Chat ID')
    try:
        link = await bot.create_chat_invite_link(target_chat_id) # Use target_chat_id
    except ChatAdminRequired:
        return await message.reply("Invite Link Generation Failed, I am Not Having Sufficient Rights.")
    except PeerIdInvalid:
        return await message.reply(f"Error: Invalid chat ID: `{target_chat_id}`.")
    except Exception as e:
        return await message.reply(f'Error: {e}')
    await message.reply(f'Here is your Invite Link {link.invite_link}')

@Client.on_message(filters.command('ban') & filters.user(info.ADMINS))
async def ban_a_user(bot, message): # Parameter name 'bot' kept as is
    if len(message.command) == 1:
        return await message.reply('Give me a user id / username')
    command_parts = message.text.split(None, 2) # Renamed r to command_parts
    user_id_or_username = command_parts[1] # Renamed chat to user_id_or_username
    reason = command_parts[2] if len(command_parts) > 2 else "No reason Provided"
    
    target_user_id = None
    try:
        target_user_id = int(user_id_or_username)
    except ValueError:
        # If not an int, it might be a username, get_users will handle it
        target_user_id = user_id_or_username 
    
    try:
        user_to_ban = await bot.get_users(target_user_id) # Renamed k to user_to_ban
    except PeerIdInvalid:
        return await message.reply("This is an invalid user ID or username. Make sure I have met this user before or the username is correct.")
    except IndexError: # Should not happen with current split logic, but good to keep
        return await message.reply("This might be a channel, make sure it's a user.")
    except Exception as e:
        return await message.reply(f'Error fetching user: {e}')
    
    # Proceed with user_to_ban.id for database operations
    if not await db.is_user_exist(user_to_ban.id):
        return await message.reply("This user hasn't started the bot yet and cannot be banned.")
        
    ban_status_details = await db.get_ban_status(user_to_ban.id) # Renamed jar to ban_status_details
    if ban_status_details['is_banned']:
        return await message.reply(f"{user_to_ban.mention} is already banned.\nReason: {ban_status_details['ban_reason']}")
        
    await db.ban_user(user_to_ban.id, reason)
    if user_to_ban.id not in temp.BANNED_USERS: # Ensure not to add duplicates
        temp.BANNED_USERS.append(user_to_ban.id)
    await message.reply(f"Successfully banned {user_to_ban.mention}.")


    
@Client.on_message(filters.command('unban') & filters.user(info.ADMINS))
async def unban_a_user(bot, message): # Parameter name 'bot' kept as is
    if len(message.command) == 1:
        return await message.reply('Give me a user id / username')
    
    command_parts = message.text.split(None, 2) # Renamed r to command_parts
    user_id_or_username = command_parts[1] # Renamed chat to user_id_or_username
    # Reason is not used in unban logic, so no need to extract command_parts[2]
    
    target_user_id = None
    try:
        target_user_id = int(user_id_or_username)
    except ValueError:
        target_user_id = user_id_or_username

    try:
        user_to_unban = await bot.get_users(target_user_id) # Renamed k to user_to_unban
    except PeerIdInvalid:
        return await message.reply("This is an invalid user ID or username. Make sure I have met this user before or the username is correct.")
    except IndexError:
        return await message.reply("This might be a channel, make sure it's a user.")
    except Exception as e:
        return await message.reply(f'Error fetching user: {e}')
    
    ban_status_details = await db.get_ban_status(user_to_unban.id) # Renamed jar to ban_status_details
    if not ban_status_details['is_banned']:
        return await message.reply(f"{user_to_unban.mention} is not currently banned.")
        
    await db.remove_ban(user_to_unban.id)
    if user_to_unban.id in temp.BANNED_USERS: # Ensure user is in list before removing
        temp.BANNED_USERS.remove(user_to_unban.id)
    await message.reply(f"Successfully unbanned {user_to_unban.mention}.")


    
@Client.on_message(filters.command('users') & filters.user(info.ADMINS))
async def list_users(bot, message): # Parameter name 'bot' kept as is
    status_message = await message.reply('Getting List Of Users...') # Renamed raju to status_message
    all_users = await db.get_all_users() # Renamed users to all_users
    output_text = "Users Saved In DB Are:\n\n" # Renamed out to output_text

    for user_doc in all_users: # Renamed user to user_doc
        output_text += f"<a href=tg://user?id={user_doc['id']}>{user_doc['name']}</a>"
        if user_doc.get('ban_status', {}).get('is_banned'): # Safer access to nested dict
            output_text += ' (Banned User)'
        output_text += '\n'

    try:
        await status_message.edit_text(output_text)
    except MessageTooLong:
        with open('users.txt', 'w+') as outfile:
            outfile.write(output_text)
        await message.reply_document('users.txt', caption="List Of Users")
        await status_message.delete() # Delete the "Getting List..." message

@Client.on_message(filters.command('chats') & filters.user(info.ADMINS))
async def list_chats(bot, message): # Parameter name 'bot' kept as is
    status_message = await message.reply('Getting List Of chats...') # Renamed raju to status_message
    all_chats = await db.get_all_chats()  # Renamed chats to all_chats
    output_text = "Chats Saved In DB Are:\n\n" # Renamed out to output_text
    
    for chat_doc in all_chats: # Renamed chat to chat_doc
        output_text += f"**Title:** `{chat_doc['title']}`\n**- ID:** `{chat_doc['id']}`"
        if chat_doc.get('chat_status', {}).get('is_disabled'): # Safer access
            output_text += ' (Disabled Chat)'
        output_text += '\n\n' # Added extra newline for better readability
    
    try:
        await status_message.edit_text(output_text)
    except MessageTooLong:
        with open('chats.txt', 'w+') as outfile:
            outfile.write(output_text)
        await message.reply_document('chats.txt', caption="List Of Chats")
        await status_message.delete() # Delete the "Getting List..." message
