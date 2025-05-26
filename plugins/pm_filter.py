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
from plugins.commands import check_user_access

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
SPELL_CHECK = {}


async def create_file_display_buttons(search_query, files_list, current_offset_val, total_results_val, settings_dict, req_user_id_val, button_key_val, file_prefix_val, is_next_page_call=False, chat_id_for_settings=None, n_offset_for_next_page=None):
    btn_list = [] 

    file_btn_text_prefix = "🔰" if is_next_page_call else "🔖"
    file_btn_text_suffix = "📁" if is_next_page_call else "🔮"

    if settings_dict['button']: 
        for file_obj in files_list:
            btn_list.append([
                InlineKeyboardButton(
                    text=f"{file_btn_text_prefix}{get_size(file_obj.file_size)}{file_btn_text_suffix}{file_obj.file_name}",
                    callback_data=f'{file_prefix_val}#{file_obj.file_id}'
                )
            ])
    else: 
        for file_obj in files_list:
            btn_list.append([
                InlineKeyboardButton(
                    text=f"{file_obj.file_name}",
                    callback_data=f'{file_prefix_val}#{file_obj.file_id}',
                ),
                InlineKeyboardButton(
                    text=f"{get_size(file_obj.file_size)}",
                    callback_data=f'{file_prefix_val}#{file_obj.file_id}',
                )
            ])

    info_tips_row = [
        InlineKeyboardButton(f'😇 Info', 'tips'),
        InlineKeyboardButton(f'📝 𝖳𝗂𝗉𝗌', 'info')
    ]
    
    search_query_row = [InlineKeyboardButton(f'🎬 {search_query} 🎬', 'rkbtn')]
    
    send_all_row = None
    if not is_next_page_call: 
        send_all_row = [InlineKeyboardButton("📤 𝖲𝖾𝗇𝖽 𝖠𝗅𝗅 𝖥𝗂𝗅𝖾𝗌 📤", callback_data=f"send_all#{req_user_id_val}#{button_key_val}#{file_prefix_val}")]

    final_button_layout = []
    final_button_layout.append(search_query_row) 
    final_button_layout.append(info_tips_row) 
    if send_all_row: 
        final_button_layout.append(send_all_row)
    
    final_button_layout.extend(btn_list) 

    max_items_per_page = 10 if settings_dict['max_btn'] else int(info.MAX_B_TN)
    
    current_page_display_num = 0
    total_pages_display_num = 0

    if isinstance(current_offset_val, str): 
        if current_offset_val == "": 
            if total_results_val > 0 and total_results_val <= max_items_per_page:
                 final_button_layout.append([InlineKeyboardButton(text="❌ 𝖭𝗈 𝖬𝗈𝗋𝖾 𝖯𝖺𝗀𝖾𝗌 𝖠𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 ! ❌",callback_data="pages")])
        else: 
            next_offset_for_first_page = int(current_offset_val)
            if total_results_val > max_items_per_page: 
                current_page_display_num = 1
                total_pages_display_num = math.ceil(total_results_val / max_items_per_page)
                final_button_layout.append(
                    [
                        InlineKeyboardButton("📃", callback_data="pages"), 
                        InlineKeyboardButton(text=f"{current_page_display_num}/{total_pages_display_num}",callback_data="pages"), 
                        InlineKeyboardButton(text="𝖭𝖤𝖷𝖳 ▶️",callback_data=f"next_{req_user_id_val}_{button_key_val}_{next_offset_for_first_page}") 
                    ]
                )
            elif total_results_val > 0: 
                final_button_layout.append([InlineKeyboardButton(text="❌ 𝖭𝗈 𝖬𝗈𝗋𝖾 𝖯𝖺𝗀𝖾𝗌 𝖠𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 ! ❌",callback_data="pages")])

    elif isinstance(current_offset_val, int): 
        current_page_start_offset = current_offset_val
        
        current_page_display_num = math.floor(current_page_start_offset / max_items_per_page) + 1
        total_pages_display_num = math.ceil(total_results_val / max_items_per_page)
        
        pagination_row_items = []
        
        if current_page_start_offset > 0: 
            back_offset_calculated = current_page_start_offset - max_items_per_page
            if back_offset_calculated < 0: back_offset_calculated = 0 
            pagination_row_items.append(InlineKeyboardButton("◀️ 𝖡𝖠𝖢𝖪", callback_data=f"next_{req_user_id_val}_{button_key_val}_{back_offset_calculated}"))
        
        pagination_row_items.append(InlineKeyboardButton(f"{current_page_display_num} / {total_pages_display_num}", callback_data="pages"))

        
        next_page_starts_at = current_page_start_offset + len(files_list) 
        if n_offset_for_next_page is not None and n_offset_for_next_page > 0 and next_page_starts_at < total_results_val:
            pagination_row_items.append(InlineKeyboardButton("𝖭𝖤𝖷𝖳 ▶️", callback_data=f"next_{req_user_id_val}_{button_key_val}_{n_offset_for_next_page}"))
        
        if pagination_row_items:
             if len(pagination_row_items) == 1 and total_pages_display_num <=1 : 
                 if total_results_val > 0 : 
                    final_button_layout.append([InlineKeyboardButton(text="❌ 𝖭𝗈 𝖬𝗈𝗋𝖾 𝖯𝖺𝗀𝖾𝗌 𝖠𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 ! ❌", callback_data="pages")])
             else:
                final_button_layout.append(pagination_row_items)
        elif total_pages_display_num <= 1 and total_results_val > 0 : 
             final_button_layout.append([InlineKeyboardButton(text="❌ 𝖭𝗈 𝖬𝗈𝗋𝖾 𝖯𝖺𝗀𝖾𝗌 𝖠𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 ! ❌", callback_data="pages")])
            
    return InlineKeyboardMarkup(final_button_layout) if final_button_layout else None


@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    glob = await global_filters(client, message)
    if not glob:
        manual = await manual_filters(client, message)
        if not manual:
            settings = await get_settings(message.chat.id)
            if settings['auto_ffilter']:
                await auto_filter(client, message)

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pv_filter(client, message):
    kd = await global_filters(client, message)
    if not kd:
        await auto_filter(client, message)

