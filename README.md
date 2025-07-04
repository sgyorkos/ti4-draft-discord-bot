# TI4 Draft Discord Bot

A Discord bot for managing Twilight Imperium 4th Edition faction drafts.

## Setup

1. Create a new Discord application and bot at https://discord.com/developers/applications
2. Copy your bot token
3. Create a `.env` file in the project root with the following content:
   ```
   DISCORD_TOKEN=your_bot_token_here
   ```
4. Install uv - https://docs.astral.sh/uv/getting-started/installation/
5. Install the required dependencies:
   ```bash
   uv sync
   ```
6. Run the bot:
   ```bash
   python src/drafter.py
   ```

## Commands

- `!startdraft` - Start a new faction draft
- `!list` - List available factions

Phase 0 commands:
- `!join` - Join the current draft
- `!start` - Begin the drafting process (requires at least 2 players)

Phase 1 commands:
- `!select <faction> <optional faction>` - Select two factions, one to put in the draft and one to optionally be added

Phase 2 commands:
- `!vote <faction>` - The faction you are voting on

Phase 3 commands:
- `!pick <faction|lication|strategy card>` - Pick a faction during your turn

The bot will automatically track turns and available factions, and will announce when the draft is complete.
