import info
from .db_client import db, mongo_sem
from pyrogram import enums
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)



async def add_gfilter(gfilters, text, reply_text, btn, file, alert):
    collection = db[str(gfilters)]
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
        logger.exception('Some error occurred during add_gfilter!', exc_info=True)


async def find_gfilter(gfilters, name):
    collection = db[str(gfilters)]
    try:
        # Fetch one matching document using find_one which is more efficient
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
        logger.exception('Some error occurred during find_gfilter!', exc_info=True)
        return None, None, None, None


async def get_gfilters(gfilters):
    collection = db[str(gfilters)]
    texts = []
    try:
        cursor = collection.find({})
        async for doc in cursor:
            text_value = doc.get('text')
            if text_value:
                texts.append(text_value)
    except Exception:
        logger.exception('Some error occurred during get_gfilters!', exc_info=True)
    return texts


async def delete_gfilter(message, text, gfilters):
    collection = db[str(gfilters)]
    query = {'text': text}
    async with mongo_sem:
        count = await collection.count_documents(query)
    if count == 1:
        async with mongo_sem:
            await collection.delete_one(query)
        await message.reply_text(
            f"'`{text}`'  deleted. I'll not respond to that gfilter anymore.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    else:
        await message.reply_text("Couldn't find that gfilter!", quote=True)


async def del_allg(message, gfilters):
    try:
        async with mongo_sem:
            collection_names = await db.list_collection_names()
        if str(gfilters) not in collection_names:
            await message.edit_text("Nothing to Remove !")
            return

        collection = db[str(gfilters)]
        async with mongo_sem:
            await collection.drop()
        await message.edit_text("All gfilters have been removed!")
    except Exception:
        logger.exception('Some error occurred during del_allg!', exc_info=True)
        await message.edit_text("Couldn't remove all gfilters!")


async def count_gfilters(gfilters):
    collection = db[str(gfilters)]
    try:
        async with mongo_sem:
            count = await collection.count_documents({})
        return False if count == 0 else count
    except Exception:
        logger.exception('Some error occurred during count_gfilters!', exc_info=True)
        return False


async def gfilter_stats():
    try:
        async with mongo_sem:
            collection_names = await db.list_collection_names()
        if "CONNECTION" in collection_names:
            collection_names.remove("CONNECTION")

        total_count = 0
        for coll_name in collection_names:
            collection = db[coll_name]
            async with mongo_sem:
                count = await collection.count_documents({})
            total_count += count

        total_collections = len(collection_names)
        return total_collections, total_count
    except Exception:
        logger.exception('Some error occurred during gfilter_stats!', exc_info=True)
        return 0, 0
