import asyncio
import json
import os
import re
import secrets
import time
from datetime import timedelta

import aiohttp
import discord
from discord import app_commands, ui
from discord.ext import commands


# Setup

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

TOKEN = ""

# Set SYNC_COMMANDS=0 to skip command syncing on startup once commands are stable.
SYNC_COMMANDS = os.getenv("SYNC_COMMANDS", "1") == "1"


# Config

WELCOME_CHANNEL_ID = 000000000000000000

WELCOME_MESSAGE = (
    "Welcome to **{server-name}** {member-mention}! "
    "We hope you enjoy your stay here!"
)

SAY_ROLE_ID = 000000000000000000
PURGE_ROLE_ID = 000000000000000000
# Role (or list of roles) allowed to run /session vote, start and end.
SESSION_ROLE_ID = 000000000000000000

KICK_BANNER = "YOUR_KICK_BANNER_URL"
KICK_MESSAGE = (
    "Hello {member-mention}, you have officially been kicked from "
    "**{server-name}**.\n\n"
    "➤ **User:** {member-mention}\n"
    "➤ **Reason:** {reason}\n"
    "➤ **Moderator:** {moderator-mention}"
)

BAN_BANNER = "YOUR_BAN_BANNER_URL"
BAN_MESSAGE = (
    "Hello {member-mention}, you have officially been banned from "
    "**{server-name}**.\n\n"
    "➤ **User:** {member-mention}\n"
    "➤ **Reason:** {reason}\n"
    "➤ **Moderator:** {moderator-mention}"
)

UNBAN_BANNER = "YOUR_UNBAN_BANNER_URL"
UNBAN_MESSAGE = (
    "Hello {member-mention}, you have officially been un-banned from "
    "**{server-name}**.\n\n"
    "➤ **User:** {member-mention}\n"
    "➤ **Moderator:** {moderator-mention}"
)

MUTE_BANNER = "YOUR_MUTE_BANNER_URL"
MUTE_MESSAGE = (
    "Hello {member-mention}, you have officially been muted in "
    "**{server-name}**.\n\n"
    "➤ **User:** {member-mention}\n"
    "➤ **Duration:** {duration} minute(s)\n"
    "➤ **Reason:** {reason}\n"
    "➤ **Moderator:** {moderator-mention}"
)

UNMUTE_BANNER = "YOUR_UNMUTE_BANNER_URL"
UNMUTE_MESSAGE = (
    "Hello {member-mention}, you have officially been un-muted in "
    "**{server-name}**.\n\n"
    "➤ **User:** {member-mention}\n"
    "➤ **Moderator:** {moderator-mention}"
)

# Discord caps timeouts at 28 days.
MAX_MUTE_MINUTES = 28 * 24 * 60

VERIFICATION_DATA_FILE = "verification_data.json"
VERIFICATION_CHANNEL_ID = 000000000000000000
VERIFIED_ROLE_ID = 000000000000000000
UNVERIFIED_ROLE_ID = 000000000000000000
VERIFICATION_BANNER = "YOUR_VERIFICATION_BANNER_URL"
VERIFICATION_TITLE = "Maryland State Verification"
VERIFICATION_CODE_LIFETIME = 60 * 60  # seconds

VERIFICATION_PANEL_MESSAGE = (
    "Welcome to **Maryland State Roleplay!** "
    "Click the button below to Verify with Maryland "
    "and gain access to the rest of the server."
)

VERIFICATION_CODE_MESSAGE = (
    "### Verification Code\n\n"
    "Your verification code is:\n\n"
    "**`{code}`**\n\n"
    "### What to do\n"
    "1. Go to your Roblox profile.\n"
    "2. Put **`{code}`** anywhere in your Roblox About/Description.\n"
    "3. Save your Roblox profile.\n"
    "4. Come back here and click **Verify** again.\n\n"
    "Your Discord nickname will only be changed to "
    "**{roblox_username}** after the code is found "
    "on your Roblox profile."
)

VERIFICATION_NOT_FOUND_MESSAGE = (
    "I could not find that Roblox account. "
    "Please check the username and try again."
)

VERIFICATION_PENDING_MESSAGE = (
    "Your Roblox profile has not been verified yet.\n\n"
    "Put this code in your Roblox About/Description:\n\n"
    "**`{code}`**\n\n"
    "After adding the code to your profile, "
    "click **Verify** again."
)

VERIFICATION_SUCCESS_MESSAGE = (
    "### Verification Successful\n\n"
    "Your Roblox account has been verified.\n\n"
    "Your Discord nickname has been changed to "
    "**{roblox_username}**."
)

SESSION_DATA_FILE = "session_data.json"

SESSION_TOP_BANNER = "YOUR_TOP_BANNER_URL"
SESSION_BOTTOM_BANNER = "YOUR_BOTTOM_BANNER_URL"
SESSION_CHANNEL = 000000000000000000
REQUIRED_SESSION_VOTES = 8
JOIN_URL = "YOUR_ERLC_JOIN_URL"

SESSION_VOTE_TITLE = "## Session Vote"
SESSION_VOTE_MESSAGE = (
    "@everyone @here\n"
    "A session vote has been hosted! Please vote up if you would like "
    "to join our server and participate in the session. We hope to see "
    "you there!"
)

SESSION_START_TITLE = "## Session Start"
SESSION_START_MESSAGE = (
    "@everyone @here\n"
    "A session has been hosted! Please join if you voted up. "
    "Failure to do so may result in a warning **only if you voted**. "
    "We hope to see you there!"
)

SESSION_END_TITLE = "## Session End"
SESSION_END_MESSAGE = (
    "The session has officially ended. Thank you to everyone "
    "who joined and participated during the session. Make sure "
    "to check back tomorrow for the next session vote!"
)

SESSION_VOTE_BUTTON = "Vote"
SESSION_VOTERS_BUTTON = "View Voters"
SESSION_JOIN_BUTTON = "Join Now"
SESSION_UNVOTE_BUTTON = "Unvote"
SESSION_CANCEL_BUTTON = "Cancel"

