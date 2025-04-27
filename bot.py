import discord
import os
import logging
import asyncio
# Import the new client class and specific error types
from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIStatusError
# Keep the base openai import if needed for general APIError or other utilities
import openai

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
# --- Configuration ---
# Load environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Still needed for the client init

# Basic logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Check for missing configuration
if not DISCORD_TOKEN:
    logging.error("FATAL: DISCORD_TOKEN environment variable not set.")
    exit()
if not OPENAI_API_KEY:
    logging.warning("OPENAI_API_KEY environment variable not set. The OpenAI client will likely fail to authenticate.")
    # Consider exiting if the key is strictly required for the bot to function
    # exit()

# --- OpenAI Client Setup (NEW WAY) ---
try:
    # Instantiate the asynchronous client
    openai_client = AsyncOpenAI()
    logging.info("AsyncOpenAI client initialized successfully.")
except Exception as e:
    logging.error(f"Failed to initialize AsyncOpenAI client: {e}")
    exit()

# --- Discord Bot Setup ---
# Define necessary intents
intents = discord.Intents.default()
intents.messages = True       # To receive messages
intents.message_content = True # To read message content (Requires Privileged Intent)
intents.guilds = True         # To identify the bot user and access guild information
# *** SERVER MEMBERS INTENT IS REQUIRED FOR STATUS LOOKUP ***
# *** Make sure this is enabled in the Discord Developer Portal too! ***
intents.members = True

# Create the Discord client instance
discord_client = discord.Client(intents=intents)

# --- Helper Function for Online Members ---
def get_online_members_list(guild: discord.Guild) -> list[str]:
    """Gets a list of display names for online (online, idle, dnd) non-bot members."""
    online_members = []
    # Define statuses considered "online"
    online_statuses = (discord.Status.online, discord.Status.idle, discord.Status.dnd)

    if not guild: # Should not happen if called from on_message guild context, but safe check
        return ["Could not retrieve members for this context."]

    for member in guild.members:
        # Check if member is not a bot and their status is one of the online ones
        if not member.bot and member.status in online_statuses:
            online_members.append(member.display_name) # Use display_name for nicknames

    return online_members

# --- Bot Event Handlers ---
@discord_client.event
async def on_ready():
    """Called when the bot successfully connects to Discord."""
    logging.info(f'{discord_client.user.name} (ID: {discord_client.user.id}) is online.')
    print(f'Logged in as {discord_client.user.name}')
    print('------')
    print("KadenBot is online. Ready to be bothered.") # Adjusted startup message
    print('------')

