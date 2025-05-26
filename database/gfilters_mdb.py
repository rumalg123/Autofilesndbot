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


async def add_gfilter(gfilters_collection_name, text, reply_text, btn, file, alert): # Renamed gfilters to gfilters_collection_name
    collection = db[str(gfilters_collection_name)]
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
    except Exception: # Consider more specific pymongo exceptions
        logger.exception('Some error occurred during add_gfilter!', exc_info=True)


async def find_gfilter(gfilters_collection_name, name): # Renamed gfilters
    collection = db[str(gfilters_collection_name)]
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
        logger.exception('Some error occurred during find_gfilter!', exc_info=True)
        return None, None, None, None


async def get_gfilters(gfilters_collection_name): # Renamed gfilters
    collection = db[str(gfilters_collection_name)]
    texts = []
    try:
        # collection.find({}) returns a pymongo cursor, usable with async for
        cursor = collection.find({})
        async for doc in cursor:
            text_value = doc.get('text')
            if text_value: # Ensure 'text' key exists
                texts.append(text_value)
    except Exception:
        logger.exception('Some error occurred during get_gfilters!', exc_info=True)
    return texts


async def delete_gfilter(message, text, gfilters_collection_name): # Renamed gfilters
    collection = db[str(gfilters_collection_name)]
    query = {'text': text}
    try: # Added try-except block for robustness
        # count_documents is awaitable
        count = await collection.count_documents(query)
        if count > 0: # Changed from == 1 to > 0
            # delete_one or delete_many is awaitable
            await collection.delete_one(query)
            await message.reply_text(
                f"'`{text}`'  deleted. I'll not respond to that gfilter anymore.",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await message.reply_text("Couldn't find that gfilter!", quote=True)
    except Exception:
        logger.exception('Some error occurred during delete_gfilter!', exc_info=True)
        await message.reply_text("An error occurred while trying to delete the gfilter.", quote=True)


async def del_allg(message, gfilters_collection_name): # Renamed gfilters
    try:
        # list_collection_names is awaitable
        collection_names = await db.list_collection_names()
        if str(gfilters_collection_name) not in collection_names:
            await message.edit_text("Nothing to Remove !") # Original message
            return

        collection = db[str(gfilters_collection_name)]
        # drop is awaitable
        await collection.drop()
        await message.edit_text("All gfilters have been removed!")
    except Exception:
        logger.exception('Some error occurred during del_allg!', exc_info=True)
        await message.edit_text("Couldn't remove all gfilters!")


async def count_gfilters(gfilters_collection_name): # Renamed gfilters
    collection = db[str(gfilters_collection_name)]
    try:
        # count_documents is awaitable
        count = await collection.count_documents({})
        return count # Returns 0 if no documents, which is fine. False was an unusual choice.
    except Exception:
        logger.exception('Some error occurred during count_gfilters!', exc_info=True)
        return 0 # Return 0 on error


async def gfilter_stats(): # No gfilters parameter needed here
    try:
        # list_collection_names is awaitable
        collection_names = await db.list_collection_names()
        
        # Ensure "CONNECTION" and other system/internal collections are handled correctly
        # It's better to iterate and sum counts for collections that are known to be gfilter collections
        # rather than excluding a few known non-gfilter ones.
        # However, if gfilters are stored in collections with arbitrary names (like group IDs),
        # the original logic of excluding 'CONNECTION' might be the intended way.
        # For now, I'll refine the exclusion list.
        
        internal_collections = ["CONNECTION", "admin", "local", "config"] # Common system/internal collections
        gfilter_collection_names = [
            name for name in collection_names 
            if name not in internal_collections and not name.startswith("system.")
        ]
        # If gfilters are specifically named like 'gfilters' or a list of such names,
        # then the logic should iterate through info.GFILTERS_COLLECTION_NAME or similar.
        # Assuming for now that any non-internal collection could be a gfilter collection
        # as per the original logic's broad sweep minus "CONNECTION".

        total_gfilter_count = 0 # Renamed total_count
        for coll_name in gfilter_collection_names:
            collection = db[coll_name]
            # count_documents is awaitable
            count_in_coll = await collection.count_documents({}) # Renamed cnt
            total_gfilter_count += count_in_coll

        total_gfilter_collections = len(gfilter_collection_names) # Renamed total_collections
        return total_gfilter_collections, total_gfilter_count
    except Exception:
        logger.exception('Some error occurred during gfilter_stats!', exc_info=True)
        return 0, 0