SESSION_ALREADY_VOTED_MESSAGE = (
    "You have already voted for this session.\n\n"
    "Would you like to remove your vote?"
)
SESSION_UNVOTED_MESSAGE = "You have been removed from the session vote."
SESSION_VOTE_KEPT_MESSAGE = "Your vote has been kept."
SESSION_NO_VOTES_MESSAGE = "## Session Voters\n\nNo one has voted yet."
SESSION_ENDED_MESSAGE = "Session ended successfully."
SESSION_CHANNEL_ERROR = "The session channel could not be found."
SESSION_ALREADY_ACTIVE_MESSAGE = "There is already an active session vote."

NO_PERMISSION = "You do not have permission to use this command."

# --------------------------------------------------------------------------------------
# DONT TOUCH ANYTHING BELOW THIS
#---------------------------------------------------------------------------------------

# State

locked_channels = set()
verification_data = {"pending": {}, "linked": {}}
active_session_vote = None
panel_checked = False


# Helpers

def make_view(*components):
    """Build a brand new LayoutView (views can't be shared between messages)."""
    view = ui.LayoutView()
    for component in components:
        view.add_item(component)
    return view


def sep(visible=True):
    return ui.Separator(visible=visible, spacing=discord.SeparatorSpacing.large)


def text_view(text):
    return make_view(ui.Container(ui.TextDisplay(text)))


def notice_view(banner, title, message):
    return make_view(
        ui.Container(
            ui.MediaGallery(discord.MediaGalleryItem(banner)),
            sep(False),
            ui.TextDisplay(f"## {title}\n{message}"),
        )
    )


def join_limited(items, limit, separator=" "):
    """Join items without cutting one in half (keeps role mentions intact)."""
    out = []
    length = 0
    for index, item in enumerate(items):
        added = len(item) + (len(separator) if out else 0)
        if length + added > limit:
            return separator.join(out) + f"\n…and {len(items) - index} more"
        out.append(item)
        length += added
    return separator.join(out)


def has_configured_role(member, role_ids):
    ids = role_ids if isinstance(role_ids, (list, tuple, set)) else [role_ids]
    return any(role.id in ids for role in member.roles)


async def require_perms(interaction: discord.Interaction, *names):
    """Allow administrators or members holding at least one of the named permissions."""
    if not interaction.guild:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return False

    perms = interaction.user.guild_permissions

    if perms.administrator or any(getattr(perms, name) for name in names):
        return True

    await interaction.response.send_message(NO_PERMISSION, ephemeral=True)
    return False


