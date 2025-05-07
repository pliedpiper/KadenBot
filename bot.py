import os
import logging
import asyncio
import discord
from dotenv import load_dotenv
from collections import defaultdict

# New-style OpenAI SDK
from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIStatusError
import openai  # keep base import for potential utilities

# ──────────────────────────  Configuration  ──────────────────────────
load_dotenv()  # Load variables from .env
DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")   # still needed implicitly

# --- Conversation Memory Configuration ---
# Max number of messages (user + assistant combined) to keep in history per channel.
# Set to 10 as requested. This means roughly 5 pairs of user/assistant messages.
MAX_HISTORY_MESSAGES = 10
# Optional: A system prompt to guide the AI's behavior
SYSTEM_PROMPT = "You are a helpful assistant integrated into a Discord server."
# --- End Memory Configuration ---

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

if not DISCORD_TOKEN:
    logging.error("FATAL: DISCORD_TOKEN environment variable not set.")
    raise SystemExit(1)

if not OPENAI_API_KEY:
    logging.warning("OPENAI_API_KEY environment variable not set – "
                    "the OpenAI client will fail once a request is made.")

# ──────────────────────────  OpenAI client  ──────────────────────────
try:
    openai_client = AsyncOpenAI()         # reads key from env
    logging.info("AsyncOpenAI client initialised.")
except Exception as e:
    logging.exception("Failed to initialise AsyncOpenAI client: %s", e)
    raise SystemExit(1)

# ─────────────────── Conversation History Storage ────────────────────
# Stores conversation history per channel { channel_id: [messages] }
# Each message is a dict: {"role": "user" | "assistant", "content": "..."}
conversation_histories = defaultdict(list)

# ──────────────────────────  Discord client  ─────────────────────────
intents = discord.Intents.default()
intents.message_content = True  # privileged
intents.guilds          = True
intents.members         = True  # REQUIRED for member lists
intents.presences       = True  # REQUIRED for .status (online / idle / dnd)
intents.messages        = True  # (redundant but explicit)

discord_client = discord.Client(intents=intents)

# ──────────────────────────  Helpers  ────────────────────────────────
ONLINE_STATES = {
    discord.Status.online,
    discord.Status.idle,
    discord.Status.dnd,
}

async def get_online_usernames(guild: discord.Guild) -> list[str]:
    """
    Return a list of usernames with a presence of Online / Idle / DND.
    Bots are excluded.
    """
    if guild is None:
        return []

    # Ensure the member cache is populated (for large guilds on first use)
    await guild.chunk(cache=True)

    return [
        member.display_name
        for member in guild.members
        if not member.bot and member.status in ONLINE_STATES
    ]

# ──────────────────────────  Events  ─────────────────────────────────
@discord_client.event
async def on_ready() -> None:
    logging.info("%s (ID %s) is connected and ready.",
                 discord_client.user, discord_client.user.id)

