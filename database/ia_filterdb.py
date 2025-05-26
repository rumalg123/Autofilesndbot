import logging
from struct import pack
import re
import base64

from pyrogram.file_id import FileId
from pymongo import AsyncMongoClient # Changed from motor.motor_asyncio
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
# Removed: from motor.motor_asyncio import AsyncIOMotorClient 
from marshmallow.exceptions import ValidationError
import info
from utils import get_settings, save_group_settings # Assuming these utils are not db-driver specific

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize asynchronous client, database and uMongo instance.
client = AsyncMongoClient(info.DATABASE_URI) # Changed from AsyncIOMotorClient
db = client[info.DATABASE_NAME]
instance = Instance.from_db(db) # Assuming umongo handles the pymongo.Database object for async

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
            2: validation error,
            3: general database error or other commit failure.
    """
    file_id, file_ref = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"([_\-.+])", " ", str(media.file_name))
    try:
        file_doc = Media( # Renamed file to file_doc to avoid conflict with built-in file
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
            await file_doc.commit() 
        except DuplicateKeyError:
            logger.warning(
                f'{getattr(media, "file_name", "NO_FILE")} is already saved in the database.'
            )
            return False, 0
        except Exception as e:
            logger.error(f"Error committing file {getattr(media, 'file_name', 'NO_FILE')} to database: {e}", exc_info=True)
            return False, 3
        else:
            logger.info(f'{getattr(media, "file_name", "NO_FILE")} is saved to the database.')
            return True, 1


async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False): # filter param seems unused
    """For a given query, return (files, next_offset, total_results)."""
    if chat_id is not None:
        settings = await get_settings(int(chat_id))
        try:
            max_results = 10 if settings['max_btn'] else int(info.MAX_B_TN)
        except KeyError: # Should ideally not happen if settings are always populated
            await save_group_settings(int(chat_id), 'max_btn', False) # Default to False if not found
            # settings = await get_settings(int(chat_id)) # Re-fetch if needed, or use default
            max_results = 10 # Default if error or not found after attempting save

    query_cleaned = re.sub(r"[-:\"';!]", " ", query) # Renamed query to query_cleaned for clarity
    query_cleaned = re.sub(r"\s+", " ", query_cleaned).strip()
    if not query_cleaned:
        raw_pattern = '.'
    elif ' ' not in query_cleaned:
        raw_pattern = r'(\b|[\.\+\-_])' + re.escape(query_cleaned) + r'(\b|[\.\+\-_])' # Added re.escape
    else:
        raw_pattern = query_cleaned.replace(' ', r'.*[\s\.\+\-_]') # Consider re.escape for parts of query_cleaned if they can have regex chars
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error as e: # More specific exception
        logger.error(f"Regex compilation error for pattern '{raw_pattern}': {e}")
        return [], '', 0 # Return empty results on regex error

    mongo_query_filter = {'file_name': regex} # Renamed mongo_filter
    if info.USE_CAPTION_FILTER:
        mongo_query_filter = {'$or': [{'file_name': regex}, {'caption': regex}]}

    if file_type:
        mongo_query_filter['file_type'] = file_type

    total_results = await Media.count_documents(mongo_query_filter)
    
    next_offset_val = offset + max_results # Renamed next_offset
    if next_offset_val >= total_results: # Changed > to >=
        next_offset_val = ''

    cursor = Media.find(mongo_query_filter).sort('$natural', -1).skip(offset).limit(max_results)
    # Changed from to_list to async list comprehension
    files = [doc async for doc in cursor] 

    return files, next_offset_val, total_results


async def get_bad_files(query, file_type=None, filter=False): # filter param seems unused
    """Return a list of files that match the query, considering the full result set."""
    query_cleaned = query.strip() # Renamed query
    if not query_cleaned:
        raw_pattern = '.'
    elif ' ' not in query_cleaned:
        raw_pattern = r'(\b|[\.\+\-_])' + re.escape(query_cleaned) + r'(\b|[\.\+\-_])' # Added re.escape
    else:
        raw_pattern = query_cleaned.replace(' ', r'.*[\s\.\+\-_]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error as e: # More specific exception
        logger.error(f"Regex compilation error for pattern '{raw_pattern}' in get_bad_files: {e}")
        return [], 0

    mongo_query_filter = {'file_name': regex} # Renamed mongo_filter
    if info.USE_CAPTION_FILTER:
        mongo_query_filter = {'$or': [{'file_name': regex}, {'caption': regex}]}

    if file_type:
        mongo_query_filter['file_type'] = file_type

    total_results = await Media.count_documents(mongo_query_filter)
    cursor = Media.find(mongo_query_filter).sort('$natural', -1) # No limit, get all matching
    # Changed from to_list to async list comprehension
    files = [doc async for doc in cursor]

    return files, total_results


async def get_file_details(file_id_query): # Renamed query to file_id_query
    """Return details for a file with the given file_id."""
    mongo_query_filter = {'file_id': file_id_query} # Renamed mongo_filter
    cursor = Media.find(mongo_query_filter) # Limit is not strictly needed if file_id is unique, but good for safety
    # Changed from to_list to async list comprehension, expect 0 or 1 result
    file_details_list = [doc async for doc in cursor] # Renamed filedetails
    return file_details_list # Returns a list (empty or with one item)


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