async def require_session_role(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return False

    if (
        interaction.user.guild_permissions.administrator
        or has_configured_role(interaction.user, SESSION_ROLE_ID)
    ):
        return True

    await interaction.response.send_message(NO_PERMISSION, ephemeral=True)
    return False


def invoker_outranks(interaction: discord.Interaction, member: discord.Member):
    guild = interaction.guild

    if member.id == guild.owner_id:
        return False

    if interaction.user.id == guild.owner_id:
        return True

    return interaction.user.top_role > member.top_role


def bot_can_manage_member(guild: discord.Guild, member: discord.Member):
    me = guild.me

    if me is None or member.id == guild.owner_id:
        return False

    return me.top_role > member.top_role


async def find_member(guild: discord.Guild, value: str):
    """Exact matches only: mention, ID, username or display name."""
    value = value.strip()

    mention_match = re.fullmatch(r"<@!?(\d+)>", value)
    if mention_match:
        value = mention_match.group(1)

    if value.isdigit():
        member = guild.get_member(int(value))
        if member:
            return member

        try:
            return await guild.fetch_member(int(value))
        except (discord.NotFound, discord.HTTPException):
            return None

    lowered = value.lower()
    matches = [
        member
        for member in guild.members
        if member.name.lower() == lowered
        or member.display_name.lower() == lowered
    ]

    # Refuse to guess if more than one member matches.
    return matches[0] if len(matches) == 1 else None


async def dm_notice(user, view):
    try:
        return await user.send(view=view)
    except (discord.Forbidden, discord.HTTPException):
        return None


async def undo_dm(message):
    if message is None:
        return
    try:
        await message.delete()
    except discord.HTTPException:
        pass


def format_template(template, guild, member, interaction=None, **extra):
    values = {
        "server-name": guild.name,
        "server-id": guild.id,
        "member": member.name,
        "member-mention": member.mention,
        "member-id": member.id,
    }

    if interaction is not None:
        values.update(
            {
                "moderator": interaction.user.name,
                "moderator-mention": interaction.user.mention,
                "moderator-id": interaction.user.id,
            }
        )

    values.update(extra)
    return template.format(**values)


def clock_text():
    return f"<t:{int(discord.utils.utcnow().timestamp())}:t>"


# Verification data

def load_verification_data():
    global verification_data

    verification_data = {"pending": {}, "linked": {}}

    if not os.path.exists(VERIFICATION_DATA_FILE):
        return

    try:
        with open(VERIFICATION_DATA_FILE, "r") as file:
            raw = json.load(file)
    except Exception:
        return

    if isinstance(raw, dict) and ("pending" in raw or "linked" in raw):
        verification_data["pending"] = raw.get("pending", {})
        verification_data["linked"] = raw.get("linked", {})
    elif isinstance(raw, dict):
        # Legacy format: a flat dict of pending verifications.
        verification_data["pending"] = raw


def save_verification_data():
    with open(VERIFICATION_DATA_FILE, "w") as file:
        json.dump(verification_data, file, indent=4)


def generate_verification_code():
    characters = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code = "".join(secrets.choice(characters) for _ in range(6))
    return f"MSRP-{code}"


ROBLOX_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def get_roblox_user(username):
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": False}

    async with aiohttp.ClientSession(timeout=ROBLOX_TIMEOUT) as session:
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                return None

            data = await response.json()

            if not data.get("data"):
                return None

            return data["data"][0]


async def get_roblox_profile(user_id):
    url = f"https://users.roblox.com/v1/users/{user_id}"

    async with aiohttp.ClientSession(timeout=ROBLOX_TIMEOUT) as session:
        async with session.get(url) as response:
            if response.status != 200:
                return None

            return await response.json()


class VerificationModal(ui.Modal, title=VERIFICATION_TITLE):
    roblox_username = ui.TextInput(
        label="Roblox Username",
        placeholder="Enter your Roblox username...",
        required=True,
        max_length=20,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Roblox calls can take longer than Discord's 3 second limit.
        await interaction.response.defer(ephemeral=True)

        username = self.roblox_username.value.strip()

        try:
            roblox_user = await get_roblox_user(username)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await interaction.followup.send(
                "Roblox could not be reached right now. Please try again later.",
                ephemeral=True,
            )
            return

        if roblox_user is None:
            await interaction.followup.send(
                VERIFICATION_NOT_FOUND_MESSAGE, ephemeral=True
            )
            return

        roblox_id = roblox_user["id"]
        actual_username = roblox_user["name"]
        discord_id = str(interaction.user.id)

        linked_to = verification_data["linked"].get(str(roblox_id))
        if linked_to and linked_to != discord_id:
            await interaction.followup.send(
                "That Roblox account is already linked to another Discord account.",
                ephemeral=True,
            )
            return

        pending = verification_data["pending"].get(discord_id)

        needs_new_code = (
            pending is None
            or pending.get("roblox_id") != roblox_id
            or time.time() - pending.get("created", 0) > VERIFICATION_CODE_LIFETIME
        )

        if needs_new_code:
            code = generate_verification_code()

            verification_data["pending"][discord_id] = {
                "roblox_id": roblox_id,
                "roblox_username": actual_username,
                "code": code,
                "created": time.time(),
            }
            save_verification_data()

            await interaction.followup.send(
                VERIFICATION_CODE_MESSAGE.format(
                    code=code, roblox_username=actual_username
                ),
                ephemeral=True,
            )
            return

        code = pending["code"]

        try:
            profile = await get_roblox_profile(roblox_id)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            profile = None

        if profile is None:
            await interaction.followup.send(
                "I could not retrieve your Roblox profile right now. "
                "Please try again later.",
                ephemeral=True,
            )
            return

        if code not in profile.get("description", ""):
            await interaction.followup.send(
                VERIFICATION_PENDING_MESSAGE.format(code=code), ephemeral=True
            )
            return

        # Roles first: they are what actually grants access.
        verified_role = interaction.guild.get_role(VERIFIED_ROLE_ID)
        old_role = interaction.guild.get_role(UNVERIFIED_ROLE_ID)

        try:
            if verified_role is not None:
                await interaction.user.add_roles(verified_role)

            if old_role is not None and old_role in interaction.user.roles:
                await interaction.user.remove_roles(old_role)

        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(
                "Your Roblox account was verified, but I could not update "
                "your Discord roles. Make sure the bot's highest role is "
                "above the roles it needs to manage.",
                ephemeral=True,
            )
            return

        # The nickname is best effort (it always fails for the server owner).
        nickname_changed = True
        try:
            await interaction.user.edit(nick=actual_username)
        except (discord.Forbidden, discord.HTTPException):
            nickname_changed = False

        verification_data["linked"][str(roblox_id)] = discord_id
        verification_data["pending"].pop(discord_id, None)
        save_verification_data()

        if nickname_changed:
            message = VERIFICATION_SUCCESS_MESSAGE.format(
                roblox_username=actual_username
            )
        else:
            message = (
                "### Verification Successful\n\n"
                "Your Roblox account has been verified, but I could not "
                f"change your nickname. Please set it to **{actual_username}** "
                "yourself."
            )

        await interaction.followup.send(message, ephemeral=True)


class VerificationButton(ui.Button):
    def __init__(self):
        super().__init__(
            label="Verify",
            style=discord.ButtonStyle.secondary,
            custom_id="verification_button",
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(VerificationModal())


class VerificationView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(
            ui.Container(
                ui.MediaGallery(discord.MediaGalleryItem(VERIFICATION_BANNER)),
                sep(),
                ui.TextDisplay(VERIFICATION_PANEL_MESSAGE),
                sep(),
                ui.ActionRow(VerificationButton()),
            )
        )


async def setup_verification_panel():
    channel = bot.get_channel(VERIFICATION_CHANNEL_ID)

    if channel is None:
        print("ERROR: Verification channel was not found.")
        return

    try:
        async for message in channel.history(limit=100):
            if message.author.id == bot.user.id and message.components:
                print(f"Existing verification panel kept: {message.id}")
                return

    except (discord.Forbidden, discord.HTTPException) as error:
        print(f"Failed to check verification panel: {error}")
        return

    try:
        message = await channel.send(
            view=VerificationView(),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        print(f"New verification panel sent: {message.id}")

    except discord.Forbidden:
        print("ERROR: I cannot send the verification panel.")

    except discord.HTTPException as error:
        print(f"Failed to send verification panel: {error}")


async def send_ghost_ping(channel):
    try:
        ping_message = await channel.send(
            content="@everyone @here",
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        await ping_message.delete()
    except discord.HTTPException:
        pass


# Session persistence

def save_session_data():
    if active_session_vote is None:
        if os.path.exists(SESSION_DATA_FILE):
            os.remove(SESSION_DATA_FILE)
        return

    with open(SESSION_DATA_FILE, "w") as file:
        json.dump(
            {
                "channel_id": active_session_vote.channel_id,
                "message_id": active_session_vote.message_id,
                "voters": active_session_vote.voters,
            },
            file,
            indent=4,
        )


def restore_session_vote():
    global active_session_vote

    if not os.path.exists(SESSION_DATA_FILE):
        return

    try:
        with open(SESSION_DATA_FILE, "r") as file:
            data = json.load(file)

        view = SessionVoteView(
            voters=data["voters"],
            channel_id=data["channel_id"],
            message_id=data["message_id"],
        )
        bot.add_view(view, message_id=data["message_id"])
        active_session_vote = view

    except Exception as error:
        print(f"Could not restore session vote: {error}")


# Events

@bot.event
async def setup_hook():
    load_verification_data()

    # Persistent views are registered once, before the bot connects.
    bot.add_view(VerificationView())
    restore_session_vote()

    if SYNC_COMMANDS:
        await bot.tree.sync()


@bot.event
async def on_ready():
    global panel_checked

    print(f"Logged in as {bot.user}")

    # on_ready can fire again after reconnects; only check the panel once.
    if not panel_checked:
        panel_checked = True
        await setup_verification_panel()


@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)

    if channel is None:
        return

    message = format_template(WELCOME_MESSAGE, member.guild, member)

    await channel.send(message, allowed_mentions=discord.AllowedMentions(users=True))


# General commands

@bot.tree.command(name="ping", description="Check the bot's latency.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        view=text_view(f"## Pong!\nLatency: `{round(bot.latency * 1000)}ms`")
    )


userinfo = app_commands.Group(
    name="user", description="Info commands", guild_only=True
)


@userinfo.command(name="info", description="View information about a user.")
@app_commands.describe(member="The user you want to view.")
async def user_info(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    guild = interaction.guild

    role_mentions = [
        role.mention for role in reversed(member.roles) if role.name != "@everyone"
    ]
    role_text = join_limited(role_mentions, 600)

    permissions = [
        permission.replace("_", " ").title()
        for permission, enabled in member.guild_permissions
        if enabled
    ]
    permission_text = join_limited(permissions, 600, ", ")

    flags = member.public_flags
    badge_map = [
        (flags.hypesquad_balance, "HypeSquad Balance"),
        (flags.hypesquad_bravery, "HypeSquad Bravery"),
        (flags.hypesquad_brilliance, "HypeSquad Brilliance"),
        (flags.staff, "Discord Staff"),
        (flags.active_developer, "Active Developer"),
        (flags.bug_hunter, "Bug Hunter"),
        (flags.bug_hunter_level_2, "Bug Hunter Level 2"),
        (flags.verified_bot_developer, "Verified Bot Developer"),
    ]
    badges = [name for enabled, name in badge_map if enabled]
    badge_text = "\n".join(badges) if badges else "No Badges"

    if guild.owner_id == member.id:
        permission_title = "Server Owner"
    elif member.guild_permissions.administrator:
        permission_title = "Administrator"
    else:
        permission_title = "Member"

    joined_at = (
        f"<t:{int(member.joined_at.timestamp())}:F> "
        f"(<t:{int(member.joined_at.timestamp())}:R>)"
        if member.joined_at
        else "Unknown"
    )
    created_at = (
        f"<t:{int(member.created_at.timestamp())}:F> "
        f"(<t:{int(member.created_at.timestamp())}:R>)"
    )

    view = make_view(
        ui.Container(
            ui.TextDisplay(f"## {member.display_name}\n{badge_text}"),
            sep(),
            ui.TextDisplay(
                "## User Information\n"
                f"**Mention:** {member.mention}\n"
                f"**Display Name:** {member.display_name}\n"
                f"**Username:** {member}\n"
                f"**Joined Server:** {joined_at}\n"
                f"**Account Created:** {created_at}"
            ),
            sep(),
            ui.TextDisplay(
                f"## Roles [{len(role_mentions)}]\n{role_text or 'No Roles'}"
            ),
        ),
        ui.Container(
            ui.TextDisplay(
                f"## Permissions - {permission_title}\n"
                f"{permission_text or 'No Special Permissions.'}"
            ),
            sep(),
            ui.TextDisplay(
                "## Account Details\n"
                f"**Bot:** {'Yes' if member.bot else 'No'}\n"
                f"**Nickname:** {member.nick or 'None'}\n"
                f"**Top Role:** {member.top_role.mention}\n"
                f"**Highest Role Position:** {member.top_role.position}"
            ),
            sep(),
            ui.TextDisplay(f"-# User ID: {member.id} • Today at {clock_text()}"),
        ),
    )

    await interaction.response.send_message(view=view)


@userinfo.command(name="avatar", description="View a users profile picture.")
@app_commands.describe(user="The member whose avatar you want to view.")
async def avatar(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user

    embed = discord.Embed()
    embed.set_image(url=user.display_avatar.url)

    await interaction.response.send_message(embed=embed)


@userinfo.command(name="banner", description="View a users banner.")
@app_commands.describe(user="The member whose banner you want to view.")
async def banner(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user

    try:
        fetched_user = await bot.fetch_user(user.id)
    except (discord.NotFound, discord.HTTPException):
        await interaction.response.send_message(
            "I couldn't retrieve that user's Discord profile.", ephemeral=True
        )
        return

    if fetched_user.banner is None:
        await interaction.response.send_message(
            "That member does not have a Discord banner.", ephemeral=True
        )
        return

    embed = discord.Embed()
    embed.set_image(url=fetched_user.banner.url)

    await interaction.response.send_message(embed=embed)


bot.tree.add_command(userinfo)


serverinfo = app_commands.Group(
    name="server", description="Info commands", guild_only=True
)


@serverinfo.command(name="info", description="Get information about the server.")
async def server_info(interaction: discord.Interaction):
    guild = interaction.guild

    rules = guild.rules_channel.mention if guild.rules_channel else "None"
    system = guild.system_channel.mention if guild.system_channel else "None"

    role_list = [
        role.mention for role in reversed(guild.roles) if role.name != "@everyone"
    ]
    role_text = join_limited(role_list, 500)

    emoji_text = join_limited([str(emoji) for emoji in guild.emojis], 300)

    feature_list = [f.replace("_", " ").title() for f in guild.features]
    feature_text = join_limited(feature_list, 300, "\n") or "No special features."

    verification = guild.verification_level.name.replace("_", " ").title()
    content_filter = guild.explicit_content_filter.name.replace("_", " ").title()
    mfa_level = guild.mfa_level.name.replace("_", " ").title()

    member_gate = (
        "Enabled"
        if guild.verification_level != discord.VerificationLevel.none
        else "Disabled"
    )

    owner = guild.owner.mention if guild.owner else f"<@{guild.owner_id}>"

    view = make_view(
        ui.Container(
            ui.TextDisplay(
                "## Basic Information\n"
                f"**Name:** {guild.name}\n"
                f"**Owner:** {owner}\n"
                f"**Created:** <t:{int(guild.created_at.timestamp())}:F>\n"
                f"**Members:** {guild.member_count}\n"
                f"**Nitro Boosts:** {guild.premium_subscription_count}"
            ),
            sep(),
            ui.TextDisplay(
                "## Security\n"
                f"**2FA Settings:** {mfa_level}\n"
                f"**Verification Level:** {verification}\n"
                f"**Explicit Content Filter:** {content_filter}\n"
                f"**Member Verification Gate:** {member_gate}"
            ),
            sep(),
            ui.TextDisplay(
                "## Server Configuration\n"
                f"**System Messages Channel:** {system}\n"
                f"**Rules Channel:** {rules}"
            ),
            sep(),
            ui.TextDisplay(
                f"## Channels [{len(guild.channels)}]\n"
                f"**Category:** {len(guild.categories)}\n"
                f"**Text:** {len(guild.text_channels)}\n"
                f"**Voice:** {len(guild.voice_channels)}"
            ),
        ),
        ui.Container(
            ui.TextDisplay(f"## Roles [{len(role_list)}]\n{role_text or 'None'}"),
            sep(),
            ui.TextDisplay(
                f"## Emojis [{len(guild.emojis)}]\n{emoji_text or 'No emojis.'}"
            ),
            sep(),
            ui.TextDisplay(f"## Features\n{feature_text}"),
            sep(),
            ui.TextDisplay(f"-# Server ID: {guild.id} • Today at {clock_text()}"),
        ),
    )

    await interaction.response.send_message(view=view)


bot.tree.add_command(serverinfo)


@bot.tree.command(name="say", description="Make the bot say a message.")
@app_commands.describe(message="The message you want the bot to send.")
@app_commands.guild_only()
async def say(interaction: discord.Interaction, message: str):
    if not has_configured_role(interaction.user, SAY_ROLE_ID):
        await interaction.response.send_message(NO_PERMISSION, ephemeral=True)
        return

    await interaction.response.send_message("Message sent!", ephemeral=True)

    await interaction.channel.send(
        message, allowed_mentions=discord.AllowedMentions.none()
    )


purge = app_commands.Group(
    name="purge", description="Purge commands.", guild_only=True
)


@purge.command(name="any", description="Bulk delete messages.")
@app_commands.describe(amount="Number of messages to delete.")
async def purge_any(interaction: discord.Interaction, amount: int):
    if not has_configured_role(interaction.user, PURGE_ROLE_ID):
        await interaction.response.send_message(NO_PERMISSION, ephemeral=True)
        return

    if amount < 1 or amount > 100:
        await interaction.response.send_message(
            "Amount must be between 1 and 100.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        deleted = await interaction.channel.purge(limit=amount)

    except discord.Forbidden:
        await interaction.followup.send(
            "I don't have permission to delete messages in this channel.",
            ephemeral=True,
        )
        return

    except discord.HTTPException:
        await interaction.followup.send(
            "Discord rejected the message deletion request.", ephemeral=True
        )
        return

    await interaction.followup.send(
        view=text_view(
            "## Messages Purged\n"
            "Successfully purged messages from this channel.\n\n"
            f"➤ **Amount:** {len(deleted)}\n"
            f"➤ **Channel:** {interaction.channel.mention}\n"
            f"➤ **Moderator:** {interaction.user.mention}"
        ),
        ephemeral=True,
    )


bot.tree.add_command(purge)


# Moderation

@bot.tree.command(name="kick", description="Kick a user.")
@app_commands.describe(user="The user you want to kick.", reason="The reason for the kick.")
@app_commands.guild_only()
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not await require_perms(interaction, "kick_members"):
        return

    if user.id == interaction.user.id:
        await interaction.response.send_message("You cannot kick yourself.", ephemeral=True)
        return

    if not invoker_outranks(interaction, user):
        await interaction.response.send_message(
            "You cannot kick someone with a role equal to or higher than yours.",
            ephemeral=True,
        )
        return

    if not bot_can_manage_member(interaction.guild, user):
        await interaction.response.send_message(
            "I cannot kick that user because their highest role is equal to or "
            "higher than my highest role.",
            ephemeral=True,
        )
        return

    message = format_template(
        KICK_MESSAGE, interaction.guild, user, interaction, reason=reason
    )

    # DM first (a kicked user may no longer be reachable), but take it back
    # if the kick itself fails.
    dm = await dm_notice(user, notice_view(KICK_BANNER, "Kicked", message))

    try:
        await user.kick(reason=f"{reason} (by {interaction.user})")

    except discord.Forbidden:
        await undo_dm(dm)
        await interaction.response.send_message(
            "I don't have permission to kick that user.", ephemeral=True
        )
        return

    except discord.HTTPException:
        await undo_dm(dm)
        await interaction.response.send_message(
            "Discord rejected the kick request. Please try again.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        view=notice_view(KICK_BANNER, "Kicked", message), ephemeral=True
    )


@bot.tree.command(name="ban", description="Ban a user.")
@app_commands.describe(
    user="Username, mention, or ID of the user you want to ban.",
    reason="The reason for the ban.",
)
@app_commands.guild_only()
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, user: str, reason: str):
    if not await require_perms(interaction, "ban_members"):
        return

    member = await find_member(interaction.guild, user)

    if member is None:
        await interaction.response.send_message(
            "I could not find exactly one user matching that. "
            "Try their mention or ID.",
            ephemeral=True,
        )
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("You cannot ban yourself.", ephemeral=True)
        return

    if not invoker_outranks(interaction, member):
        await interaction.response.send_message(
            "You cannot ban someone with a role equal to or higher than yours.",
            ephemeral=True,
        )
        return

    if not bot_can_manage_member(interaction.guild, member):
        await interaction.response.send_message(
            "I cannot ban that user because their highest role is equal to or "
            "higher than my highest role.",
            ephemeral=True,
        )
        return

    message = format_template(
        BAN_MESSAGE, interaction.guild, member, interaction, reason=reason
    )

    dm = await dm_notice(member, notice_view(BAN_BANNER, "Banned", message))

    try:
        await member.ban(reason=f"{reason} (by {interaction.user})")

    except discord.Forbidden:
        await undo_dm(dm)
        await interaction.response.send_message(
            "I don't have permission to ban that user.", ephemeral=True
        )
        return

    except discord.HTTPException:
        await undo_dm(dm)
        await interaction.response.send_message(
            "Discord rejected the ban request. Please try again.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        view=notice_view(BAN_BANNER, "Banned", message), ephemeral=True
    )


@bot.tree.command(name="unban", description="Unban a user.")
@app_commands.describe(user_id="The ID of the user you want to unban.")
@app_commands.guild_only()
@app_commands.default_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    if not await require_perms(interaction, "ban_members"):
        return

    try:
        user = await bot.fetch_user(int(user_id))
    except (ValueError, discord.NotFound, discord.HTTPException):
        await interaction.response.send_message(
            "I could not find that user.", ephemeral=True
        )
        return

    try:
        await interaction.guild.unban(user, reason=f"Unbanned by {interaction.user}")

    except discord.NotFound:
        await interaction.response.send_message("That user is not banned.", ephemeral=True)
        return

    except discord.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to unban that user.", ephemeral=True
        )
        return

    except discord.HTTPException:
        await interaction.response.send_message(
            "Discord rejected the unban request. Please try again.", ephemeral=True
        )
        return

    message = format_template(UNBAN_MESSAGE, interaction.guild, user, interaction)

    await interaction.response.send_message(
        view=notice_view(UNBAN_BANNER, "Un-banned", message), ephemeral=True
    )


@bot.tree.command(name="mute", description="Mute a user.")
@app_commands.describe(
    user="The user you want to mute.",
    duration="Mute duration in minutes.",
    reason="The reason for the mute.",
)
@app_commands.guild_only()
@app_commands.default_permissions(moderate_members=True)
async def mute(
    interaction: discord.Interaction,
    user: discord.Member,
    duration: int,
    reason: str,
):
    if not await require_perms(interaction, "moderate_members"):
        return

    if user.id == interaction.user.id:
        await interaction.response.send_message("You cannot mute yourself.", ephemeral=True)
        return

    if not invoker_outranks(interaction, user):
        await interaction.response.send_message(
            "You cannot mute a user with an equal or higher role.", ephemeral=True
        )
        return

    if not bot_can_manage_member(interaction.guild, user):
        await interaction.response.send_message(
            "I cannot mute that user because their highest role is equal to or "
            "higher than my highest role.",
            ephemeral=True,
        )
        return

    if duration < 1 or duration > MAX_MUTE_MINUTES:
        await interaction.response.send_message(
            f"Duration must be between 1 and {MAX_MUTE_MINUTES} minutes (28 days).",
            ephemeral=True,
        )
        return

    timeout_until = discord.utils.utcnow() + timedelta(minutes=duration)

    try:
        await user.timeout(timeout_until, reason=f"{reason} (by {interaction.user})")

    except discord.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to mute that user.", ephemeral=True
        )
        return

    except discord.HTTPException:
        await interaction.response.send_message(
            "Discord rejected the mute request. Please try again.", ephemeral=True
        )
        return

    message = format_template(
        MUTE_MESSAGE, interaction.guild, user, interaction,
        reason=reason, duration=duration,
    )

    await dm_notice(user, notice_view(MUTE_BANNER, "Muted", message))

    await interaction.response.send_message(
        view=notice_view(MUTE_BANNER, "Muted", message)
    )


@bot.tree.command(name="unmute", description="Unmute a user.")
@app_commands.describe(user="The user you want to unmute.")
@app_commands.guild_only()
@app_commands.default_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, user: discord.Member):
    if not await require_perms(interaction, "moderate_members"):
        return

    if user.id != interaction.user.id and not invoker_outranks(interaction, user):
        await interaction.response.send_message(
            "You cannot unmute a user with an equal or higher role.", ephemeral=True
        )
        return

    if user.id != interaction.user.id and not bot_can_manage_member(
        interaction.guild, user
    ):
        await interaction.response.send_message(
            "I cannot unmute that user because their highest role is equal to or "
            "higher than my highest role.",
            ephemeral=True,
        )
        return

    try:
        await user.timeout(None, reason=f"Unmuted by {interaction.user}")

    except discord.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to unmute that user.", ephemeral=True
        )
        return

    except discord.HTTPException:
        await interaction.response.send_message(
            "Discord rejected the unmute request. Please try again.", ephemeral=True
        )
        return

    message = format_template(UNMUTE_MESSAGE, interaction.guild, user, interaction)

    await interaction.response.send_message(
        view=notice_view(UNMUTE_BANNER, "Un-muted", message)
    )


@bot.tree.command(name="nick", description="Change or clear a user's nickname.")
@app_commands.describe(
    user="The user whose nickname you want to change.",
    nickname="The new nickname. Leave blank to clear it.",
)
@app_commands.guild_only()
@app_commands.default_permissions(manage_nicknames=True)
async def nick(interaction: discord.Interaction, user: discord.Member, nickname: str = None):
    if not await require_perms(interaction, "manage_nicknames"):
        return

    if user.id != interaction.user.id and not invoker_outranks(interaction, user):
        await interaction.response.send_message(
            "You cannot change the nickname of a user with an equal or higher role.",
            ephemeral=True,
        )
        return

    if user.id != interaction.user.id and not bot_can_manage_member(
        interaction.guild, user
    ):
        await interaction.response.send_message(
            "I cannot change that user's nickname because their highest role is "
            "equal to or higher than my highest role.",
            ephemeral=True,
        )
        return

    try:
        await user.edit(nick=nickname)

    except discord.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to change that user's nickname.", ephemeral=True
        )
        return

    except discord.HTTPException:
        await interaction.response.send_message(
            "Discord rejected the nickname change. Please try again.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        view=text_view(
            "## Nickname Updated\n"
            f"The nickname for {user.mention} has been updated.\n\n"
            f"➤ **User:** {user.mention}\n"
            f"➤ **Nickname:** {nickname or 'Cleared'}\n"
            f"➤ **Moderator:** {interaction.user.mention}"
        )
    )


@bot.tree.command(name="lock", description="Lock a channel.")
@app_commands.describe(channel="The channel you want to lock.")
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction, channel: discord.TextChannel):
    if not await require_perms(interaction, "manage_channels"):
        return

    try:
        await channel.set_permissions(
            interaction.guild.default_role, send_messages=False
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to lock that channel.", ephemeral=True
        )
        return

    except discord.HTTPException:
        await interaction.response.send_message(
            "Discord rejected the channel permission change.", ephemeral=True
        )
        return

    locked_channels.add(channel.id)

    await interaction.response.send_message(
        view=text_view(
            "## Channel Locked\n"
            f"{channel.mention} has been locked by {interaction.user.mention}"
        )
    )


