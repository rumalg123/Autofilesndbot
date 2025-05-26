# DramaShipbot - Advanced Telegram AutoFilter Bot

<p align="center">
  <img src="https://te.legra.ph/file/85c75538ff6fb565c821a.jpg" alt="DramaShip Bot Logo" width="200">
</p>

<p align="center">
  ![Typing SVG](https://readme-typing-svg.herokuapp.com/?lines=𝚆𝙴𝙻𝙲𝙾𝙼𝙴+𝚃𝙾+DramaShip+𝙱𝙾𝚃+!;𝙰+𝙿𝙾𝚆𝙴𝚁𝙵𝚄𝙻+𝙰𝚄𝚃𝙾𝙵𝙸𝙻𝚃𝙴𝚁+𝙱𝙾𝚃+!;𝙲𝚁𝙴𝙰𝚃𝙴𝙳+𝙱𝚈+KDramaWorld+Team!)
</p>

<p align="center">
  <a href="https://github.com/KDramaWorld/DramaShip"><img src="https://img.shields.io/github/stars/KDramaWorld/DramaShip?color=yellow&logo=github&logoColor=yellow&style=for-the-badge" alt="Stars" /></a>
  <a href="https://github.com/KDramaWorld/DramaShip/network/members"> <img src="https://img.shields.io/github/forks/KDramaWorld/DramaShip?color=yellow&logo=github&logoColor=yellow&style=for-the-badge" /></a>
  <a href="https://github.com/KDramaWorld/DramaShip/blob/main/LICENSE"> <img src="https://img.shields.io/badge/License-AGPL%20v3.0-blue?style=for-the-badge" alt="License" /> </a>
  <a href="https://www.python.org/"> <img src="https://img.shields.io/badge/Written%20in-Python-blueviolet?style=for-the-badge&logo=python" alt="Python" /> </a>
  <a href="https://pypi.org/project/Pyrogram/"> <img src="https://img.shields.io/pypi/v/pyrogram?color=blueviolet&label=pyrogram&logo=python&logoColor=white&style=for-the-badge" /></a>
</p>

DramaShip is a powerful and feature-rich Telegram bot designed for automatically filtering files in groups and channels. It helps manage large collections of media by providing easy search and access capabilities.

## Key Features

*   **Advanced File Indexing:** Capable of indexing files, including those larger than 2GB.
*   **Force Subscription:** Can require users to subscribe to specified channels before using the bot.
*   **Automatic and Manual Filtering:** Supports both automatic filtering based on user messages and manual filter definitions.
    *   Global filters applicable across all connected groups.
    *   Per-chat filters.
*   **Premium User Management:**
    *   Configurable premium duration (`PREMIUM_DURATION_DAYS`).
    *   Premium status expiration with automatic removal of expired premium users.
    *   Admin logging for premium additions and removals.
    *   `/premiumusers` command to list premium users, their count, and expiration dates.
*   **Sophisticated User Data Handling:**
    *   Stores and updates user `first_name` and `username` upon interaction.
    *   Handles unavailable user data gracefully using default values.
*   **Enhanced "No Results Found" Logic:**
    *   Detailed logging of "no results found" events to the `LOG_CHANNEL`.
    *   User-facing "no results" messages can be toggled via the `NO_RESULTS_MSG` environment variable.
*   **Configurable Auto-Delete:**
    *   `AUTO_DELETE` setting for messages sent by the bot.
    *   `AUTO_DELETE_MESSAGE_TIME` environment variable to control the deletion delay (default: 600 seconds).
*   **IMDb Integration:** Fetches movie/series information from IMDb.
*   **Spelling Check:** Suggests alternatives for misspelled queries.
*   **File Store Integration:** Create shareable links for files stored in designated channels.
*   **Admin Tools:**
    *   Comprehensive admin commands for bot management.
    *   User and group broadcast capabilities.
    *   Ban/unban users, disable/enable chats.
    *   Notification to admin if `/addpremium` is used for a user not yet in the database.
*   **User Interaction & Info:**
    *   Inline search functionality.
    *   Display of user IDs and information.
    *   Bot stats (total users, chats, DB size).
*   **Customization:**
    *   Customizable start message, file captions, and IMDB templates.
    *   Option to protect content (forward restriction).
    *   Single or double button layout for filter results.
*   **Code Quality:** Recent refactoring efforts have improved code maintainability and efficiency.

## Required Variables

*   `BOT_TOKEN`: Your bot's Telegram API token from [@BotFather](https://telegram.dog/BotFather).
*   `API_ID`: Your API ID obtained from [my.telegram.org/apps](https://my.telegram.org/apps).
*   `API_HASH`: Your API Hash obtained from [my.telegram.org/apps](https://my.telegram.org/apps).
*   `CHANNELS`: Username or ID of channels/groups for the bot to operate in. Separate multiple IDs with a space.
*   `ADMINS`: Username or ID of bot admins. Separate multiple IDs with a space. The first admin in the list is considered the bot owner.
*   `DATABASE_URI`: MongoDB connection URI.
*   `DATABASE_NAME`: Name of your database in MongoDB.
*   `LOG_CHANNEL`: ID of a Telegram channel where the bot will log its activities (e.g., new users, errors, admin actions). Ensure the bot is an admin in this channel.

## Optional Variables

*   `PICS`: A space-separated list of Telegraph image links for the bot's start message.
*   `FILE_STORE_CHANNEL`: Space-separated list of channel IDs from which file store links can be generated.
*   `SESSION`: Custom session name for Pyrogram (default: `Media_search`).
*   `UPSTREAM_REPO`: For deploying/updating using a custom Git repository.
*   `UPSTREAM_BRANCH`: Branch for the `UPSTREAM_REPO`.
*   `CACHE_TIME`: Duration in seconds for caching inline query results (default: `300`).
*   `PREMIUM_DURATION_DAYS`: Duration in days for a premium subscription (default: `30`).
*   `NON_PREMIUM_DAILY_LIMIT`: Daily file retrieval limit for non-premium users (default: `20`).
*   `AUTO_DELETE_MESSAGE_TIME`: Time in seconds after which bot's messages (like filter results or welcome messages if `AUTO_DELETE` is enabled) are deleted (default: `600`).
*   `NO_RESULTS_MSG`: Set to `True` or `False`. If `True` (default), the bot will send a message when no results are found for a query. If `False`, it will not send a message (but will still log it).
*   `SUPPORT_CHAT_ID`: ID of the support chat for logging certain user-specific errors if direct PM fails.
*   `MAX_B_TN`: Maximum number of buttons to show per row for file results (default: `10`, but also influenced by `MAX_BTN`).
*   `MAX_BTN`: Boolean (`True`/`False`) to enable a fixed max button layout (default: `True`, typically 10 buttons).
*   `P_TTI_SHOW_OFF`: If `True`, redirects users to PM for `/start` instead of sending files directly in groups (default: `False`).
*   `IMDB`: Enable/disable IMDb details in search results (default: `True`).
*   `AUTO_FFILTER`: Enable/disable automatic file filtering in groups (default: `True`).
*   `AUTO_DELETE`: Enable/disable auto-deletion of bot's messages after a set time (default: `True`). See `AUTO_DELETE_MESSAGE_TIME`.
*   `SINGLE_BUTTON`: Use single or double buttons for file results (default: `True` for single).
*   `CUSTOM_FILE_CAPTION`: Custom template for file captions. Placeholders: `{file_name}`, `{file_size}`, `{file_caption}`.
*   `BATCH_FILE_CAPTION`: Custom template for batch file captions. Placeholders: `{file_name}`, `{file_size}`, `{file_caption}`.
*   `IMDB_TEMPLATE`: Template for IMDb information display. Many placeholders available (see code).
*   `LONG_IMDB_DESCRIPTION`: Use longer plot outlines for IMDb info (default: `False`).
*   `SPELL_CHECK_REPLY`: Enable/disable spelling suggestions for queries (default: `True`).
*   `MELCOW_NEW_USERS`: Enable/disable welcome messages for new users (default: `True`).
*   `PROTECT_CONTENT`: Enable/disable forward protection on sent files (default: `False`).
*   For more variables, please refer to `info.py`.

## Deployment Methods
<details><summary>Deploy To Heroku</summary>
<p>
<br>
<a href="https://heroku.com/deploy?template=https://github.com/KDramaWorld/DramaShip">
  <img src="https://www.herokucdn.com/deploy/button.svg" alt="Deploy To Heroku">
</a>
</p>
</details>

<details><summary>Deploy To Koyeb</summary>
<b>The fastest way to deploy the application is to click the Deploy to Koyeb button below.</b>
<br>
<a href="https://app.koyeb.com/deploy?type=git&repository=https://github.com/KDramaWorld/DramaShip&branch=main&name=dramashipbot">
  <img alt="Deploy to Koyeb" src="https://www.koyeb.com/static/images/deploy/button.svg">
</a>
</details>

<details><summary>Deploy on Railway</summary>
<a href="https://railway.app/new/template/y0ryFO"> <!-- Ensure this template link is correct for your repo -->
<img src="https://railway.app/button.svg" alt="Deploy on Railway">
</a>
</details>

<details><summary>Deploy To VPS</summary>
<p>
<pre>
# Clone the repository
git clone https://github.com/KDramaWorld/DramaShip
cd DramaShip

# Install dependencies
pip3 install -U -r requirements.txt

# Create and edit your configuration file (e.g., .env)
cp sample.env .env
nano .env # Or use your preferred editor to fill in the variables

# Run the bot
python3 bot.py
</pre>
</p>
</details>


## Commands

A brief overview of some common commands:

*   `/start`: Initiates interaction with the bot.
*   `/filter <keyword> <content>`: Adds a manual filter for the given keyword.
*   `/filters`: Views all active filters in a chat.
*   `/del <keyword>`: Deletes a specific filter.
*   `/delall`: Deletes all filters in a chat (owner/bot admin only).
*   `/gfilter <keyword> <content>`: Adds a global filter (bot admin only).
*   `/viewgfilters`: Lists all global filters (bot admin only).
*   `/delg <keyword>`: Deletes a global filter (bot admin only).
*   `/delallg`: Deletes all global filters (bot admin only).
*   `/connect`: Connects the bot to a group from PM for settings management.
*   `/disconnect`: Disconnects from all groups for settings management.
*   `/settings`: Opens the settings panel for the connected group (or current group if used in a group).
*   `/imdb <movie_name>`: Fetches IMDb information for a movie/series.
*   `/broadcast <message>`: Broadcasts a message to all users (bot admin only).
*   `/group_broadcast <message>`: Broadcasts a message to all groups (bot admin only).
*   `/addpremium <user_id>`: Grants premium status to a user (bot owner only).
*   `/removepremium <user_id>`: Revokes premium status from a user (bot owner only).
*   `/premiumusers`: Lists all premium users with their expiration dates (bot admin only).
*   `/stats`: Shows bot statistics (total files, users, chats, DB size).
*   `/users`: Lists all users in the database (bot admin only).
*   `/chats`: Lists all chats the bot is in (bot admin only).
*   `/ban <user_id> [reason]`: Bans a user from using the bot (bot admin only).
*   `/unban <user_id>`: Unbans a user (bot admin only).
*   `/leave <chat_id>`: Makes the bot leave a specific chat (bot admin only).
*   `/disable <chat_id> [reason]`: Disables the bot in a specific chat (bot admin only).
*   `/enable <chat_id>`: Re-enables the bot in a previously disabled chat (bot admin only).
*   `/logs`: Sends the bot's log file (bot admin only).
*   `/restart`: Restarts the bot and attempts to pull updates from Git (bot admin only, private chat).

*For more detailed command usage, refer to the bot's `/help` command or source code.*

## Thanks To
 - EvaMaria Devs For Their AutoFIlterBot
 - Everyone who has contributed to the Pyrogram and broader Python/Telegram bot community.

## Note 🏷️
 - **Forking and Credits:** Please fork this repository to make your own changes. If you use significant portions of this code, kindly give appropriate credit to the original developers.
 - **Bugs and Errors:** If you find any bugs or errors, please report them by opening an issue on GitHub or contacting the support group.

## Telegram Support
*   **Support Group:** [@DramaShip_Support](https://t.me/DramaShip_Support) (Example, replace with actual link)
*   **Updates Channel:** [@DramaShip_Updates](https://t.me/DramaShip_Updates) (Example, replace with actual link)

## Disclaimer
[![GNU Affero General Public License 3.0](https://www.gnu.org/graphics/agplv3-155x51.png)](https://www.gnu.org/licenses/agpl-3.0.en.html#header)    
This project is licensed under the [GNU Affero General Public License v3.0.](https://github.com/KDramaWorld/DramaShip/blob/main/LICENSE)
Selling the source code of this bot is strictly prohibited.
