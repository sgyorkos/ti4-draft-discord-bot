import aiohttp
import json
import os
import random
from dataclasses import dataclass, field

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# TI4 Factions
TI4_FACTIONS = [
    # Base Game
    "The Arborec",
    "The Barony of Letnev",
    "The Clan of Saar",
    "The Embers of Muaat",
    "The Emirates of Hacan",
    "The Federation of Sol",
    "The Ghosts of Creuss",
    "The L1Z1X Mindnet",
    "The Mentak Coalition",
    "The Naalu Collective",
    "The Nekro Virus",
    "The Sardakk N'orr",
    "The Universities of Jol-Nar",
    "The Winnu",
    "The Xxcha Kingdom",
    "The Yin Brotherhood",
    "The Yssaril Tribes",
    # Prophecy of Kings Expansion
    "The Argent Flight",
    "The Empyrean",
    "The Mahact Gene-Sorcerers",
    "The Naaz-Rokha Alliance",
    "The Nomad",
    "The Titans of Ul",
    "The Vuil'Raith Cabal",
    # Bonus Factions
    "The Council Keleres",
]

# Helper: Faction index mapping
FACTION_INDEX = {i + 1: name for i, name in enumerate(TI4_FACTIONS)}
FACTION_NAME_TO_INDEX = {name: i + 1 for i, name in enumerate(TI4_FACTIONS)}

# Draft state
active_drafts = {}


@dataclass
class Draft:
    channel_id: int
    players: list = field(default_factory=list)
    phase: int = (
        0  # 0 for not started, 1 for initial selection, 2 for voting, 3 for snake draft
    )
    player_factions: dict = field(
        default_factory=dict
    )  # player_id -> [4 random factions]
    selected_factions: dict = field(
        default_factory=dict
    )  # player_id -> [selected faction, optional faction]
    optional_factions: set = field(default_factory=set)  # Set of all optional factions
    votes: dict = field(
        default_factory=dict
    )  # faction -> set of player_ids who voted for it
    final_factions: set = field(
        default_factory=set
    )  # Set of all selectable factions after voting
    draft_order: list = field(default_factory=list)  # Order for snake draft
    current_picker: int = 0  # Index in draft_order for current picker
    draft_round: int = 1  # Current round of snake draft
    player_choices: dict = field(
        default_factory=dict
    )  # player_id -> {"faction": None, "location": None, "strategy": None}
    available_locations: list = field(
        default_factory=list
    )  # List of available locations for the draft
    available_strategies: list = field(
        default_factory=list
    )  # List of available strategy orders for the draft
    map_url: str = ""  # URL for the generated map
    draft_direction: int = 1

    async def initialize(self):
        """Generate a map using the TI4 map generator."""
        async with aiohttp.ClientSession() as session:
            # Generate a random seed for the map
            player_count = len(self.players)
            seed = random.randint(1, 9999)
            self.map_url = (
                f"https://keeganw.github.io/ti4/?settings=TFFFF{player_count}000"
                f"{seed}FFF"
            )
            self.available_locations = list(range(1, player_count + 1))
            self.available_strategies = list(range(1, player_count + 1))

    async def save(self):
        """Save the draft state to a file."""
        with open(f"draft_{self.channel_id}.json", "w") as f:
            data = {
                "channel_id": self.channel_id,
                "players": self.players,
                "phase": self.phase,
                "player_factions": self.player_factions,
                "selected_factions": self.selected_factions,
                "optional_factions": list(self.optional_factions),
                "votes": {k: list(v) for k, v in self.votes.items()},
                "final_factions": list(self.final_factions),
                "draft_order": self.draft_order,
                "current_picker": self.current_picker,
                "draft_round": self.draft_round,
                "player_choices": self.player_choices,
                "available_locations": self.available_locations,
                "available_strategies": self.available_strategies,
                "map_url": self.map_url,
            }
            json.dump(data, f, indent=4)

    @classmethod
    def load(cls, channel_id: int):
        """Load a draft state from a file."""
        try:
            with open(f"draft_{channel_id}.json", "r") as f:
                data = json.load(f)
                draft = cls(
                    channel_id=data["channel_id"],
                    players=data["players"],
                    phase=data["phase"],
                    player_factions=data["player_factions"],
                    selected_factions=data["selected_factions"],
                    optional_factions=set(data["optional_factions"]),
                    votes={k: set(v) for k, v in data["votes"].items()},
                    final_factions=set(data["final_factions"]),
                    draft_order=data["draft_order"],
                    current_picker=data["current_picker"],
                    draft_round=data["draft_round"],
                    player_choices=data["player_choices"],
                    available_locations=data["available_locations"],
                    available_strategies=data["available_strategies"],
                    map_url=data["map_url"],
                )
                return draft
        except FileNotFoundError:
            return None


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")


