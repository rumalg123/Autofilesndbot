import ast
import asyncio
import math
import random
import re

lock = asyncio.Lock()

from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
from database.connections_mdb import active_connection, all_connections, delete_connection, if_active, make_active, \
    make_inactive
import info
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from pyrogram import Client, filters, enums
from pyrogram.errors import UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import get_size, is_subscribed, get_poster, temp, get_settings, save_group_settings
from database.users_chats_db import db
from database.ia_filterdb import Media, get_file_details, get_search_results, get_bad_files
from database.filters_mdb import (
    del_all,
    find_filter,
    get_filters,
)
from database.gfilters_mdb import (
    find_gfilter,
    get_gfilters,
    del_allg
)
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
SPELL_CHECK = {}


# @Client.on_message(filters.group & filters.text & filters.incoming)
# async def give_filter(client, message):
#     if message.chat.id != SUPPORT_CHAT_ID:
#         glob = await global_filters(client, message)
#         if glob == False:
#             manual = await manual_filters(client, message)
#             if manual == False:
#                 settings = await get_settings(message.chat.id)
#                 try:
#                     if settings['auto_ffilter']:
#                         await auto_filter(client, message)
#                 except KeyError:
#                     grpid = await active_connection(str(message.from_user.id))
#                     await save_group_settings(grpid, 'auto_ffilter', True)
#                     settings = await get_settings(message.chat.id)
#                     if settings['auto_ffilter']:
#                         await auto_filter(client, message)
#     else: #a better logic to avoid repeated lines of code in auto_filter function
#         search = message.text
#         temp_files, temp_offset, total_results = await get_search_results(chat_id=message.chat.id, query=search.lower(), offset=0, filter=True)
#         if total_results == 0:
#             return
#         else:
#             return await message.reply_text(f"<b>👋 𝖧𝖾𝗒 {message.from_user.mention} \n📁 {str(total_results)} 𝖱𝖾𝗌𝗎𝗅𝗍𝗌 𝖺𝗋𝖾 𝖿𝗈𝗎𝗇𝖽 𝖿𝗈𝗋 𝗒𝗈𝗎𝗋 𝗊𝗎𝖾𝗋𝗒 {search}.\n\nKindly ask movies and series here ⬇\n@kdramasmirrorchat </b>")

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    glob = await global_filters(client, message)
    if not glob:
        manual = await manual_filters(client, message)
        if not manual:
            settings = await get_settings(message.chat.id)
            try:
                if settings['auto_ffilter']:
                    await auto_filter(client, message)
            except KeyError:
                grpid = await active_connection(str(message.from_user.id))
                await save_group_settings(grpid, 'auto_ffilter', True)
                settings = await get_settings(message.chat.id)
                if settings['auto_ffilter']:
                    await auto_filter(client, message)

            

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pv_filter(client, message):
    kd = await global_filters(client, message)
    if not kd:
        await auto_filter(client, message)

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    try:
        offset = int(offset)
    except Exception:
        offset = 0
    search = BUTTONS.get(key)
    if not search:
        return query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)


    files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
    try:
        n_offset = int(n_offset)
    except Exception:
        n_offset = 0

    if not files:
        return
    settings = await get_settings(query.message.chat.id)
    pre = 'filep' if settings.get('file_secure') else 'file' # Use .get for safety
    temp.FILES_IDS[key] = files
    if settings.get('button'): # Use .get for safety
        btn = [
            [
                InlineKeyboardButton(
                   text=f"🔰{get_size(file.file_size)}📁{file.file_name}", callback_data=f'{pre}#{file.file_id}'
                ),
            ]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{file.file_name}", callback_data=f'{pre}#{file.file_id}'
                ),
                InlineKeyboardButton(
                    text=f"{get_size(file.file_size)}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
            ]
            for file in files
        ]

    # Simplified 'auto_delete' button insertion. The button is the same regardless of the setting's value.
    # The try-except for auto_delete here was primarily to set a default if the key was missing.
    # get_settings should ideally return settings with defaults, or we can use .get()
    # For now, let's assume get_settings populates defaults or the key always exists.
    # If not, the original try-except for initializing the setting is better.
    # However, the button content itself doesn't change based on auto_delete's boolean value.
    btn.insert(0,
        [
            InlineKeyboardButton(f'😇 Info', 'tips'),
            InlineKeyboardButton(f'📝 𝖳𝗂𝗉𝗌', 'info')
        ]
    )

    # settings = await get_settings(query.message.chat.id) # Already fetched

    if settings.get('max_btn', False): # Default to False if key is missing
        if 0 < offset <= 10:
            off_set = 0
        elif offset == 0:
            off_set = None
        else:
            off_set = offset - 10
        if n_offset == 0:
            btn.append(
                [InlineKeyboardButton("◀️ 𝖡𝖠𝖢𝖪", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
            )
        elif off_set is None:
            btn.append([InlineKeyboardButton("📃", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"), InlineKeyboardButton("𝖭𝖤𝖷𝖳 ▶️", callback_data=f"next_{req}_{key}_{n_offset}")])
        else:
            btn.append(
                [
                    InlineKeyboardButton("◀️ 𝖡𝖠𝖢𝖪", callback_data=f"next_{req}_{key}_{off_set}"),
                    InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                    InlineKeyboardButton("𝖭𝖤𝖷𝖳 ▶️", callback_data=f"next_{req}_{key}_{n_offset}")
                ],
            )
    else: # max_btn is False or not set
        if 0 < offset <= int(info.MAX_B_TN):
            off_set = 0
        elif offset == 0:
                off_set = None
            else:
                off_set = offset - 10
            if n_offset == 0:
                btn.append(
                    [InlineKeyboardButton("◀️ 𝖡𝖠𝖢𝖪", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
                )
            elif off_set is None:
                btn.append([InlineKeyboardButton("📃", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"), InlineKeyboardButton("𝖭𝖤𝖷𝖳 ▶️", callback_data=f"next_{req}_{key}_{n_offset}")])
            else:
                btn.append(
                    [
                        InlineKeyboardButton("◀️ 𝖡𝖠𝖢𝖪", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                        InlineKeyboardButton("𝖭𝖤𝖷𝖳 ▶️", callback_data=f"next_{req}_{key}_{n_offset}")
                    ],
                )
        else:
            if 0 < offset <= int(info.MAX_B_TN):
                off_set = 0
            elif offset == 0:
                off_set = None
            else:
                off_set = offset - int(info.MAX_B_TN)
            if n_offset == 0:
                btn.append(
                    [InlineKeyboardButton("◀️ 𝖡𝖠𝖢𝖪", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(info.MAX_B_TN))+1} / {math.ceil(total/int(info.MAX_B_TN))}", callback_data="pages")]
                )
            elif off_set is None:
                btn.append([InlineKeyboardButton("📃", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(info.MAX_B_TN))+1} / {math.ceil(total/int(info.MAX_B_TN))}", callback_data="pages"), InlineKeyboardButton("𝖭𝖤𝖷𝖳 ▶️", callback_data=f"next_{req}_{key}_{n_offset}")])
            else:
                btn.append(
                    [
                        InlineKeyboardButton("◀️ 𝖡𝖠𝖢𝖪", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"{math.ceil(int(offset)/int(info.MAX_B_TN))+1} / {math.ceil(total/int(info.MAX_B_TN))}", callback_data="pages"),
                        InlineKeyboardButton("𝖭𝖤𝖷𝖳 ▶️", callback_data=f"next_{req}_{key}_{n_offset}")
                    ],
                )
    except KeyError:
        await save_group_settings(query.message.chat.id, 'max_btn', False)
        settings = await get_settings(query.message.chat.id)
        if settings['max_btn']:
            if 0 < offset <= 10:
                off_set = 0
            elif offset == 0:
                off_set = None
            else:
            off_set = offset - int(info.MAX_B_TN) # Use info.MAX_B_TN
            if n_offset == 0:
                btn.append(
                    [InlineKeyboardButton("◀️ 𝖡𝖠𝖢𝖪", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(info.MAX_B_TN))+1} / {math.ceil(total/int(info.MAX_B_TN))}", callback_data="pages")]
                )
            elif off_set is None:
                btn.append([InlineKeyboardButton("📃", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(info.MAX_B_TN))+1} / {math.ceil(total/int(info.MAX_B_TN))}", callback_data="pages"), InlineKeyboardButton("𝖭𝖤𝖷𝖳 ▶️", callback_data=f"next_{req}_{key}_{n_offset}")])
            else:
                btn.append(
                    [
                        InlineKeyboardButton("◀️ 𝖡𝖠𝖢𝖪", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"{math.ceil(int(offset)/int(info.MAX_B_TN))+1} / {math.ceil(total/int(info.MAX_B_TN))}", callback_data="pages"),
                        InlineKeyboardButton("𝖭𝖤𝖷𝖳 ▶️", callback_data=f"next_{req}_{key}_{n_offset}")
                    ],
                )

    # This try-except for max_btn was to initialize it if missing.
    # settings.get('max_btn', False) handles this more cleanly now.
    # The original code had a repetition of the button creation logic inside the except block.
    # This is now avoided.

    btn.insert(0, [ # This was btn.insert(0, [...])
        InlineKeyboardButton(f'🎬 {search} 🎬', 'rkbtn')
    ])
    btn.insert(2, [ # This was btn.insert(2, [...])
        InlineKeyboardButton("📤 𝖲𝖾𝗇𝖽 𝖠𝗅𝗅 𝖥𝗂𝗅𝖾𝗌 📤", callback_data=f"send_all#{req}#{key}#{pre}")
    ])
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass # It's okay if the message is not modified
    return await query.answer()


@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query):
    _, user, movie_ = query.data.split('#')
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)
    if not movies:
        return await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    if movie_ == "close_spellcheck":
        return await query.message.delete()
    movie = movies[(int(movie_))]
    await query.answer(script.TOP_ALRT_MSG)
    gl = await global_filters(bot, query.message, text=movie)
    if not gl:
        k = await manual_filters(bot, query.message, text=movie)
        if not k:
            files, offset, total_results = await get_search_results(query.message.chat.id, movie, offset=0, filter=True)
            if files:
                k = (movie, files, offset, total_results)
                await auto_filter(bot, query, k)
            else:
                reqstr1 = query.from_user.id if query.from_user else None
                if reqstr1 is None:
                    return
                reqstr = await bot.get_users(reqstr1)
                if info.NO_RESULTS_MSG: # This logging can remain for all cases as per original logic
                    await bot.send_message(chat_id=info.LOG_CHANNEL, text=(script.NORSLTS.format(reqstr.id, reqstr.mention, movie)))

                if query.message.chat.type == enums.ChatType.PRIVATE:
                    k = await query.message.edit("No results found for this selection. Try another keyword or main search.")
                else:
                    k = await query.message.edit(script.MVE_NT_FND) # Original message for groups

                await asyncio.sleep(10) # Consider making this delay configurable or shorter for PM no-result message
                await k.delete()


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        await query.message.delete()
    elif query.data == "gfiltersdeleteallconfirm":
        await del_allg(query.message, 'gfilters')
        await query.answer("Done !")
        return
    elif query.data == "gfiltersdeleteallcancel": 
        await query.message.reply_to_message.delete()
        await query.message.delete()
        await query.answer("Process Cancelled !")
        return
    elif query.data == "delallconfirm":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            grpid = await active_connection(str(userid))
            if grpid is not None:
                grp_id = grpid
                try:
                    chat = await client.get_chat(grpid)
                    title = chat.title
                except:
                    await query.message.edit_text("Make sure I'm present in your group!!")
                    return await query.answer('Support Us By Sharing The Channel And Bot')
            else:
                await query.message.edit_text(
                    "I'm not connected to any groups!\nCheck /connections or connect to any groups"
                )
                return await query.answer('Support Us By Sharing The Channel And Bot')

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            title = query.message.chat.title

        else:
            return await query.answer('Support Us By Sharing The Channel And Bot')

        st = await client.get_chat_member(grp_id, userid)
        if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in info.ADMINS):
            await del_all(query.message, grp_id, title)
        else:
            await query.answer("You need to be Group Owner or an Auth User to do that!", show_alert=True)
    elif query.data == "delallcancel":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            await query.message.reply_to_message.delete()
            await query.message.delete()

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            st = await client.get_chat_member(grp_id, userid)
            if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in info.ADMINS):
                await query.message.delete()
                try:
                    await query.message.reply_to_message.delete()
                except:
                    pass
            else:
                await query.answer("That's not for you!!", show_alert=True)
    elif "groupcb" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        act = query.data.split(":")[2]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id

        if act == "":
            stat = "CONNECT"
            cb = "connectcb"
        else:
            stat = "DISCONNECT"
            cb = "disconnect"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{stat}", callback_data=f"{cb}:{group_id}"),
             InlineKeyboardButton("DELETE", callback_data=f"deletecb:{group_id}")],
            [InlineKeyboardButton("BACK", callback_data="backcb")]
        ])

        await query.message.edit_text(
            f"Group Name : **{title}**\nGroup ID : `{group_id}`",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return await query.answer('Support Us By Sharing The Channel And Bot')
    elif "connectcb" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title

        user_id = query.from_user.id

        mkact = await make_active(str(user_id), str(group_id))

        if mkact:
            await query.message.edit_text(
                f"Connected to **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text('Disconnected from', parse_mode=enums.ParseMode.MARKDOWN)
        return await query.answer('Support Us By Sharing The Channel And Bot')
    elif "disconnect" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title
        user_id = query.from_user.id

        mkinact = await make_inactive(str(user_id))

        if mkinact:
            await query.message.edit_text(
                f"Disconnected from **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer('Support Us By Sharing The Channel And Bot')
    elif "deletecb" in query.data:
        await query.answer()

        user_id = query.from_user.id
        group_id = query.data.split(":")[1]

        delcon = await delete_connection(str(user_id), str(group_id))

        if delcon:
            await query.message.edit_text(
                "Successfully deleted connection"
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer('Support Us By Sharing The Channel And Bot')
    elif query.data == "backcb":
        await query.answer()

        userid = query.from_user.id

        groupids = await all_connections(str(userid))
        if groupids is None:
            await query.message.edit_text(
                "There are no active connections!! Connect to some groups first.",
            )
            return await query.answer('Support Us By Sharing The Channel And Bot')
        buttons = []
        for groupid in groupids:
            try:
                ttl = await client.get_chat(int(groupid))
                title = ttl.title
                active = await if_active(str(userid), str(groupid))
                act = " - ACTIVE" if active else ""
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                        )
                    ]
                )
            except:
                pass
        if buttons:
            await query.message.edit_text(
                "Your connected group details ;\n\n",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    elif "gfilteralert" in query.data:
        grp_id = query.message.chat.id
        i = query.data.split(":")[1]
        keyword = query.data.split(":")[2]
        reply_text, btn, alerts, fileid = await find_gfilter('gfilters', keyword)
        if alerts is not None:
            alerts = ast.literal_eval(alerts)
            alert = alerts[int(i)]
            alert = alert.replace("\\n", "\n").replace("\\t", "\t")
            await query.answer(alert, show_alert=True)
    elif "alertmessage" in query.data:
        grp_id = query.message.chat.id
        i = query.data.split(":")[1]
        keyword = query.data.split(":")[2]
        reply_text, btn, alerts, fileid = await find_filter(grp_id, keyword)
        if alerts is not None:
            alerts = ast.literal_eval(alerts)
            alert = alerts[int(i)]
            alert = alert.replace("\\n", "\n").replace("\\t", "\t")
            await query.answer(alert, show_alert=True)
    if query.data.startswith("file"):
        clicked = query.from_user.id
        try:
            typed = query.message.reply_to_message.from_user.id
        except:
            typed = query.from_user.id
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('No such file exist.')
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        settings = await get_settings(query.message.chat.id)
        if info.KEEP_ORIGINAL_CAPTION:
            try:
                f_caption = files.caption
            except:
                f_caption = f"{title}"
        elif info.CUSTOM_FILE_CAPTION:
            try:
                f_caption = info.CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files.file_name}"

        try:
            if info.AUTH_CHANNEL and not await is_subscribed(client, query):
                if clicked == typed:
                    await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
                    return
                else:
                    await query.answer(f"𝖧𝖾𝗒 {query.from_user.first_name}, 𝖳𝗁𝗂𝗌 𝗂𝗌 𝗇𝗈𝗍 𝗒𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 !", show_alert=True)
            elif settings['botpm']:
                if clicked == typed:
                    await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
                    return
                else:
                    await query.answer(f"𝖧𝖾𝗒 {query.from_user.first_name}, 𝖳𝗁𝗂𝗌 𝗂𝗌 𝗇𝗈𝗍 𝗒𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 !", show_alert=True)
            else:
                if clicked == typed:
                    await client.send_cached_media(
                        chat_id=query.from_user.id,
                        file_id=file_id,
                        caption=f_caption,
                        protect_content=True if ident == "filep" else False,
                        reply_markup=InlineKeyboardMarkup( [ [ InlineKeyboardButton('⎋ Main Channel ⎋', url="https://t.me/kdramaworld_ongoing") ] ] ))
                else:
                    await query.answer(f"𝖧𝖾𝗒 {query.from_user.first_name}, 𝖳𝗁𝗂𝗌 𝗂𝗌 𝗇𝗈𝗍 𝗒𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 !", show_alert=True)
                await query.answer('𝖢𝗁𝖾𝖼𝗄 𝖯𝖬, 𝖨 𝗁𝖺𝗏𝖾 𝗌𝖾𝗇𝗍 𝖿𝗂𝗅𝖾𝗌 𝗂𝗇 𝖯𝖬', show_alert=True)
        except UserIsBlocked:
            await query.answer('𝖴𝗇𝖻𝗅𝗈𝖼𝗄 𝗍𝗁𝖾 𝖻𝗈𝗍 𝗆𝖺𝗇𝗁 !', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
        except Exception as e:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
    elif query.data.startswith("checksub"):
        if info.AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer("𝖨 𝖫𝗂𝗄𝖾 𝖸𝗈𝗎𝗋 𝖲𝗆𝖺𝗋𝗍𝗇𝖾𝗌𝗌, 𝖡𝗎𝗍 𝖣𝗈𝗇'𝗍 𝖡𝖾 𝖮𝗏𝖾𝗋𝗌𝗆𝖺𝗋𝗍 😒 \n𝖩𝗈𝗂𝗇 𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 𝖿𝗂𝗋𝗌𝗍 ;)", show_alert=True)
            return
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('No such file exist.')
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        if info.KEEP_ORIGINAL_CAPTION:
            try:
                f_caption = files.caption
            except:
                f_caption = f"{title}"
        if info.CUSTOM_FILE_CAPTION:
            try:
                f_caption = info.CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
                f_caption = f_caption
        if f_caption is None:
            f_caption = f"{title}"
        await query.answer()
        await client.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file_id,
            caption=f_caption,
            protect_content=True if ident == 'checksubp' else False,
            reply_markup=InlineKeyboardMarkup( [ [ InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL) ] ] ))
    elif query.data == "pages":
        await query.answer()

    elif query.data.startswith("send_all"):
        _, req, key, pre = query.data.split("#")
        logger.info(f"{req} {key} {pre}")
        if int(req) not in [query.from_user.id, 0]:
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=all_{key}_{pre}")
        

    elif query.data.startswith("killfilesdq"):
        ident, keyword = query.data.split("#")
        await query.message.edit_text(f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
        files, total = await get_bad_files(keyword)
        await query.message.edit_text(f"<b>Found {total} files for your query {keyword} !\n\nFile deletion process will start in 5 seconds !</b>")
        await asyncio.sleep(5)
        deleted = 0
        async with lock:
            try:
                for file in files:
                    file_ids = file.file_id
                    file_name = file.file_name
                    result = await Media.collection.delete_one({
                        '_id': file_ids,
                    })
                    if result.deleted_count:
                        logger.info(f'File Found for your query {keyword}! Successfully deleted {file_name} from database.')
                    deleted += 1
                    if deleted % 20 == 0:
                        await query.message.edit_text(f"<b>Process started for deleting files from DB. Successfully deleted {str(deleted)} files from DB for your query {keyword} !\n\nPlease wait...</b>")
            except Exception as e:
                logger.exception(e)
                await query.message.edit_text(f'Error: {e}')
            else:
                await query.message.edit_text(f"<b>Process Completed for file deletion !\n\nSuccessfully deleted {str(deleted)} files from database for your query {keyword}.</b>")

    elif query.data.startswith("opnsetgrp"):
        ident, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in info.ADMINS
        ):
            await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)
            return
        title = query.message.chat.title
        settings = await get_settings(grp_id)
        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('𝖥𝗂𝗅𝗍𝖾𝗋 𝖡𝗎𝗍𝗍𝗈𝗇',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('𝖲𝗂𝗇𝗀𝗅𝖾 𝖡𝗎𝗍𝗍𝗈𝗇' if settings["button"] else '𝖣𝗈𝗎𝖻𝗅𝖾',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖥𝗂𝗅𝖾 𝖲𝖾𝗇𝖽 𝖬𝗈𝖽𝖾', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
                    InlineKeyboardButton('𝖬𝖺𝗇𝗎𝖺𝗅 𝖲𝗍𝖺𝗋𝗍' if settings["botpm"] else '𝖠𝗎𝗍𝗈 𝖲𝖾𝗇𝖽',
                                         callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖯𝗋𝗈𝗍𝖾𝖼𝗍 𝖢𝗈𝗇𝗍𝖾𝗇𝗍',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["file_secure"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖨𝖬𝖣𝖻', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["imdb"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖲𝗉𝖾𝗅𝗅 𝖢𝗁𝖾𝖼𝗄',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["spell_check"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖬𝖾𝗌𝗌𝖺𝗀𝖾', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["welcome"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖠𝗎𝗍𝗈 𝖣𝖾𝗅𝖾𝗍𝖾',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('5 𝖬𝗂𝗇' if settings["auto_delete"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖠𝗎𝗍𝗈-𝖥𝗂𝗅𝗍𝖾𝗋',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["auto_ffilter"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖬𝖺𝗑 𝖡𝗎𝗍𝗍𝗈𝗇𝗌',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{info.MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_text(
                text=f"<b>𝖢𝗁𝖺𝗇𝗀𝖾 𝖸𝗈𝗎𝗋 𝖲𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝖥𝗈𝗋 {title} 𝖠𝗌 𝖸𝗈𝗎𝗋 𝖶𝗂𝗌𝗁</b>",
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML
            )
            await query.message.edit_reply_markup(reply_markup)
        
    elif query.data.startswith("opnsetpm"):
        ident, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in info.ADMINS
        ):
            await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)
            return
        title = query.message.chat.title
        settings = await get_settings(grp_id)
        btn2 = [[
                 InlineKeyboardButton("➡ 𝖮𝗉𝖾𝗇 𝗂𝗇 𝖯𝖬 ➡", url=f"t.me/{temp.U_NAME}")
               ]]
        reply_markup = InlineKeyboardMarkup(btn2)
        await query.message.edit_text(f"<b>𝖸𝗈𝗎𝗋 𝗌𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝗆𝖾𝗇𝗎 𝖿𝗈𝗋 {title} 𝗁𝖺𝗌 𝖻𝖾𝖾𝗇 𝗌𝖾𝗇𝗍 𝗍𝗈 𝗒𝗈𝗎𝗋 𝖯𝖬</b>")
        await query.message.edit_reply_markup(reply_markup)
        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('𝖥𝗂𝗅𝗍𝖾𝗋 𝖡𝗎𝗍𝗍𝗈𝗇',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('𝖲𝗂𝗇𝗀𝗅𝖾 𝖡𝗎𝗍𝗍𝗈𝗇' if settings["button"] else '𝖣𝗈𝗎𝖻𝗅𝖾',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖥𝗂𝗅𝖾 𝖲𝖾𝗇𝖽 𝖬𝗈𝖽𝖾', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
                    InlineKeyboardButton('𝖬𝖺𝗇𝗎𝖺𝗅 𝖲𝗍𝖺𝗋𝗍' if settings["botpm"] else '𝖠𝗎𝗍𝗈 𝖲𝖾𝗇𝖽',
                                         callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖯𝗋𝗈𝗍𝖾𝖼𝗍 𝖢𝗈𝗇𝗍𝖾𝗇𝗍',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["file_secure"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖨𝖬𝖣𝖻', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["imdb"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖲𝗉𝖾𝗅𝗅 𝖢𝗁𝖾𝖼𝗄',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["spell_check"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖬𝖾𝗌𝗌𝖺𝗀𝖾', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["welcome"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖠𝗎𝗍𝗈 𝖣𝖾𝗅𝖾𝗍𝖾',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('5 𝖬𝗂𝗇' if settings["auto_delete"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖠𝗎𝗍𝗈-𝖥𝗂𝗅𝗍𝖾𝗋',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["auto_ffilter"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖬𝖺𝗑 𝖡𝗎𝗍𝗍𝗈𝗇𝗌',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{info.MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await client.send_message(
                chat_id=userid,
                text=f"<b>𝖢𝗁𝖺𝗇𝗀𝖾 𝖸𝗈𝗎𝗋 𝖲𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝖥𝗈𝗋 {title} 𝖠𝗌 𝖸𝗈𝗎𝗋 𝖶𝗂𝗌𝗁</b>",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=query.message.id
            )

    elif query.data.startswith("show_option"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("⚠ Unavailable ⚠", callback_data=f"unavailable#{from_user}"),
                InlineKeyboardButton("✅ 𝖴𝗉𝗅𝗈𝖺𝖽𝖾𝖽 ✅", callback_data=f"uploaded#{from_user}")
             ],[
                InlineKeyboardButton("🔰 𝖠𝗅𝗋𝖾𝖺𝖽𝗒 𝖠𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 🔰", callback_data=f"already_available#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton("❕ 𝖵𝗂𝖾𝗐 𝖲𝗍𝖺𝗍𝗎𝗌 ❕", url=f"{query.message.link}")
               ]]
        if query.from_user.id in info.ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("𝖧𝖾𝗋𝖾 𝖺𝗋𝖾 𝗍𝗁𝖾 𝗈𝗉𝗍𝗂𝗈𝗇𝗌")
        else:
            await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)
        
    elif query.data.startswith("unavailable"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("⚠ 𝖴𝗇𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 ⚠", callback_data=f"unalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton("❕ 𝖵𝗂𝖾𝗐 𝖲𝗍𝖺𝗍𝗎𝗌 ❕", url=f"{query.message.link}")
               ]]
        if query.from_user.id in info.ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("𝖲𝖾𝗍 𝗍𝗈 𝖴𝗇𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾")
            try:
                await client.send_message(chat_id=int(from_user), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖲𝗈𝗋𝗋𝗒 𝗒𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝗎𝗇𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾. 𝖲𝗈 𝗆𝗈𝖽𝖾𝗋𝖺𝗍𝗈𝗋𝗌 𝖼𝖺𝗇'𝗍 𝖺𝖽𝖽 𝗂𝗍 !</b>", reply_markup=InlineKeyboardMarkup(btn2))
            except UserIsBlocked:
                await client.send_message(chat_id=int(info.SUPPORT_CHAT_ID), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖲𝗈𝗋𝗋𝗒 𝗒𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝗎𝗇𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾. 𝖲𝗈 𝗆𝗈𝖽𝖾𝗋𝖺𝗍𝗈𝗋𝗌 𝖼𝖺𝗇'𝗍 𝖺𝖽𝖽 𝗂𝗍 !\n\n📝 𝖭𝗈𝗍𝖾: 𝖳𝗁𝗂𝗌 𝗆𝖾𝗌𝗌𝖺𝗀𝖾 𝗂𝗌 𝗌𝖾𝗇𝗍 𝗂𝗇 𝖦𝗋𝗈𝗎𝗉 𝖻𝖾𝖼𝖺𝗎𝗌𝖾 𝗒𝗈𝗎 𝗁𝖺𝗏𝖾 𝖡𝗅𝗈𝖼𝗄𝖾𝖽 𝗍𝗁𝖾 𝖡𝗈𝗍 ! 𝖴𝗇𝖻𝗅𝗈𝖼𝗄 𝗍𝗁𝖾 𝖡𝗈𝗍 !</b>", reply_markup=InlineKeyboardMarkup(btn2))
        else:
            await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)

    elif query.data.startswith("uploaded"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("✅ 𝖴𝗉𝗅𝗈𝖺𝖽𝖾𝖽 ✅", callback_data=f"upalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton("❕ 𝖵𝗂𝖾𝗐 𝖲𝗍𝖺𝗍𝗎𝗌 ❕", url=f"{query.message.link}")
               ]]
        if query.from_user.id in info.ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("𝖲𝖾𝗍 𝗍𝗈 𝖴𝗉𝗅𝗈𝖺𝖽𝖾𝖽")
            try:
                await client.send_message(chat_id=int(from_user), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗁𝖺𝗌 𝖻𝖾𝖾𝗇 𝗎𝗉𝗅𝗈𝖺𝖽𝖾𝖽 𝖻𝗒 𝗆𝗈𝖽𝖾𝗋𝖺𝗍𝗈𝗋. 𝖪𝗂𝗇𝖽𝗅𝗒 𝗌𝖾𝖺𝗋𝖼𝗁 𝖺𝗀𝖺𝗂𝗇 @kdramasmirrorchat !</b>", reply_markup=InlineKeyboardMarkup(btn2))
            except UserIsBlocked:
                await client.send_message(chat_id=int(info.SUPPORT_CHAT_ID), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗁𝖺𝗌 𝖻𝖾𝖾𝗇 𝗎𝗉𝗅𝗈𝖺𝖽𝖾𝖽 𝖻𝗒 𝗆𝗈𝖽𝖾𝗋𝖺𝗍𝗈𝗋. 𝖪𝗂𝗇𝖽𝗅𝗒 𝗌𝖾𝖺𝗋𝖼𝗁 𝖺𝗀𝖺𝗂𝗇 @kdramasmirrorchat !\n\n📝 𝖭𝗈𝗍𝖾: 𝖳𝗁𝗂𝗌 𝗆𝖾𝗌𝗌𝖺𝗀𝖾 𝗂𝗌 𝗌𝖾𝗇𝗍 𝗂𝗇 𝖦𝗋𝗈𝗎𝗉 𝖻𝖾𝖼𝖺𝗎𝗌𝖾 𝗒𝗈𝗎 𝗁𝖺𝗏𝖾 𝖡𝗅𝗈𝖼𝗄𝖾𝖽 𝗍𝗁𝖾 𝖡𝗈𝗍 ! 𝖴𝗇𝖻𝗅𝗈𝖼𝗄 𝗍𝗁𝖾 𝖡𝗈𝗍 !</b>", reply_markup=InlineKeyboardMarkup(btn2))
        else:
            await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)

    elif query.data.startswith("already_available"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("🔰 𝖠𝗅𝗋𝖾𝖺𝖽𝗒 𝖠𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 🔰", callback_data=f"alalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton("❕ 𝖵𝗂𝖾𝗐 𝖲𝗍𝖺𝗍𝗎𝗌 ❕", url=f"{query.message.link}")
               ]]
        if query.from_user.id in info.ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("𝖲𝖾𝗍 𝗍𝗈 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 !")
            try:
                await client.send_message(chat_id=int(from_user), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 𝗈𝗇 𝖡𝗈𝗍. 𝖪𝗂𝗇𝖽𝗅𝗒 𝗌𝖾𝖺𝗋𝖼𝗁 𝖺𝗀𝖺𝗂𝗇 @kdramasmirrorchat !</b>", reply_markup=InlineKeyboardMarkup(btn2))
            except UserIsBlocked:
                await client.send_message(chat_id=int(info.SUPPORT_CHAT_ID), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 𝗈𝗇 𝖡𝗈𝗍. 𝖪𝗂𝗇𝖽𝗅𝗒 𝗌𝖾𝖺𝗋𝖼𝗁 𝖺𝗀𝖺𝗂𝗇 @kdramasmirrorchat !\n\n📝 𝖭𝗈𝗍𝖾: 𝖳𝗁𝗂𝗌 𝗆𝖾𝗌𝗌𝖺𝗀𝖾 𝗂𝗌 𝗌𝖾𝗇𝗍 𝗂𝗇 𝖦𝗋𝗈𝗎𝗉 𝖻𝖾𝖼𝖺𝗎𝗌𝖾 𝗒𝗈𝗎 𝗁𝖺𝗏𝖾 𝖡𝗅𝗈𝖼𝗄𝖾𝖽 𝗍𝗁𝖾 𝖡𝗈𝗍 ! 𝖴𝗇𝖻𝗅𝗈𝖼𝗄 𝗍𝗁𝖾 𝖡𝗈𝗍 !</b>", reply_markup=InlineKeyboardMarkup(btn2))
        else:
            await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)

    elif query.data.startswith("alalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"𝖧𝖾𝗒 {user.first_name}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 !", show_alert=True)
        else:
            await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)

    elif query.data.startswith("upalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"𝖧𝖾𝗒 {user.first_name}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝗎𝗉𝗅𝗈𝖺𝖽𝖾𝖽 !", show_alert=True)
        else:
            await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)
        
    elif query.data.startswith("unalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"𝖧𝖾𝗒 {user.first_name}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝗎𝗇𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 !", show_alert=True)
        else:
            await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)

    elif query.data == 'rkbtn':
        await query.answer("𝖧𝖾𝗒 𝖡𝗋𝗈 😍\n\n🎯 𝖢𝗅𝗂𝖼𝗄 𝖮𝗇 𝖳𝗁𝖾 𝖡𝗎𝗍𝗍𝗈𝗇 𝖻𝖾𝗅𝗈𝗐 𝖳𝗁𝖾 𝖥𝗂𝗅𝖾𝗌 𝖸𝗈𝗎 𝖶𝖺𝗇𝗍 𝖠𝗇𝖽 𝖲𝗍𝖺𝗋𝗍 𝖳𝗁𝖾 𝖡𝗈𝗍 ⬇️", True)

    elif query.data == 'info':
        await query.answer("𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝘀 𝗙𝗼𝗿𝗺𝗮𝘁𝘀\n\n• Hyper Knife s01e08\n• Our Blooming Youth\n• The Vanished 2018 1080p\n• The Vanished 2018\n• goblin e01\n\n‼️𝗗𝗼𝗻𝘁 𝗮𝗱𝗱 𝘄𝗼𝗿𝗱𝘀 & 𝘀𝘆𝗺𝗯𝗼𝗹𝘀  , . - 𝗹𝗶𝗸𝗲 send link movie series 𝗲𝘁𝗰‼️", True)
    
    elif query.data == 'tips':
        await query.answer("𝖳𝗁𝗂𝗌 𝖬𝖾𝗌𝗌𝖺𝗀𝖾 𝖶𝗂𝗅𝗅 𝖡𝖾 𝖣𝖾𝗅𝖾𝗍𝖾𝖽 𝖠𝖿𝗍𝖾𝗋 5 𝖬𝗂𝗇𝗎𝗍𝖾𝗌 𝗍𝗈 𝖯𝗋𝖾𝗏𝖾𝗇𝗍 𝖢𝗈𝗉𝗒𝗋𝗂𝗀𝗁𝗍 !\n\n𝖳𝗁𝖺𝗇𝗄 𝖸𝗈𝗎 𝖥𝗈𝗋 𝖴𝗌𝗂𝗇𝗀 𝖬𝖾 😊\n\n\n𝖯𝗈𝗐𝖾𝗋𝖾𝖽 𝖡𝗒 KDramaWorld", True)

    elif query.data == "start":
        buttons = [[
                    InlineKeyboardButton('➕ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ➕', url=f"https://t.me/{temp.U_NAME}?startgroup=true")
                ],[
                    InlineKeyboardButton('ᴏᴡɴᴇʀ', callback_data="owner_info"),
                    InlineKeyboardButton('ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=f"https://t.me/{info.SUPPORT_CHAT}")
                ],[
                    InlineKeyboardButton('ʜᴇʟᴘ', callback_data='help'),
                    InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about'),
                ],[
                    InlineKeyboardButton('ꜱᴇᴀʀᴄʜ ᴅʀᴀᴍᴀꜱ', switch_inline_query_current_chat='')
                  ]]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer('Support Us By Sharing The Channel And Bot')

    elif query.data == "filters":
        buttons = [[
            InlineKeyboardButton('✏ 𝖬𝖺𝗇𝗎𝖺𝗅 𝖥𝗂𝗅𝗍𝖾𝗋', callback_data='manuelfilter'),
            InlineKeyboardButton('📊 𝖠𝗎𝗍𝗈 𝖥𝗂𝗅𝗍𝖾𝗋', callback_data='autofilter')
        ],[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='help'),
            InlineKeyboardButton('📈 𝖦𝗅𝗈𝖻𝖺𝗅 𝖥𝗂𝗅𝗍𝖾𝗋', callback_data='global_filters')
        ]]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        await query.message.edit_text(
            text=script.ALL_FILTERS.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "global_filters":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='filters')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.GFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    
    elif query.data == "help":
        buttons = [[
            InlineKeyboardButton('💼 𝖥𝗂𝗅𝗍𝖾𝗋𝗌 𝖬𝗈𝖽𝖾', callback_data='filters'),
            InlineKeyboardButton('🗂 𝖥𝗂𝗅𝖾 𝖲𝗍𝗈𝗋𝖾', callback_data='store_file')
        ], [
            InlineKeyboardButton('📟 𝖢𝗈𝗇𝗇𝖾𝖼𝗍𝗂𝗈𝗇𝗌', callback_data='coct'),
            InlineKeyboardButton('⚙ 𝖤𝗑𝗍𝗋𝖺 𝖬𝗈𝖽𝖾𝗌', callback_data='extra')
        ], [
            InlineKeyboardButton('🏘 𝖧𝗈𝗆𝖾', callback_data='start'),
            InlineKeyboardButton('♻️ Status', callback_data='stats')
        ]]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        await query.message.edit_text(
            text=script.HELP_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "about":
        buttons = [[
            InlineKeyboardButton('🧬 𝖲𝗎𝗉𝗉𝗈𝗋𝗍 𝖦𝗋𝗈𝗎𝗉', url=f"https://t.me/{info.SUPPORT_CHAT}"),
            InlineKeyboardButton('📍 𝖲𝗈𝗎𝗋𝖼𝖾 𝖢𝗈𝖽𝖾', callback_data='source')
        ],[
            InlineKeyboardButton('🏘 𝖧𝗈𝗆𝖾', callback_data='start'),
            InlineKeyboardButton('❌ 𝖢𝗅𝗈𝗌𝖾', callback_data='close_data')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "source":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        await query.message.edit_text(
            text=script.SOURCE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "manuelfilter":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='filters'),
            InlineKeyboardButton('⏺ 𝖡𝗎𝗍𝗍𝗈𝗇𝗌', callback_data='button')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        await query.message.edit_text(
            text=script.MANUELFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "button":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='manuelfilter')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.BUTTON_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "autofilter":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='filters')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.AUTOFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "coct":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='help')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.CONNECTION_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "extra":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='help'),
            InlineKeyboardButton('⚠ 𝖠𝖽𝗆𝗂𝗇', callback_data='admin')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.EXTRAMOD_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    
    elif query.data == "store_file":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='help')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.FILE_STORE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    
    elif query.data == "admin":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='extra')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ADMIN_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "stats":
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='help'),
            InlineKeyboardButton('♻️ 𝖱𝖾𝖿𝗋𝖾𝗌𝗁', callback_data='rfrsh')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        total = await Media.count_documents()
        users = await db.total_users_count()
        chats = await db.total_chat_count()
        monsize = await db.get_db_size()
        free = 536870912 - monsize
        monsize = get_size(monsize)
        free = get_size(free)
        await query.message.edit_text(
            text=script.STATUS_TXT.format(total, users, chats, monsize, free),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "rfrsh":
        await query.answer("Fetching MongoDb DataBase...")
        buttons = [[
            InlineKeyboardButton('👩‍🦯 𝖡𝖺𝖼𝗄', callback_data='help'),
            InlineKeyboardButton('♻️ 𝖱𝖾𝖿𝗋𝖾𝗌𝗁', callback_data='rfrsh')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(info.PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        total = await Media.count_documents()
        users = await db.total_users_count()
        chats = await db.total_chat_count()
        monsize = await db.get_db_size()
        free = 536870912 - monsize
        monsize = get_size(monsize)
        free = get_size(free)
        await query.message.edit_text(
            text=script.STATUS_TXT.format(total, users, chats, monsize, free),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "owner_info":
            btn = [[
                    InlineKeyboardButton("👩‍🦯 𝖡𝖺𝖼𝗄", callback_data="start"),
                    InlineKeyboardButton("📞 𝖢𝗈𝗇𝗍𝖺𝖼𝗍", url="https://t.me/matthewmurdock001")
                  ]]
            await client.edit_message_media(
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(random.choice(info.PICS))
            )
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_text(
                text=script.OWNER_INFO,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )

    elif query.data.startswith("setgs"):
        ident, set_type, status, grp_id = query.data.split("#")
        grpid = await active_connection(str(query.from_user.id))

        if str(grp_id) != str(grpid):
            await query.message.edit("Your Active Connection Has Been Changed. Go To /settings.")
            return await query.answer('Support Us By Sharing The Channel And Bot')

        if status == "True":
            await save_group_settings(grpid, set_type, False)
        else:
            await save_group_settings(grpid, set_type, True)

        settings = await get_settings(grpid)

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('𝖥𝗂𝗅𝗍𝖾𝗋 𝖡𝗎𝗍𝗍𝗈𝗇',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('𝖲𝗂𝗇𝗀𝗅𝖾 𝖡𝗎𝗍𝗍𝗈𝗇' if settings["button"] else '𝖣𝗈𝗎𝖻𝗅𝖾',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖥𝗂𝗅𝖾 𝖲𝖾𝗇𝖽 𝖬𝗈𝖽𝖾', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
                    InlineKeyboardButton('𝖬𝖺𝗇𝗎𝖺𝗅 𝖲𝗍𝖺𝗋𝗍' if settings["botpm"] else '𝖠𝗎𝗍𝗈 𝖲𝖾𝗇𝖽',
                                         callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖯𝗋𝗈𝗍𝖾𝖼𝗍 𝖢𝗈𝗇𝗍𝖾𝗇𝗍',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["file_secure"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖨𝖬𝖣𝖻', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["imdb"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖲𝗉𝖾𝗅𝗅 𝖢𝗁𝖾𝖼𝗄',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["spell_check"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖬𝖾𝗌𝗌𝖺𝗀𝖾', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["welcome"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖠𝗎𝗍𝗈 𝖣𝖾𝗅𝖾𝗍𝖾',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('5 𝖬𝗂𝗇' if settings["auto_delete"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖠𝗎𝗍𝗈-𝖥𝗂𝗅𝗍𝖾𝗋',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ 𝖮𝗇' if settings["auto_ffilter"] else '❌ 𝖮𝖿𝖿',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('𝖬𝖺𝗑 𝖡𝗎𝗍𝗍𝗈𝗇𝗌',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{info.MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_reply_markup(reply_markup)
    await query.answer('Support Us By Sharing The Channel And Bot')

    
async def auto_filter(client, msg, spoll=False):
    reqstr1 = msg.from_user.id if msg.from_user else None
    if reqstr1 is None:
        return
    reqstr = await client.get_users(reqstr1)
    if not spoll:
        message = msg
        settings = await get_settings(message.chat.id) # Ensure settings are loaded once upfront
        if message.text.startswith("/"): return  # ignore commands
        if re.findall(r"((^/|^,|^!|^\.|^[😀-󠁿]).*)", message.text):
            return
        if len(message.text) < 100:
            search = message.text
            files, offset, total_results = await get_search_results(message.chat.id ,search.lower(), offset=0, filter=True)
            if not files:
                if settings["spell_check"]:
                    return await advantage_spell_chok(client, msg)
                else:
                    if message.chat.type == enums.ChatType.PRIVATE:
                        await message.reply_text("No results found. Try another keyword.")
                    elif info.NO_RESULTS_MSG: # Log only if not PM and NO_RESULTS_MSG is True
                        await client.send_message(chat_id=info.LOG_CHANNEL, text=(script.NORSLTS.format(reqstr.id, reqstr.mention, search)))
                    return
        else:
            return
    else:
        message = msg.message.reply_to_message  # msg will be callback query
        search, files, offset, total_results = spoll
        settings = await get_settings(msg.message.chat.id)
        
    key = f"{message.chat.id}-{message.id}" # Used for BUTTONS and temp.FILES_IDS
    temp.FILES_IDS[key] = files
    pre = 'filep' if settings.get('file_secure') else 'file' # Use .get for safety
    req = message.from_user.id if message.from_user else 0
    BUTTONS[key] = search
    
    if settings.get("button"): # Use .get for safety
        btn = [
            [
                InlineKeyboardButton(
                    text=f"🔖{get_size(file.file_size)}🔮{file.file_name}", callback_data=f'{pre}#{file.file_id}'
                ),
            ]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{file.file_name}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
                InlineKeyboardButton(
                    text=f"{get_size(file.file_size)}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
            ]
            for file in files
        ]

    # The 'Info' and 'Tips' buttons are always added regardless of 'auto_delete' value.
    # The try-except for 'auto_delete' here was mainly for initializing the setting if absent.
    # Assuming get_settings now ensures 'auto_delete' exists (e.g., with a default).
    btn.insert(0,
        [
            InlineKeyboardButton(f'😇 Info', 'tips'),
            InlineKeyboardButton(f'📝 𝖳𝗂𝗉𝗌', 'info')
        ]
    )
                      
    btn.insert(0, [ # This was btn.insert(0, [...])
        InlineKeyboardButton(f'🎬 {search} 🎬', 'rkbtn')
    ])
    btn.insert(2, [ # This was btn.insert(2, [...])
        InlineKeyboardButton("📤 𝖲𝖾𝗇𝖽 𝖠𝗅𝗅 𝖥𝗂𝗅𝖾𝗌 📤", callback_data=f"send_all#{req}#{key}#{pre}")
    ])
    
    if offset != "": # If there is a next page
        # settings = await get_settings(message.chat.id) # Settings already fetched
        if settings.get('max_btn', False): # Default to False if key is missing
            btn.append(
                [InlineKeyboardButton("📃", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="𝖭𝖤𝖷𝖳 ▶️",callback_data=f"next_{req}_{key}_{offset}")]
            )
        else: # max_btn is False or not set
            btn.append(
                [InlineKeyboardButton("📃", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(info.MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="𝖭𝖤𝖷𝖳 ▶️",callback_data=f"next_{req}_{key}_{offset}")]
            )
        # The original try-except KeyError for 'max_btn' which re-fetched settings and repeated logic is removed
        # as .get() handles the case of missing key more cleanly.
    else: # No more pages
        btn.append(
            [InlineKeyboardButton(text="❌ 𝖭𝗈 𝖬𝗈𝗋𝖾 𝖯𝖺𝗀𝖾𝗌 𝖠𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 ! ❌",callback_data="pages")]
        )

    imdb = await get_poster(search, file=(files[0]).file_name) if settings.get("imdb") else None # Use .get
    TEMPLATE = settings.get('template', info.IMDB_TEMPLATE) # Use .get with a fallback to global default
    if imdb:
        cap = TEMPLATE.format(
            query=search,
            title=imdb['title'],
            votes=imdb['votes'],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb['box_office'],
            localized_title=imdb['localized_title'],
            kind=imdb['kind'],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb['release_date'],
            year=imdb['year'],
            genres=imdb['genres'],
            poster=imdb['poster'],
            plot=imdb['plot'],
            rating=imdb['rating'],
            url=imdb['url'],
            **locals()
        )
    else:
        cap = f"<b>👋 𝖧𝖾𝗒 {message.from_user.mention}\n📁 𝖸𝗈𝗎𝗋 𝖥𝗂𝗅𝖾𝗌 𝖠𝗋𝖾 𝖱𝖾𝖺𝖽𝗒\n\n♨️ 𝖯𝗈𝗐𝖾𝗋𝖾𝖽 𝖡𝗒 @kdramaworld_ongoing</b>"
    if imdb and imdb.get('poster'):
        try:
            hehe = await message.reply_photo(photo=imdb.get('poster'), caption=cap[:1024], reply_markup=InlineKeyboardMarkup(btn))
            try:
                if settings['auto_delete']:
                    delete_time = info.AUTO_DELETE_TIME
                    await asyncio.sleep(delete_time)
                    await hehe.delete()
                    await message.delete()
            except KeyError:
                # This block might be redundant if settings always have 'auto_delete'
                # Consider ensuring 'auto_delete' is always present in settings initialization
                grpid = await active_connection(str(message.from_user.id))
                if grpid: # Ensure grpid is not None
                    await save_group_settings(grpid, 'auto_delete', True) # Default to True if missing
                    settings = await get_settings(message.chat.id) # Refresh settings
                    if settings.get('auto_delete'): # Check again
                        delete_time = info.AUTO_DELETE_TIME
                        await asyncio.sleep(delete_time)
                        await hehe.delete()
                        await message.delete()
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            hmm = await message.reply_photo(photo=poster, caption=cap[:1024], reply_markup=InlineKeyboardMarkup(btn))
            try:
                if settings['auto_delete']:
                    delete_time = info.AUTO_DELETE_TIME
                    await asyncio.sleep(delete_time)
                    await hmm.delete()
                    await message.delete()
            except KeyError:
                grpid = await active_connection(str(message.from_user.id))
                if grpid:
                    await save_group_settings(grpid, 'auto_delete', True)
                    settings = await get_settings(message.chat.id)
                    if settings.get('auto_delete'):
                        delete_time = info.AUTO_DELETE_TIME
                        await asyncio.sleep(delete_time)
                        await hmm.delete()
                        await message.delete()
        except Exception as e:
            logger.exception(e)
            fek = await message.reply_photo(photo=info.NOR_IMG, caption=cap, reply_markup=InlineKeyboardMarkup(btn))
            try:
                if settings['auto_delete']:
                    delete_time = info.AUTO_DELETE_TIME
                    await asyncio.sleep(delete_time)
                    await fek.delete()
                    await message.delete()
            except KeyError:
                grpid = await active_connection(str(message.from_user.id))
                if grpid:
                    await save_group_settings(grpid, 'auto_delete', True)
                    settings = await get_settings(message.chat.id)
                    if settings.get('auto_delete'):
                        delete_time = info.AUTO_DELETE_TIME
                        await asyncio.sleep(delete_time)
                        await fek.delete()
                        await message.delete()
    else:
        fuk = await message.reply_photo(photo=info.NOR_IMG, caption=cap, reply_markup=InlineKeyboardMarkup(btn))
        try:
            if settings['auto_delete']:
                delete_time = info.AUTO_DELETE_TIME
                await asyncio.sleep(delete_time)
                await fuk.delete()
                await message.delete()
        except KeyError:
            grpid = await active_connection(str(message.from_user.id))
            if grpid:
                await save_group_settings(grpid, 'auto_delete', True)
                settings = await get_settings(message.chat.id)
                if settings.get('auto_delete'):
                    delete_time = info.AUTO_DELETE_TIME
                    await asyncio.sleep(delete_time)
                    await fuk.delete()
                    await message.delete()
    if spoll:
        await msg.message.delete()

async def advantage_spell_chok(client, msg):
    mv_id = msg.id
    mv_rqst = msg.text
    reqstr1 = msg.from_user.id if msg.from_user else None
    if reqstr1 is None:
        return
    reqstr = await client.get_users(reqstr1)
    settings = await get_settings(msg.chat.id)
    query = re.sub(
        r"\b(pl([ie])*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br(([ou])h?)*|^h([ea])?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t([iy])?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", msg.text, flags=re.IGNORECASE)  # plis contribute some common words
    query = query.strip() + " movie"
    try:
        movies = await get_poster(mv_rqst, bulk=True)
    except Exception as e:
        logger.exception(e)
        reqst_gle = mv_rqst.replace(" ", "+")
        button = [[
                   InlineKeyboardButton("🔎 𝖦𝗈𝗈𝗀𝗅𝖾", url=f"https://www.google.com/search?q={reqst_gle}")
        ]]
        if info.NO_RESULTS_MSG: # Log to channel if enabled
            await client.send_message(chat_id=info.LOG_CHANNEL, text=(script.NORSLTS.format(reqstr.id, reqstr.mention, mv_rqst)))

        if msg.chat.type == enums.ChatType.PRIVATE:
            await msg.reply_text("No results found. Try another keyword.")
            # No need to send image or Google button in PM if no results from spell check.
            # The sleep and delete for 'k' is also not needed here.
        else: # Original behavior for groups
            k = await msg.reply_photo(
                photo=info.SPELL_IMG,
                caption=script.I_CUDNT.format(mv_rqst),
                reply_markup=InlineKeyboardMarkup(button)
            )
            await asyncio.sleep(30) # This sleep and delete is for the group message
            await k.delete()
        return # Return after handling no results.
    movielist = []
    if not movies: # This block should ideally not be reached if the above `if not movies:` in `get_poster` catches it.
                  # However, keeping it as a safeguard.
        if info.NO_RESULTS_MSG: # Log to channel if enabled
            await client.send_message(chat_id=info.LOG_CHANNEL, text=(script.NORSLTS.format(reqstr.id, reqstr.mention, mv_rqst)))

        if msg.chat.type == enums.ChatType.PRIVATE:
            await msg.reply_text("No results found. Try another keyword.")
        else: # Original behavior for groups
            reqst_gle = mv_rqst.replace(" ", "+") # reqst_gle was defined inside the `except` block before
            button = [[
                       InlineKeyboardButton("🔎 𝖦𝗈𝗈𝗀𝗅𝖾", url=f"https://www.google.com/search?q={reqst_gle}")
            ]]
            k = await msg.reply_photo(
                photo=info.SPELL_IMG,
                caption=script.I_CUDNT.format(mv_rqst),
                reply_markup=InlineKeyboardMarkup(button)
            )
            await asyncio.sleep(30)
            await k.delete()
        return
    movielist += [movie.get('title') for movie in movies]
    movielist += [f"{movie.get('title')} {movie.get('year')}" for movie in movies]
    SPELL_CHECK[mv_id] = movielist
    btn = [
        [
            InlineKeyboardButton(
                text=movie_name.strip(),
                callback_data=f"spol#{reqstr1}#{k}",
            )
        ]
        for k, movie_name in enumerate(movielist)
    ]
    btn.append([InlineKeyboardButton(text="Close", callback_data=f'spol#{reqstr1}#close_spellcheck')])
    spell_check_del = await msg.reply_photo(
        photo=info.SPELL_IMG,
        caption=(script.CUDNT_FND.format(mv_rqst)),
        reply_markup=InlineKeyboardMarkup(btn),quote=True
    )
    try:
        if settings['auto_delete']:
            delete_time = info.AUTO_DELETE_TIME
            await asyncio.sleep(delete_time)
            await spell_check_del.delete()
    except KeyError:
            grpid = await active_connection(str(msg.from_user.id))
            if grpid:
                await save_group_settings(grpid, 'auto_delete', True)
                settings = await get_settings(msg.chat.id)
                if settings.get('auto_delete'):
                    delete_time = info.AUTO_DELETE_TIME
                    await asyncio.sleep(delete_time)
                    await spell_check_del.delete()


async def manual_filters(client, message, text=False):
    settings = await get_settings(message.chat.id)
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_filters(group_id)
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_filter(group_id, keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            piroxrk = await client.send_message(
                                group_id, 
                                reply_text, 
                                disable_web_page_preview=True,
                                protect_content=True if settings["file_secure"] else False,
                                reply_to_message_id=reply_id
                            )
                            try:
                                if settings['auto_ffilter']:
                                    await auto_filter(client, message)
                                    try:
                                        if settings['auto_delete']:
                                            delete_time = info.AUTO_DELETE_TIME
                                            await asyncio.sleep(delete_time) # Wait before deleting original trigger and bot reply
                                            await piroxrk.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        if grpid:
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings.get('auto_delete'):
                                                delete_time = info.AUTO_DELETE_TIME
                                                await asyncio.sleep(delete_time)
                                                await piroxrk.delete()
                                else: # if auto_ffilter is false
                                    try:
                                        if settings['auto_delete']:
                                            delete_time = info.AUTO_DELETE_TIME
                                            await asyncio.sleep(delete_time)
                                            await piroxrk.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        if grpid:
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings.get('auto_delete'):
                                                delete_time = info.AUTO_DELETE_TIME
                                                await asyncio.sleep(delete_time)
                                                await piroxrk.delete()
                            except KeyError: # This is for 'auto_ffilter'
                                grpid = await active_connection(str(message.from_user.id))
                                if grpid: await save_group_settings(grpid, 'auto_ffilter', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_ffilter']:
                                    await auto_filter(client, message)

                        else:
                            button = eval(btn)
                            piroxrk = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                protect_content=True if settings["file_secure"] else False,
                                reply_to_message_id=reply_id
                            )
                            try:
                                if settings['auto_ffilter']:
                                    await auto_filter(client, message)
                                    try:
                                        if settings['auto_delete']:
                                            delete_time = info.AUTO_DELETE_TIME
                                            await asyncio.sleep(delete_time) # Wait before deleting
                                            await piroxrk.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        if grpid:
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings.get('auto_delete'):
                                                delete_time = info.AUTO_DELETE_TIME
                                                await asyncio.sleep(delete_time)
                                                await piroxrk.delete()
                                else: # if auto_ffilter is false
                                    try:
                                        if settings['auto_delete']:
                                            delete_time = info.AUTO_DELETE_TIME
                                            await asyncio.sleep(delete_time)
                                            await piroxrk.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        if grpid:
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings.get('auto_delete'):
                                                delete_time = info.AUTO_DELETE_TIME
                                                await asyncio.sleep(delete_time)
                                                await piroxrk.delete()
                            except KeyError: # This is for 'auto_ffilter'
                                grpid = await active_connection(str(message.from_user.id))
                                if grpid: await save_group_settings(grpid, 'auto_ffilter', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_ffilter']:
                                    await auto_filter(client, message)

                    elif btn == "[]":
                        piroxrk = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            protect_content=True if settings["file_secure"] else False,
                            reply_to_message_id=reply_id
                        )
                        try:
                            if settings['auto_ffilter']:
                                await auto_filter(client, message)
                                try:
                                    if settings['auto_delete']:
                                        delete_time = info.AUTO_DELETE_TIME
                                        await asyncio.sleep(delete_time) # Wait before deleting
                                        await piroxrk.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    if grpid:
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings.get('auto_delete'):
                                            delete_time = info.AUTO_DELETE_TIME
                                            await asyncio.sleep(delete_time)
                                            await piroxrk.delete()
                            else: # if auto_ffilter is false
                                try:
                                    if settings['auto_delete']:
                                        delete_time = info.AUTO_DELETE_TIME
                                        await asyncio.sleep(delete_time)
                                        await piroxrk.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    if grpid:
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings.get('auto_delete'):
                                            delete_time = info.AUTO_DELETE_TIME
                                            await asyncio.sleep(delete_time)
                                            await piroxrk.delete()
                        except KeyError: # This is for 'auto_ffilter'
                            grpid = await active_connection(str(message.from_user.id))
                            if grpid: await save_group_settings(grpid, 'auto_ffilter', True)
                            settings = await get_settings(message.chat.id)
                            if settings['auto_ffilter']:
                                await auto_filter(client, message)

                    else:
                        button = eval(btn)
                        piroxrk = await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                        try:
                            if settings['auto_ffilter']:
                                await auto_filter(client, message)
                                try:
                                    if settings['auto_delete']:
                                        delete_time = info.AUTO_DELETE_TIME
                                        await asyncio.sleep(delete_time) # Wait before deleting
                                        await piroxrk.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    if grpid:
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings.get('auto_delete'):
                                            delete_time = info.AUTO_DELETE_TIME
                                            await asyncio.sleep(delete_time)
                                            await piroxrk.delete()
                            else: # if auto_ffilter is false
                                try:
                                    if settings['auto_delete']:
                                        delete_time = info.AUTO_DELETE_TIME
                                        await asyncio.sleep(delete_time)
                                        await piroxrk.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    if grpid:
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings.get('auto_delete'):
                                            delete_time = info.AUTO_DELETE_TIME
                                            await asyncio.sleep(delete_time)
                                            await piroxrk.delete()
                        except KeyError: # This is for 'auto_ffilter'
                            grpid = await active_connection(str(message.from_user.id))
                            if grpid: await save_group_settings(grpid, 'auto_ffilter', True)
                            settings = await get_settings(message.chat.id)
                            if settings['auto_ffilter']:
                                await auto_filter(client, message)

                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False

async def global_filters(client, message, text=False):
    settings = await get_settings(message.chat.id)
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_gfilters('gfilters')

    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_gfilter('gfilters', keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            piroxrk = None # Initialize piroxrk to None

            if btn is not None:
                try:
                    if fileid == "None": # Text message from global filter
                        if btn == "[]": # No buttons
                            piroxrk = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_to_message_id=reply_id
                            )
                        else: # With buttons
                            button = eval(btn)
                            piroxrk = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id
                            )
                    elif btn == "[]": # Cached media without buttons
                        piroxrk = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id
                        )
                    else: # Cached media with buttons
                        button = eval(btn)
                        piroxrk = await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )

                    # Common logic after piroxrk is potentially set
                    if piroxrk:
                        manual_triggered = await manual_filters(client, message)
                        settings = await get_settings(message.chat.id) # Refresh settings

                        if not manual_triggered:
                            try:
                                if settings.get('auto_ffilter'):
                                    await auto_filter(client, message) # auto_filter handles its own deletion
                                    # Global filter message (piroxrk) might still be deleted based on chat's auto_delete
                                    if settings.get('auto_delete'):
                                        delete_time = info.AUTO_DELETE_TIME
                                        await asyncio.sleep(delete_time)
                                        await piroxrk.delete()
                                elif settings.get('auto_delete'): # auto_ffilter is false, but chat wants to delete bot messages
                                    delete_time = info.AUTO_DELETE_TIME
                                    await asyncio.sleep(delete_time)
                                    await piroxrk.delete()

                            except KeyError: # Catch if 'auto_ffilter' or 'auto_delete' is somehow missing
                                grpid = await active_connection(str(message.from_user.id))
                                if grpid:
                                    # Ensure defaults are set if keys are missing
                                    if 'auto_ffilter' not in settings:
                                        await save_group_settings(grpid, 'auto_ffilter', True)
                                    if 'auto_delete' not in settings:
                                        await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id) # Refresh again
                                    if settings.get('auto_ffilter'):
                                        await auto_filter(client, message)
                                        if settings.get('auto_delete'):
                                            delete_time = info.AUTO_DELETE_TIME
                                            await asyncio.sleep(delete_time)
                                            await piroxrk.delete()
                                    elif settings.get('auto_delete'):
                                        delete_time = info.AUTO_DELETE_TIME
                                        await asyncio.sleep(delete_time)
                                        await piroxrk.delete()

                        else: # Manual filter was triggered, piroxrk is the global filter's message
                            if settings.get('auto_delete'):
                                delete_time = info.AUTO_DELETE_TIME
                                await asyncio.sleep(delete_time)
                                await piroxrk.delete()
                    return True # Global filter was triggered

                except Exception as e:
                    logger.exception(e)
                break # Exit loop once a keyword is matched and processed
    return False # No global filter was triggered
