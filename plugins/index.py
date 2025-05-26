import asyncio
import logging
import re

from pyrogram import Client, filters, enums
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, \
    UsernameNotModified
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.ia_filterdb import save_file
from utils import temp
import info

logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO) # Original level was INFO, kept as is.
lock = asyncio.Lock()


@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(client, query): # Renamed bot to client
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")

    # query.data format: index#action#chat_id#start_msg_id#requester_id
    try:
        _, action, chat_to_index_id_str, start_message_id_str, requester_user_id_str = query.data.split("#") # Renamed variables
    except ValueError:
        logger.error(f"Error splitting callback_data: {query.data}")
        return await query.answer("Error: Invalid callback data format.", show_alert=True)

    requester_user_id = int(requester_user_id_str)
    start_message_id = int(start_message_id_str)

    if action == 'reject':
        logger.info(f"Indexing request for chat {chat_to_index_id_str} from user {requester_user_id} rejected by {query.from_user.id}.") # Added logging
        await query.message.delete()
        await client.send_message(requester_user_id, # Use int version of ID
                               f'Your Submission for indexing {chat_to_index_id_str} has been declined by our moderators.',
                               reply_to_message_id=start_message_id) # Use int version of ID
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    
    status_update_message = query.message # Renamed msg

    await query.answer('Processing...⏳', show_alert=True)
    if requester_user_id not in info.ADMINS: # Check if original requester is admin
        await client.send_message(requester_user_id,
                               f'Your Submission for indexing {chat_to_index_id_str} has been accepted by our moderators and will be added soon.',
                               reply_to_message_id=start_message_id)
    
    await status_update_message.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    
    target_chat_id_int_or_str = None
    try:
        target_chat_id_int_or_str = int(chat_to_index_id_str) # Try to convert to int
    except ValueError:
        target_chat_id_int_or_str = chat_to_index_id_str # Keep as string if not numeric (username)
    
    # Pass the potentially int or string chat_id and int start_message_id
    return await index_files_to_db(start_message_id, target_chat_id_int_or_str, status_update_message, client)