@bot.command(name="startdraft")
async def start_draft(ctx):
    """Start a new TI4 faction draft."""
    if ctx.channel.id in active_drafts:
        await ctx.send("A draft is already in progress in this channel!")
        return

    draft = Draft(channel_id=ctx.channel.id)
    active_drafts[ctx.channel.id] = draft
    await ctx.send("TI4 Faction Draft started! Use !join to join the draft.")


@bot.command(name="join")
async def join_draft(ctx):
    """Join the current draft."""
    if ctx.channel.id not in active_drafts:
        await ctx.send(
            "No draft is currently in progress. Use !startdraft to start one!"
        )
        return

    draft = active_drafts[ctx.channel.id]
    if ctx.author.id in draft.players:
        await ctx.send("You've already joined this draft!")
        return

    if draft.phase != 0:
        await ctx.send("The draft has already started! You can't join now.")
        return

    draft.players.append(ctx.author.id)
    draft.player_choices[ctx.author.id] = {
        "faction": None,
        "location": None,
        "strategy": None,
    }
    await draft.save()  # Save after joining
    await ctx.send(
        f"{ctx.author.mention} has joined the draft! ({len(draft.players)} players). To"
        " start the draft, run the command !start"
    )


@bot.command(name="start")
async def start_drafting(ctx):
    """Start the actual drafting process."""
    if ctx.channel.id not in active_drafts:
        await ctx.send(
            "No draft is currently in progress. Use !startdraft to start one!"
        )
        return

    draft: Draft = active_drafts[ctx.channel.id]
    if len(draft.players) < 2:
        await ctx.send("Need at least 2 players to start drafting!")
        return

    draft.phase = 1
    await draft.initialize()

    # Assign 4 random factions to each player (by index)
    all_indices = list(FACTION_INDEX.keys())
    random.shuffle(all_indices)
    assigned = set()
    for player_id in draft.players:
        # Pick 4 factions not already assigned
        available = [idx for idx in all_indices if idx not in assigned]
        if len(available) < 4:
            # Not enough unique factions left, reshuffle unassigned
            remaining_needed = 4 - len(available)
            available += random.sample(list(assigned), remaining_needed)
        player_factions = random.sample(available, 4)
        draft.player_factions[player_id] = player_factions
        assigned.update(player_factions)

    await draft.save()  # Save after assigning factions

    # Send each player their factions (by index)
    for player_id in draft.players:
        player = await bot.fetch_user(player_id)
        indices = draft.player_factions[player_id]
        factions = [f"{idx}: {FACTION_INDEX[idx]}" for idx in indices]
        await ctx.send(f"{player.mention}, your factions are:\n" + "\n".join(factions))

    await ctx.send(
        "Phase 1: Each player must select one faction to be selectable and one optional"
        " faction. Use !select <faction_index> <optional_faction_index>. Use "
        "!regenerate-map to regenerate the map."
    )