@bot.tree.command(name="unlock", description="Unlock a channel.")
@app_commands.describe(channel="The channel you want to unlock.")
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction, channel: discord.TextChannel):
    if not await require_perms(interaction, "manage_channels"):
        return

    try:
        # None removes the override instead of creating an explicit "allow".
        await channel.set_permissions(
            interaction.guild.default_role, send_messages=None
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to unlock that channel.", ephemeral=True
        )
        return

    except discord.HTTPException:
        await interaction.response.send_message(
            "Discord rejected the channel permission change.", ephemeral=True
        )
        return

    locked_channels.discard(channel.id)

    await interaction.response.send_message(
        view=text_view(
            "## Channel Un-Locked\n"
            f"{channel.mention} has been un-locked by {interaction.user.mention}"
        )
    )


@bot.tree.command(name="locked", description="List temporarily locked channels.")
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
async def locked_channels_command(interaction: discord.Interaction):
    if not await require_perms(interaction, "manage_channels"):
        return

    channels = []

    for channel_id in locked_channels:
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            channels.append(channel.mention)

    channel_text = "\n".join(channels) if channels else "No channels are currently locked."

    await interaction.response.send_message(
        view=text_view(f"## Locked Channels\n{channel_text}"), ephemeral=True
    )


roles_group = app_commands.Group(
    name="roles", description="Role commands.", guild_only=True
)


