from pymongo import AsyncMongoClient # Changed from motor.motor_asyncio
import info
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Create a MongoDB client using PyMongo.
# PyMongo's MongoClient can be used with async/await in modern Python.
client = AsyncMongoClient(info.DATABASE_URI) # Changed from motor.motor_asyncio.AsyncIOMotorClient
db = client[info.DATABASE_NAME]
collection = db['CONNECTION']


async def add_connection(group_id, user_id):
    # find_one is awaitable with pymongo in an async context
    query = await collection.find_one(
        {"_id": user_id},
        {"_id": 0, "active_group": 0} # Projection
    )
    if query is not None:
        # Ensure group_details exists and is a list
        group_details_list = query.get("group_details", [])
        if isinstance(group_details_list, list):
            group_ids = [x.get("group_id") for x in group_details_list if isinstance(x, dict)]
            if group_id in group_ids:
                return False
        # If group_details is not a list (unexpected), treat as if group_id not found

    group_details_to_add = {"group_id": group_id} # Renamed for clarity
    data_to_insert = { # Renamed for clarity
        "_id": user_id,
        "group_details": [group_details_to_add],
        "active_group": group_id,
    }

    # count_documents is awaitable
    if await collection.count_documents({"_id": user_id}) == 0:
        try:
            # insert_one is awaitable
            await collection.insert_one(data_to_insert)
            return True
        except Exception: # Consider more specific exceptions if possible
            logger.exception("Some error occurred during insert_one!")
            return False # Ensure False is returned on exception
    else:
        try:
            # update_one is awaitable
            await collection.update_one(
                {"_id": user_id},
                {
                    "$push": {"group_details": group_details_to_add},
                    "$set": {"active_group": group_id},
                }
            )
            return True
        except Exception: # Consider more specific exceptions
            logger.exception("Some error occurred during update_one!")
            return False # Ensure False is returned on exception
    # Removed redundant return False from original logic if count_documents was not 0 and no exception occurred


async def active_connection(user_id):
    query = await collection.find_one(
        {"_id": user_id},
        {"_id": 0, "group_details": 0} # Projection
    )
    if not query:
        return None

    group_id = query.get("active_group")
    return int(group_id) if group_id is not None else None


async def all_connections(user_id):
    query = await collection.find_one(
        {"_id": user_id},
        {"_id": 0, "active_group": 0} # Projection
    )
    if query is not None:
        group_details_list = query.get("group_details", [])
        if isinstance(group_details_list, list):
             return [x.get("group_id") for x in group_details_list if isinstance(x, dict) and x.get("group_id") is not None]
        return [] # Return empty list if group_details is not a list or missing
    else:
        return None # Or return [] if an empty list is preferred for non-existent user


async def if_active(user_id, group_id):
    query = await collection.find_one(
        {"_id": user_id},
        {"_id": 0, "group_details": 0} # Projection
    )
    # Ensure group_id is compared correctly (e.g. if one is int and other is str)
    return query is not None and str(query.get("active_group")) == str(group_id)


async def make_active(user_id, group_id):
    # Ensure group_id is string if that's how it's stored, or int if stored as int
    update_result = await collection.update_one(
        {"_id": user_id},
        {"$set": {"active_group": group_id}} # Storing as received (str or int)
    )
    return update_result.modified_count > 0 # Check if modified_count is not 0


async def make_inactive(user_id):
    update_result = await collection.update_one(
        {"_id": user_id},
        {"$set": {"active_group": None}}
    )
    return update_result.modified_count > 0 # Check if modified_count is not 0


async def delete_connection(user_id, group_id_to_delete): # Renamed group_id to group_id_to_delete
    try:
        # Ensure group_id_to_delete type matches stored type if necessary (e.g. int or str)
        update_result = await collection.update_one(
            {"_id": user_id},
            {"$pull": {"group_details": {"group_id": group_id_to_delete}}}
        )
        if update_result.modified_count == 0:
            # This means the group_id was not found in the array, or user_id not found
            return False

        current_user_doc = await collection.find_one({"_id": user_id}) # Renamed query
        if current_user_doc and current_user_doc.get("group_details"):
            # If the active group was the one deleted, set active_group to the last one in the list, or None if list is empty
            if str(current_user_doc.get("active_group")) == str(group_id_to_delete):
                if current_user_doc["group_details"]: # If list is not empty after pull
                    previous_group_id = current_user_doc["group_details"][-1]["group_id"]
                    await collection.update_one(
                        {"_id": user_id},
                        {"$set": {"active_group": previous_group_id}}
                    )
                else: # List is empty after pull
                    await collection.update_one(
                        {"_id": user_id},
                        {"$set": {"active_group": None}}
                    )
        else: # No group_details left, or user document gone (should not happen if update_one succeeded)
            await collection.update_one(
                {"_id": user_id},
                {"$set": {"active_group": None}}
            )
        return True
    except Exception as e:
        logger.exception(f"Some error occurred during delete_connection! {e}")
        return False