@bot.command(name="select")
async def select_factions(ctx, faction_index: int, optional_faction_index: int):
    """Select a faction and an optional faction by index."""
    if ctx.channel.id not in active_drafts:
        await ctx.send("No draft is currently in progress!")
        return

    draft = active_drafts[ctx.channel.id]
    if draft.phase != 1:
        await ctx.send("This command is only available in Phase 1!")
        return

    if ctx.author.id not in draft.players:
        await ctx.send("You're not part of this draft!")
        return

    if ctx.author.id in draft.selected_factions:
        await ctx.send("You've already made your selection!")
        return

    player_factions = draft.player_factions[ctx.author.id]
    if (
        faction_index not in player_factions
        or optional_faction_index not in player_factions
    ):
        await ctx.send("Both factions must be from your assigned factions (by index)!")
        return

    if faction_index == optional_faction_index:
        await ctx.send("You must select two different factions!")
        return

    draft.selected_factions[ctx.author.id] = [faction_index, optional_faction_index]
    draft.final_factions.add(faction_index)
    draft.optional_factions.add(optional_faction_index)

    await draft.save()  # Save after selection

    await ctx.send(
        f"{ctx.author.mention} has selected {faction_index}: "
        f"{FACTION_INDEX[faction_index]} as selectable and {optional_faction_index}: "
        f"{FACTION_INDEX[optional_faction_index]} as optional."
    )

    # Check if all players have made their selections
    if len(draft.selected_factions) == len(draft.players):
        await ctx.send(
            "All players have made their selections! Moving to Phase 2: Voting on "
            "optional factions."
        )
        # Set up draft order for voting
        draft.draft_order = draft.players.copy()
        random.shuffle(draft.draft_order)
        draft.current_voter = 0
        draft.phase = 2
        await draft.save()  # Save after moving to voting phase
        await ctx.send(
            "Use !vote <faction_index> to vote for an optional faction. Voting will "
            "proceed in draft order. A faction needs 2 votes to be included."
        )
        vote_status = []
        for idx in sorted(draft.optional_factions):
            count = len(draft.votes.get(idx, set()))
            vote_status.append(
                f"{idx}: {FACTION_INDEX[idx]} ({count} vote{'s' if count != 1 else ''})"
            )
        await ctx.send(
            "Optional factions available to vote for:\n" + "\n".join(vote_status)
        )
        await ctx.send("Voting order:")
        for i, player_id in enumerate(draft.draft_order):
            player = await bot.fetch_user(player_id)
            await ctx.send(f"{i+1}. {player.name}")
        first_voter = await bot.fetch_user(draft.draft_order[0])
        await ctx.send(f"It's {first_voter.mention}'s turn to vote!")


@bot.command(name="vote")
async def vote_faction(ctx, faction_index: int):
    """Vote for an optional faction by index, in draft order."""
    if ctx.channel.id not in active_drafts:
        await ctx.send("No draft is currently in progress!")
        return

    draft = active_drafts[ctx.channel.id]
    if draft.phase != 2:
        await ctx.send("This command is only available in Phase 2!")
        return

    if ctx.author.id not in draft.players:
        await ctx.send("You're not part of this draft!")
        return

    # Only allow the current voter in draft order to vote
    if ctx.author.id != draft.draft_order[draft.current_voter]:
        current_voter = await bot.fetch_user(draft.draft_order[draft.current_voter])
        await ctx.send(
            f"It's not your turn to vote! It's {current_voter.mention}'s turn."
        )
        return

    if faction_index not in draft.optional_factions:
        await ctx.send("This faction is not in the optional pool!")
        return

    if faction_index in draft.final_factions:
        await ctx.send("This faction has already been voted in!")
        return

    # Initialize votes for this faction if not exists
    if faction_index not in draft.votes:
        draft.votes[faction_index] = set()

    # Add vote
    draft.votes[faction_index].add(ctx.author.id)

    # Check if faction has enough votes
    if len(draft.votes[faction_index]) >= 2:
        draft.final_factions.add(faction_index)
        draft.optional_factions.remove(faction_index)
        await ctx.send(
            f"{faction_index}: {FACTION_INDEX[faction_index]} has received enough votes"
            " and is now selectable!"
        )

    await draft.save()  # Save after voting

    # Move to next voter
    draft.current_voter += 1
    if draft.current_voter >= len(draft.draft_order):
        draft.current_voter = 0

    # If all players have voted in this round (one vote per player per round)
    all_voted = all(
        any(voter_id in votes for votes in draft.votes.values())
        for voter_id in draft.draft_order
    )
    if not draft.optional_factions or all_voted:
        await ctx.send(
            "Voting phase complete! Moving to Phase 3: Snake Draft for Factions, "
            "Locations, and Strategy Order."
        )
        draft.phase = 3
        await draft.save()  # Save after moving to snake draft
        # Set up snake draft order (reuse draft.draft_order)
        await ctx.send("Draft order:")
        for i, player_id in enumerate(draft.draft_order):
            player = await bot.fetch_user(player_id)
            await ctx.send(f"{i+1}. {player.name}")
        first_player = await bot.fetch_user(draft.draft_order[0])
        await ctx.send(
            "Use !pick <faction/location/strategy> <value> to make your selection."
        )
        await ctx.send(f"Map URL: {draft.map_url}")
        available_factions = [
            f"{idx}: {FACTION_INDEX[idx]}" for idx in sorted(draft.final_factions)
        ]
        await ctx.send(
            "Available factions: "
            + (", ".join(available_factions) if available_factions else "None")
        )
        await ctx.send(
            "Available locations (1 is the top of the map, 2 is the next clockwise,"
            " and so on): "
            + (
                ", ".join(map(str, draft.available_locations))
                if draft.available_locations
                else "None"
            )
        )
        await ctx.send(
            "Available strategy orders: "
            + (
                ", ".join(map(str, draft.available_strategies))
                if draft.available_strategies
                else "None"
            )
        )
        await ctx.send(f"It's {first_player.mention}'s turn to pick!")
    else:
        # Print the current vote counts for each faction
        vote_counts = {
            f"{faction_index} - {FACTION_INDEX[faction_index]}": len(votes)
            for faction_index, votes in draft.votes.items()
        }
        await ctx.send(
            f"The vote count is now:\n"
            + "\n".join(
                f"{faction}: {count} votes" for faction, count in vote_counts.items()
            )
        )
        # Announce next voter
        next_voter = await bot.fetch_user(draft.draft_order[draft.current_voter])
        await ctx.send(f"It's {next_voter.mention}'s turn to vote!")


