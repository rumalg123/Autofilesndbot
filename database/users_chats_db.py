import motor.motor_asyncio
import info
from datetime import datetime, date

class Database:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
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
        # Returns a list of all user documents
        return await self.col.find({}).to_list(length=None)
    
    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    async def get_banned(self):
        # Returns lists of banned user IDs and disabled chat IDs
        users_cursor = self.col.find({'ban_status.is_banned': True})
        chats_cursor = self.grp.find({'chat_status.is_disabled': True})
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
        default = {
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
            return chat_doc.get('settings', default)
        return default
    
    async def disable_chat(self, chat, reason="No Reason"):
        chat_status = {
            'is_disabled': True,
            'reason': reason,
        }
        await self.grp.update_one({'id': int(chat)}, {'$set': {'chat_status': chat_status}})
    
    async def total_chat_count(self):
        count = await self.grp.count_documents({})
        return count
    
    async def get_all_chats(self):
        # Returns a list of all group documents
        return await self.grp.find({}).to_list(length=None)
    
    async def get_db_size(self):
        # Returns the database size (dataSize in bytes)
        stats = await self.db.command("dbstats")
        return stats.get('dataSize', 0)

    async def update_premium_status(self, user_id, is_premium):
        activation_date = datetime.now() if is_premium else None
        await self.col.update_one(
            {'id': user_id},
            {'$set': {'is_premium': is_premium, 'premium_activation_date': activation_date}}
        )

    async def increment_retrieval_count(self, user_id):
        user = await self.col.find_one({'id': user_id})
        if not user:
            # This case should ideally not be hit if add_user is called correctly before this.
            # Returning a very high number will cause the limit check to fail.
            return float('inf') 

        today = date.today()
        last_retrieval_val = user.get('last_retrieval_date') # This could be None, date, or datetime
        daily_retrieval_count = user.get('daily_retrieval_count', 0)

        retrieval_date_obj = None
        if isinstance(last_retrieval_val, datetime):
            retrieval_date_obj = last_retrieval_val.date()
        elif isinstance(last_retrieval_val, date):
            retrieval_date_obj = last_retrieval_val
        # If last_retrieval_val is None, retrieval_date_obj remains None; (None != today) is True.

        if retrieval_date_obj != today:
            daily_retrieval_count = 0
        
        daily_retrieval_count += 1
        
        # Store today's date (as a date object, Motor/MongoDB will handle BSON conversion)
        await self.col.update_one(
            {'id': user_id},
            {'$set': {
                'daily_retrieval_count': daily_retrieval_count, 
                'last_retrieval_date': today  # Storing datetime.date object
                }
            }
        )
        return daily_retrieval_count

    async def get_user_data(self, user_id):
        user = await self.col.find_one({'id': user_id})
        if not user:
            return None
        
        return {
            'is_premium': user.get('is_premium', False),
            'premium_activation_date': user.get('premium_activation_date'),
            'daily_retrieval_count': user.get('daily_retrieval_count', 0),
            'last_retrieval_date': user.get('last_retrieval_date')
        }


db = Database(info.DATABASE_URI, info.DATABASE_NAME)
