import re
import logging
from pyrogram import Client, filters
import info
from database.ia_filterdb import Media, unpack_new_file_id

logger = logging.getLogger(__name__)

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(info.DELETE_CHANNELS) & media_filter)
async def delete_media_on_channel_message(client, message): # Renamed function and bot to client
    """Delete media from database when a message is deleted in specified channels."""

    for file_type in ("document", "video", "audio"):
        media = getattr(message, file_type, None)
        if media is not None:
            break
    else:
        logger.warning(f"No media found in message {message.id} from chat {message.chat.id}")
        return

    file_id, file_ref = unpack_new_file_id(media.file_id)

    # Attempt 1: Delete by file_id
    result_by_id = await Media.collection.delete_one({
        '_id': file_id,
    })

    if result_by_id.deleted_count > 0:
        logger.info(f"File with file_id '{file_id}' was successfully deleted from database (triggered by message {message.id} in chat {message.chat.id}).")
    else:
        # Attempt 2: Delete by normalized file_name, file_size, and mime_type
        normalized_file_name = re.sub(r"([_\-.+])", " ", str(media.file_name))
        query_by_attributes = {
            'file_name': normalized_file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
        }
        result_by_attributes = await Media.collection.delete_many(query_by_attributes)

        if result_by_attributes.deleted_count > 0:
            logger.info(f"{result_by_attributes.deleted_count} file(s) matching attributes (name: '{normalized_file_name}', size: {media.file_size}, mime: {media.mime_type}) were successfully deleted from database (triggered by message {message.id} in chat {message.chat.id}).")
        else:
            logger.info(f"File not found in database using file_id '{file_id}' or attributes (name: '{normalized_file_name}', size: {media.file_size}, mime: {media.mime_type}) (triggered by message {message.id} in chat {message.chat.id}).")