@roles_group.command(name="all", description="List or search server roles.")
@app_commands.describe(
    user="View the roles of a specific user.",
    search="Search for a specific role.",
)
async def roles_all(
    interaction: discord.Interaction,
    user: discord.Member = None,
    search: str = None,
):
    if not await require_perms(interaction, "manage_roles"):
        return

    guild = interaction.guild

    if user:
        found = [
            role.mention
            for role in reversed(user.roles)
            if role != guild.default_role
        ]
        text = "\n".join(found) if found else "This user has no roles."
        title = f"## Roles - {user.display_name}"

    elif search:
        found = [
            role.mention
            for role in guild.roles
            if search.lower() in role.name.lower()
        ]
        text = "\n".join(found) if found else "No roles found."
        title = "## Role Search"

    else:
        found = [
            role.mention
            for role in reversed(guild.roles)
            if role != guild.default_role
        ]
        text = "\n".join(found) if found else "No roles found."
        title = "## Server Roles"

    if len(text) > 3500:
        text = join_limited(found, 3500, "\n")

    await interaction.response.send_message(
        view=text_view(f"{title}\n{text}"), ephemeral=True
    )


bot.tree.add_command(roles_group)


@bot.tree.command(name="help", description="View all available bot commands.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot Commands", description="Here are all available commands:"
    )

    commands_list = sorted(bot.tree.get_commands(), key=lambda command: command.name)

    for command in commands_list:
        if isinstance(command, app_commands.Group):
            for subcommand in command.commands:
                embed.add_field(
                    name=f"/{command.name} {subcommand.name}",
                    value=subcommand.description or "No description provided.",
                    inline=False,
                )
        else:
            embed.add_field(
                name=f"/{command.name}",
                value=command.description or "No description provided.",
                inline=False,
            )

    if interaction.guild:
        embed.set_footer(text=f"{interaction.guild.name} • Help")

    await interaction.response.send_message(embed=embed)