async def handle_setgs_cb(client: Client, query: CallbackQuery):
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

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        await handle_close_data(client, query)
    elif query.data == "gfiltersdeleteallconfirm":
        await handle_gfilters_delete_all_confirm(client, query)
    elif query.data == "gfiltersdeleteallcancel":
        await handle_gfilters_delete_all_cancel(client, query)
    elif query.data == "delallconfirm":
        await handle_del_all_confirm(client, query)
    elif query.data == "delallcancel":
        await handle_del_all_cancel(client, query)
    elif "groupcb" in query.data:
        await handle_group_cb(client, query)
    elif "connectcb" in query.data:
        await handle_connect_cb(client, query)
    elif "disconnect" in query.data:
        await handle_disconnect_cb(client, query)
    elif "deletecb" in query.data:
        await handle_delete_cb(client, query)
    elif query.data == "backcb":
        await handle_back_cb(client, query)
    elif "gfilteralert" in query.data:
        await handle_gfilter_alert(client, query)
    elif "alertmessage" in query.data:
        await handle_alert_message(client, query)
    elif query.data.startswith("file"):
        await handle_file_cb(client, query)
    elif query.data.startswith("checksub"):
        await handle_checksub_cb(client, query)
    elif query.data == "pages":
        await handle_pages_cb(client, query)
    elif query.data.startswith("send_all"):
        await handle_send_all_cb(client, query)
    elif query.data.startswith("killfilesdq"):
        await handle_kill_files_cb(client, query)
    elif query.data.startswith("opnsetgrp"):
        await handle_open_set_group_cb(client, query)
    elif query.data.startswith("opnsetpm"):
        await handle_open_set_pm_cb(client, query)
    elif query.data.startswith("show_option"):
        await handle_show_option_cb(client, query)
    elif query.data.startswith("unavailable"):
        await handle_unavailable_cb(client, query)
    elif query.data.startswith("uploaded"):
        await handle_uploaded_cb(client, query)
    elif query.data.startswith("already_available"):
        await handle_already_available_cb(client, query)
    elif query.data.startswith("alalert"):
        await handle_alalert_cb(client, query)
    elif query.data.startswith("upalert"):
        await handle_upalert_cb(client, query)
    elif query.data.startswith("unalert"):
        await handle_unalert_cb(client, query)
    elif query.data == 'rkbtn':
        await handle_rkbtn_cb(client, query)
    elif query.data == 'info':
        await handle_info_cb(client, query)
    elif query.data == 'tips':
        await handle_tips_cb(client, query)
    elif query.data == "start":
        await handle_start_cb(client, query)
    elif query.data == "filters":
        await handle_filters_cb(client, query)
    elif query.data == "global_filters":
        await handle_global_filters_cb(client, query)
    elif query.data == "help":
        await handle_help_cb(client, query)
    elif query.data == "about":
        await handle_about_cb(client, query)
    elif query.data == "source":
        await handle_source_cb(client, query)
    elif query.data == "manuelfilter":
        await handle_manuel_filter_cb(client, query)
    elif query.data == "button":
        await handle_button_cb(client, query)
    elif query.data == "autofilter":
        await handle_autofilter_cb(client, query)
    elif query.data == "coct":
        await handle_coct_cb(client, query)
    elif query.data == "extra":
        await handle_extra_cb(client, query)
    elif query.data == "store_file":
        await handle_store_file_cb(client, query)
    elif query.data == "admin":
        await handle_admin_cb(client, query)
    elif query.data == "stats":
        await handle_stats_cb(client, query)
    elif query.data == "rfrsh":
        await handle_rfrsh_cb(client, query)
    elif query.data == "owner_info":
        await handle_owner_info_cb(client, query)
    elif query.data.startswith("setgs"):
        await handle_setgs_cb(client, query)
    else:
        await query.answer('Support Us By Sharing The Channel And Bot')

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset_str = query.data.split("_") 
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    try:
        offset = int(offset_str) 
    except ValueError: 
        offset = 0 
    
    search = BUTTONS.get(key)
    if not search:
        return await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)

    files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
    
    if not files: 
        return await query.answer("No more files found on this page.", show_alert=True)

    settings = await get_settings(query.message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file' 
    temp.FILES_IDS[key] = files 

    reply_markup = await create_file_display_buttons(
        search_query=search,
        files_list=files,
        current_offset_val=offset, 
        total_results_val=total,
        settings_dict=settings,
        req_user_id_val=int(req), 
        button_key_val=key,
        file_prefix_val=pre,
        is_next_page_call=True, 
        chat_id_for_settings=query.message.chat.id, 
        n_offset_for_next_page=n_offset 
    )
    
    try:
        if reply_markup: 
            await query.edit_message_reply_markup(reply_markup=reply_markup)
    except MessageNotModified:
        pass 
    return await query.answer()

async def auto_filter(client, msg, spoll=False):
    reqstr1 = msg.from_user.id if msg.from_user else None
    if reqstr1 is None:
        return
    reqstr = await client.get_users(reqstr1)
    
    base_message_for_context = msg if not spoll else msg.message 
    
    if not spoll:
        message = msg 
        settings = await get_settings(message.chat.id)
        if message.text.startswith("/"): return 
        if re.findall(r"((^/|^,|^!|^\.|^[😀-󠁿]).*)", message.text):
            return
        if len(message.text) < 100: 
            search_query_text = message.text
            files, next_offset_str, total_results = await get_search_results(message.chat.id ,search_query_text.lower(), offset=0, filter=True)
            if not files:
                if settings['spell_check']: 
                    return await advantage_spell_chok(client, msg)
                else: # Spell check is off
                    if message.chat.type == enums.ChatType.PRIVATE: # Check if it's a PM
                        await client.send_message(
                            chat_id=message.chat.id,
                            text="No results found. Try another keyword or request from the support group. You can find the support group link in /help or /start."
                        )
                    # For group chats, no message is sent directly to the chat if spell_check is off and no files are found.
                    # Logging to LOG_CHANNEL happens if info.NO_RESULTS_MSG is True, which is a separate condition.
                    elif info.NO_RESULTS_MSG and message.chat.type != enums.ChatType.PRIVATE: 
                        await client.send_message(
                            chat_id=info.LOG_CHANNEL, 
                            text=(script.NORSLTS.format(reqstr.id, reqstr.mention, search_query_text))
                        )
                    return
        else: 
            return
    else: 
        message = msg.message.reply_to_message 
        search_query_text, files, next_offset_str, total_results = spoll 
        settings = await get_settings(msg.message.chat.id) 

    user_id_of_requester = message.from_user.id 
    can_access, access_reason = await check_user_access(client, message, user_id_of_requester,increment=False)
    if not can_access:
        await base_message_for_context.reply_text(access_reason) 
        return
        
    button_key = f"{message.chat.id}-{message.id}" 
    temp.FILES_IDS[button_key] = files
    file_prefix = 'filep' if settings['file_secure'] else 'file'
    requester_id_for_buttons = message.from_user.id if message.from_user else 0 
    BUTTONS[button_key] = search_query_text
    
    reply_markup = await create_file_display_buttons(
        search_query=search_query_text,
        files_list=files,
        current_offset_val=next_offset_str, 
        total_results_val=total_results,
        settings_dict=settings,
        req_user_id_val=requester_id_for_buttons,
        button_key_val=button_key,
        file_prefix_val=file_prefix,
        is_next_page_call=False, 
        chat_id_for_settings=base_message_for_context.chat.id,
        n_offset_for_next_page=None 
    )

    imdb_info = await get_poster(search_query_text, file=(files[0]).file_name) if settings["imdb"] and files else None
    template_to_use = settings['template'] 
    
    final_caption = ""
    if imdb_info:
        final_caption = template_to_use.format(
            query=search_query_text,
            title=imdb_info.get('title', ''), 
            votes=imdb_info.get('votes', ''),
            aka=imdb_info.get("aka", ''),
            seasons=imdb_info.get("seasons", ''),
            box_office=imdb_info.get('box_office', ''),
            localized_title=imdb_info.get('localized_title', ''),
            kind=imdb_info.get('kind', ''),
            imdb_id=imdb_info.get("imdb_id", ''),
            cast=imdb_info.get("cast", ''),
            runtime=imdb_info.get("runtime", ''),
            countries=imdb_info.get("countries", ''),
            certificates=imdb_info.get("certificates", ''),
            languages=imdb_info.get("languages", ''),
            director=imdb_info.get("director", ''),
            writer=imdb_info.get("writer", ''),
            producer=imdb_info.get("producer", ''),
            composer=imdb_info.get("composer", ''),
            cinematographer=imdb_info.get("cinematographer", ''),
            music_team=imdb_info.get("music_team", ''),
            distributors=imdb_info.get("distributors", ''),
            release_date=imdb_info.get('release_date', ''),
            year=imdb_info.get('year', ''),
            genres=imdb_info.get('genres', ''),
            poster=imdb_info.get('poster', ''),
            plot=imdb_info.get('plot', ''),
            rating=imdb_info.get('rating', ''),
            url=imdb_info.get('url', ''),
            **locals() 
        )
    else: 
        final_caption = f"<b>👋 𝖧𝖾𝗒 {message.from_user.mention}\n📁 𝖸𝗈𝗎𝗋 𝖥𝗂𝗅𝖾𝗌 𝖠𝗋𝖾 𝖱𝖾𝖺𝖽𝗒\n\n♨️ 𝖯𝗈𝗐𝖾𝗋𝖾𝖽 𝖡𝗒 @kdramaworld_ongoing</b>"

    reply_target_message = base_message_for_context 

    sent_message_to_delete = None
    if imdb_info and imdb_info.get('poster'):
        try:
            sent_message_to_delete = await reply_target_message.reply_photo(photo=imdb_info.get('poster'), caption=final_caption[:1024], reply_markup=reply_markup)
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb_info.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            sent_message_to_delete = await reply_target_message.reply_photo(photo=poster, caption=final_caption[:1024], reply_markup=reply_markup)
        except Exception as e:
            logger.exception(e)
            sent_message_to_delete = await reply_target_message.reply_photo(photo=info.NOR_IMG, caption=final_caption, reply_markup=reply_markup)
    else:
        sent_message_to_delete = await reply_target_message.reply_photo(photo=info.NOR_IMG, caption=final_caption, reply_markup=reply_markup)

    if settings['auto_delete'] and sent_message_to_delete: 
        await asyncio.sleep(600) 
        await sent_message_to_delete.delete()
        if not spoll : await message.delete() 

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
        "", msg.text, flags=re.IGNORECASE)
    query = query.strip() + " movie"
    try:
        movies = await get_poster(mv_rqst, bulk=True)
    except Exception as e:
        logger.exception(e)
        reqst_gle = mv_rqst.replace(" ", "+")
        button = [[
                   InlineKeyboardButton("🔎 𝖦𝗈𝗈𝗀𝗅𝖾", url=f"https://www.google.com/search?q={reqst_gle}")
        ]]
        if info.NO_RESULTS_MSG:
            await client.send_message(chat_id=info.LOG_CHANNEL, text=(script.NORSLTS.format(reqstr.id, reqstr.mention, mv_rqst)))
        k = await msg.reply_photo(
            photo=info.SPELL_IMG,
            caption="No results found. Try another keyword or request from the support group. You can find the support group link in /help or /start.",
            reply_markup=InlineKeyboardMarkup(button)
        )
        await asyncio.sleep(30)
        await k.delete()
        return
    movielist = []
    if not movies:
        reqst_gle = mv_rqst.replace(" ", "+")
        button = [[
                   InlineKeyboardButton("🔎 𝖦𝗈𝗈𝗀𝗅𝖾", url=f"https://www.google.com/search?q={reqst_gle}")
        ]]
        if info.NO_RESULTS_MSG:
            await client.send_message(chat_id=info.LOG_CHANNEL, text=(script.NORSLTS.format(reqstr.id, reqstr.mention, mv_rqst)))
        k = await msg.reply_photo(
            photo=info.SPELL_IMG,
            caption="No results found. Try another keyword or request from the support group. You can find the support group link in /help or /start.",
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
    if settings['auto_delete']:
        await asyncio.sleep(600)
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
                user_id = message.from_user.id
                if fileid != "None": 
                    can_access, reason = await check_user_access(client, message, user_id,increment=False)
                    if not can_access:
                        await message.reply_text(reason)
                        break 
                    can_send, reason = await check_user_access(
                        client, message, user_id,
                        increment=True
                    )
                    if not can_send:
                        await message.reply_text(reason)
                        break

                try:
                    if fileid == "None":
                        if btn == "[]":
                            piroxrk = await client.send_message(
                                group_id, 
                                reply_text, 
                                disable_web_page_preview=True,
                                protect_content=settings["file_secure"], 
                                reply_to_message_id=reply_id
                            )
                            if settings['auto_ffilter']:
                                await auto_filter(client, message)
                                if settings['auto_delete']:
                                    await piroxrk.delete()
                            else:
                                if settings['auto_delete']:
                                    await asyncio.sleep(600)
                                    await piroxrk.delete()
                        else:
                            button = eval(btn)
                            piroxrk = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                protect_content=settings["file_secure"], 
                                reply_to_message_id=reply_id
                            )
                            if settings['auto_ffilter']:
                                await auto_filter(client, message)
                                if settings['auto_delete']:
                                    await piroxrk.delete()
                            else:
                                if settings['auto_delete']:
                                    await asyncio.sleep(600)
                                    await piroxrk.delete()
                    elif btn == "[]":
                        piroxrk = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            protect_content=settings["file_secure"], 
                            reply_to_message_id=reply_id
                        )
                        if settings['auto_ffilter']:
                            await auto_filter(client, message)
                            if settings['auto_delete']:
                                await piroxrk.delete()
                        else:
                            if settings['auto_delete']:
                                await asyncio.sleep(600)
                                await piroxrk.delete()
                    else:
                        button = eval(btn)
                        piroxrk = await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                        if settings['auto_ffilter']:
                            await auto_filter(client, message)
                            if settings['auto_delete']:
                                await piroxrk.delete()
                        else:
                            if settings['auto_delete']:
                                await asyncio.sleep(600)
                                await piroxrk.delete()
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

            if btn is not None:
                user_id = message.from_user.id
                if fileid != "None": 
                    can_access, reason = await check_user_access(client, message, user_id,increment=False)
                    if not can_access:
                        await message.reply_text(reason)
                        break 
                    ok, reason = await check_user_access(
                        client, message, user_id,
                        increment=True
                    )
                    if not ok:
                        await message.reply_text(reason)
                        break
                try:
                    if fileid == "None":
                        if btn == "[]":
                            piroxrk = await client.send_message(
                                group_id, 
                                reply_text, 
                                disable_web_page_preview=True,
                                reply_to_message_id=reply_id
                            )
                            manual = await manual_filters(client, message)
                            if not manual:
                                if settings['auto_ffilter']:
                                    await auto_filter(client, message)
                                    if settings['auto_delete']:
                                        await piroxrk.delete()
                                else:
                                    if settings['auto_delete']:
                                        await asyncio.sleep(600)
                                        await piroxrk.delete()
                            else: 
                                if settings['auto_delete']: 
                                     await piroxrk.delete()
                        else:
                            button = eval(btn)
                            piroxrk = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id
                            )
                            manual = await manual_filters(client, message)
                            if not manual:
                                if settings['auto_ffilter']:
                                    await auto_filter(client, message)
                                    if settings['auto_delete']:
                                        await piroxrk.delete()
                                else:
                                    if settings['auto_delete']:
                                        await asyncio.sleep(600)
                                        await piroxrk.delete()
                            else: 
                                if settings['auto_delete']: 
                                     await piroxrk.delete()

                    elif btn == "[]":
                        piroxrk = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id
                        )
                        manual = await manual_filters(client, message)
                        if not manual:
                            if settings['auto_ffilter']:
                                await auto_filter(client, message)
                                if settings['auto_delete']:
                                    await piroxrk.delete()
                            else:
                                if settings['auto_delete']:
                                    await asyncio.sleep(600)
                                    await piroxrk.delete()
                        else: 
                            if settings['auto_delete']: 
                                 await piroxrk.delete()
                    else:
                        button = eval(btn)
                        piroxrk = await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                        manual = await manual_filters(client, message)
                        if not manual:
                            if settings['auto_ffilter']:
                                await auto_filter(client, message)
                                if settings['auto_delete']:
                                    await piroxrk.delete()
                            else:
                                if settings['auto_delete']:
                                    await asyncio.sleep(600)
                                    await piroxrk.delete()
                        else: 
                            if settings['auto_delete']: 
                                 await piroxrk.delete()
                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False

