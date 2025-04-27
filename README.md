# KadenBot - Discord GPT-4o Assistant

KadenBot is a simple Discord bot that listens for mentions (@KadenBot) and responds to user questions by querying the OpenAI GPT-4o model.

## Features

-   Responds to mentions in any channel it can read.
-   Forwards the user's question (after the mention) to OpenAI's GPT-4o API.
-   Posts the AI's response back to the original Discord channel/thread.
-   Shows a "typing..." indicator while waiting for the AI response.
-   Handles basic API errors and rate limits gracefully.
-   Truncates very long responses to fit Discord's message limit.
-   Logs basic activity and Q&A pairs to standard output.

## Prerequisites

-   Python 3.10 or higher.
-   A Discord Bot Token.
-   An OpenAI API Key.

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url> # Or download the files
    cd <repository-directory>
    ```

2.  **Create a Discord Bot Application:**
    *   Go to the [Discord Developer Portal](https://discord.com/developers/applications).
    *   Create a "New Application". Give it a name (e.g., KadenBot).
    *   Navigate to the "Bot" tab.
    *   Click "Add Bot".
    *   **Enable Privileged Gateway Intents:**
        *   Enable `MESSAGE CONTENT INTENT`. This is crucial for reading message text.
    *   **Copy the Bot Token:** Under the bot's username, click "Reset Token" (or "View Token") and copy it securely. **This is your `DISCORD_TOKEN`.**
    *   **Invite the Bot:**
        *   Go to the "OAuth2" -> "URL Generator" tab.
        *   Select the `bot` scope.
        *   Under "Bot Permissions", select:
            *   `Send Messages`
            *   `Read Message History`
            *   (Optional but recommended: `Read Messages/View Channels`)
        *   Copy the generated URL and paste it into your browser. Select the server you want to add the bot to and authorize it.

3.  **Get an OpenAI API Key:**
    *   Go to the [OpenAI Platform](https://platform.openai.com/api-keys).
    *   Create a new secret key. Copy it securely. **This is your `OPENAI_API_KEY`.**
    *   Ensure your OpenAI account has billing set up or sufficient credits to use the GPT-4o model.

4.  **Set Environment Variables:**
    The bot reads the Discord token and OpenAI key from environment variables. You need to set them in your terminal session or system environment.

    *   **Linux/macOS:**
        ```bash
        export DISCORD_TOKEN="your_discord_bot_token_here"
        export OPENAI_API_KEY="your_openai_api_key_here"
        ```
    *   **Windows (Command Prompt):**
        ```cmd
        set DISCORD_TOKEN="your_discord_bot_token_here"
        set OPENAI_API_KEY="your_openai_api_key_here"
        ```
    *   **Windows (PowerShell):**
        ```powershell
        $env:DISCORD_TOKEN="your_discord_bot_token_here"
        $env:OPENAI_API_KEY="your_openai_api_key_here"
        ```
    *   **(Optional) Using a `.env` file for local development:**
        *   If you uncomment `python-dotenv` in `requirements.txt` and install it (`pip install python-dotenv`), you can create a file named `.env` in the same directory as `bot.py`:
          ```dotenv
          DISCORD_TOKEN="your_discord_bot_token_here"
          OPENAI_API_KEY="your_openai_api_key_here"
          ```
        *   Add `from dotenv import load_dotenv` and `load_dotenv()` at the top of `bot.py` (after imports, before reading env vars). **Remember to add `.env` to your `.gitignore` file!**

5.  **Install Dependencies:**
    Create a virtual environment (recommended) and install the required packages.
    ```bash
    python -m venv venv
    # Activate the virtual environment
    # Linux/macOS:
    source venv/bin/activate
    # Windows:
    .\venv\Scripts\activate

    # Install requirements
    pip install -r requirements.txt
    ```

## Running the Bot

Once the setup is complete and environment variables are set, run the bot script:

```bash
python bot.py