# Sessions

class UnvoteConfirmation(discord.ui.View):
    def __init__(self, vote_view):
        super().__init__(timeout=30)
        self.vote_view = vote_view

    @discord.ui.button(label=SESSION_UNVOTE_BUTTON, style=discord.ButtonStyle.secondary)
    async def confirm_unvote(self, interaction, button):
        if interaction.user.id in self.vote_view.voters:
            self.vote_view.voters.remove(interaction.user.id)
            save_session_data()

        self.vote_view.update_vote_button()

        await interaction.response.edit_message(
            content=SESSION_UNVOTED_MESSAGE, view=None
        )

        message = self.vote_view.message
        if message:
            try:
                await message.edit(view=self.vote_view)
            except discord.HTTPException:
                pass

    @discord.ui.button(label=SESSION_CANCEL_BUTTON, style=discord.ButtonStyle.secondary)
    async def cancel_unvote(self, interaction, button):
        await interaction.response.edit_message(
            content=SESSION_VOTE_KEPT_MESSAGE, view=None
        )


class SessionVoteView(discord.ui.LayoutView):
    def __init__(self, voters=None, channel_id=None, message_id=None):
        super().__init__(timeout=None)

        self.voters = list(voters or [])
        self.channel_id = channel_id
        self.message_id = message_id
        self.session_started = False

        self.vote_button = discord.ui.Button(
            label=f"{SESSION_VOTE_BUTTON} ({len(self.voters)})",
            custom_id="session_vote_button",
            style=discord.ButtonStyle.secondary,
        )
        self.voters_button = discord.ui.Button(
            label=SESSION_VOTERS_BUTTON,
            custom_id="session_view_voters",
            style=discord.ButtonStyle.secondary,
        )

        self.vote_button.callback = self.vote_callback
        self.voters_button.callback = self.view_voters_callback

        self.add_item(
            discord.ui.Container(
                discord.ui.MediaGallery(discord.MediaGalleryItem(SESSION_TOP_BANNER)),
                sep(),
                discord.ui.TextDisplay(
                    f"{SESSION_VOTE_TITLE}\n{SESSION_VOTE_MESSAGE}"
                ),
                sep(),
                discord.ui.ActionRow(self.vote_button, self.voters_button),
                sep(),
                discord.ui.MediaGallery(discord.MediaGalleryItem(SESSION_BOTTOM_BANNER)),
            )
        )

    @property
    def message(self):
        if self.channel_id is None or self.message_id is None:
            return None

        channel = bot.get_channel(self.channel_id)
        if channel is None:
            return None

        return channel.get_partial_message(self.message_id)

    def update_vote_button(self):
        self.vote_button.label = f"{SESSION_VOTE_BUTTON} ({len(self.voters)})"

    async def vote_callback(self, interaction: discord.Interaction):
        global active_session_vote

        user_id = interaction.user.id

        if user_id in self.voters:
            await interaction.response.send_message(
                SESSION_ALREADY_VOTED_MESSAGE,
                ephemeral=True,
                view=UnvoteConfirmation(self),
            )
            return

        self.voters.append(user_id)
        save_session_data()
        self.update_vote_button()

        await interaction.response.edit_message(view=self)

        if len(self.voters) < REQUIRED_SESSION_VOTES or self.session_started:
            return

        self.session_started = True

        voter_mentions = " ".join(f"<@{voter}>" for voter in self.voters)

        session_view = make_view(
            discord.ui.Container(
                discord.ui.MediaGallery(discord.MediaGalleryItem(SESSION_TOP_BANNER)),
                sep(),
                discord.ui.TextDisplay(
                    f"{SESSION_START_TITLE}\n{SESSION_START_MESSAGE}\n\n{voter_mentions}"
                ),
                sep(),
                discord.ui.ActionRow(
                    discord.ui.Button(
                        label=SESSION_JOIN_BUTTON,
                        style=discord.ButtonStyle.link,
                        url=JOIN_URL,
                    )
                ),
                sep(),
                discord.ui.MediaGallery(discord.MediaGalleryItem(SESSION_BOTTOM_BANNER)),
            )
        )

        channel = interaction.guild.get_channel(SESSION_CHANNEL)

        if channel:
            await channel.send(view=session_view)
            await send_ghost_ping(channel)

        message = self.message
        if message:
            try:
                await message.delete()
            except discord.HTTPException:
                pass

        if active_session_vote is self:
            active_session_vote = None
            save_session_data()

    async def view_voters_callback(self, interaction: discord.Interaction):
        if not self.voters:
            await interaction.response.send_message(
                SESSION_NO_VOTES_MESSAGE, ephemeral=True
            )
            return

        voter_list = [
            f"**{number}.** <@{voter}>"
            for number, voter in enumerate(self.voters, start=1)
        ]

        await interaction.response.send_message(
            "## Session Voters\n\n" + join_limited(voter_list, 3500, "\n"),
            ephemeral=True,
        )


