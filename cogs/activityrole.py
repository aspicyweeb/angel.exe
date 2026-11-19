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

    @app_commands.command(name="activitysetup", description="Set the activity role + who gets tracked")
    @app_commands.describe(
        role="Role that unlocks the locked channels",
        track_role="Only manage people who already have this role",
        required="Messages needed in the last 7 days",
        channels="Channels that count (mention them)",
        exempt_roles="Roles that always keep the activity role",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def activitysetup(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        track_role: discord.Role,
        required: app_commands.Range[int, 1, 500] = 40,
        channels: str = "",
        exempt_roles: str = "",
    ):
        channel_ids = []
        for part in channels.split():
            if part.startswith("<#") and part.endswith(">"):
                try:
                    channel_ids.append(int(part[2:-1]))
                except:
                    pass

        if not channel_ids:
            return await interaction.response.send_message("Mention at least one channel.", ephemeral=True)

        exempt_ids = []
        for part in exempt_roles.split():
            if part.startswith("<@&") and part.endswith(">"):
                try:
                    exempt_ids.append(int(part[3:-1]))
                except:
                    pass

        data = load()
        g = str(interaction.guild_id)
        data.setdefault(g, {})["activity"] = {
            "role_id": role.id,
            "track_role_id": track_role.id,
            "required": required,
            "channels": channel_ids,
            "exempt_roles": exempt_ids,
            "messages": {},
        }
        save(data)

        ch_mentions = " ".join(f"<#{cid}>" for cid in channel_ids)
        exempt_mentions = " ".join(f"<@&{rid}>" for rid in exempt_ids) or "None"
        await interaction.response.send_message(
            f"Set.\n**Unlocks:** {role.mention}\n**Only tracks:** {track_role.mention}\n**Required:** {required}/7d\n**Channels:** {ch_mentions}\n**Exempt:** {exempt_mentions}",
            ephemeral=True,
        )

    @app_commands.command(name="activitybackfill", description="Count recent messages")
    @app_commands.describe(
        days="Days back (max 7)",
        channels="Channels to search (optional — leave blank to use setup channels)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def activitybackfill(
        self,
        interaction: discord.Interaction,
        days: app_commands.Range[int, 1, 7] = 7,
        channels: str = "",
    ):
        cfg = get_cfg(interaction.guild_id)
        if not cfg:
            return await interaction.response.send_message("Run /activitysetup first.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # Use provided channels or fall back to setup channels
        channel_ids = []
        if channels.strip():
            for part in channels.split():
                if part.startswith("<#") and part.endswith(">"):
                    try:
                        channel_ids.append(int(part[2:-1]))
                    except:
                        pass
        if not channel_ids:
            channel_ids = cfg.get("channels", [])

        if not channel_ids:
            return await interaction.followup.send("No channels to search.", ephemeral=True)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        data = load()
        g = str(interaction.guild_id)
        activity = data.setdefault(g, {}).setdefault("activity", {})
        msgs = activity.setdefault("messages", {})
        track_role_id = cfg.get("track_role_id")

        counted = 0
        searched = []
        for channel_id in channel_ids:
            channel = interaction.guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue
            searched.append(channel.mention)
            try:
                async for message in channel.history(limit=500, after=cutoff):
                    if message.author.bot:
                        continue
                    if track_role_id and not any(r.id == track_role_id for r in message.author.roles):
                        continue
                    uid = str(message.author.id)
                    msgs.setdefault(uid, []).append(message.created_at.isoformat())
                    counted += 1
            except Exception:
                continue

        clean_cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        for uid in list(msgs.keys()):
            msgs[uid] = [t for t in msgs[uid] if datetime.fromisoformat(t) > clean_cutoff]

        save(data)
        await interaction.followup.send(
            f"Backfill done. Counted **{counted}** messages in {' '.join(searched)}.",
            ephemeral=True,
        )

    @app_commands.command(name="activitycheck", description="Force role check now")
    @app_commands.checks.has_permissions(administrator=True)
    async def activitycheck(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.check_activity()
        await interaction.followup.send("Check finished.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        cfg = get_cfg(message.guild.id)
        if not cfg or message.channel.id not in cfg.get("channels", []):
            return

        track_role_id = cfg.get("track_role_id")
        if track_role_id and not any(r.id == track_role_id for r in message.author.roles):
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
            track_role = guild.get_role(cfg.get("track_role_id")) if cfg.get("track_role_id") else None
            if not role or not track_role:
                continue

            required = cfg.get("required", 40)
            exempt_ids = set(cfg.get("exempt_roles", []))
            msgs = cfg.get("messages", {})
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)

            for member in guild.members:
                if member.bot or track_role not in member.roles:
                    continue

                has_exempt = any(r.id in exempt_ids for r in member.roles)
                has_role = role in member.roles

                if has_exempt:
                    if not has_role:
                        try:
                            await member.add_roles(role, reason="Activity exempt")
                        except:
                            pass
                    continue

                timestamps = msgs.get(str(member.id), [])
                recent = sum(1 for t in timestamps if datetime.fromisoformat(t) > cutoff)

                if recent >= required and not has_role:
                    try:
                        await member.add_roles(role, reason="Activity role")
                    except:
                        pass
                elif recent < required and has_role:
                    try:
                        await member.remove_roles(role, reason="Activity expired")
                    except:
                        pass

    @check_activity.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityRole(bot))