# cb_handler helper functions
async def handle_close_data(client: Client, query: CallbackQuery):
    await query.message.delete()

async def handle_gfilters_delete_all_confirm(client: Client, query: CallbackQuery):
    await del_allg(query.message, 'gfilters')
    await query.answer("Done !")

async def handle_gfilters_delete_all_cancel(client: Client, query: CallbackQuery):
    await query.message.reply_to_message.delete()
    await query.message.delete()
    await query.answer("Process Cancelled !")

async def handle_del_all_confirm(client: Client, query: CallbackQuery):
    userid = query.from_user.id
    chat_type = query.message.chat.type
    grp_id = None 
    title = None 

    if chat_type == enums.ChatType.PRIVATE:
        grpid_conn = await active_connection(str(userid))
        if grpid_conn is not None:
            grp_id = grpid_conn
            try:
                chat = await client.get_chat(grpid_conn)
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
        return await query.answer('Unsupported chat type for this action.', show_alert=True)

    if not grp_id or not title: 
        await query.message.edit_text("Error: Could not determine group information.")
        return await query.answer('Error processing request.', show_alert=True)
        
    st = await client.get_chat_member(grp_id, userid)
    if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in info.ADMINS):
        await del_all(query.message, grp_id, title)
    else:
        await query.answer("You need to be Group Owner or an Auth User to do that!", show_alert=True)

