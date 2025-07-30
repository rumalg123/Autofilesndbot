import info
from pyrogram import enums
import logging
from .db_client import db, mongo_sem

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)



async def add_filter(grp_id, text, reply_text, btn, file, alert):
    collection = db[str(grp_id)]
    async with mongo_sem:
        await collection.create_index('text')
    
    data = {
        'text': str(text),
        'reply': str(reply_text),
        'btn': str(btn),
        'file': str(file),
        'alert': str(alert)
    }
    
    try:
        async with mongo_sem:
            await collection.update_one({'text': str(text)}, {"$set": data}, upsert=True)
    except Exception:
        logger.exception('Some error occurred while updating the filter!', exc_info=True)
             

async def find_filter(group_id, name):
    collection = db[str(group_id)]
    try:
        # Using find_one to retrieve a single matching filter
        async with mongo_sem:
            doc = await collection.find_one({"text": name})
        if doc is None:
            return None, None, None, None
        
        reply_text = doc.get('reply')
        btn = doc.get('btn')
        fileid = doc.get('file')
        alert = doc.get('alert', None)
        return reply_text, btn, alert, fileid
    except Exception:
        logger.exception("Error occurred during find_filter", exc_info=True)
        return None, None, None, None


async def get_filters(group_id):
    collection = db[str(group_id)]
    texts = []
    try:
        cursor = collection.find({})
        async for doc in cursor:
            text_value = doc.get('text')
            if text_value:
                texts.append(text_value)
    except Exception:
        logger.exception("Error occurred during get_filters", exc_info=True)
    return texts


async def delete_filter(message, text, group_id):
    collection = db[str(group_id)]
    myquery = {'text': text}
    try:
        async with mongo_sem:
            count = await collection.count_documents(myquery)
        if count == 1:
            async with mongo_sem:
                await collection.delete_one(myquery)
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
        async with mongo_sem:
            collection_names = await db.list_collection_names()
        if str(group_id) not in collection_names:
            await message.edit_text(f"Nothing to remove in {title}!")
            return

        collection = db[str(group_id)]
        async with mongo_sem:
            await collection.drop()
        await message.edit_text(f"All filters from {title} have been removed")
    except Exception:
        logger.exception("Error occurred during del_all", exc_info=True)
        await message.edit_text("Couldn't remove all filters from group!")


async def count_filters(group_id):
    collection = db[str(group_id)]
    try:
        async with mongo_sem:
            count = await collection.count_documents({})
        return False if count == 0 else count
    except Exception:
        logger.exception("Error occurred during count_filters", exc_info=True)
        return False


async def filter_stats():
    try:
        async with mongo_sem:
            collection_names = await db.list_collection_names()
        if "CONNECTION" in collection_names:
            collection_names.remove("CONNECTION")

        total_count = 0
        for coll_name in collection_names:
            collection = db[coll_name]
            async with mongo_sem:
                cnt = await collection.count_documents({})
            total_count += cnt

        total_collections = len(collection_names)
        return total_collections, total_count
    except Exception:
        logger.exception("Error occurred during filter_stats", exc_info=True)
        return 0, 0