@Client.on_message((filters.forwarded | (filters.regex(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def send_for_index(client, message): # Renamed bot to client
    target_chat_id = None # Renamed chat_id
    target_last_msg_id = None # Renamed last_msg_id

    if message.text:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return await message.reply('Invalid link')
        
        chat_id_str_from_link = match.group(4)
        target_last_msg_id = int(match.group(5))
        if chat_id_str_from_link.isnumeric():
            target_chat_id  = int(("-100" + chat_id_str_from_link))
        else:
            target_chat_id = chat_id_str_from_link # Username
            
    elif message.forward_from_chat and message.forward_from_chat.type == enums.ChatType.CHANNEL:
        target_last_msg_id = message.forward_from_message_id
        target_chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        return await message.reply("Unsupported message type for indexing. Please forward from a channel or provide a public channel message link.")

    try:
        await client.get_chat(target_chat_id)
    except ChannelInvalid:
        return await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        logger.exception(f"Error getting chat {target_chat_id}: {e}")
        return await message.reply(f'Errors - {e}')
    
    try:
        target_message_check = await client.get_messages(target_chat_id, target_last_msg_id) # Renamed k
    except Exception as e: # Broad exception for cases like bot not being admin
        logger.warning(f"Could not get message {target_last_msg_id} from chat {target_chat_id}: {e}")
        return await message.reply('Make sure that I am an Admin in the Channel if it is private, or that the message ID is correct.')
    
    if not target_message_check: # Check if target_message_check is None or empty (though get_messages usually raises error)
         return await message.reply('Could not fetch the specified message. This may be a group and I am not an admin, or the message does not exist.')


    if message.from_user.id in info.ADMINS:
        buttons = [
            [
                InlineKeyboardButton('Yes',
                                     callback_data=f'index#accept#{target_chat_id}#{target_last_msg_id}#{message.from_user.id}')
            ],
            [
                InlineKeyboardButton('close', callback_data='close_data'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you Want To Index This Channel/ Group ?\n\nChat ID/ Username: <code>{target_chat_id}</code>\nStart Message ID: <code>{target_last_msg_id}</code>', # Updated to target_last_msg_id
            reply_markup=reply_markup)

    invite_link_for_submission = "" # Renamed link
    if isinstance(target_chat_id, int): # Check if target_chat_id is an int (not username)
        try:
            invite_link_for_submission = (await client.create_chat_invite_link(target_chat_id)).invite_link
        except ChatAdminRequired:
            logger.warning(f"Bot needs admin rights in chat {target_chat_id} to create invite link for indexing request.")
            invite_link_for_submission = "Not available (Bot not admin or no permission)"
        except Exception as e:
            logger.error(f"Error creating invite link for chat {target_chat_id}: {e}")
            invite_link_for_submission = "Error creating link"

    elif message.forward_from_chat and message.forward_from_chat.username: # If it was a forward and has username
         invite_link_for_submission = f"@{message.forward_from_chat.username}"
    elif isinstance(target_chat_id, str) : # if target_chat_id is a username string from link
        invite_link_for_submission = f"@{target_chat_id}"


    buttons = [
        [
            InlineKeyboardButton('Accept Index',
                                 callback_data=f'index#accept#{target_chat_id}#{target_last_msg_id}#{message.from_user.id}')
        ],
        [
            InlineKeyboardButton('Reject Index',
                                 callback_data=f'index#reject#{target_chat_id}#{message.id}#{message.from_user.id}'), # message.id is used for reply_to in rejection message
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    # Send to INDEX_REQ_CHANNEL
    await client.send_message(info.INDEX_REQ_CHANNEL,
                           f'#IndexRequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username: <code>{target_chat_id}</code>\nStart Message ID: <code>{target_last_msg_id}</code>\nInviteLink: {invite_link_for_submission}',
                           reply_markup=reply_markup)
    return await message.reply('Thank You For the Contribution. Wait for our moderators to verify the files.')


@Client.on_message(filters.command('setskip') & filters.user(info.ADMINS))
async def set_skip_number(client, message): # Renamed bot to client
    if ' ' in message.text:
        _, skip_str = message.text.split(" ", 1) # Renamed skip to skip_str
        try:
            skip_number = int(skip_str) # Renamed skip to skip_number
        except ValueError:
            return await message.reply("Skip number should be an integer.")
        temp.CURRENT = skip_number # Use skip_number
        return await message.reply(f"Successfully set SKIP number as {skip_number}")
    else:
        return await message.reply("Give me a skip number. Usage: /setskip <number>")


async def index_files_to_db(start_message_id, target_chat_id_int_or_str, status_update_message, client): # Renamed parameters
    total_files_saved = 0 # Renamed total_files
    duplicate_files_skipped = 0 # Renamed duplicate
    errors_occurred = 0 # Renamed errors
    deleted_messages_skipped = 0 # Renamed deleted
    non_media_skipped = 0 # Renamed no_media
    unsupported_media_skipped = 0 # Renamed unsupported
    
    async with lock:
        try:
            messages_processed_count = temp.CURRENT # Renamed current
            temp.CANCEL = False
            
            # Iterating from start_message_id down to 0 (or until temp.CURRENT if it's set high)
            async for current_message_object in client.iter_messages(target_chat_id_int_or_str, reverse=True, offset_id=start_message_id, limit=abs(start_message_id - temp.CURRENT) if temp.CURRENT < start_message_id else None): # Renamed message
                if temp.CANCEL:
                    await status_update_message.edit(f"Successfully Cancelled!!\n\nSaved <code>{total_files_saved}</code> files to database!\nDuplicate Files Skipped: <code>{duplicate_files_skipped}</code>\nDeleted Messages Skipped: <code>{deleted_messages_skipped}</code>\nNon-Media messages skipped: <code>{non_media_skipped + unsupported_media_skipped}</code> (Unsupported Media - `{unsupported_media_skipped}`)\nErrors Occurred: <code>{errors_occurred}</code>")
                    break
                
                messages_processed_count += 1 # This now counts messages actually processed in this run. If temp.CURRENT was for resuming, logic might need adjustment.
                                          # For now, it counts messages iterated in this session.

                if messages_processed_count % 20 == 0:
                    cancel_button_list = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]] # Renamed can
                    cancel_reply_markup = InlineKeyboardMarkup(cancel_button_list) # Renamed reply
                    await asyncio.sleep(2) # Kept sleep
                    await status_update_message.edit_text(
                        text=f"Total messages fetched: <code>{messages_processed_count}</code>\nTotal files saved: <code>{total_files_saved}</code>\nDuplicate Files Skipped: <code>{duplicate_files_skipped}</code>\nDeleted Messages Skipped: <code>{deleted_messages_skipped}</code>\nNon-Media messages skipped: <code>{non_media_skipped + unsupported_media_skipped}</code> (Unsupported Media - `{unsupported_media_skipped}`)\nErrors Occurred: <code>{errors_occurred}</code>",
                        reply_markup=cancel_reply_markup
                    )
                
                if not current_message_object: # Handle if message object is None (though iter_messages usually doesn't yield None)
                    deleted_messages_skipped +=1
                    continue
                if current_message_object.empty:
                    deleted_messages_skipped += 1
                    continue
                elif not current_message_object.media:
                    non_media_skipped += 1
                    continue
                elif current_message_object.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                    unsupported_media_skipped += 1
                    continue
                
                media_object = getattr(current_message_object, current_message_object.media.value, None) # Renamed media
                if not media_object:
                    unsupported_media_skipped += 1 # Should be rare if previous checks pass
                    continue
                
                media_object.file_type = current_message_object.media.value
                media_object.caption = current_message_object.caption
                
                was_saved, save_status_code = await save_file(media_object) # Renamed aynav, vnay

                if was_saved:
                    total_files_saved += 1
                else: # Not saved
                    if save_status_code == 0: # Duplicate
                        duplicate_files_skipped += 1
                    elif save_status_code == 2 or save_status_code == 3: # Validation error or other DB error
                        errors_occurred += 1
                    # else: for any other save_status_code, it's currently not counted as a specific error type here.
                        # Could add an 'unknown_error' counter if save_file can return other codes.

        except Exception as e:
            logger.exception(f"Error during indexing chat {target_chat_id_int_or_str}: {e}")
            await status_update_message.edit(f'Error: {e}')
        else:
            await status_update_message.edit(f'Successfully saved <code>{total_files_saved}</code> files to database!\nDuplicate Files Skipped: <code>{duplicate_files_skipped}</code>\nDeleted Messages Skipped: <code>{deleted_messages_skipped}</code>\nNon-Media messages skipped: <code>{non_media_skipped + unsupported_media_skipped}</code> (Unsupported Media - `{unsupported_media_skipped}`)\nErrors Occurred: <code>{errors_occurred}</code>')