async def handle_del_all_cancel(client: Client, query: CallbackQuery):
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

async def handle_group_cb(client: Client, query: CallbackQuery):
    await query.answer()
    group_id = query.data.split(":")[1]
    act = query.data.split(":")[2]
    hr = await client.get_chat(int(group_id))
    title = hr.title
    
    stat = "CONNECT" if act == "" else "DISCONNECT"
    cb = "connectcb" if act == "" else "disconnect"

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
    
async def handle_connect_cb(client: Client, query: CallbackQuery):
    await query.answer()
    group_id = query.data.split(":")[1]
    hr = await client.get_chat(int(group_id))
    title = hr.title
    user_id = query.from_user.id
    mkact = await make_active(str(user_id), str(group_id))
    if mkact:
        await query.message.edit_text(f"Connected to **{title}**", parse_mode=enums.ParseMode.MARKDOWN)
    else:
        await query.message.edit_text('Some error occurred while connecting!', parse_mode=enums.ParseMode.MARKDOWN)

async def handle_disconnect_cb(client: Client, query: CallbackQuery):
    await query.answer()
    user_id = query.from_user.id
    mkinact = await make_inactive(str(user_id))
    if mkinact:
        await query.message.edit_text(f"Disconnected from All Groups", parse_mode=enums.ParseMode.MARKDOWN)
    else:
        await query.message.edit_text(f"Some error occurred!!", parse_mode=enums.ParseMode.MARKDOWN)

async def handle_delete_cb(client: Client, query: CallbackQuery):
    await query.answer()
    user_id = query.from_user.id
    group_id = query.data.split(":")[1]
    delcon = await delete_connection(str(user_id), str(group_id))
    if delcon:
        await query.message.edit_text("Successfully deleted connection")
    else:
        await query.message.edit_text(f"Some error occurred!!", parse_mode=enums.ParseMode.MARKDOWN)

