from pyrogram import Client, filters
import datetime
import time
from database.users_chats_db import db
import info
from utils import broadcast_messages, broadcast_messages_group
import asyncio
        
@Client.on_message(filters.command("broadcast") & filters.user(info.ADMINS) & filters.reply)
async def broadcast_to_users(bot, message): # Renamed from verupikkals
    users = await db.get_all_users()
    message_to_broadcast = message.reply_to_message # Renamed from b_msg
    status_message = await message.reply_text( # Renamed from sts
        text='Broadcasting your messages...'
    )
    start_time = time.time()
    total_users = len(users) # Optimized
    done = 0
    blocked = 0
    deleted = 0
    failed = 0
    success = 0

    for user_doc in users: # Renamed user to user_doc to avoid conflict with users list
        is_success, status_reason = await broadcast_messages(int(user_doc['id']), message_to_broadcast) # Renamed pti to is_success, sh to status_reason
        if is_success: # Clarified condition
            success += 1
        else: # Clarified condition
            if status_reason == "Blocked":
                blocked += 1
            elif status_reason == "Deleted":
                deleted += 1
            elif status_reason == "Error": # Assuming "Error" is a possible status_reason
                failed += 1
        done += 1
        await asyncio.sleep(2) # Kept sleep as it was in original
        if not done % 20:
            await status_message.edit(f"Broadcast in progress:\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nBlocked: {blocked}\nDeleted: {deleted}\nFailed: {failed}")    
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await status_message.edit(f"Broadcast Completed:\nCompleted in {time_taken} seconds.\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nBlocked: {blocked}\nDeleted: {deleted}\nFailed: {failed}")

@Client.on_message(filters.command("group_broadcast") & filters.user(info.ADMINS) & filters.reply)
async def broadcast_group(bot, message):
    groups = await db.get_all_chats()
    message_to_broadcast = message.reply_to_message # Renamed from b_msg
    status_message = await message.reply_text( # Renamed from sts
        text='Broadcasting your messages To Groups...'
    )
    start_time = time.time()
    total_groups = len(groups) # Optimized
    done = 0
    failed = 0
    success = 0

    for group_doc in groups: # Renamed group to group_doc
        is_success, status_reason = await broadcast_messages_group(int(group_doc['id']), message_to_broadcast) # Renamed pti to is_success, sh to status_reason
        if is_success: # Clarified condition
            success += 1
        else: # Clarified condition
            if status_reason == "Error": # Assuming "Error" is the primary failure reason for groups
                failed += 1
            # If broadcast_messages_group can return other statuses like "Blocked" or "Deleted", 
            # additional handling would be needed here.
        done += 1
        # Removed asyncio.sleep(2) as it was not in the original broadcast_group function
        if not done % 20:
            await status_message.edit(f"Broadcast in progress:\n\nTotal Groups {total_groups}\nCompleted: {done} / {total_groups}\nSuccess: {success}\nFailed: {failed}")    
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await status_message.edit(f"Broadcast Completed:\nCompleted in {time_taken} seconds.\n\nTotal Groups {total_groups}\nCompleted: {done} / {total_groups}\nSuccess: {success}\nFailed: {failed}")