@bot.command(name="pick")
async def pick_selection(ctx, selection_type: str, value: str):
    """Pick a faction, location, or strategy order."""
    if ctx.channel.id not in active_drafts:
        await ctx.send("No draft is currently in progress!")
        return

    draft = active_drafts[ctx.channel.id]
    if draft.phase != 3:
        await ctx.send("This command is only available in Phase 3!")
        return

    if ctx.author.id not in draft.players:
        await ctx.send("You're not part of this draft!")
        return

    if ctx.author.id != draft.draft_order[draft.current_picker]:
        await ctx.send("It's not your turn to pick!")
        return

    selection_type = selection_type.lower()
    if selection_type not in ["faction", "location", "strategy"]:
        await ctx.send(
            "Invalid selection type! Choose from: faction, location, strategy"
        )
        return

    # Check if player has already made this type of selection
    if draft.player_choices[ctx.author.id][selection_type] is not None:
        await ctx.send(f"You've already selected your {selection_type}!")
        return

    # Validate and process the selection
    if selection_type == "faction":
        try:
            faction_index = int(value)
        except ValueError:
            await ctx.send("Faction must be a number (index)!")
            return
        if faction_index not in draft.final_factions:
            await ctx.send(
                "Invalid faction! Choose from the available factions (by index)."
            )
            return
        draft.player_choices[ctx.author.id]["faction"] = faction_index
    elif selection_type == "location":
        try:
            location = int(value)
            if location not in draft.available_locations:
                await ctx.send("Invalid location! Choose from available locations.")
                return
            draft.player_choices[ctx.author.id]["location"] = location
            draft.available_locations.remove(location)
        except ValueError:
            await ctx.send("Location must be a number!")
            return
    elif selection_type == "strategy":
        try:
            strategy = int(value)
            if strategy not in draft.available_strategies:
                await ctx.send(
                    "Invalid strategy number! Choose from available strategies."
                )
                return
            draft.player_choices[ctx.author.id]["strategy"] = strategy
            draft.available_strategies.remove(strategy)
        except ValueError:
            await ctx.send("Strategy must be a number!")
            return

    await draft.save()  # Save after each pick

    if selection_type == "faction":
        await ctx.send(
            f"{ctx.author.mention} has selected {faction_index}: "
            f"{FACTION_INDEX[faction_index]} as their faction."
        )
    else:
        await ctx.send(
            f"{ctx.author.mention} has selected {value} as their {selection_type}."
        )

    # Move to next picker
    draft.current_picker += draft.draft_direction
    if draft.current_picker >= len(draft.draft_order) or draft.current_picker < 0:
        # End of round: reverse direction and move to next round
        draft.draft_direction *= -1
        if draft.draft_direction == 1:
            draft.draft_round += 1
            draft.current_picker = 0
        else:
            draft.current_picker = len(draft.draft_order) - 1

    # Check if draft is complete
    all_choices_made = all(
        all(choice is not None for choice in choices.values())
        for choices in draft.player_choices.values()
    )

    if all_choices_made:
        await ctx.send("Draft complete! Here are the final selections:")
        for player_id, choices in draft.player_choices.items():
            player = await bot.fetch_user(player_id)
            await ctx.send(f"{player.name}:")
            if choices["faction"] is not None:
                await ctx.send(
                    f"Faction: {choices['faction']}: "
                    f"{FACTION_INDEX[choices['faction']]}"
                )
            else:
                await ctx.send(f"Faction: None")
            await ctx.send(f"Location: {choices['location']}")
            await ctx.send(f"Strategy Order: {choices['strategy']}")
        await ctx.send(f"Map URL: {draft.map_url}")
        del active_drafts[ctx.channel.id]
    else:
        next_player_id = draft.draft_order[draft.current_picker]
        next_player = await bot.fetch_user(next_player_id)
        # Show only categories the next player hasn't picked yet
        choices = draft.player_choices[next_player_id]
        messages = []
        if choices["faction"] is None:
            picked_factions = [
                c["faction"]
                for c in draft.player_choices.values()
                if c["faction"] is not None
            ]
            available_factions = [
                f"{idx}: {FACTION_INDEX[idx]}"
                for idx in sorted(draft.final_factions)
                if idx not in picked_factions
            ]
            messages.append(
                "Available factions: "
                + (", ".join(available_factions) if available_factions else "None")
            )
        if choices["location"] is None:
            messages.append(
                "Available locations (1 is the top of the map, 2 is the next clockwise,"
                " and so on): "
                + (
                    ", ".join(map(str, draft.available_locations))
                    if draft.available_locations
                    else "None"
                )
            )
        if choices["strategy"] is None:
            messages.append(
                "Available strategy orders: "
                + (
                    ", ".join(map(str, draft.available_strategies))
                    if draft.available_strategies
                    else "None"
                )
            )
        if messages:
            await ctx.send("\n".join(messages))
        await ctx.send(f"It's {next_player.mention}'s turn to pick!")
        await ctx.send(
            "Use !pick <faction/location/strategy> <value> to make your selection."
        )