async def handle_back_cb(client: Client, query: CallbackQuery):
    await query.answer()
    userid = query.from_user.id
    groupids = await all_connections(str(userid))
    if groupids is None:
        await query.message.edit_text("There are no active connections!! Connect to some groups first.")
        return
    buttons = []
    for groupid in groupids:
        try:
            ttl = await client.get_chat(int(groupid))
            title = ttl.title
            active = await if_active(str(userid), str(groupid))
            act = " - ACTIVE" if active else ""
            buttons.append([InlineKeyboardButton(text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}")])
        except:
            pass
    if buttons:
        await query.message.edit_text("Your connected group details ;\n\n", reply_markup=InlineKeyboardMarkup(buttons))
    
async def handle_gfilter_alert(client: Client, query: CallbackQuery):
    i = query.data.split(":")[1]
    keyword = query.data.split(":")[2]
    reply_text, btn, alerts, fileid = await find_gfilter('gfilters', keyword)
    if alerts is not None:
        alerts = ast.literal_eval(alerts)
        alert = alerts[int(i)]
        alert = alert.replace("\\n", "\n").replace("\\t", "\t")
        await query.answer(alert, show_alert=True)

async def handle_alert_message(client: Client, query: CallbackQuery):
    grp_id = query.message.chat.id 
    i = query.data.split(":")[1]
    keyword = query.data.split(":")[2]
    reply_text, btn, alerts, fileid = await find_filter(grp_id, keyword)
    if alerts is not None:
        alerts = ast.literal_eval(alerts)
        alert = alerts[int(i)]
        alert = alert.replace("\\n", "\n").replace("\\t", "\t")
        await query.answer(alert, show_alert=True)

async def handle_file_cb(client: Client, query: CallbackQuery):
    clicked = query.from_user.id
    typed = query.from_user.id
    if query.message.reply_to_message and query.message.reply_to_message.from_user:
        typed = query.message.reply_to_message.from_user.id
        
    ident, file_id = query.data.split("#")
    files_ = await get_file_details(file_id)
    if not files_:
        return await query.answer('No such file exist.')
    
    file_item = files_[0] 
    title = file_item.file_name
    size = get_size(file_item.file_size)
    f_caption = file_item.caption
    settings = await get_settings(query.message.chat.id)

    if info.KEEP_ORIGINAL_CAPTION:
        f_caption = file_item.caption 
    elif info.CUSTOM_FILE_CAPTION:
        try:
            f_caption = info.CUSTOM_FILE_CAPTION.format(file_name=title or '',
                                                   file_size=size or '',
                                                   file_caption=f_caption or '')
        except Exception as e:
            logger.exception(e)
    if f_caption is None: 
        f_caption = f"{title}"
        
    if clicked != typed:
        return await query.answer(f"𝖧𝖾𝗒 {query.from_user.first_name}, 𝖳𝗁𝗂𝗌 𝗂𝗌 𝗇𝗈𝗍 𝗒𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 !", show_alert=True)

    try:
        if info.AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
            return
        elif settings['botpm']: 
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
            return
        else:
            user_id = query.from_user.id
            can_access, reason = await check_user_access(client, query.message, user_id,increment=False)
            if not can_access:
                await query.answer(reason, show_alert=True)
                return
            ok, reason = await check_user_access(client, query.message, user_id,increment=True)
            if not ok:
                await query.answer(reason, show_alert=True)
                return

            await client.send_cached_media(
                chat_id=query.from_user.id,
                file_id=file_id,
                caption=f_caption,
                protect_content=True if ident == "filep" else False,
                reply_markup=InlineKeyboardMarkup( [ [ InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL) ] ] ))
            await query.answer('𝖢𝗁𝖾𝖼𝗄 𝖯𝖬, 𝖨 𝗁𝖺𝗏𝖾 𝗌𝖾𝗇𝗍 𝖿𝗂𝗅𝖾𝗌 𝗂𝗇 𝖯𝖬', show_alert=True)
    except UserIsBlocked:
        await query.answer('𝖴𝗇𝖻𝗅𝗈𝖼𝗄 𝗍𝗁𝖾 𝖻𝗈𝗍 𝗆𝖺𝗇𝗁 !', show_alert=True)
    except PeerIdInvalid: 
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
    except Exception as e: 
        logger.error(f"Error in cb_handler 'file': {e}", exc_info=True)
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}") 

async def handle_checksub_cb(client: Client, query: CallbackQuery):
    user_id = query.from_user.id 
    if info.AUTH_CHANNEL and not await is_subscribed(client, query): 
        await query.answer("𝖨 𝖫𝗂𝗄𝖾 𝖸𝗈𝗎𝗋 𝖲𝗆𝖺𝗋𝗍𝗇𝖾𝗌𝗌, 𝖡𝗎𝗍 𝖣𝗈𝗇'𝗍 𝖡𝖾 𝖮𝗏𝖾𝗋𝗌𝗆𝖺𝗋𝗍 😒 \n𝖩𝗈𝗂𝗇 𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 𝖿𝗂𝗋𝗌𝗍 ;)", show_alert=True)
        return

    can_access, reason = await check_user_access(client, query.message, user_id,increment=False)
    if not can_access:
        await query.answer(reason, show_alert=True)
        return
        
    ident, file_id = query.data.split("#")
    files_ = await get_file_details(file_id)
    if not files_:
        return await query.answer('No such file exist.')
    
    file_item = files_[0] 
    title = file_item.file_name
    size = get_size(file_item.file_size)
    f_caption = file_item.caption 
    if info.KEEP_ORIGINAL_CAPTION:
        f_caption = file_item.caption
    elif info.CUSTOM_FILE_CAPTION: 
        try:
            f_caption = info.CUSTOM_FILE_CAPTION.format(file_name=title or '',
                                                   file_size=size or '',
                                                   file_caption=f_caption or '')
        except Exception as e:
            logger.exception(e)
    if f_caption is None: 
        f_caption = f"{title}"

    await query.answer() 
    ok, reason = await check_user_access(client, query.message, user_id, increment=True)
    if not ok:
        await query.answer(reason, show_alert=True)
        return
    try:
        await client.send_cached_media(
            chat_id=query.from_user.id, 
            file_id=file_id,
            caption=f_caption,
            protect_content=True if ident == 'checksubp' else False, 
            reply_markup=InlineKeyboardMarkup( [ [ InlineKeyboardButton('⎋ Main Channel ⎋', url=info.MAIN_CHANNEL) ] ] ))
    except UserIsBlocked:
        await query.answer('𝖴𝗇𝖻𝗅𝗈𝖼𝗄 𝗍𝗁𝖾 𝖻𝗈𝗍 𝗆𝖺𝗇𝗁 !', show_alert=True)
    except Exception as e:
        logger.error(f"Error in cb_handler 'checksub': {e}", exc_info=True)
        await query.answer("An error occurred while sending the file.", show_alert=True)

