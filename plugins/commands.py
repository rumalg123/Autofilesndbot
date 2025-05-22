import os
import logging
import random
import asyncio
import sys


from Script import script
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified
from database.ia_filterdb import Media, get_file_details, unpack_new_file_id, get_bad_files
from database.users_chats_db import db
#from info import CHANNELS, ADMINS, AUTH_CHANNEL, LOG_CHANNEL, PICS, BATCH_FILE_CAPTION, CUSTOM_FILE_CAPTION, SUPPORT_CHAT, PROTECT_CONTENT, REQST_CHANNEL, SUPPORT_CHAT_ID, MAX_B_TN, FILE_STORE_CHANNEL, PUBLIC_FILE_STORE, KEEP_ORIGINAL_CAPTION, initialize_configuration
import info
from utils import get_settings, get_size, is_subscribed, save_group_settings, temp
from database.connections_mdb import active_connection
import re
import json
import base64
import time
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
RESTART_FILE = "restart_msg.txt"

BATCH_FILES = {}

CMD = ["/", "."]

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [[
                    InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ ➕', url=f"https://t.me/{temp.U_NAME}?startgroup=true")
                ],[
                    InlineKeyboardButton('ᴏᴡɴᴇʀ', callback_data="owner_info"),
                    InlineKeyboardButton('ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=f"https://t.me/{info.SUPPORT_CHAT}")
                ],[
                    InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
                    InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about')
                ],[
                    InlineKeyboardButton('ꜱᴇᴀʀᴄʜ ᴅʀᴀᴍᴀꜱ', switch_inline_query_current_chat='')
                  ],
        #[InlineKeyboardButton("🔞 Adult Content Channel", url="https://t.me/eseoaOF")],
        [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")],]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(script.START_TXT.format(message.from_user.mention if message.from_user else message.chat.title, temp.U_NAME, temp.B_NAME), reply_markup=reply_markup)
        await asyncio.sleep(2)
        if not await db.get_chat(message.chat.id):
            total=await client.get_chat_members_count(message.chat.id)
            await client.send_message(info.LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown"))
            await db.add_chat(message.chat.id, message.chat.title)
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(info.LOG_CHANNEL, script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention))
    if len(message.command) != 2:
        buttons = [[
                    InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ ➕', url=f"https://t.me/{temp.U_NAME}?startgroup=true")
                ],[
                    InlineKeyboardButton('ᴏᴡɴᴇʀ', callback_data="owner_info"),
                    InlineKeyboardButton('ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=f"https://t.me/{info.SUPPORT_CHAT}")
                ],[
                    InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
                    InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about'),
                ],[
                    InlineKeyboardButton('ꜱᴇᴀʀᴄʜ ᴅʀᴀᴍᴀꜱ', switch_inline_query_current_chat='')
                  ],
            #[InlineKeyboardButton("🔞 Adult Content Channel", url="https://t.me/eseoaOF")],
            [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=random.choice(info.PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    if info.AUTH_CHANNEL and not await is_subscribed(client, message):
        try:
            invite_link = await client.create_chat_invite_link(int(info.AUTH_CHANNEL))
        except ChatAdminRequired:
            logger.error("Make sure Bot is admin in Force Sub channel")
        btn = [
            [
                InlineKeyboardButton(
                    "🤖 𝖩𝗈𝗂𝗇 𝖴𝗉𝖽𝖺𝗍𝖾𝗌 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 🤖", url=invite_link.invite_link
                )
            ]
        ]

        if message.command[1] != "subscribe" or message.command[1] != "send_all":
            try:
                kk, file_id = message.command[1].split("_", 1)
                pre = 'checksubp' if kk == 'filep' else 'checksub' 
                btn.append([InlineKeyboardButton("⟳ 𝖳𝗋𝗒 𝖠𝗀𝖺𝗂𝗇 ⟳", callback_data=f"{pre}#{file_id}")])
            except (IndexError, ValueError):
                btn.append([InlineKeyboardButton("⟳ 𝖳𝗋𝗒 𝖠𝗀𝖺𝗂𝗇 ⟳", url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}")])
        await client.send_message(
            chat_id=message.from_user.id,
            text="**Please Join My Updates Channel to use this Bot!**",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.MARKDOWN
            )
    if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help"]:
        buttons = [[
                    InlineKeyboardButton('➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ ➕', url=f"https://t.me/{temp.U_NAME}?startgroup=true")
                ],[
                    InlineKeyboardButton('ᴏᴡɴᴇʀ', callback_data="owner_info"),
                    InlineKeyboardButton('ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=f"https://t.me/{info.SUPPORT_CHAT}")
                ],[
                    InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
                    InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about')
                ],[
                    InlineKeyboardButton('ꜱᴇᴀʀᴄʜ ᴅʀᴀᴍᴀꜱ', switch_inline_query_current_chat='')
                    
                  ],
            #[InlineKeyboardButton("🔞 Adult Content Channel", url="https://t.me/eseoaOF")],
            [InlineKeyboardButton("🍺 Buy Me A Beer", url="https://buymeacoffee.com/matthewmurdock001")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=random.choice(info.PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    data = message.command[1]
    try:
        pre, file_id = data.split('_', 1)
    except:
        file_id = data
        pre = ""
        
    if data.startswith("all"):
        _, key, pre = data.split("_", 2)
        #logger.info(f"Sending all files of {key} to {pre}")
        files = temp.FILES_IDS.get(key)
        #logger.info(files)
        if not files:
            await message.reply('<b><i>No such file exist.</b></i>')
        
        for file in files:
            title = file.file_name
            size=get_size(file.file_size)
            #f_caption=file.caption
            f_caption = None
            if info.KEEP_ORIGINAL_CAPTION:
                try:
                    f_caption = file.caption
                except :
                    f_caption = file.file_name
            elif info.CUSTOM_FILE_CAPTION:
                try:
                    f_caption=info.CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
                except:
                    f_caption=f_caption
            if f_caption is None:
                f_caption = f"{file.file_name}"
            await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file.file_id,
                caption=f_caption,
                protect_content=True if pre == 'filep' else False,
                parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION else enums.ParseMode.DEFAULT,
                reply_markup=InlineKeyboardMarkup( [ [ InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL) ],
                                                     # [InlineKeyboardButton("🔞 Adult Content Channel",
                                                     #                       url="https://t.me/eseoaOF")],
                                                     [InlineKeyboardButton("🍺 Buy Me A Beer",
                                                                           url="https://buymeacoffee.com/matthewmurdock001")],
                                                     ] ),
            )
    
    if data.split("-", 1)[0] == "BATCH":
        sts = await message.reply("<b>Please wait...</b>")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            file = await client.download_media(file_id)
            try: 
                with open(file) as file_data:
                    msgs=json.loads(file_data.read())
            except:
                await sts.edit("FAILED")
                await client.send_message(info.LOG_CHANNEL, "UNABLE TO OPEN FILE.")
            os.remove(file)
            BATCH_FILES[file_id] = msgs
        for msg in msgs:
            title = msg.get("title")
            size=get_size(int(msg.get("size", 0)))
            #f_caption=msg.get("caption", "")
            f_caption = None
            if info.KEEP_ORIGINAL_CAPTION:
                try:
                    f_caption = msg.get("caption")
                except:
                    f_caption = msg.get("title")
            elif info.BATCH_FILE_CAPTION:
                try:
                    f_caption=info.BATCH_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
                except Exception as e:
                    logger.exception(e)
                    f_caption=f_caption
            if f_caption is None:
                f_caption = f"{title}"
            try:
                await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=msg.get("file_id"),
                    caption=f_caption,
                    protect_content=msg.get('protect', False),
                    parse_mode= enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION else enums.ParseMode.DEFAULT,
                    reply_markup=InlineKeyboardMarkup( [ [ InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL) ],
                                                         # [InlineKeyboardButton("🔞 Adult Content Channel",
                                                         #                       url="https://t.me/eseoaOF")],
                                                         [InlineKeyboardButton("🍺 Buy Me A Beer",
                                                                               url="https://buymeacoffee.com/matthewmurdock001")],
                                                         ] ),
                    
                )
            except FloodWait as e:
                await asyncio.sleep(e.x) # type: ignore[attr-defined]
                logger.warning(f"Floodwait of {e.x} sec.") # type: ignore[attr-defined]
                await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=msg.get("file_id"),
                    caption=f_caption,
                    parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION else enums.ParseMode.DEFAULT,
                    protect_content=msg.get('protect', False),
                    reply_markup=InlineKeyboardMarkup( [ [ InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL) ],
                                                         # [InlineKeyboardButton("🔞 Adult Content Channel",
                                                         #                       url="https://t.me/eseoaOF")],
                                                         [InlineKeyboardButton("🍺 Buy Me A Beer",
                                                                               url="https://buymeacoffee.com/matthewmurdock001")],
                                                         ] ),
                )
            except Exception as e:
                logger.warning(e, exc_info=True)
                continue
            await asyncio.sleep(1) 
        await sts.delete()
    elif data.split("-", 1)[0] == "DSTORE":
        sts = await message.reply("<b>Please wait...</b>")
        b_string = data.split("-", 1)[1]
        decoded = (base64.urlsafe_b64decode(b_string + "=" * (-len(b_string) % 4))).decode("ascii")
        try:
            f_msg_id, l_msg_id, f_chat_id, protect = decoded.split("_", 3)
        except:
            f_msg_id, l_msg_id, f_chat_id = decoded.split("_", 2)
            protect = "/pbatch" if info.PROTECT_CONTENT else "batch"
        diff = int(l_msg_id) - int(f_msg_id)
        async for msg in client.iter_messages(int(f_chat_id), int(l_msg_id), int(f_msg_id)):
            if msg.media:
                media = getattr(msg, msg.media.value)

                if info.KEEP_ORIGINAL_CAPTION:
                    try:
                        f_caption = getattr(msg,'caption','')
                    except:
                        f_caption = getattr(media, 'file_name', '')
                elif info.BATCH_FILE_CAPTION:
                    try:
                        f_caption=info.BATCH_FILE_CAPTION.format(file_name=getattr(media, 'file_name', ''), file_size=getattr(media, 'file_size', ''), file_caption=getattr(msg, 'caption', ''))
                    except Exception as e:
                        logger.exception(e)
                        f_caption = getattr(msg, 'caption', '')
                else:
                    media = getattr(msg, msg.media.value)
                    file_name = getattr(media, 'file_name', '')
                    f_caption = getattr(msg, 'caption', file_name)
                try:
                    await msg.copy(message.chat.id, caption=f_caption, protect_content=True if protect == "/pbatch" else False,)
                except FloodWait as e:
                    await asyncio.sleep(e.x) # type: ignore[attr-defined]
                    await msg.copy(message.chat.id, caption=f_caption, protect_content=True if protect == "/pbatch" else False)
                except Exception as e:
                    logger.exception(e)
                    continue
            elif msg.empty:
                continue
            else:
                try:
                    await msg.copy(message.chat.id, protect_content=True if protect == "/pbatch" else False)
                except FloodWait as e:
                    await asyncio.sleep(e.x) # type: ignore[attr-defined]
                    await msg.copy(message.chat.id, protect_content=True if protect == "/pbatch" else False)
                except Exception as e:
                    logger.exception(e)
                    continue
            await asyncio.sleep(1) 
        await sts.delete()
        

    files_ = await get_file_details(file_id)           
    if not files_:
        pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
        try:
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file_id,
                parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION else enums.ParseMode.DEFAULT,
                protect_content=True if pre == 'filep' else False,
                reply_markup=InlineKeyboardMarkup( [ [ InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL) ],
                                                     # [InlineKeyboardButton("🔞 Adult Content Channel",
                                                     #                       url="https://t.me/eseoaOF")],
                                                     [InlineKeyboardButton("🍺 Buy Me A Beer",
                                                                           url="https://buymeacoffee.com/matthewmurdock001")],
                                                     ] ),
            )
            filetype = msg.media
            file = getattr(msg, filetype.value)
            title = file.file_name
            size=get_size(file.file_size)
            f_caption = f"<code>{title}</code>"
            if info.KEEP_ORIGINAL_CAPTION:
                try:
                    f_caption = file.caption
                except:
                    f_caption = f"<code>{title}</code>"
            elif info.CUSTOM_FILE_CAPTION:
                try:
                    f_caption=info.CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='')
                except Exception as e:
                    logger.exception(e)
                    f_caption=f_caption

            await msg.edit_caption(f_caption)
        except:
            pass
        await message.reply('<b><i>No such file exist.</b></i>')
    files = files_[0]
    title = files.file_name
    size=get_size(files.file_size)
    f_caption=files.caption
    if info.KEEP_ORIGINAL_CAPTION:
        try:
            f_caption = files.caption
        except:
            f_caption = f"<code>{title}</code>"
    elif info.CUSTOM_FILE_CAPTION:
        try:
            f_caption=info.CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
        except Exception as e:
            logger.exception(e)
            f_caption=f_caption
    if f_caption is None:
        f_caption = f"{files.file_name}"
    await client.send_cached_media(
        chat_id=message.from_user.id,
        file_id=file_id,
        caption=f_caption,
        parse_mode=enums.ParseMode.HTML if info.KEEP_ORIGINAL_CAPTION else enums.ParseMode.DEFAULT,
        protect_content=True if pre == 'filep' else False,
        reply_markup=InlineKeyboardMarkup( [ [ InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL) ],
                                             # [InlineKeyboardButton("🔞 Adult Content Channel",
                                             #                       url="https://t.me/eseoaOF")],
                                             [InlineKeyboardButton("🍺 Buy Me A Beer",
                                                                   url="https://buymeacoffee.com/matthewmurdock001")],
                                             ] ),
    )
                    

@Client.on_message(filters.command('channel') & filters.user(info.ADMINS))
async def channel_info(bot, message):
           
    """Send basic information of channel"""
    if isinstance(info.CHANNELS, (int, str)):
        channels = [info.CHANNELS]
    elif isinstance(info.CHANNELS, list):
        channels = info.CHANNELS
    else:
        raise ValueError("Unexpected type of CHANNELS")

    text = '📑 **Indexed channels/groups**\n'
    for channel in channels:
        chat = await bot.get_chat(channel)
        if chat.username:
            text += '\n@' + chat.username
        else:
            text += '\n' + chat.title or chat.first_name

    text += f'\n\n**Total:** {len(info.CHANNELS)}'

    if len(text) < 4096:
        await message.reply(text)
    else:
        file = 'Indexed channels.txt'
        with open(file, 'w') as f:
            f.write(text)
        await message.reply_document(file)
        os.remove(file)


@Client.on_message(filters.command('logs') & filters.user(info.ADMINS))
async def log_file(bot, message):
    """Send log file"""
    try:
        await message.reply_document('Logs.txt')
    except Exception as e:
        await message.reply(str(e))

@Client.on_message(filters.command('delete') & filters.user(info.ADMINS))
async def delete(bot, message):
    """Delete file from database"""
    reply = message.reply_to_message
    if reply and reply.media:
        msg = await message.reply("Processing...⏳", quote=True)
    else:
        await message.reply('Reply to file with /delete which you want to delete', quote=True)

    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None:
            break
    else:
        await msg.edit('This is not supported file format')
    
    file_id, file_ref = unpack_new_file_id(media.file_id)

    result = await Media.collection.delete_one({
        '_id': file_id,
    })
    if result.deleted_count:
        await msg.edit('File is successfully deleted from database')
    else:
        file_name = re.sub(r"([_\-.+])", " ", str(media.file_name))
        result = await Media.collection.delete_many({
            'file_name': file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
            })
        if result.deleted_count:
            await msg.edit('File is successfully deleted from database')
        else:
            result = await Media.collection.delete_many({
                'file_name': media.file_name,
                'file_size': media.file_size,
                'mime_type': media.mime_type
            })
            if result.deleted_count:
                await msg.edit('File is successfully deleted from database')
            else:
                await msg.edit('File not found in database')


@Client.on_message(filters.command('deleteall') & filters.user(info.ADMINS))
async def delete_all_index(bot, message):
    await message.reply_text(
        'This will delete all indexed files.\nDo you want to continue??',
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="YES", callback_data="autofilter_delete"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="CANCEL", callback_data="close_data"
                    )
                ],
            ]
        ),
        quote=True,
    )


