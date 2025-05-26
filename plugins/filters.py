import io
import logging # Added
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import ChatAdminRequired, PeerIdInvalid, UsernameInvalid # Added for specific exceptions

from database.filters_mdb import(
   add_filter,
   get_filters,
   delete_filter,
   count_filters
)

from database.connections_mdb import active_connection
from utils import get_file_id, parser, split_quotes
import info

logger = logging.getLogger(__name__) # Added


@Client.on_message(filters.command(['filter', 'addf']) & filters.incoming)
async def addfilter(client, message):
    user_id = message.from_user.id if message.from_user else None # Renamed userid
    if not user_id:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    
    chat_type = message.chat.type
    args = message.text.html.split(None, 1)
    target_group_id = None # Renamed grp_id
    title = None # To store chat title

    if chat_type == enums.ChatType.PRIVATE:
        group_id_from_connection = await active_connection(str(user_id)) # Renamed grpid
        if group_id_from_connection is not None:
            target_group_id = group_id_from_connection
            try:
                chat_details = await client.get_chat(target_group_id) # Renamed chat
                title = chat_details.title
            except Exception as e: # Catch potential errors like bot not in group
                logger.warning(f"Error getting chat details for group {target_group_id} from PM: {e}", exc_info=True)
                await message.reply_text("Make sure I'm present in your group and you're connected!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups! Connect to one first.", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        target_group_id = message.chat.id
        title = message.chat.title
    else:
        # Should not happen if filters are set correctly
        return 

    try:
        user_chat_status = await client.get_chat_member(target_group_id, user_id) # Renamed st
        if not (
            user_chat_status.status == enums.ChatMemberStatus.ADMINISTRATOR
            or user_chat_status.status == enums.ChatMemberStatus.OWNER
            or str(user_id) in info.ADMINS
        ):
            # No reply if user is not admin, or silently return
            return 
    except Exception as e:
        logger.error(f"Error checking chat member status for user {user_id} in group {target_group_id}: {e}", exc_info=True)
        return # In case of error, don't proceed

    if len(args) < 2:
        await message.reply_text("Command Incomplete :(", quote=True)
        return

    extracted = split_quotes(args[1])
    filter_keyword = extracted[0].lower() # Renamed text
    fileid = None 
    reply_text = ""
    btn = "[]"
    alert = None

    if not message.reply_to_message and len(extracted) < 2:
        await message.reply_text("Add some content to save your filter!", quote=True)
        return

    if (len(extracted) >= 2) and not message.reply_to_message:
        reply_text, btn, alert = parser(extracted[1], filter_keyword)
        # fileid remains None
        if not reply_text:
            await message.reply_text("You cannot have buttons alone, give some text to go with it!", quote=True)
            return

    elif message.reply_to_message and message.reply_to_message.reply_markup:
        try:
            reply_markup_object = message.reply_to_message.reply_markup # Renamed rm
            btn = reply_markup_object.inline_keyboard
            media_object = get_file_id(message.reply_to_message) # Renamed msg
            if media_object:
                fileid = media_object.file_id
                reply_text = message.reply_to_message.caption.html if message.reply_to_message.caption else ""
            else:
                reply_text = message.reply_to_message.text.html if message.reply_to_message.text else ""
                fileid = None
            # alert not parsed from reply_markup
        except Exception as e:
            logger.warning(f"Error parsing filter content for '{filter_keyword}' in group {target_group_id} from reply_markup: {e}", exc_info=True)
            reply_text = ""
            btn = "[]"
            fileid = None
            alert = None

    elif message.reply_to_message and message.reply_to_message.media:
        try:
            media_object = get_file_id(message.reply_to_message) # Renamed msg
            fileid = media_object.file_id if media_object else None
            
            caption_content = ""
            if message.reply_to_message.caption and message.reply_to_message.caption.html:
                caption_content = message.reply_to_message.caption.html
            elif message.reply_to_message.text and message.reply_to_message.text.html: 
                 caption_content = message.reply_to_message.text.html
            else:
                caption_content = ""

            if len(extracted) >= 2:
                 text_to_parse = extracted[1]
            else:
                 text_to_parse = caption_content
            reply_text, btn, alert = parser(text_to_parse, filter_keyword)
        except Exception as e:
            logger.warning(f"Error parsing filter content for '{filter_keyword}' in group {target_group_id} from media reply: {e}", exc_info=True)
            reply_text = ""
            btn = "[]"
            if 'media_object' in locals() and media_object and hasattr(media_object, 'file_id'):
                fileid = media_object.file_id
            else:
                fileid = None
            alert = None

    elif message.reply_to_message and message.reply_to_message.text:
        try:
            fileid = None
            if len(extracted) >= 2:
                text_to_parse = extracted[1]
            else:
                text_to_parse = message.reply_to_message.text.html
            reply_text, btn, alert = parser(text_to_parse, filter_keyword)
        except Exception as e:
            logger.warning(f"Error parsing filter content for '{filter_keyword}' in group {target_group_id} from text reply: {e}", exc_info=True)
            reply_text = ""
            btn = "[]"
            alert = None
    else:
        await message.reply_text("Could not determine the content for the filter. Please reply to a message or provide text.", quote=True)
        return

    await add_filter(target_group_id, filter_keyword, reply_text, btn, fileid, alert)

    await message.reply_text(
        f"Filter for  `{filter_keyword}`  added in  **{title}**",
        quote=True,
        parse_mode=enums.ParseMode.MARKDOWN
    )


@Client.on_message(filters.command(['viewfilters', 'filters']) & filters.incoming)
async def view_filters(client, message): # Renamed get_all to view_filters
    user_id = message.from_user.id if message.from_user else None # Renamed userid
    if not user_id:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    
    chat_type = message.chat.type
    target_group_id = None # Renamed grp_id
    title = None

    if chat_type == enums.ChatType.PRIVATE:
        group_id_from_connection = await active_connection(str(user_id)) # Renamed grpid
        if group_id_from_connection is not None:
            target_group_id = group_id_from_connection
            try:
                chat_details = await client.get_chat(target_group_id) # Renamed chat
                title = chat_details.title
            except (ChatAdminRequired, PeerIdInvalid, UsernameInvalid) as e: # Specific exceptions
                logger.warning(f"Error getting chat details for group {target_group_id} in view_filters: {e}", exc_info=True)
                await message.reply_text("Make sure I'm present in your group and you're connected!", quote=True)
                return
            except Exception as e:
                logger.error(f"Unexpected error getting chat details for group {target_group_id} in view_filters: {e}", exc_info=True)
                await message.reply_text("An error occurred while fetching group details.", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        target_group_id = message.chat.id
        title = message.chat.title
    else:
        return

    try:
        user_chat_status = await client.get_chat_member(target_group_id, user_id) # Renamed st
        if not (
            user_chat_status.status == enums.ChatMemberStatus.ADMINISTRATOR
            or user_chat_status.status == enums.ChatMemberStatus.OWNER
            or str(user_id) in info.ADMINS
        ):
            return # No reply if not admin
    except Exception as e:
        logger.error(f"Error checking chat member status for user {user_id} in group {target_group_id} (view_filters): {e}", exc_info=True)
        return


    filter_keywords = await get_filters(target_group_id) # Renamed texts
    count = await count_filters(target_group_id)
    if count:
        output_message = f"Total number of filters in **{title}** : {count}\n\n" # Renamed filterlist

        for keyword in filter_keywords: # Renamed text to keyword
            keyword_line = " ×  `{}`\n".format(keyword) # Renamed keywords to keyword_line
            output_message += keyword_line

        if len(output_message) > 4096:
            with io.BytesIO(str.encode(output_message.replace("`", ""))) as keyword_file_obj: # Renamed keyword_file
                keyword_file_obj.name = "filters_list.txt" # More descriptive
                await message.reply_document(
                    document=keyword_file_obj,
                    caption=f"All filters in {title}", # Added caption
                    quote=True
                )
            return
    else:
        output_message = f"There are no active filters in **{title}**"

    await message.reply_text(
        text=output_message,
        quote=True,
        parse_mode=enums.ParseMode.MARKDOWN
    )
        
@Client.on_message(filters.command('del') & filters.incoming)
async def deletefilter(client, message):
    user_id = message.from_user.id if message.from_user else None # Renamed userid
    if not user_id:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    
    chat_type = message.chat.type
    target_group_id = None # Renamed grp_id
    # title is not strictly needed for deletion but can be for context if desired later

    if chat_type == enums.ChatType.PRIVATE:
        group_id_from_connection  = await active_connection(str(user_id)) # Renamed grpid
        if group_id_from_connection is not None:
            target_group_id = group_id_from_connection
            try:
                # Verifying bot is in group and getting title (optional for delete, but good check)
                chat_details = await client.get_chat(target_group_id) # Renamed chat
                # title = chat_details.title 
            except Exception as e:
                logger.warning(f"Error getting chat details for group {target_group_id} (deletefilter from PM): {e}", exc_info=True)
                await message.reply_text("Make sure I'm present in your group and you're connected!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        target_group_id = message.chat.id
        # title = message.chat.title
    else:
        return

    try:
        user_chat_status = await client.get_chat_member(target_group_id, user_id) # Renamed st
        if not (
            user_chat_status.status == enums.ChatMemberStatus.ADMINISTRATOR
            or user_chat_status.status == enums.ChatMemberStatus.OWNER
            or str(user_id) in info.ADMINS
        ):
            return
    except Exception as e:
        logger.error(f"Error checking chat member status for user {user_id} in group {target_group_id} (deletefilter): {e}", exc_info=True)
        return


    try:
        cmd, filter_keyword_to_delete_cmd = message.text.split(" ", 1) # Renamed text
    except ValueError: # More specific
        await message.reply_text(
            "<i>Mention the filtername which you wanna delete!</i>\n\n"
            "<code>/del filtername</code>\n\n"
            "Use /viewfilters to view all available filters",
            quote=True
        )
        return

    filter_keyword_to_delete = filter_keyword_to_delete_cmd.lower() # Renamed query

    await delete_filter(message, filter_keyword_to_delete, target_group_id)
        

@Client.on_message(filters.command('delall') & filters.incoming)
async def delallconfirm(client, message): # Renamed from delallconfirm, though the original was also delallconfirm
    user_id = message.from_user.id if message.from_user else None # Renamed userid
    if not user_id:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    
    chat_type = message.chat.type
    target_group_id = None # Renamed grp_id
    title = None

    if chat_type == enums.ChatType.PRIVATE:
        group_id_from_connection  = await active_connection(str(user_id)) # Renamed grpid
        if group_id_from_connection is not None:
            target_group_id = group_id_from_connection
            try:
                chat_details = await client.get_chat(target_group_id) # Renamed chat
                title = chat_details.title
            except Exception as e:
                logger.warning(f"Error getting chat details for group {target_group_id} (delallconfirm from PM): {e}", exc_info=True)
                await message.reply_text("Make sure I'm present in your group and you're connected!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        target_group_id = message.chat.id
        title = message.chat.title
    else:
        return

    try:
        user_chat_status = await client.get_chat_member(target_group_id, user_id) # Renamed st
        if not (
            user_chat_status.status == enums.ChatMemberStatus.OWNER # Only owner or bot admins can delete all
            or str(user_id) in info.ADMINS
        ):
            await message.reply_text("You need to be the group owner or a bot admin to delete all filters.", quote=True)
            return
    except Exception as e:
        logger.error(f"Error checking chat member status for user {user_id} in group {target_group_id} (delallconfirm): {e}", exc_info=True)
        return

    await message.reply_text(
        f"This will delete all filters from '{title}'.\nDo you want to continue??",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="YES, DELETE ALL",callback_data="delallconfirm")], # Callback data remains the same
            [InlineKeyboardButton(text="CANCEL",callback_data="delallcancel")]
        ]),
        quote=True
    )