@discord_client.event
async def on_message(message: discord.Message) -> None:
    # Ignore the bot’s own messages
    if message.author == discord_client.user:
        return

    content_lower = message.content.lower()
    channel_id = message.channel.id

    # ───── “who’s online” command (either !online or mention) ─────
    is_prefix_cmd = content_lower.startswith("!online")
    is_mention_cmd_online = (
        discord_client.user in message.mentions and "who's online" in content_lower
    )

    if is_prefix_cmd or is_mention_cmd_online:
        logging.info("Received online status request from %s in channel %s",
                     message.author, channel_id)

        async with message.channel.typing():
            users_online = await get_online_usernames(message.guild)

        if users_online:
            if len(users_online) == 1:
                reply = f"{users_online[0]} is online right now."
            else:
                *first, last = users_online
                reply = f"{', '.join(first)}, and {last} are online right now."
        else:
            reply = "Nobody (except me) is currently online or visible."

        try:
            await message.reply(reply)
        except discord.HTTPException as e:
            logging.error("Discord error when replying with online list: %s", e)
        return  # Do not continue to OpenAI logic

    # ───── OpenAI chat: triggered when the bot is mentioned (and not asking who's online) ─────
    if discord_client.user not in message.mentions:
        return

    logging.info("Bot mentioned by %s in #%s (channel_id: %s)",
                 message.author, message.channel, channel_id)

    async with message.channel.typing():
        try:
            mention_plain  = f"<@{discord_client.user.id}>"
            mention_nick   = f"<@!{discord_client.user.id}>"
            question = message.content.replace(mention_plain, "").replace(
                mention_nick, ""
            ).strip()

            if not question:
                await message.reply("You mentioned me but asked nothing!")
                return

            # --- Prepare message history for OpenAI ---
            # Start with the system prompt
            messages_for_api = []
            if SYSTEM_PROMPT:
                 messages_for_api.append({"role": "system", "content": SYSTEM_PROMPT})

            # Add existing history for this channel (up to the limit)
            # Keep MAX_HISTORY_MESSAGES - 1 to leave space for the current user message
            history = conversation_histories[channel_id]
            # Calculate how many messages to actually take from history
            # Ensure we don't try to take more than available or more than the limit allows
            history_limit_for_api = max(0, MAX_HISTORY_MESSAGES - 1) # Max history items to send
            actual_history_to_send = history[-history_limit_for_api:] # Get the slice

            messages_for_api.extend(actual_history_to_send)

            # Add the new user question
            user_message = {"role": "user", "content": question}
            messages_for_api.append(user_message)
            # --- End History Preparation ---

            logging.info("Forwarding query to OpenAI (history length %d): %s",
                         len(actual_history_to_send), # Log actual history length sent
                         question)

            chat_completion = await openai_client.chat.completions.create(
                model="gpt-4.1",   # adjust to an available model name
                messages=messages_for_api, # Send history + new question
            )
            # Ensure we handle potential empty responses gracefully
            ai_reply = chat_completion.choices[0].message.content if chat_completion.choices else "Sorry, I couldn't generate a response."
            ai_message = {"role": "assistant", "content": ai_reply}

            # --- Update conversation history ---
            # Add the user's actual question
            conversation_histories[channel_id].append(user_message)
            # Add the AI's response
            conversation_histories[channel_id].append(ai_message)
            # Prune history to max length (ensures storage doesn't exceed MAX_HISTORY_MESSAGES)
            conversation_histories[channel_id] = conversation_histories[channel_id][-MAX_HISTORY_MESSAGES:]
            logging.info("Updated history for channel %s, new stored length: %d",
                         channel_id, len(conversation_histories[channel_id]))
            # --- End History Update ---

        except RateLimitError:
            logging.warning("OpenAI Rate Limit encountered in channel %s", channel_id)
            await message.reply("OpenAI is rate-limited right now – please wait a bit.")
            return
        except APIConnectionError as e:
            logging.error("OpenAI connection issue: %s", e)
            await message.reply("Couldn’t reach OpenAI right now – try again later.")
            return
        except APIStatusError as e:
            logging.error("OpenAI API status error: %s %s", e.status_code, e)
            await message.reply("OpenAI returned an error. Try again later.")
            return
        except Exception as e:
            logging.exception("Unexpected error during OpenAI interaction: %s", e)
            await message.reply("An unexpected error occurred – sorry!")
            return

        # Discord hard limit 2000 chars
        try:
            if len(ai_reply) <= 2000:
                await message.reply(ai_reply)
            else:
                # Send truncated message if too long
                await message.reply(ai_reply[:1996] + " ...")
                logging.warning("AI response truncated for channel %s due to >2000 char limit.", channel_id)
        except discord.HTTPException as e:
            logging.error("Discord error when sending AI reply: %s", e)


# ──────────────────────────  Main  ───────────────────────────────────
if __name__ == "__main__":
    try:
        discord_client.run(DISCORD_TOKEN, log_handler=None)
    except discord.LoginFailure:
        logging.error("FATAL: bad Discord token.")
    except Exception:
        logging.exception("FATAL: error during bot runtime.")