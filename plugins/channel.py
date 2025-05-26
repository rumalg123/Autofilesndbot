from pyrogram import Client, filters
import info
from database.ia_filterdb import save_file
import logging

logger = logging.getLogger(__name__)

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(info.CHANNELS) & media_filter)
async def media(bot, message):
    """Media Handler"""
    for file_type in ("document", "video", "audio"):
        media = getattr(message, file_type, None)
        if media is not None:
            break
    else:
        return

    media.file_type = file_type
    media.caption = message.caption # message.caption can be None, save_file handles it by using .html if available
    
    saved_successfully, error_code = await save_file(media)

    if not saved_successfully:
        logger.error(f"Failed to save file from message {message.id} in chat {message.chat.id}. File: {getattr(media, 'file_name', 'N/A')}. Error code: {error_code}")