session = app_commands.Group(
    name="session", description="Session commands", guild_only=True
)


@session.command(name="vote", description="Host a session vote")
async def session_vote(interaction: discord.Interaction):
    global active_session_vote

    if not await require_session_role(interaction):
        return

    if active_session_vote is not None:
        await interaction.response.send_message(
            SESSION_ALREADY_ACTIVE_MESSAGE, ephemeral=True
        )
        return

    vote_view = SessionVoteView()

    # Claim the slot before awaiting so two simultaneous commands can't both pass.
    active_session_vote = vote_view

    try:
        await interaction.response.send_message(view=vote_view)
        sent = await interaction.original_response()
    except discord.HTTPException:
        active_session_vote = None
        return

    vote_view.channel_id = sent.channel.id
    vote_view.message_id = sent.id
    save_session_data()

    await send_ghost_ping(interaction.channel)


@session.command(name="end", description="Ends a session")
async def session_end(interaction: discord.Interaction):
    global active_session_vote

    if not await require_session_role(interaction):
        return

    if active_session_vote is not None:
        message = active_session_vote.message

        if message:
            try:
                await message.delete()
            except discord.HTTPException:
                pass

        active_session_vote = None
        save_session_data()

    view = make_view(
        discord.ui.Container(
            discord.ui.MediaGallery(discord.MediaGalleryItem(SESSION_TOP_BANNER)),
            sep(),
            discord.ui.TextDisplay(f"{SESSION_END_TITLE}\n{SESSION_END_MESSAGE}"),
            sep(),
            discord.ui.MediaGallery(discord.MediaGalleryItem(SESSION_BOTTOM_BANNER)),
        )
    )

    channel = interaction.guild.get_channel(SESSION_CHANNEL)

    if channel:
        await channel.send(view=view)
        await interaction.response.send_message(SESSION_ENDED_MESSAGE, ephemeral=True)
    else:
        await interaction.response.send_message(SESSION_CHANNEL_ERROR, ephemeral=True)


@session.command(name="start", description="Starts a session")
async def session_start(interaction: discord.Interaction):
    if not await require_session_role(interaction):
        return

    view = make_view(
        discord.ui.Container(
            discord.ui.MediaGallery(discord.MediaGalleryItem(SESSION_TOP_BANNER)),
            sep(),
            discord.ui.Section(
                f"{SESSION_START_TITLE}\n{SESSION_START_MESSAGE}",
                accessory=discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    url=JOIN_URL,
                    label=SESSION_JOIN_BUTTON,
                ),
            ),
            sep(),
            discord.ui.MediaGallery(discord.MediaGalleryItem(SESSION_BOTTOM_BANNER)),
        )
    )

    await interaction.response.send_message(view=view)
    await send_ghost_ping(interaction.channel)


bot.tree.add_command(session)


bot.run(TOKEN)
