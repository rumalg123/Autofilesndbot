import info
from .db_client import db, mongo_sem
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Use the shared DB client
collection = db['CONNECTION']


async def add_connection(group_id, user_id):
    async with mongo_sem:
        query = await collection.find_one(
            {"_id": user_id},
            {"_id": 0, "active_group": 0}
        )
    if query is not None:
        group_ids = [x["group_id"] for x in query["group_details"]]
        if group_id in group_ids:
            return False

    group_details = {"group_id": group_id}
    data = {
        "_id": user_id,
        "group_details": [group_details],
        "active_group": group_id,
    }

    async with mongo_sem:
        exists = await collection.count_documents({"_id": user_id})
    if exists == 0:
        try:
            async with mongo_sem:
                await collection.insert_one(data)
            return True
        except Exception:
            logger.exception("Some error occurred during insert_one!")
    else:
        try:
            async with mongo_sem:
                await collection.update_one(
                    {"_id": user_id},
                    {
                        "$push": {"group_details": group_details},
                        "$set": {"active_group": group_id},
                    }
                )
            return True
        except Exception:
            logger.exception("Some error occurred during update_one!")
    return False


async def active_connection(user_id):
    async with mongo_sem:
        query = await collection.find_one(
            {"_id": user_id},
            {"_id": 0, "group_details": 0}
        )
    if not query:
        return None

    group_id = query.get("active_group")
    return int(group_id) if group_id is not None else None


async def all_connections(user_id):
    async with mongo_sem:
        query = await collection.find_one(
            {"_id": user_id},
            {"_id": 0, "active_group": 0}
        )
    if query is not None:
        return [x["group_id"] for x in query["group_details"]]
    else:
        return None


async def if_active(user_id, group_id):
    async with mongo_sem:
        query = await collection.find_one(
            {"_id": user_id},
            {"_id": 0, "group_details": 0}
        )
    return query is not None and query.get("active_group") == group_id


async def make_active(user_id, group_id):
    async with mongo_sem:
        update_result = await collection.update_one(
            {"_id": user_id},
            {"$set": {"active_group": group_id}}
        )
    return update_result.modified_count != 0


async def make_inactive(user_id):
    async with mongo_sem:
        update_result = await collection.update_one(
            {"_id": user_id},
            {"$set": {"active_group": None}}
        )
    return update_result.modified_count != 0


async def delete_connection(user_id, group_id):
    try:
        async with mongo_sem:
            update_result = await collection.update_one(
                {"_id": user_id},
                {"$pull": {"group_details": {"group_id": group_id}}}
            )
        if update_result.modified_count == 0:
            return False

        async with mongo_sem:
            query = await collection.find_one({"_id": user_id})
        if query and query.get("group_details"):
            if query.get("active_group") == group_id:
                previous_group = query["group_details"][-1]["group_id"]
                async with mongo_sem:
                    await collection.update_one(
                        {"_id": user_id},
                        {"$set": {"active_group": previous_group}}
                    )
        else:
            async with mongo_sem:
                await collection.update_one(
                    {"_id": user_id},
                    {"$set": {"active_group": None}}
                )
        return True
    except Exception as e:
        logger.exception(f"Some error occurred during delete_connection! {e}")
        return False