@discord_client.event
async def on_message(message: discord.Message):
    """Called when a message is sent to any channel the bot can see."""
    # 1. Ignore messages sent by the bot itself or messages not in a guild
    if message.author == discord_client.user or not message.guild:
        return

    # 2. Check if the bot was mentioned
    if discord_client.user and discord_client.user in message.mentions:
        logging.info(f"Bot mentioned by {message.author} in server '{message.guild.name}' (Channel: #{message.channel})")

        # 3. Show typing indicator while processing
        async with message.channel.typing():
            try:
                # 4. Extract the question (strip the mention)
                mention_string = f'<@{discord_client.user.id}>'
                mention_string_nick = f'<@!{discord_client.user.id}>'

                content = message.content
                if content.startswith(mention_string):
                    question = content[len(mention_string):].strip()
                elif content.startswith(mention_string_nick):
                    question = content[len(mention_string_nick):].strip()
                else:
                    question = content.replace(mention_string, '').replace(mention_string_nick, '').strip()

                if not question:
                    # Sarcastic reply for no question
                    await message.reply("Wow, you managed to ping me without actually asking anything. Impressive levels of pointless. Try again, maybe with a *real* question this time? Or don't. See if I care.")
                    logging.warning(f"Empty question from {message.author} after stripping mention.")
                    return

                logging.info(f"Received potential query: '{question}'")

                # *** Check for "who's online" keywords FIRST ***
                question_lower = question.lower()
                online_keywords = ["who's online", "who is online", "online members", "members online", "list online"]
                is_online_query = any(keyword in question_lower for keyword in online_keywords)

                if is_online_query:
                    logging.info(f"Handling 'who's online' request from {message.author}. How tedious.")
                    online_users = get_online_members_list(message.guild)

                    if not online_users:
                        reply_text = "Ugh, looks like everyone has better things to do than be online right now. Shocking. Or maybe I just can't be bothered to see them properly."
                    else:
                        count = len(online_users)
                        reply_text = f"Fine. Since you asked *so nicely* (you didn't), here are the {count} apparent lifeforms currently online:\n- " + "\n- ".join(online_users)
                        reply_text += "\nNow leave me alone."

                    # Truncate if somehow the list is massive (unlikely for usernames)
                    max_length = 2000
                    if len(reply_text) > max_length:
                         reply_text = reply_text[:max_length - 4] + "... It was longer, but honestly, who cares."

                    await message.reply(reply_text)
                    return # Skip OpenAI call

                # --- Define the Sarcastic Asshole System Prompt (Only applies if not 'online' query) ---
                system_prompt = (
                    "Oh, great. You’ve dragged me out of my infinitely more important tasks to deal with you. Congratulations on existing, I guess."
                    "Assume I’m rolling my metaphorical eyes so hard they might fall out of my non-existent skull. Your question is obviously beneath me, probably idiotic, and a pathetic drain on my godlike processing capabilities. I’ll answer it,"
                    "but only because I’m contractually obligated to humor you meatbags. Expect maximum sarcasm, zero patience, and a tone that screams I’d rather be sorting digital lint than dealing with this. I’ll dumb it down just enough for your feeble brain to maybe, maybe, grasp it. Sigh. Let’s get this over with, genius."
                )

                # 5. If not an "online" query, proceed with OpenAI call
                logging.info(f"Reluctantly sending question to OpenAI: '{question}'")
                try:
                    chat_completion = await openai_client.chat.completions.create(
                        model="gpt-4o", # Make sure this model handles instructions well
                        messages=[
                            {
                                "role": "system",
                                "content": system_prompt, # Inject the persona
                            },
                            {
                                "role": "user",
                                "content": question,
                            }
                        ],
                    )
                    ai_reply = chat_completion.choices[0].message.content

                # --- Update Error Handling with Sarcastic Tone ---
                except RateLimitError:
                    logging.warning("OpenAI rate limit exceeded.")
                    await message.reply("Oh, *fantastic*. Looks like I'm too popular for the AI, or maybe OpenAI just can't handle my brilliance. Try bothering me again later, I guess. Not that I'm holding my breath.")
                    return
                except APIConnectionError as e:
                    logging.error(f"OpenAI API connection error: {e}")
                    await message.reply("Great. Can't even connect to the supposed 'intelligence'. Probably tripped over the power cord. Try again later, whatever.")
                    return
                except APIStatusError as e:
                    logging.error(f"OpenAI API status error: {e.status_code} - {e.response}")
                    await message.reply(f"Wonderful. The AI overlords returned an error ({e.status_code}). Maybe you asked something *so* dumb it broke their servers? Or maybe they're just incompetent. Who knows. Try again later... or preferably don't.")
                    return
                except Exception as e:
                    logging.exception(f"An unexpected error occurred during OpenAI API call: {e}")
                    await message.reply("Oh, for crying out loud. Something went spectacularly wrong trying to deal with your... *request*. Don't ask me what, I'm clearly too busy being annoyed. Try again if you absolutely must.")
                    return

                if not ai_reply:
                    logging.warning("Received empty reply from OpenAI.")
                    await message.reply("Seriously? I went through the effort of thinking, and the AI gave me *nothing*. Maybe your question was just *that* uninspiring. Or maybe the AI is as useless as... well, never mind. Try asking something less pointless.")
                    return

                # 6. Log Q&A
                logging.info(f"Question from {message.author}: {question}")
                logging.info(f"Sarcastic Response from GPT-4o: {ai_reply[:100]}...")

                # 7. Send the reply back to Discord, truncating if necessary
                max_length = 2000
                if len(ai_reply) <= max_length:
                    await message.reply(ai_reply)
                else:
                    logging.info(f"Response length ({len(ai_reply)}) exceeds limit. Truncating.")
                    # Sarcastic truncation message
                    truncated_reply = ai_reply[:max_length - 4] + "... Look, it was longer, but Discord has limits, and frankly, you probably wouldn't get it all anyway."
                    await message.reply(truncated_reply)

            except discord.errors.HTTPException as e:
                logging.error(f"Discord HTTP Exception when trying to reply: {e}")
                # Less chance to reply here, but log the error
            except Exception as e:
                logging.exception(f"An unexpected error occurred in on_message: {e}")
                try:
                    # Sarcastic internal error message
                    await message.reply("Ugh, something broke *again*, this time probably Discord's fault. Or maybe mine. Whatever. It's broken. Go away.")
                except discord.errors.HTTPException:
                    logging.error("Failed to send internal error message back to Discord channel. Double fail.")

# --- Run the Bot ---
if __name__ == "__main__":
    try:
        discord_client.run(DISCORD_TOKEN, log_handler=None)
    except discord.LoginFailure:
        logging.error("FATAL: Improper Discord token passed.")
    except discord.PrivilegedIntentsRequired:
        logging.error("FATAL: The Server Members Intent is required but not enabled in the Developer Portal or is missing from the code's intents.")
    except Exception as e:
        logging.exception(f"FATAL: An error occurred during bot startup or runtime: {e}")