@bot.command(name="load")
async def load_draft(ctx):
    """Load a draft state from a file."""
    if ctx.channel.id in active_drafts:
        await ctx.send("A draft is already in progress in this channel!")
        return

    draft = Draft.load(ctx.channel.id)
    if not draft:
        await ctx.send("No saved draft found for this channel!")
        return

    active_drafts[ctx.channel.id] = draft
    await ctx.send("Draft state loaded successfully!")
    await ctx.send(f"Map URL: {draft.map_url}")
    await ctx.send(f"Current phase: {draft.phase}")


@bot.command(name="list")
async def list_factions(ctx):
    """List available factions, locations, and strategies."""
    if ctx.channel.id not in active_drafts:
        await ctx.send("No draft is currently in progress!")
        return

    draft = active_drafts[ctx.channel.id]
    if draft.phase == 1:
        if ctx.author.id in draft.player_factions:
            indices = draft.player_factions[ctx.author.id]
            await ctx.send(
                f"Your factions: "
                + ", ".join(f"{idx}: {FACTION_INDEX[idx]}" for idx in indices)
            )
        else:
            await ctx.send("You haven't been assigned factions yet!")
    elif draft.phase == 2:
        await ctx.send(
            f"Selectable factions: "
            + ", ".join(
                f"{idx}: {FACTION_INDEX[idx]}" for idx in sorted(draft.final_factions)
            )
        )
        if draft.optional_factions:
            await ctx.send(
                f"Optional factions (needs votes): "
                + ", ".join(
                    f"{idx}: {FACTION_INDEX[idx]}"
                    for idx in sorted(draft.optional_factions)
                )
            )
    elif draft.phase == 3:
        await ctx.send(
            f"Available factions: "
            + ", ".join(
                f"{idx}: {FACTION_INDEX[idx]}" for idx in sorted(draft.final_factions)
            )
        )
        await ctx.send(
            "Available locations (1 is the top of the map, 2 is the next clockwise, "
            f"and so on): {', '.join(map(str, draft.available_locations))}"
        )
        await ctx.send(
            f"Available strategy orders: "
            f"{', '.join(map(str, draft.available_strategies))}"
        )
        await ctx.send(f"Map URL: {draft.map_url}")
    else:
        await ctx.send("The draft is not in progress!")


@bot.command(name="regenerate-map")
async def regenerate_map(ctx):
    """Regenerate the map URL."""
    if ctx.channel.id not in active_drafts:
        await ctx.send("No draft is currently in progress!")
        return
    if ctx.author.id not in active_drafts[ctx.channel.id].players:
        await ctx.send("You're not part of this draft!")
        return
    if active_drafts[ctx.channel.id].phase != 1:
        await ctx.send("You can only regenerate the map URL in Phase 1!")
        return

    draft = active_drafts[ctx.channel.id]
    await draft.initialize()
    await ctx.send(f"Map URL regenerated: {draft.map_url}")


def main():
    # Get the token from environment variable
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Error: DISCORD_TOKEN environment variable not set!")
        return

    bot.run(token)


if __name__ == "__main__":
    main()