async def handle_pages_cb(client: Client, query: CallbackQuery):
    await query.answer()

async def handle_send_all_cb(client: Client, query: CallbackQuery):
    _, req, key, pre = query.data.split("#")
    logger.info(f"{req} {key} {pre}") 
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    
    await query.answer(url=f"https://t.me/{temp.U_NAME}?start=all_{key}_{pre}")
    
async def handle_kill_files_cb(client: Client, query: CallbackQuery):
    ident, keyword = query.data.split("#")
    await query.message.edit_text(f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
    files, total = await get_bad_files(keyword)
    if total == 0:
        return await query.message.edit_text(f"<b>No files found for query {keyword}. Nothing to delete.</b>")
    await query.message.edit_text(f"<b>Found {total} files for your query {keyword} !\n\nFile deletion process will start in 5 seconds !</b>")
    await asyncio.sleep(5)
    deleted = 0
    async with lock:
        try:
            for file_doc in files:
                file_ids = file_doc.file_id
                file_name = file_doc.file_name
                result = await Media.collection.delete_one({'_id': file_ids})
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

async def handle_open_set_group_cb(client: Client, query: CallbackQuery):
    ident, grp_id = query.data.split("#")
    userid = query.from_user.id if query.from_user else None
    st = await client.get_chat_member(grp_id, userid)
    if not (
            st.status == enums.ChatMemberStatus.ADMINISTRATOR
            or st.status == enums.ChatMemberStatus.OWNER
            or str(userid) in info.ADMINS
    ):
        await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)
        return
    
    title = query.message.chat.title 
    settings = await get_settings(grp_id) 
    
    buttons = [
        [
            InlineKeyboardButton('𝖥𝗂𝗅𝗍𝖾𝗋 𝖡𝗎𝗍𝗍𝗈𝗇', callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
            InlineKeyboardButton('𝖲𝗂𝗇𝗀𝗅𝖾 𝖡𝗎𝗍𝗍𝗈𝗇' if settings["button"] else '𝖣𝗈𝗎𝖻𝗅𝖾', callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖥𝗂𝗅𝖾 𝖲𝖾𝗇𝖽 𝖬𝗈𝖽𝖾', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
            InlineKeyboardButton('𝖬𝖺𝗇𝗎𝖺𝗅 𝖲𝗍𝖺𝗋𝗍' if settings["botpm"] else '𝖠𝗎𝗍𝗈 𝖲𝖾𝗇𝖽', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖯𝗋𝗈𝗍𝖾𝖼𝗍 𝖢𝗈𝗇𝗍𝖾𝗇𝗍', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if settings["file_secure"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖨𝖬𝖣𝖻', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if settings["imdb"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖲𝗉𝖾𝗅𝗅 𝖢𝗁𝖾𝖼𝗄', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if settings["spell_check"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖬𝖾𝗌𝗌𝖺𝗀𝖾', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if settings["welcome"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖠𝗎𝗍𝗈 𝖣𝖾𝗅𝖾𝗍𝖾', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
            InlineKeyboardButton('5 𝖬𝗂𝗇' if settings["auto_delete"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖠𝗎𝗍𝗈-𝖥𝗂𝗅𝗍𝖾𝗋', callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if settings["auto_ffilter"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖬𝖺𝗑 𝖡𝗎𝗍𝗍𝗈𝗇𝗌', callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
            InlineKeyboardButton('10' if settings["max_btn"] else f'{info.MAX_B_TN}', callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.message.edit_text(
        text=f"<b>𝖢𝗁𝖺𝗇𝗀𝖾 𝖸𝗈𝗎𝗋 𝖲𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝖥𝗈𝗋 {title} 𝖠𝗌 𝖸𝗈𝗎𝗋 𝖶𝗂𝗌𝗁</b>",
        reply_markup=reply_markup, 
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML
    )
    await query.answer('Support Us By Sharing The Channel And Bot')    

async def handle_open_set_pm_cb(client: Client, query: CallbackQuery):
    ident, grp_id = query.data.split("#")
    userid = query.from_user.id if query.from_user else None
    st = await client.get_chat_member(grp_id, userid)
    if not (
            st.status == enums.ChatMemberStatus.ADMINISTRATOR
            and st.status == enums.ChatMemberStatus.OWNER
            and str(userid) not in info.ADMINS
    ):
        await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)
        return
    
    title = query.message.chat.title
    settings = await get_settings(grp_id) 
    
    btn2 = [[
             InlineKeyboardButton("➡ 𝖮𝗉𝖾𝗇 𝗂𝗇 𝖯𝖬 ➡", url=f"t.me/{temp.U_NAME}?start=settings_{grp_id}") 
           ]]
    reply_markup_group_msg = InlineKeyboardMarkup(btn2)
    await query.message.edit_text(f"<b>𝖸𝗈𝗎𝗋 𝗌𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝗆𝖾𝗇𝗎 𝖿𝗈𝗋 {title} 𝗁𝖺𝗌 𝖻𝖾𝖾𝗇 𝗌𝖾𝗇𝗍 𝗍𝗈 𝗒𝗈𝗎𝗋 𝖯𝖬</b>", reply_markup=reply_markup_group_msg) 
    
    buttons_pm = [
        [
            InlineKeyboardButton('𝖥𝗂𝗅𝗍𝖾𝗋 𝖡𝗎𝗍𝗍𝗈𝗇', callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
            InlineKeyboardButton('𝖲𝗂𝗇𝗀𝗅𝖾 𝖡𝗎𝗍𝗍𝗈𝗇' if settings["button"] else '𝖣𝗈𝗎𝖻𝗅𝖾', callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖥𝗂𝗅𝖾 𝖲𝖾𝗇𝖽 𝖬𝗈𝖽𝖾', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
            InlineKeyboardButton('𝖬𝖺𝗇𝗎𝖺𝗅 𝖲𝗍𝖺𝗋𝗍' if settings["botpm"] else '𝖠𝗎𝗍𝗈 𝖲𝖾𝗇𝖽', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖯𝗋𝗈𝗍𝖾𝖼𝗍 𝖢𝗈𝗇𝗍𝖾𝗇𝗍', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if settings["file_secure"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖨𝖬𝖣𝖻', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if settings["imdb"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖲𝗉𝖾𝗅𝗅 𝖢𝗁𝖾𝖼𝗄', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if settings["spell_check"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖬𝖾𝗌𝗌𝖺𝗀𝖾', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if settings["welcome"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖠𝗎𝗍𝗈 𝖣𝖾𝗅𝖾𝗍𝖾', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
            InlineKeyboardButton('5 𝖬𝗂𝗇' if settings["auto_delete"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖠𝗎𝗍𝗈-𝖥𝗂𝗅𝗍𝖾𝗋', callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ 𝖮𝗇' if settings["auto_ffilter"] else '❌ 𝖮𝖿𝖿', callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('𝖬𝖺𝗑 𝖡𝗎𝗍𝗍𝗈𝗇𝗌', callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
            InlineKeyboardButton('10' if settings["max_btn"] else f'{info.MAX_B_TN}', callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
        ]
    ]
    reply_markup_pm = InlineKeyboardMarkup(buttons_pm)
    await client.send_message(
        chat_id=userid,
        text=f"<b>𝖢𝗁𝖺𝗇𝗀𝖾 𝖸𝗈𝗎𝗋 𝖲𝖾𝗍𝗍𝗂𝗇𝗀𝗌 𝖥𝗈𝗋 {title} 𝖠𝗌 𝖸𝗈𝗎𝗋 𝖶𝗂𝗌𝗁</b>",
        reply_markup=reply_markup_pm,
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML,
    )
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_show_option_cb(client: Client, query: CallbackQuery):
    ident, from_user = query.data.split("#")
    btn = [[
            InlineKeyboardButton("⚠ Unavailable ⚠", callback_data=f"unavailable#{from_user}"),
            InlineKeyboardButton("✅ 𝖴𝗉𝗅𝗈𝖺𝖽𝖾𝖽 ✅", callback_data=f"uploaded#{from_user}")
         ],[
            InlineKeyboardButton("🔰 𝖠𝗅𝗋𝖾𝖺𝖽𝗒 𝖠𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 🔰", callback_data=f"already_available#{from_user}")
          ]]
    if query.from_user.id in info.ADMINS:
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_reply_markup(reply_markup)
        await query.answer("𝖧𝖾𝗋𝖾 𝖺𝗋𝖾 𝗍𝗁𝖾 𝗈𝗉𝗍𝗂𝗈𝗇𝗌")
    else:
        await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)
   
async def handle_unavailable_cb(client: Client, query: CallbackQuery):
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
        await query.message.edit_text(f"<b><strike>{content}</strike></b>", reply_markup=reply_markup) 
        await query.answer("𝖲𝖾𝗍 𝗍𝗈 𝖴𝗇𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾")
        try:
            await client.send_message(chat_id=int(from_user), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖲𝗈𝗋𝗋𝗒 𝗒𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝗎𝗇𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾. 𝖲𝗈 𝗆𝗈𝖽𝖾𝗋𝖺𝗍𝗈𝗋𝗌 𝖼𝖺𝗇'𝗍 𝖺𝖽𝖽 𝗂𝗍 !</b>", reply_markup=InlineKeyboardMarkup(btn2))
        except UserIsBlocked:
            await client.send_message(chat_id=int(info.SUPPORT_CHAT_ID), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖲𝗈𝗋𝗋𝗒 𝗒𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝗎𝗇𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾. 𝖲𝗈 𝗆𝗈𝖽𝖾𝗋𝖺𝗍𝗈𝗋𝗌 𝖼𝖺𝗇'𝗍 𝖺𝖽𝖽 𝗂𝗍 !\n\n📝 𝖭𝗈𝗍𝖾: 𝖳𝗁𝗂𝗌 𝗆𝖾𝗌𝗌𝖺𝗀𝖾 𝗂𝗌 𝗌𝖾𝗇𝗍 𝗂𝗇 𝖦𝗋𝗈𝗎𝗉 𝖻𝖾𝖼𝖺𝗎𝗌𝖾 𝗒𝗈𝗎 𝗁𝖺𝗏𝖾 𝖡𝗅𝗈𝖼𝗄𝖾𝖽 𝗍𝗁𝖾 𝖡𝗈𝗍 ! 𝖴𝗇𝖻𝗅𝗈𝖼𝗄 𝗍𝗁𝖾 𝖡𝗈𝗍 !</b>", reply_markup=InlineKeyboardMarkup(btn2))
    else:
        await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)
    
async def handle_uploaded_cb(client: Client, query: CallbackQuery):
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
        await query.message.edit_text(f"<b><strike>{content}</strike></b>", reply_markup=reply_markup)
        await query.answer("𝖲𝖾𝗍 𝗍𝗈 𝖴𝗉𝗅𝗈𝖺𝖽𝖾𝖽")
        try:
            await client.send_message(chat_id=int(from_user), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗁𝖺𝗌 𝖻𝖾𝖾𝗇 𝗎𝗉𝗅𝗈𝖺𝖽𝖾𝖽 𝖻𝗒 𝗆𝗈𝖽𝖾𝗋𝖺𝗍𝗈𝗋. 𝖪𝗂𝗇𝖽𝗅𝗒 𝗌𝖾𝖺𝗋𝖼𝗁 𝖺𝗀𝖺𝗂𝗇 @kdramasmirrorchat !</b>", reply_markup=InlineKeyboardMarkup(btn2))
        except UserIsBlocked:
            await client.send_message(chat_id=int(info.SUPPORT_CHAT_ID), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗁𝖺𝗌 𝖻𝖾𝖾𝗇 𝗎𝗉𝗅𝗈𝖺𝖽𝖾𝖽 𝖻𝗒 𝗆𝗈𝖽𝖾𝗋𝖺𝗍𝗈𝗋. 𝖪𝗂𝗇𝖽𝗅𝗒 𝗌𝖾𝖺𝗋𝖼𝗁 𝖺𝗀𝖺𝗂𝗇 @kdramasmirrorchat !\n\n📝 𝖭𝗈𝗍𝖾: 𝖳𝗁𝗂𝗌 𝗆𝖾𝗌𝗌𝖺𝗀𝖾 𝗂𝗌 𝗌𝖾𝗇𝗍 𝗂𝗇 𝖦𝗋𝗈𝗎𝗉 𝖻𝖾𝖼𝖺𝗎𝗌𝖾 𝗒𝗈𝗎 𝗁𝖺𝗏𝖾 𝖡𝗅𝗈𝖼𝗄𝖾𝖽 𝗍𝗁𝖾 𝖡𝗈𝗍 ! 𝖴𝗇𝖻𝗅𝗈𝖼𝗄 𝗍𝗁𝖾 𝖡𝗈𝗍 !</b>", reply_markup=InlineKeyboardMarkup(btn2))
    else:
        await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)

async def handle_already_available_cb(client: Client, query: CallbackQuery):
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
        await query.message.edit_text(f"<b><strike>{content}</strike></b>", reply_markup=reply_markup)
        await query.answer("𝖲𝖾𝗍 𝗍𝗈 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 !")
        try:
            await client.send_message(chat_id=int(from_user), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 𝗈𝗇 𝖡𝗈𝗍. 𝖪𝗂𝗇𝖽𝗅𝗒 𝗌𝖾𝖺𝗋𝖼𝗁 𝖺𝗀𝖺𝗂𝗇 @kdramasmirrorchat !</b>", reply_markup=InlineKeyboardMarkup(btn2))
        except UserIsBlocked:
            await client.send_message(chat_id=int(info.SUPPORT_CHAT_ID), text=f"<b>𝖧𝖾𝗒 {user.mention}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 𝗈𝗇 𝖡𝗈𝗍. 𝖪𝗂𝗇𝖽𝗅𝗒 𝗌𝖾𝖺𝗋𝖼𝗁 𝖺𝗀𝖺𝗂𝗇 @kdramasmirrorchat !\n\n📝 𝖭𝗈𝗍𝖾: 𝖳𝗁𝗂𝗌 𝗆𝖾𝗌𝗌𝖺𝗀𝖾 𝗂𝗌 𝗌𝖾𝗇𝗍 𝗂𝗇 𝖦𝗋𝗈𝗎𝗉 𝖻𝖾𝖼𝖺𝗎𝗌𝖾 𝗒𝗈𝗎 𝗁𝖺𝗏𝖾 𝖡𝗅𝗈𝖼𝗄𝖾𝖽 𝗍𝗁𝖾 𝖡𝗈𝗍 ! 𝖴𝗇𝖻𝗅𝗈𝖼𝗄 𝗍𝗁𝖾 𝖡𝗈𝗍 !</b>", reply_markup=InlineKeyboardMarkup(btn2))
    else:
        await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)

async def handle_alalert_cb(client: Client, query: CallbackQuery):
    ident, from_user = query.data.split("#")
    if int(query.from_user.id) == int(from_user):
        user = await client.get_users(from_user)
        await query.answer(f"𝖧𝖾𝗒 {user.first_name}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 !", show_alert=True)
    else:
        await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)
    
async def handle_upalert_cb(client: Client, query: CallbackQuery):
    ident, from_user = query.data.split("#")
    if int(query.from_user.id) == int(from_user):
        user = await client.get_users(from_user)
        await query.answer(f"𝖧𝖾𝗒 {user.first_name}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝗎𝗉𝗅𝗈𝖺𝖽𝖾𝖽 !", show_alert=True)
    else:
        await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)
    
async def handle_unalert_cb(client: Client, query: CallbackQuery):
    ident, from_user = query.data.split("#")
    if int(query.from_user.id) == int(from_user):
        user = await client.get_users(from_user)
        await query.answer(f"𝖧𝖾𝗒 {user.first_name}, 𝖸𝗈𝗎𝗋 𝗋𝖾𝗊𝗎𝖾𝗌𝗍 𝗂𝗌 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝗎𝗇𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 !", show_alert=True)
    else:
        await query.answer("𝖸𝗈𝗎 𝖽𝗈𝗇'𝗍 𝗁𝖺𝗏𝖾 𝗌𝗎𝖿𝖿𝗂𝖼𝗂𝖾𝗇𝗍 𝗋𝗂𝗀𝗁𝗍𝗌 𝗍𝗈 𝖽𝗈 𝗍𝗁𝗂𝗌 !", show_alert=True)

async def handle_rkbtn_cb(client: Client, query: CallbackQuery):
    await query.answer("𝖧𝖾𝗒 𝖡𝗋𝗈 😍\n\n🎯 𝖢𝗅𝗂𝖼𝗄 𝖮𝗇 𝖳𝗁𝖾 𝖡𝗎𝗍𝗍𝗈𝗇 𝖻𝖾𝗅𝗈𝗐 𝖳𝗁𝖾 𝖥𝗂𝗅𝖾𝗌 𝖸𝗈𝗎 𝖶𝖺𝗇𝗍 𝖠𝗇𝖽 𝖲𝗍𝖺𝗋𝗍 𝖳𝗁𝖾 𝖡𝗈𝗍 ⬇️", True)

async def handle_info_cb(client: Client, query: CallbackQuery):
    await query.answer("𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝘀 𝗙𝗼𝗿𝗺𝗮𝘁𝘀\n\n• Hyper Knife s01e08\n• Our Blooming Youth\n• The Vanished 2018 1080p\n• The Vanished 2018\n• goblin e01\n\n‼️𝗗𝗼𝗻𝘁 𝗮𝗱𝗱 𝘄𝗼𝗿𝗱𝘀 & 𝘀𝘆𝗺𝗯𝗼𝗹𝘀  , . - 𝗹𝗶𝗸𝗲 send link movie series 𝗲𝘁𝗰‼️", True)

async def handle_tips_cb(client: Client, query: CallbackQuery):
    await query.answer("𝖳𝗁𝗂𝗌 𝖬𝖾𝗌𝗌𝖺𝗀𝖾 𝖶𝗂𝗅𝗅 𝖡𝖾 𝖣𝖾𝗅𝖾𝗍𝖾𝖽 𝖠𝖿𝗍𝖾𝗋 5 𝖬𝗂𝗇𝗎𝗍𝖾𝗌 𝗍𝗈 𝖯𝗋𝖾𝗏𝖾𝗇𝗍 𝖢𝗈𝗉𝗒𝗋𝗂𝗀𝗁𝗍 !\n\n𝖳𝗁𝖺𝗇𝗄 𝖸𝗈𝗎 𝖥𝗈𝗋 𝖴𝗌𝗂𝗇𝗀 𝖬𝖾 😊\n\n\n𝖯𝗈𝗐𝖾𝗋𝖾𝖽 𝖡𝗒 KDramaWorld", True)

async def handle_start_cb(client: Client, query: CallbackQuery):
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

async def handle_filters_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_global_filters_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_help_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_about_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_source_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_manuel_filter_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_button_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_autofilter_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_coct_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_extra_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_store_file_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_admin_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_stats_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_rfrsh_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')

async def handle_owner_info_cb(client: Client, query: CallbackQuery):
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
    await query.answer('Support Us By Sharing The Channel And Bot')
