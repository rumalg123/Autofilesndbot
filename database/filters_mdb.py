from pymongo import AsyncMongoClient # Changed from motor.motor_asyncio
import info
from pyrogram import enums
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR) # Original level was ERROR, can be changed to INFO or DEBUG if needed

# Create a MongoDB client using PyMongo.
# PyMongo's MongoClient can be used with async/await in modern Python.
client = AsyncMongoClient(info.DATABASE_URI) # Changed from motor.motor_asyncio.AsyncIOMotorClient
db = client[info.DATABASE_NAME]


async def add_filter(grp_id, text, reply_text, btn, file, alert):
    collection = db[str(grp_id)]
    # Optional: await collection.create_index([('text', 'text')]) # create_index is also awaitable if needed
    
    data = {
        'text': str(text),
        'reply': str(reply_text),
        'btn': str(btn),
        'file': str(file),
        'alert': str(alert)
    }
    
    try:
        # update_one is awaitable with pymongo in an async context
        await collection.update_one({'text': str(text)}, {"$set": data}, upsert=True)
    except Exception: # Consider more specific pymongo exceptions if appropriate
        logger.exception('Some error occurred while updating the filter!', exc_info=True)
             

async def find_filter(group_id, name):
    collection = db[str(group_id)]
    try:
        # find_one is awaitable
        doc = await collection.find_one({"text": name})
        if doc is None:
            return None, None, None, None
        
        reply_text = doc.get('reply')
        btn = doc.get('btn')
        fileid = doc.get('file')
        alert = doc.get('alert', None) # Default to None if 'alert' is not present
        return reply_text, btn, alert, fileid
    except Exception:
        logger.exception("Error occurred during find_filter", exc_info=True)
        return None, None, None, None


async def get_filters(group_id):
    collection = db[str(group_id)]
    texts = []
    try:
        # collection.find({}) returns a pymongo cursor, usable with async for
        cursor = collection.find({}) 
        async for doc in cursor:
            text_value = doc.get('text')
            if text_value: # Ensure 'text' key exists
                texts.append(text_value)
    except Exception:
        logger.exception("Error occurred during get_filters", exc_info=True)
    return texts


async def delete_filter(message, text, group_id):
    collection = db[str(group_id)]
    myquery = {'text': text}
    try:
        # count_documents is awaitable
        count = await collection.count_documents(myquery)
        if count > 0: # Changed from == 1 to > 0 to handle potential duplicates if any (though upsert should prevent)
            # delete_one or delete_many is awaitable
            await collection.delete_one(myquery) # If multiple should be deleted, use delete_many
            await message.reply_text(
                f"'`{text}`'  deleted. I'll not respond to that filter anymore.",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await message.reply_text("Couldn't find that filter!", quote=True)
    except Exception:
        logger.exception("Error occurred during delete_filter", exc_info=True)


async def del_all(message, group_id, title):
    try:
        # list_collection_names is awaitable
        collection_names = await db.list_collection_names()
        if str(group_id) not in collection_names:
            await message.edit_text(f"Nothing to remove in {title}!")
            return

        collection = db[str(group_id)]
        # drop is awaitable
        await collection.drop()
        await message.edit_text(f"All filters from {title} have been removed")
    except Exception:
        logger.exception("Error occurred during del_all", exc_info=True)
        await message.edit_text("Couldn't remove all filters from group!")


async def count_filters(group_id):
    collection = db[str(group_id)]
    try:
        # count_documents is awaitable
        count = await collection.count_documents({})
        return count # Returns 0 if no documents, which is fine. False was an unusual choice.
    except Exception:
        logger.exception("Error occurred during count_filters", exc_info=True)
        return 0 # Return 0 on error, or False if specifically needed by caller


async def filter_stats():
    try:
        # list_collection_names is awaitable
        collection_names = await db.list_collection_names()
        
        # Ensure "CONNECTION" is handled correctly if it might not exist
        if "CONNECTION" in collection_names:
            collection_names.remove("CONNECTION")
        # Add other system/internal collections if they exist and should be excluded
        internal_collections = ["admin", "local", "config"] # Common system collections
        collection_names = [name for name in collection_names if name not in internal_collections and not name.startswith("system.")]


        total_filter_count = 0 # Renamed total_count
        for coll_name in collection_names:
            collection = db[coll_name]
            # count_documents is awaitable
            count_in_coll = await collection.count_documents({}) # Renamed cnt
            total_filter_count += count_in_coll

        total_filter_collections = len(collection_names) # Renamed total_collections
        return total_filter_collections, total_filter_count
    except Exception:
        logger.exception("Error occurred during filter_stats", exc_info=True)
        return 0, 0