@Client.on_callback_query(filters.regex(r'^autofilter_delete'))
async def delete_all_index_confirm(bot, message):
    await Media.collection.drop()
    await message.answer('Support Us By Sharing The Channel And Bot')
    await message.message.edit('Succesfully Deleted All The Indexed Files.')


@Client.on_message(filters.command('settings'))
async def settings(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                return await message.reply_text("Make sure I'm present in your group!!", quote=True)

        else:
            return await message.reply_text("I'm not connected to any groups!", quote=True)


    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title

    else:
        return None

    st = await client.get_chat_member(grp_id, userid)
    if (
            st.status != enums.ChatMemberStatus.ADMINISTRATOR
            and st.status != enums.ChatMemberStatus.OWNER
            and str(userid) not in info.ADMINS
    ):
        return None
    
    settings = await get_settings(grp_id)

    try:
        if settings['max_btn']:
            settings = await get_settings(grp_id)
    except KeyError:
        await save_group_settings(grp_id, 'max_btn', False)
        settings = await get_settings(grp_id)

    if settings is not None:
        buttons = [
            [
                InlineKeyboardButton(
                    '𝖥𝗂𝗅𝗍𝖾𝗋 𝖡𝗎𝗍𝗍𝗈𝗇',
                    callback_data=f'setgs#button#{settings["button"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '𝖲𝗂𝗇𝗀𝗅𝖾 𝖡𝗎𝗍𝗍𝗈𝗇' if settings["button"] else '𝖣𝗈𝗎𝖻𝗅𝖾',
                    callback_data=f'setgs#button#{settings["button"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖥𝗂𝗅𝖾 𝖲𝖾𝗇𝖽 𝖬𝗈𝖽𝖾',
                    callback_data=f'setgs#botpm#{settings["botpm"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '𝖬𝖺𝗇𝗎𝖺𝗅 𝖲𝗍𝖺𝗋𝗍' if settings["botpm"] else '𝖠𝗎𝗍𝗈 𝖲𝖾𝗇𝖽',
                    callback_data=f'setgs#botpm#{settings["botpm"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖯𝗋𝗈𝗍𝖾𝖼𝗍 𝖢𝗈𝗇𝗍𝖾𝗇𝗍',
                    callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ 𝖮𝗇' if settings["file_secure"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖨𝖬𝖣𝖻',
                    callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ 𝖮𝗇' if settings["imdb"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖲𝗉𝖾𝗅𝗅 𝖢𝗁𝖾𝖼𝗄',
                    callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ 𝖮𝗇' if settings["spell_check"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖬𝖾𝗌𝗌𝖺𝗀𝖾',
                    callback_data=f'setgs#welcome#{settings["welcome"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ 𝖮𝗇' if settings["welcome"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#welcome#{settings["welcome"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖠𝗎𝗍𝗈 𝖣𝖾𝗅𝖾𝗍𝖾',
                    callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '5 𝖬𝗂𝗇' if settings["auto_delete"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖠𝗎𝗍𝗈-𝖥𝗂𝗅𝗍𝖾𝗋',
                    callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '✅ 𝖮𝗇' if settings["auto_ffilter"] else '❌ 𝖮𝖿𝖿',
                    callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{grp_id}',
                ),
            ],
            [
                InlineKeyboardButton(
                    '𝖬𝖺𝗑 𝖡𝗎𝗍𝗍𝗈𝗇𝗌',
                    callback_data=f'setgs#max_btn#{settings["max_btn"]}#{grp_id}',
                ),
                InlineKeyboardButton(
                    '10' if settings["max_btn"] else f'{info.MAX_B_TN}',
                    callback_data=f'setgs#max_btn#{settings["max_btn"]}#{grp_id}',
                ),
            ],
        ]

        btn = [[
                InlineKeyboardButton("⬇ 𝖮𝗉𝖾𝗇 𝖧𝖾𝗋𝖾 ⬇", callback_data=f"opnsetgrp#{grp_id}"),
                InlineKeyboardButton("➡ 𝖮𝗉𝖾𝗇 𝗂𝗇 𝖯𝖬 ➡", callback_data=f"opnsetpm#{grp_id}")
              ]]

        reply_markup = InlineKeyboardMarkup(buttons)
        if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            await message.reply_text(
                text="<b>𝖣𝗈 𝖸𝗈𝗎 𝖶𝖺𝗇𝗍 𝖳𝗈 𝖮𝗉𝖾𝗇 𝖲𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝖧𝖾𝗋𝖾 ?</b>",
                reply_markup=InlineKeyboardMarkup(btn),
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=message.id
            )
        else:
            await message.reply_text(
                text=f"<b>𝖢𝗁𝖺𝗇𝗀𝖾 𝖸𝗈𝗎𝗋 𝖲𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝖥𝗈𝗋 {title} 𝖠𝗌 𝖸𝗈𝗎𝗋 𝖶𝗂𝗌𝗁</b>",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=message.id
            )



@Client.on_message(filters.command("send") & filters.user(info.ADMINS))
async def send_msg(bot, message):
    if message.reply_to_message:
        target_id = message.text
        command = ["/send"]
        out = "Users Saved In DB Are:\n\n"
        for cmd in command:
            if cmd in target_id:
                target_id = target_id.replace(cmd, "")
        success = False
        try:
            user = await bot.get_users(target_id)
            users = await db.get_all_users()
            async for usr in users:
                out += f"{usr['id']}"
                out += '\n'
            if str(user.id) in str(out):
                await message.reply_to_message.copy(int(user.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>Your message has been successfully send to {user.mention}.</b>")
            else:
                await message.reply_text("<b>This user didn't started this bot yet !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error: {e}</b>")
    else:
        await message.reply_text("<b>Use this command as a reply to any message using the target chat id. For eg: /send userid</b>")

@Client.on_message(filters.command('set_template'))
async def save_template(client, message):
    sts = await message.reply("Checking template")
    userid = message.from_user.id if message.from_user else None
    if not userid:
        await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title

    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
            st.status != enums.ChatMemberStatus.ADMINISTRATOR
            and st.status != enums.ChatMemberStatus.OWNER
            and str(userid) not in info.ADMINS
    ):
        return

    if len(message.command) < 2:
        await sts.edit("No Input!!")
    template = message.text.split(" ", 1)[1]
    await save_group_settings(grp_id, 'template', template)
    await sts.edit(f"Successfully changed template for {title} to\n\n{template}")


# @Client.on_message((filters.command(["request", "Request"]) | filters.regex("#request") | filters.regex("#Request")) & filters.group)
# async def requests(bot, message):
#     if REQST_CHANNEL is None or SUPPORT_CHAT_ID is None: return # Must add REQST_CHANNEL and SUPPORT_CHAT_ID to use this feature
#     if message.from_user:
#         reporter = str(message.from_user.id)
#         mention = str(message.from_user.mention)
#     elif message.sender_chat:
#         reporter = str(message.sender_chat.id)
#         mention = str(message.sender_chat.mention)
#     else:
#         await message.reply_text("<b>Unable to process the request: Missing user or channel information.</b>")
#         return
#     success = True
#     if message.reply_to_message and SUPPORT_CHAT_ID == message.chat.id:
#         chat_id = message.chat.id
#         #reporter = str(message.from_user.id)
#         #mention = message.from_user.mention
#         #success = True
#         content = message.reply_to_message.text
#         try:
#             if REQST_CHANNEL is not None:
#                 btn = [[
#                         InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.reply_to_message.link}"),
#                         InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
#                       ]]
#                 reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
#                 success = True
#             elif len(content) >= 3:
#                 for admin in ADMINS:
#                     btn = [[
#                         InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.reply_to_message.link}"),
#                         InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
#                       ]]
#                     reported_post = await bot.send_message(chat_id=admin, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
#                     success = True
#             else:
#                 if len(content) < 3:
#                     await message.reply_text("<b>You must type about your request [Minimum 3 Characters]. Requests can't be empty.</b>")
#             if len(content) < 3:
#                 success = False
#         except Exception as e:
#             await message.reply_text(f"Error: {e}")
#             pass
#
#     elif SUPPORT_CHAT_ID == message.chat.id:
#         chat_id = message.chat.id
#         reporter = str(message.from_user.id)
#         mention = message.from_user.mention
#         success = True
#         content = message.text
#         keywords = ["#request", "/request", "#Request", "/Request"]
#         for keyword in keywords:
#             if keyword in content:
#                 content = content.replace(keyword, "")
#         try:
#             if REQST_CHANNEL is not None and len(content) >= 3:
#                 btn = [[
#                         InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.link}"),
#                         InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
#                       ]]
#                 reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
#                 success = True
#             elif len(content) >= 3:
#                 for admin in ADMINS:
#                     btn = [[
#                         InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.link}"),
#                         InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
#                       ]]
#                     reported_post = await bot.send_message(chat_id=admin, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
#                     success = True
#             else:
#                 if len(content) < 3:
#                     await message.reply_text("<b>You must type about your request [Minimum 3 Characters]. Requests can't be empty.</b>")
#             if len(content) < 3:
#                 success = False
#         except Exception as e:
#             await message.reply_text(f"Error: {e}")
#             pass
#
#     else:
#         success = False
#
#     if success:
#         btn = [[
#                 InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{reported_post.link}")
#               ]]
#         await message.reply_text("<b>Your request has been added! Please wait for some time.</b>", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(
    (filters.command(["request", "Request"]) | filters.regex("#request") | filters.regex("#Request"))
    & filters.group
)
async def requests(bot, message):
    # Preliminary check: Ensure that SUPPORT_CHAT_ID and REQST_CHANNEL are defined when required.
    if info.REQST_CHANNEL is None or info.SUPPORT_CHAT_ID is None:
        return

    reported_post = None

    # Safely retrieve the reporter and mention
    if message.from_user:
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
    elif message.sender_chat:
        await message.reply_text("<b>Anonymous users or channels cannot request. Please use original user profile</b>")
        return
        # Fallback for channel posts or anonymous messages
        #reporter = str(message.sender_chat.id)
        #mention = message.sender_chat.title
    else:
        await message.reply_text("<b>Unable to process the request: Missing user or channel information.</b>")
        return

    success = True
    # Depending on the context of the message, determine the content and handle accordingly:
    if message.reply_to_message and info.SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        content = message.reply_to_message.text
        try:
            if len(content) < 3:
                await message.reply_text("<b>You must type about your request [Minimum 3 Characters]. Requests can't be empty.</b>")
                success = False
            elif info.REQST_CHANNEL is not None:
                btn = [[
                        InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.reply_to_message.link}"),
                        InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(
                    chat_id=info.REQST_CHANNEL,
                    text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            else:
                # Optionally send to ADMINS if REQST_CHANNEL is not defined
                for admin in info.ADMINS:
                    btn = [[
                            InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.reply_to_message.link}"),
                            InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
                          ]]
                    reported_post = await bot.send_message(
                        chat_id=admin,
                        text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            return

    elif info.SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        content = message.text
        # Remove keywords before processing
        for keyword in ["#request", "/request", "#Request", "/Request"]:
            content = content.replace(keyword, "")
        try:
            if len(content) < 3:
                await message.reply_text("<b>You must type about your request [Minimum 3 Characters]. Requests can't be empty.</b>")
                return
            if info.REQST_CHANNEL is not None:
                btn = [[
                        InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.link}"),
                        InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(
                    chat_id=info.REQST_CHANNEL,
                    text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            else:
                for admin in info.ADMINS:
                    btn = [[
                        InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{message.link}"),
                        InlineKeyboardButton('📝 𝖲𝗁𝗈𝗐 𝖮𝗉𝗍𝗂𝗈𝗇𝗌 📝', callback_data=f'show_option#{reporter}')
                      ]]
                    reported_post = await bot.send_message(
                        chat_id=admin,
                        text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            return

    else:
        # If message context doesn't match expected sources, simply exit
        return

    # Acknowledge successful request submission
    # if success:
    #     if reported_post is None:
    #         # If reported_post was never assigned, handle the error gracefully.
    #         await message.reply_text("Error: Unable to process your request. Please try again later.")
    #         return
    #     btn = [[
    #         InlineKeyboardButton('📥 𝖵𝗂𝖾𝗐 𝖱𝖾𝗊𝗎𝖾𝗌𝗍 📥', url=f"{reported_post.link}")
    #     ]]
    #     await message.reply_text("<b>Your request has been added! Please wait for some time.</b>", reply_markup=InlineKeyboardMarkup(btn))


@Client.on_message(filters.command("usend") & filters.user(info.ADMINS))
async def send_msg(bot, message):
    if message.reply_to_message:
        target_id = message.text.split(" ", 1)[1]
        out = "Users Saved In DB Are:\n\n"
        success = False
        try:
            user = await bot.get_users(target_id)
            users = await db.get_all_users()
            async for usr in users:
                out += f"{usr['id']}"
                out += '\n'
            if str(user.id) in str(out):
                await message.reply_to_message.copy(int(user.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>𝖸𝗈𝗎𝗋 𝖬𝖾𝗌𝗌𝖺𝗀𝖾 𝖧𝖺𝗌 𝖲𝗎𝖼𝖼𝖾𝗌𝗌𝖿𝗎𝗅𝗅𝗒 𝖲𝖾𝗇𝗍 𝖳𝗈 {user.mention}.</b>")
            else:
                await message.reply_text("<b>An Error Occurred !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error :- <code>{e}</code></b>")
    else:
        await message.reply_text("<b>Error𝖢𝗈𝗆𝗆𝖺𝗇𝖽 𝖨𝗇𝖼𝗈𝗆𝗉𝗅𝖾𝗍𝖾 !</b>")
        
@Client.on_message(filters.command("send") & filters.user(info.ADMINS))
async def send_msg(bot, message):
    if message.reply_to_message:
        target_id = message.text.split(" ", 1)[1]
        out = "Users Saved In DB Are:\n\n"
        success = False
        try:
            user = await bot.get_users(target_id)
            users = await db.get_all_users()
            async for usr in users:
                out += f"{usr['id']}"
                out += '\n'
            if str(user.id) in str(out):
                await message.reply_to_message.copy(int(user.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>Your message has been successfully send to {user.mention}.</b>")
            else:
                await message.reply_text("<b>This user didn't started this bot yet !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error: {e}</b>")
    else:
        await message.reply_text("<b>Use this command as a reply to any message using the target chat id. For eg: /send userid</b>")

@Client.on_message(filters.command("gsend") & filters.user(info.ADMINS))
async def send_chatmsg(bot, message):
    if message.reply_to_message:
        target_id = message.text.split(" ", 1)[1]
        out = "Chats Saved In DB Are:\n\n"
        success = False
        try:
            chat = await bot.get_chat(target_id)
            chats = await db.get_all_chats()
            async for cht in chats:
                out += f"{cht['id']}"
                out += '\n'
            if str(chat.id) in str(out):
                await message.reply_to_message.copy(int(chat.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>Your message has been successfully send to <code>{chat.id}</code>.</b>")
            else:
                await message.reply_text("<b>An Error Occurred !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error :- <code>{e}</code></b>")
    else:
        await message.reply_text("<b>Error𝖢𝗈𝗆𝗆𝖺𝗇𝖽 𝖨𝗇𝖼𝗈𝗆𝗉𝗅𝖾𝗍𝖾 !</b>")

@Client.on_message(filters.command("deletefiles") & filters.user(info.ADMINS))
async def deletemultiplefiles(bot, message):
    chat_type = message.chat.type
    if chat_type != enums.ChatType.PRIVATE:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, This command won't work in groups. It only works on my PM !</b>")
    else:
        pass
    try:
        keyword = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, Give me a keyword along with the command to delete files.</b>")
    k = await bot.send_message(chat_id=message.chat.id, text=f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
    files, total = await get_bad_files(keyword)
    await k.edit_text(f"<b>Found {total} files for your query {keyword} !\n\nFile deletion process will start in 5 seconds !</b>")
    await asyncio.sleep(5)
    deleted = 0
    for file in files:
        await k.edit_text(f"<b>Process started for deleting files from DB. Successfully deleted {str(deleted)} files from DB for your query {keyword} !\n\nPlease wait...</b>")
        file_ids = file.file_id
        file_name = file.file_name
        result = await Media.collection.delete_one({
            '_id': file_ids,
        })
        if result.deleted_count:
            logger.info(f'File Found for your query {keyword}! Successfully deleted {file_name} from database.')
        deleted += 1
    await k.edit_text(text=f"<b>Process Completed for file deletion !\n\nSuccessfully deleted {str(deleted)} files from database for your query {keyword}.</b>")

async def allowed(_, __, message):
    if info.PUBLIC_FILE_STORE:
        return True
    if message.from_user and message.from_user.id in info.ADMINS:
        return True
    return False

@Client.on_message(filters.command(['link', 'plink']) & filters.create(allowed))
async def gen_link_s(bot, message):
    replied = message.reply_to_message
    if not replied:
        return await message.reply('Reply to a message to get a shareable link.')
    file_type = replied.media
    if file_type not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
        return await message.reply("Reply to a supported media")
    if message.has_protected_content and message.chat.id not in info.ADMINS:
        return await message.reply("okDa")
    file_id, ref = unpack_new_file_id((getattr(replied, file_type.value)).file_id)
    string = 'filep_' if message.text.lower().strip() == "/plink" else 'file_'
    string += file_id
    outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
    await message.reply(f"Here is your Link:\nhttps://t.me/{temp.U_NAME}?start={outstr}")
    
    
@Client.on_message(filters.command(['batch', 'pbatch']) & filters.create(allowed))
async def gen_link_batch(bot, message):
    if " " not in message.text:
        return await message.reply("Use correct format.\nExample <code>/batch https://t.me/kdramaworld_ongoing/10 https://t.me/kdramaworld_ongoing/20</code>.")
    links = message.text.strip().split(" ")
    if len(links) != 3:
        return await message.reply("Use correct format.\nExample <code>/batch https://t.me/kdramaworld_ongoing/10 https://t.me/kdramaworld_ongoing/20</code>.")
    cmd, first, last = links
    regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
    match = regex.match(first)
    if not match:
        return await message.reply('Invalid link')
    f_chat_id = match.group(4)
    f_msg_id = int(match.group(5))
    if f_chat_id.isnumeric():
        f_chat_id  = int(("-100" + f_chat_id))
    match = regex.match(last)
    if not match:
        return await message.reply('Invalid link')
    l_chat_id = match.group(4)
    l_msg_id = int(match.group(5))
    if l_chat_id.isnumeric():
        l_chat_id  = int(("-100" + l_chat_id))

    if f_chat_id != l_chat_id:
        return await message.reply("Chat ids not matched.")
    try:
        chat_id = (await bot.get_chat(f_chat_id)).id
    except ChannelInvalid:
        return await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        return await message.reply(f'Errors - {e}')

    sts = await message.reply("Generating link for your message.\nThis may take time depending upon number of messages")
    if chat_id in info.FILE_STORE_CHANNEL:
        string = f"{f_msg_id}_{l_msg_id}_{chat_id}_{cmd.lower().strip()}"
        b_64 = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
        return await sts.edit(f"Here is your link https://t.me/{temp.U_NAME}?start=DSTORE-{b_64}")

    FRMT = "Generating Link...\nTotal Messages: `{total}`\nDone: `{current}`\nRemaining: `{rem}`\nStatus: `{sts}`"

    outlist = []

    # file store without db channel
    og_msg = 0
    tot = 0
    async for msg in bot.iter_messages(f_chat_id, l_msg_id, f_msg_id):
        tot += 1
        if msg.empty or msg.service:
            continue
        if not msg.media:
            # only media messages supported.
            continue
        try:
            file_type = msg.media
            file = getattr(msg, file_type.value)
            caption = getattr(msg, 'caption', '')
            if caption and not isinstance(caption, str) and hasattr(caption, "html"):
                caption = caption.html

            if file:
                file = {
                    "file_id": file.file_id,
                    "caption": caption,
                    "title": getattr(file, "file_name", ""),
                    "size": file.file_size,
                    "protect": cmd.lower().strip() == "/pbatch",
                }

                og_msg +=1
                outlist.append(file)
        except:
            pass
        if not og_msg % 20:
            try:
                await sts.edit(FRMT.format(total=l_msg_id-f_msg_id, current=tot, rem=((l_msg_id-f_msg_id) - tot), sts="Saving Messages"))
            except:
                pass
    with open(f"batchmode_{message.from_user.id}.json", "w+", encoding="utf-8") as out:
        out.write(json.dumps(outlist))
    post = await bot.send_document(info.LOG_CHANNEL, f"batchmode_{message.from_user.id}.json", file_name="Batch.json", caption="⚠️Generated for filestore.")
    os.remove(f"batchmode_{message.from_user.id}.json")
    file_id, ref = unpack_new_file_id(post.document.file_id)
    await sts.edit(f"Here is your link\nContains `{og_msg}` files.\n https://t.me/{temp.U_NAME}?start=BATCH-{file_id}")


@Client.on_message(filters.command('alive', CMD))
async def check_alive(_, message):
    await message.reply_text("𝖡𝗎𝖽𝖽𝗒 𝖨𝖺𝗆 𝖠𝗅𝗂𝗏𝖾 :)")


@Client.on_message(filters.command("ping", CMD))
async def ping(_, message):
    start_t = time.time()
    rm = await message.reply_text("...........")
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    await rm.edit(f"𝖯𝗂𝗇𝗀!\n{time_taken_s:.3f} ms")

# @Client.on_message(filters.command("restart") & filters.user(info.ADMINS) &filters.private)
# async def restart_bot(client, message):
#     status_msg = await message.reply_text("🔄 Updating code from UPSTREAM_REPO...")
#     proc = await asyncio.create_subprocess_exec(
#         sys.executable, "update.py",
#         stdout=asyncio.subpr, stderr=STDOUT
#     )
#     stdout, _ = await proc.communicate()
#     # Send a message and capture the returned message object
#     restart_msg = await message.reply_text("♻️ Restarting bot... Please wait.")
#     # Save the chat id and message id to a file (using a delimiter, e.g., "|")
#     with open(RESTART_FILE, "w") as f:
#         f.write(f"{message.chat.id}|{restart_msg.id}")
#     # Wait a moment to ensure the message is sent
#     await asyncio.sleep(2)
#     # Restart the current process (Docker will auto-restart the container)
#     os.execl(sys.executable, sys.executable, *sys.argv)

@Client.on_message(filters.command("restart") & filters.user(info.ADMINS) & filters.private)
async def restart_bot(client, message):
    # Notify user about restart
    restart_msg = await message.reply_text("♻️ **Restarting bot...**\n\n*Updating code and restarting. Please wait.*")

    if os.path.exists("Logs.txt"):
        os.remove("Logs.txt")

    # Save chat and message ID for later status update
    with open(RESTART_FILE, "w") as f:
        f.write(f"{message.chat.id}|{restart_msg.id}")

    # Run update.py to fetch latest code
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "update.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            logger.error(f"Update failed: {error_msg}")
            await message.reply_text(f"❌ **Update failed!**\n\n`{error_msg}`")
            return
    except Exception as e:
        logger.error(f"Error during update: {e}")
        await message.reply_text(f"❌ **Update error!**\n\n`{str(e)}`")
        return

    # Restart the bot process
    logger.info("✅ Update successful. Restarting bot...")
    os.execl(sys.executable, sys.executable, *sys.argv)


async def update_restart_status(client):
    if os.path.exists(RESTART_FILE):
        with open(RESTART_FILE, "r") as f:
            data = f.read().strip().split("|")
        if len(data) == 2:
            chat_id, message_id = data
            try:
                await client.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=int(message_id),
                    text="✅ Successfully restarted! V1.0.1"
                )
            except Exception as e:
                print("Failed to update restart message:", e)
        os.remove(RESTART_FILE)

