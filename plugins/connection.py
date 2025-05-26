import logging

from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import ChatAdminRequired, PeerIdInvalid, UsernameInvalid # Added for specific exceptions

from database.connections_mdb import add_connection, all_connections, if_active, delete_connection
import info

logger = logging.getLogger(__name__)
# logger.setLevel(logging.ERROR) # Original level was ERROR, can be changed to INFO or DEBUG if needed for more verbose logs from this file

@Client.on_message((filters.private | filters.group) & filters.command('connect'))
async def addconnection(client, message):
    user_id = message.from_user.id if message.from_user else None # Renamed userid to user_id for consistency
    if not user_id:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")

    chat_type = message.chat.type
    group_id_str = None  # Renamed group_id to group_id_str for clarity as it's a string from split

    if chat_type == enums.ChatType.PRIVATE:
        try:
            cmd, group_id_str = message.text.split(" ", 1)
        except ValueError: # More specific exception
            await message.reply_text(
                "<b>Enter in correct format!</b>\n\n"
                "<code>/connect groupid</code>\n\n"
                "<i>Get your Group id by adding this bot to your group and use <code>/id</code></i>",
                quote=True
            )
            return
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        group_id_str = str(message.chat.id) # Ensure group_id_str is a string
    else:
        return await message.reply_text("Unsupported chat type.", quote=True)

    try:
        # Ensure group_id_str is converted to int for get_chat_member if it's a numeric ID
        gid_to_check = int(group_id_str) if group_id_str.lstrip('-').isdigit() else group_id_str
        user_chat_status = await client.get_chat_member(gid_to_check, user_id) # Renamed st to user_chat_status
        if (
                user_chat_status.status != enums.ChatMemberStatus.ADMINISTRATOR
                and user_chat_status.status != enums.ChatMemberStatus.OWNER
                and user_id not in info.ADMINS
        ):
            await message.reply_text("You should be an admin in the given group!", quote=True)
            return
    except Exception as e:
        logger.exception(f"Error checking user admin status in group {group_id_str}: {e}")
        await message.reply_text(
            "Invalid Group ID!\n\nIf correct, make sure I'm present in your group and you have admin rights there.",
            quote=True,
        )
        return

    try:
        gid_to_check_bot = int(group_id_str) if group_id_str.lstrip('-').isdigit() else group_id_str
        bot_chat_status = await client.get_chat_member(gid_to_check_bot, "me") # Renamed st to bot_chat_status
        if bot_chat_status.status == enums.ChatMemberStatus.ADMINISTRATOR:
            chat_details = await client.get_chat(gid_to_check_bot) # Renamed ttl to chat_details
            title = chat_details.title

            add_con_result = await add_connection(group_id_str, str(user_id)) # Renamed addcon to add_con_result
            if add_con_result:
                await message.reply_text(
                    f"Successfully connected to **{title}**\nNow manage your group from my PM!",
                    quote=True,
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                    await client.send_message(
                        user_id,
                        f"Connected to **{title}**!",
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
            else:
                await message.reply_text("You're already connected to this chat!", quote=True)
        else:
            await message.reply_text("Add me as an admin in the group.", quote=True)
    except Exception as e:
        logger.exception(f"Error during connection process for group {group_id_str}: {e}")
        await message.reply_text('Some error occurred! Try again later.', quote=True)
        return


@Client.on_message((filters.private | filters.group) & filters.command('disconnect'))
async def deleteconnection(client, message):
    user_id = message.from_user.id if message.from_user else None # Renamed userid to user_id
    if not user_id:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        await message.reply_text("Run /connections to view or disconnect from groups!", quote=True)

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        group_id = message.chat.id

        user_chat_status = await client.get_chat_member(group_id, user_id) # Renamed st to user_chat_status
        if (
                user_chat_status.status != enums.ChatMemberStatus.ADMINISTRATOR
                and user_chat_status.status != enums.ChatMemberStatus.OWNER
                and str(user_id) not in info.ADMINS
        ):
            return # No reply needed if user is not admin

        del_con_result = await delete_connection(str(user_id), str(group_id)) # Renamed delcon to del_con_result
        if del_con_result:
            await message.reply_text("Successfully disconnected from this chat.", quote=True)
        else:
            await message.reply_text("This chat isn't connected to me!\nDo /connect to connect.", quote=True)


@Client.on_message(filters.private & filters.command(["connections"]))
async def connections(client, message):
    user_id = message.from_user.id # Renamed userid to user_id

    group_ids = await all_connections(str(user_id)) # Renamed groupids to group_ids
    if not group_ids: # Simpler check for empty list or None
        await message.reply_text(
            "There are no active connections!! Connect to some groups first.",
            quote=True
        )
        return
        
    buttons = []
    for group_id_str in group_ids: # Renamed groupid to group_id_str
        try:
            # Ensure group_id_str is int for get_chat if it's numeric
            gid_to_fetch = int(group_id_str) if group_id_str.lstrip('-').isdigit() else group_id_str
            chat_details = await client.get_chat(gid_to_fetch) # Renamed ttl to chat_details
            title = chat_details.title
            is_active_connection = await if_active(str(user_id), group_id_str) # Renamed active to is_active_connection
            active_text = " - ACTIVE" if is_active_connection else "" # Renamed act to active_text
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{title}{active_text}", callback_data=f"groupcb:{group_id_str}:{active_text}" # Used group_id_str
                    )
                ]
            )
        except (ChatAdminRequired, PeerIdInvalid, UsernameInvalid) as e: # Specific exceptions
            logger.warning(f"Could not fetch details for group {group_id_str}: {e}")
            pass # Continue to the next groupid
        except Exception as e:
            logger.error(f"Unexpected error fetching details for group {group_id_str}: {e}", exc_info=True) # Log other unexpected errors
            pass

    if buttons:
        await message.reply_text(
            "Your connected group details:\n\n", # Simplified text
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )
    else:
        await message.reply_text(
            "There are no active connections for which details could be fetched or you are not connected to any groups.", # More informative
            quote=True
        )
