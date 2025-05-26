from pymongo import MongoClient # Changed from motor.motor_asyncio
import info
from datetime import datetime, date, time 
import logging

logger = logging.getLogger(__name__)

class Database:
    
    def __init__(self, uri, database_name):
        self._client = MongoClient(uri) # Changed from AsyncIOMotorClient
        self.db = self._client[database_name]
        self.col = self.db.users   # Users collection
        self.grp = self.db.groups  # Groups collection

    def new_user(self, id, name):
        return dict(
            id=id,
            name=name,
            ban_status={
                'is_banned': False,
                'ban_reason': "",
            },
            is_premium=False,
            premium_activation_date=None, 
            daily_retrieval_count=0,
            last_retrieval_date=None, 
        )

    def new_group(self, id, title):
        return dict(
            id=id,
            title=title,
            chat_status={
                'is_disabled': False,
                'reason': "",
            },
        )
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)
    
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id': int(id)})
        return bool(user)
    
    async def total_users_count(self):
        # count_documents is awaitable in pymongo's async usage
        count = await self.col.count_documents({})
        return count
    
    async def remove_ban(self, id):
        ban_status = {
            'is_banned': False,
            'ban_reason': ''
        }
        await self.col.update_one({'id': id}, {'$set': {'ban_status': ban_status}})
    
    async def ban_user(self, user_id, ban_reason="No Reason"):
        ban_status = {
            'is_banned': True,
            'ban_reason': ban_reason
        }
        await self.col.update_one({'id': user_id}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, id):
        default = {
            'is_banned': False,
            'ban_reason': ''
        }
        user = await self.col.find_one({'id': int(id)})
        if not user:
            return default
        return user.get('ban_status', default)

    async def get_all_users(self):
        # Changed from .to_list(length=None) to async list comprehension
        return [user async for user in self.col.find({})]
    
    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    async def get_banned(self):
        users_cursor = self.col.find({'ban_status.is_banned': True})
        chats_cursor = self.grp.find({'chat_status.is_disabled': True})
        # Async list comprehensions are standard for pymongo async cursors
        b_users = [user['id'] async for user in users_cursor]
        b_chats = [chat['id'] async for chat in chats_cursor]
        return b_users, b_chats

    async def add_chat(self, chat, title):
        chat_doc = self.new_group(chat, title)
        await self.grp.insert_one(chat_doc)
    
    async def get_chat(self, chat):
        chat_doc = await self.grp.find_one({'id': int(chat)})
        return False if not chat_doc else chat_doc.get('chat_status')
    
    async def re_enable_chat(self, id):
        chat_status = {
            'is_disabled': False,
            'reason': "",
        }
        await self.grp.update_one({'id': int(id)}, {'$set': {'chat_status': chat_status}})
        
    async def update_settings(self, id, settings):
        await self.grp.update_one({'id': int(id)}, {'$set': {'settings': settings}})
        
    async def get_settings(self, id):
        default_settings = {
            'button': info.SINGLE_BUTTON,
            'botpm': info.P_TTI_SHOW_OFF,
            'file_secure': info.PROTECT_CONTENT,
            'imdb': info.IMDB,
            'spell_check': info.SPELL_CHECK_REPLY,
            'welcome': info.MELCOW_NEW_USERS,
            'auto_delete': info.AUTO_DELETE,
            'auto_ffilter': info.AUTO_FFILTER,
            'max_btn': info.MAX_BTN,
            'template': info.IMDB_TEMPLATE
        }
        chat_doc = await self.grp.find_one({'id': int(id)})
        if chat_doc:
            stored_settings = chat_doc.get('settings')
            if stored_settings:
                merged_settings = default_settings.copy()
                merged_settings.update(stored_settings)
                return merged_settings
        return default_settings.copy() 
    
    async def disable_chat(self, chat, reason="No Reason"):
        chat_status = {
            'is_disabled': True,
            'reason': reason,
        }
        await self.grp.update_one({'id': int(chat)}, {'$set': {'chat_status': chat_status}})
    
    async def total_chat_count(self):
        # count_documents is awaitable in pymongo's async usage
        count = await self.grp.count_documents({})
        return count
    
    async def get_all_chats(self):
        # Changed from .to_list(length=None) to async list comprehension
        return [chat async for chat in self.grp.find({})]
    
    async def get_db_size(self):
        # db.command is awaitable in pymongo's async usage
        stats = await self.db.command("dbstats")
        return stats.get('dataSize', 0)

    async def update_premium_status(self, user_id, is_premium):
        if is_premium:
            logger.info(f"Adding user {user_id} to premium.")
        else:
            logger.info(f"Removing user {user_id} from premium.")
        activation_date = datetime.utcnow() if is_premium else None 
        await self.col.update_one(
            {'id': user_id},
            {'$set': {'is_premium': is_premium, 'premium_activation_date': activation_date}}
        )

    async def increment_retrieval_count(self, user_id):
        user = await self.col.find_one({'id': user_id})
        if not user:
            # If user does not exist, add them with a default name and re-fetch.
            await self.add_user(user_id, f"User {user_id}")
            user = await self.col.find_one({'id': user_id})
            if not user: # Should ideally not happen after add_user
                logger.error(f"Failed to add or find user {user_id} after attempting to add them in increment_retrieval_count.")
                return float('inf') # Error case or prevent further processing

        today_utc = datetime.utcnow().date() 
        today_dt_utc = datetime.combine(today_utc, datetime.min.time()) 

        last_retrieval_val = user.get('last_retrieval_date') 
        daily_retrieval_count = user.get('daily_retrieval_count', 0)

        retrieval_date_obj = None
        if isinstance(last_retrieval_val, datetime): 
            retrieval_date_obj = last_retrieval_val.date()
        elif isinstance(last_retrieval_val, date): 
            retrieval_date_obj = last_retrieval_val
        
        if retrieval_date_obj != today_utc: 
            daily_retrieval_count = 0
        
        daily_retrieval_count += 1
        
        await self.col.update_one(
            {'id': user_id},
            {'$set': {
                'daily_retrieval_count': daily_retrieval_count, 
                'last_retrieval_date': today_dt_utc  
                }
            }
        )
        return daily_retrieval_count

    async def get_user_data(self, user_id):
        user = await self.col.find_one({'id': user_id})
        if not user:
            # If user doesn't exist, add them with a default name and then return their data.
            await self.add_user(user_id, f"User {user_id}")
            user = await self.col.find_one({'id': user_id})
            if not user: # Should ideally not happen if add_user was successful
                 logger.error(f"Failed to add or find user {user_id} after attempting to add them in get_user_data.")
                 return { # Return a default structure in case of very rare failure
                    'is_premium': False,
                    'premium_activation_date': None,
                    'daily_retrieval_count': 0,
                    'last_retrieval_date': None
                }

        return {
            'is_premium': user.get('is_premium', False),
            'premium_activation_date': user.get('premium_activation_date'),
            'daily_retrieval_count': user.get('daily_retrieval_count', 0),
            'last_retrieval_date': user.get('last_retrieval_date')
        }


db = Database(info.DATABASE_URI, info.DATABASE_NAME)
