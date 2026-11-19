import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands, tasks

DATA_FILE = Path("/data/config.json")

def load() -> dict:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {}

def save(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def get_cfg(guild_id: int) -> dict:
    return load().get(str(guild_id), {}).get("activity", {})

class ActivityRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_activity.start()

    def cog_unload(self):
        self.check_activity.cancel()

    @app_commands.command(name="activitysetup", description="Set role + channels that count for weekly messages")
    @app_commands.describe(
        role="Role to give/remove",
        required="Messages needed in the last 7 days",
        channels="Channels that count (mention them)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def activitysetup(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        required: app_commands.Range[int, 1, 500] = 50,
        channels: str = "",
    ):
        channel_ids = []
        for part in channels.split():
            if part.startswith("<#") and part.endswith(">"):
                try:
                    channel_ids.append(int(part[2:-1]))
                except:
                    pass

        if not channel_ids:
            return await interaction.response.send_message(
                "Mention at least one channel that should count (e.g. #general #chat).",
                ephemeral=True,
            )

        data = load()
        g = str(interaction.guild_id)
        data.setdefault(g, {})["activity"] = {
            "role_id": role.id,
            "required": required,
            "channels": channel_ids,
            "messages": {},
        }
        save(data)

        ch_mentions = " ".join(f"<#{cid}>" for cid in channel_ids)
        await interaction.response.send_message(
            f"Activity role set.\n"
            f"**Role:** {role.mention}\n"
            f"**Required:** {required} messages / 7 days\n"
            f"**Channels:** {ch_mentions}",
            ephemeral=True,
        )

    @app_commands.command(name="activitybackfill", description="Scan recent messages to count this week's activity")
    @app_commands.describe(days="How many days back to scan (max 7)")
    @app_commands.checks.has_permissions(administrator=True)
    async def activitybackfill(self, interaction: discord.Interaction, days: app_commands.Range[int, 1, 7] = 7):
        cfg = get_cfg(interaction.guild_id)
        if not cfg:
            return await interaction.response.send_message("Run /activitysetup first.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        data = load()
        g = str(interaction.guild_id)
        activity = data.setdefault(g, {}).setdefault("activity", {})
        msgs = activity.setdefault("messages", {})

        counted = 0
        for channel_id in cfg.get("channels", []):
            channel = interaction.guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue
            try:
                async for message in channel.history(limit=1000, after=cutoff):
                    if message.author.bot:
                        continue
                    uid = str(message.author.id)
                    ts = message.created_at.isoformat()
                    msgs.setdefault(uid, []).append(ts)
                    counted += 1
            except discord.Forbidden:
                continue

        clean_cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        for uid in list(msgs.keys()):
            msgs[uid] = [t for t in msgs[uid] if datetime.fromisoformat(t) > clean_cutoff]

        save(data)
        await interaction.followup.send(
            f"Backfill done. Counted **{counted}** messages from the last {days} day(s).",
            ephemeral=True,
        )

    @app_commands.command(name="activitycheck", description="Force an activity role check right now")
    @app_commands.checks.has_permissions(administrator=True)
    async def activitycheck(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.check_activity()
        await interaction.followup.send("Activity check finished.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        cfg = get_cfg(message.guild.id)
        if not cfg or message.channel.id not in cfg.get("channels", []):
            return

        data = load()
        g = str(message.guild.id)
        activity = data.setdefault(g, {}).setdefault("activity", {})
        msgs = activity.setdefault("messages", {})
        uid = str(message.author.id)
        now = datetime.now(timezone.utc).isoformat()
        msgs.setdefault(uid, []).append(now)
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        msgs[uid] = [t for t in msgs[uid] if datetime.fromisoformat(t) > cutoff]
        save(data)

    @tasks.loop(minutes=30)
    async def check_activity(self):
        data = load()
        for gid_str, guild_data in data.items():
            cfg = guild_data.get("activity")
            if not cfg:
                continue
            guild = self.bot.get_guild(int(gid_str))
            if not guild:
                continue
            role = guild.get_role(cfg.get("role_id"))
            if not role:
                continue
            required = cfg.get("required", 50)
            msgs = cfg.get("messages", {})
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)

            for member in guild.members:
                if member.bot:
                    continue
                timestamps = msgs.get(str(member.id), [])
                recent = sum(1 for t in timestamps if datetime.fromisoformat(t) > cutoff)
                has_role = role in member.roles
                if recent >= required and not has_role:
                    try:
                        await member.add_roles(role, reason="Activity role")
                    except:
                        pass
                elif recent < required and has_role:
                    try:
                        await member.remove_roles(role, reason="Activity role expired")
                    except:
                        pass

    @check_activity.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityRole(bot))