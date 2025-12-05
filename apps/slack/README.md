# Neuro-SAN Slack Bot Setup Guide

This guide will walk you through setting up the Neuro-SAN Slack bot from scratch.

## Prerequisites

- Python 3.10 or higher
- A Slack workspace where you have admin permissions
- Neuro-SAN server running locally
- `slack_bolt>=1.27.0`

## Step 1: Create a Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Select **"From scratch"**
4. Enter:
   - **App Name**: `Neuro-SAN Bot` (or your preferred name)
   - **Workspace**: Select your workspace
5. Click **"Create App"**

## Step 2: Enable Socket Mode

Socket Mode allows your bot to connect to Slack without requiring a public URL.

1. In your app's settings, go to **"Socket Mode"** (left sidebar)
2. Toggle **"Enable Socket Mode"** to **ON**
3. Click **"Generate an app-level token"**
   - **Token Name**: `socket-token` (or your preferred name)
   - **Scopes**: Select `connections:write`
4. Click **"Generate"**
5. **Copy the token** (starts with `xapp-`) - this is your `SLACK_APP_TOKEN`
6. Click **"Done"**

## Step 3: Configure Bot Token Scopes

1. Go to **"OAuth & Permissions"** (left sidebar)
2. Scroll down to **"Scopes" → "Bot Token Scopes"**
3. Click **"Add an OAuth Scope"** and add the following scopes:
   - `app_mentions:read` - To receive @mentions
   - `chat:write` - To send messages
   - `channels:history` - To read channel messages
   - `groups:history` - To read private channel messages
   - `im:history` - To read direct messages
   - `commands` - To use slash commands

## Step 4: Install the App to Your Workspace

1. Scroll to the top of **"OAuth & Permissions"** page
2. Click **"Install to Workspace"**
3. Review permissions and click **"Allow"**
4. **Copy the "Bot User OAuth Token"** (starts with `xoxb-`) - this is your `SLACK_BOT_TOKEN`

## Step 5: Subscribe to Bot Events

1. Go to **"Event Subscriptions"** (left sidebar)
2. Toggle **"Enable Events"** to **ON**
3. Under **"Subscribe to bot events"**, add:
   - `app_mention` - When someone @mentions your bot
   - `message.channels` - Messages in public channels
   - `message.groups` - Messages in private channels
   - `message.im` - Direct messages
4. Click **"Save Changes"**

## Step 6: Enable App Home Messaging (Required for DM Support)

Slack disables direct messaging to apps unless this setting is turned on.

1. Go to "App Home" (left sidebar)

2. Scroll to "Show Tabs"

3. Enable:

   ✅ Messages Tab

   ✅ Allow users to send Slash commands and messages from the messages tab

4. Click "Save Changes" if the button appears

## Step 7: Create Slash Commands

1. Go to **"Slash Commands"** (left sidebar)
2. Click **"Create New Command"**

### Command 1: `/list_networks`
- **Command**: `/list_networks`
- **Short Description**: `List all available Neuro-SAN networks`
- Click **"Save"**

### Command 2: `/neuro_san_help`
- **Command**: `/neuro_san_help`
- **Short Description**: `Show usage instructions`
- Click **"Save"**

## Step 8: Reinstall the App

After adding events and commands:
1. Go back to **"OAuth & Permissions"**
2. Click **"Reinstall to Workspace"**
3. Click **"Allow"**

## Step 9: Set Up Your Python Environment

### Install Dependencies

```bash
# Create a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install slack-bolt python-dotenv requests
```

### Create `.env` File

Create a `.env` file in your project directory:

```bash
# Slack tokens
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here

# Neuro-SAN server port
NEURO_SAN_SERVER_HTTP_PORT=8080 (or any port you want)
```

**Replace the tokens with the ones you copied earlier.**

## Step 10: Start the Neuro-SAN Server

Make sure your Neuro-SAN server is running on the port specified in `.env`:

```bash
# Example - adjust based on your setup
python -m neuro_san.service.main_loop.server_main_loop
```

## Step 11: Run the Bot

```bash
python -m apps.slack.main
```

You should see:
```
Starting Slack bot, connecting to API at localhost:8080
⚡️ Bolt app is running!
```

## Step 12: Test Your Bot

### In Direct Messages (DM)

1. Open a DM with your bot (search for the bot name in Slack)
2. List available networks:
   ```
   /list_networks
   ```
3. Connect to a network:
   ```
   music_nerd_pro
   ```
4. Send a message:
   ```
   Tell me about jazz
   ```

### In a Channel

1. Invite the bot to a channel:
   ```
   /invite @YourBotName
   ```
2. Mention the bot with a network:
   ```
   @YourBotName music_nerd_pro
   ```
3. Continue the conversation in the thread:
   ```
   @YourBotName Tell me about jazz
   ```

## Usage Examples

### Basic Usage
```
music_nerd_pro
Tell me about jazz
```

### With sly_data
```
math_guy --sly_data {"x": 7, "y": 6}
multiply
```

### With Input Prompt
```
music_nerd_pro Tell me about jazz
```

### Complete Example
```
math_guy multiply --sly_data {"x": 7, "y": 6}
```

## Troubleshooting

### Bot doesn't respond
- Check that the bot is running
- Verify tokens in `.env` are correct
- Check that Socket Mode is enabled
- Make sure the bot is invited to the channel

### "dispatch_failed" error
- Restart the bot
- Check that all required scopes are added
- Reinstall the app to workspace

### Connection errors
- Verify Neuro-SAN server is running
- Check `NEURO_SAN_SERVER_HTTP_PORT` matches your server
- Look at bot logs for specific error messages

### No logs appearing
- Check that logging is configured in the code
- Verify the bot is actually receiving messages
- Check Slack app Event Subscriptions are saved

## Security Notes

⚠️ **Important Security Practices:**

1. **Never commit `.env` to version control**
2. **Keep your tokens secret** - they provide full access to your bot
3. **Rotate tokens** if you suspect they've been compromised
4. **Use environment variables** in production, not `.env` files

## Getting Help

### Slack Commands
- `/list_networks` - See all available networks
- `/neuro_san_help` - Show usage instructions

### Resources
- [Slack Bolt Python Documentation](https://slack.dev/bolt-python/)
- [Slack API Documentation](https://api.slack.com/)

## Common Commands Quick Reference

| Action | Direct Message | In Channel |
|--------|---------------|------------|
| List networks | `/list_networks` | `/list_networks` |
| Connect to network | `network_name` | `@Bot network_name` |
| Send message | `your message` | `@Bot your message` |
| With sly_data | `network --sly_data {"x": 1}` | `@Bot network --sly_data {"x": 1}` |
| Get help | `/neuro_san_help` | `/neuro_san_help` |

---

**Need more help?** Check the logs in your terminal where the bot is running for detailed error messages.