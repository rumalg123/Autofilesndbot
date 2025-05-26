import openai

import logging # Added
import info # Added

logger = logging.getLogger(__name__) # Added

async def ai(query):
    openai.api_key = " " #Your openai api key - MAKE SURE THIS IS SET VIA ENV OR CONFIG, NOT HARDCODED
    if not openai.api_key or openai.api_key == " ":
        logger.error("OpenAI API key is not set or is invalid.")
        return None # Indicate failure if API key is missing

    try:
        response = openai.Completion.create(engine="text-davinci-002", prompt=query, max_tokens=100, n=1, stop=None, temperature=0.9, timeout=10) # Increased timeout
        if response.choices and response.choices[0].text:
            return response.choices[0].text.strip()
        else:
            logger.warning(f"OpenAI response for query '{query}' was empty or had no choices.")
            return None # Indicate no meaningful content
    except openai.error.OpenAIError as e: # Catch specific OpenAI errors
        logger.error(f"OpenAI API error for query '{query}': {e}")
        raise # Re-raise to be caught by ask_ai
    except Exception as e: # Catch other potential errors like network issues
        logger.error(f"Generic error during OpenAI call for query '{query}': {e}")
        raise # Re-raise
     
async def ask_ai(client, m, message): # 'client' is the Pyrogram Client, 'm' is the status message to edit, 'message' is the user's original message
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    question = ""

    try:
        question = message.text.split(" ", 1)[1]
        response_text = await ai(question)

        if response_text and len(response_text) > 5: # Assuming a response shorter than 5 chars is "no meaningful content"
            await m.edit(f"{response_text}")
        else: # No meaningful content or ai() returned None
            no_meaningful_content_msg = "Sorry, I couldn't find a meaningful answer for that."
            if info.NO_RESULTS_MSG:
                await m.edit(no_meaningful_content_msg)
            else:
                await m.edit("No answer found.") # Shorter message if NO_RESULTS_MSG is False

            # Logging "No Meaningful Content"
            try:
                log_text = (
                    f"⚠️ No Meaningful Content (OpenAI) ⚠️\n"
                    f"User ID: {user_id} ({user_mention})\n"
                    f"Query: {question}"
                )
                if info.LOG_CHANNEL:
                    await client.send_message(chat_id=info.LOG_CHANNEL, text=log_text)
                else:
                    logger.warning("LOG_CHANNEL not set. Cannot log 'No Meaningful Content' for OpenAI.")
            except Exception as log_e:
                logger.error(f"Failed to log 'No Meaningful Content' (OpenAI) to LOG_CHANNEL: {log_e}", exc_info=True)

    except Exception as e:
        # Handle other errors (including those re-raised from ai())
        error_message_user = f"An error occurred while processing your request with the AI: {type(e).__name__}"
        if info.NO_RESULTS_MSG: # Check if we should send detailed error or generic
             await m.edit(error_message_user + f"\nDetails: {str(e)[:100]}") # Show limited error details
        else:
            await m.edit("An error occurred with the AI request.")

        # Logging the error
        try:
            log_text = (
                f"❌ OpenAI API Error ❌\n"
                f"User ID: {user_id} ({user_mention})\n"
                f"Query: {question if question else 'N/A (error before query extraction)'}\n"
                f"Error: {type(e).__name__}: {e}"
            )
            if info.LOG_CHANNEL:
                await client.send_message(chat_id=info.LOG_CHANNEL, text=log_text)
            else:
                logger.warning("LOG_CHANNEL not set. Cannot log OpenAI API Error.")
        except Exception as log_e:
            logger.error(f"Failed to log OpenAI API Error to LOG_CHANNEL: {log_e}", exc_info=True)
