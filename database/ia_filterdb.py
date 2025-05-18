import logging
from struct import pack
import re
import base64

from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
import info
from utils import get_settings, save_group_settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize asynchronous client, database and uMongo instance.
client = AsyncIOMotorClient(info.DATABASE_URI)
db = client[info.DATABASE_NAME]
instance = Instance.from_db(db)

@instance.register
class Media(Document):
    file_id = fields.StringField(attribute='_id')
    file_ref = fields.StringField(allow_none=True)
    file_name = fields.StringField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StringField(allow_none=True)
    mime_type = fields.StringField(allow_none=True)
    caption = fields.StringField(allow_none=True)

    class Meta:
        indexes = ('$file_name', )
        collection_name = info.COLLECTION_NAME


async def save_file(media):
    """Save file in the database.

    Returns a tuple (status, code):
        - status: True if the file was saved; False otherwise.
        - code: an integer code representing the result.
            1: successfully saved,
            0: duplicate file,
            2: validation error.
    """
    # Unpack the new file_id into file_id and file_ref
    file_id, file_ref = unpack_new_file_id(media.file_id)
    # Normalize the file name (replace special characters with spaces)
    file_name = re.sub(r"([_\-.+])", " ", str(media.file_name))
    try:
        file = Media(
            file_id=file_id,
            file_ref=file_ref,
            file_name=file_name,
            file_size=media.file_size,
            file_type=media.file_type,
            mime_type=media.mime_type,
            caption=media.caption.html if media.caption else None,
        )
    except ValidationError:
        logger.exception('Error occurred while validating file data.')
        return False, 2
    else:
        try:
            await file.commit() # type: ignore
        except DuplicateKeyError:
            logger.warning(
                f'{getattr(media, "file_name", "NO_FILE")} is already saved in the database.'
            )
            return False, 0
        else:
            logger.info(f'{getattr(media, "file_name", "NO_FILE")} is saved to the database.')
            return True, 1


async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """For a given query, return (files, next_offset, total_results)."""
    # Adjust results count based on group settings
    if chat_id is not None:
        settings = await get_settings(int(chat_id))
        try:
            max_results = 10 if settings['max_btn'] else int(info.MAX_B_TN)
        except KeyError:
            await save_group_settings(int(chat_id), 'max_btn', False)
            settings = await get_settings(int(chat_id))
            max_results = 10 if settings['max_btn'] else int(info.MAX_B_TN)

    # Clean and prepare the query pattern
    query = re.sub(r"[-:\"';!]", " ", query)
    query = re.sub(r"\s+", " ", query).strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except Exception:
        return []

    if info.USE_CAPTION_FILTER:
        mongo_filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        mongo_filter = {'file_name': regex}

    if file_type:
        mongo_filter['file_type'] = file_type

    # Get the total number of matching documents
    total_results = await Media.count_documents(mongo_filter)
    next_offset = offset + max_results
    if next_offset > total_results:
        next_offset = ''

    # Build a cursor with sorting, skipping, and limiting results
    cursor = Media.find(mongo_filter).sort('$natural', -1).skip(offset).limit(max_results)
    files = await cursor.to_list(length=max_results)

    return files, next_offset, total_results


async def get_bad_files(query, file_type=None, filter=False):
    """Return a list of files that match the query, considering the full result set."""
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except Exception:
        return []

    if info.USE_CAPTION_FILTER:
        mongo_filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        mongo_filter = {'file_name': regex}

    if file_type:
        mongo_filter['file_type'] = file_type

    total_results = await Media.count_documents(mongo_filter)
    cursor = Media.find(mongo_filter).sort('$natural', -1)
    files = await cursor.to_list(length=total_results)

    return files, total_results


async def get_file_details(query):
    """Return details for a file with the given file_id."""
    mongo_filter = {'file_id': query}
    cursor = Media.find(mongo_filter)
    filedetails = await cursor.to_list(length=1)
    return filedetails


def encode_file_id(s: bytes) -> str:
    """Encode a file ID into a URL-safe base64 string."""
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")


def encode_file_ref(file_ref: bytes) -> str:
    """Encode a file reference into a URL-safe base64 string."""
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")


def unpack_new_file_id(new_file_id):
    """Return file_id and file_ref from the given file identifier."""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref
