import json
from pathlib import Path
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = Path("/data/config.json")
PASTEL_BLUE = 0xA7C7E7
PASTEL_PINK = 0xFFB6C1

def load() -> dict:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {}

def save(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def get_tickets_cfg(guild_id: int) -> dict:
    data = load()
    return data.get(str(guild_id), {}).get("tickets", {})

class TicketView(discord.ui.View):
    def __init__(self, types: dict):
        super().__init__(timeout=None)
        for key, info in types.items():
            self.add_item(TicketButton(key, info))

class TicketButton(discord.ui.Button):
    def __init__(self, key: str, info: dict):
        emoji = info.get("emoji")
        super().__init__(
            label=info.get("label", key),
            style=discord.ButtonStyle.secondary,
            custom_id=f"ticket_{key}",
            emoji=emoji if emoji else None,
        )
        self.key = key
        self.info = info

    async def callback(self, interaction: discord.Interaction):
        cfg = get_tickets_cfg(interaction.guild_id)
        staff_role_id = cfg.get("staff_role_id")

        try:
            thread = await interaction.channel.create_thread(
                name=f"{self.info.get('label', self.key)} • {interaction.user.display_name}",
                type=discord.ChannelType.private_thread,
                invitable=False,
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I can't create threads here. Need Manage Threads permission.", ephemeral=True
            )

        await thread.add_user(interaction.user)

        staff_mentions = ""
        if staff_role_id:
            role = interaction.guild.get_role(staff_role_id)
            if role:
                for member in role.members[:30]:
                    try:
                        await thread.add_user(member)
                    except:
                        pass
                staff_mentions = role.mention

        embed = discord.Embed(
            title=self.info.get("title", f"{self.info.get('label', self.key)} Ticket"),
            description=self.info.get("instructions", "Staff will be with you shortly."),
            color=PASTEL_PINK,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"Opened by {interaction.user}")

        await thread.send(
            content=f"{interaction.user.mention} {staff_mentions}".strip(),
            embed=embed,
            view=CloseView(),
        )

        await interaction.response.send_message(
            f"Ticket opened: {thread.mention}", ephemeral=True
        )

class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message("This isn't a ticket thread.", ephemeral=True)

        cfg = get_tickets_cfg(interaction.guild_id)
        staff_role_id = cfg.get("staff_role_id")
        is_staff = staff_role_id and any(r.id == staff_role_id for r in interaction.user.roles)

        if not (is_staff or interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message("Only staff can close tickets.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # Build transcript
        transcript_lines = []
        async for msg in interaction.channel.history(limit=200, oldest_first=True):
            time = msg.created_at.strftime("%Y-%m-%d %H:%M")
            content = msg.content or ""
            if msg.embeds:
                content += " [embed]"
            transcript_lines.append(f"[{time}] {msg.author}: {content}")

        transcript = "\n".join(transcript_lines) or "No messages."

        # Send transcript to log channel
        log_channel_id = cfg.get("transcript_channel_id")
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if isinstance(log_channel, discord.TextChannel):
                file = discord.File(
                    fp=transcript.encode(),
                    filename=f"transcript-{interaction.channel.name}.txt"
                )
                embed = discord.Embed(
                    title="Ticket Transcript",
                    description=f"Closed by {interaction.user.mention}\nThread: {interaction.channel.name}",
                    color=PASTEL_BLUE,
                    timestamp=discord.utils.utcnow(),
                )
                try:
                    await log_channel.send(embed=embed, file=file)
                except:
                    pass

        await interaction.followup.send("Ticket closed and transcript saved.", ephemeral=True)
        await interaction.channel.edit(archived=True, locked=True)

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(CloseView())

    @app_commands.command(name="ticketpanel", description="Send the ticket panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketpanel(self, interaction: discord.Interaction):
        cfg = get_tickets_cfg(interaction.guild_id)
        types = cfg.get("types", {})
        if not types:
            return await interaction.response.send_message("No ticket types yet.", ephemeral=True)

        embed = discord.Embed(
            title="Tickets",
            description="Please open a ticket below to reach our staff ♡",
            color=PASTEL_BLUE,
        )
        view = TicketView(types)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Panel sent.", ephemeral=True)

    @app_commands.command(name="ticketadd", description="Add a ticket type")
    @app_commands.describe(
        key="Short ID",
        label="Button text",
        title="Title inside ticket",
        instructions="Instructions",
        emoji="Custom emoji (optional)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketadd(self, interaction, key: str, label: str, title: str, instructions: str, emoji: str | None = None):
        data = load()
        guild = str(interaction.guild_id)
        data.setdefault(guild, {})
        tickets = data[guild].setdefault("tickets", {})
        types = tickets.setdefault("types", {})
        types[key.lower()] = {"label": label, "title": title, "instructions": instructions, "emoji": emoji}
        save(data)
        await interaction.response.send_message(f"Added **{label}**.", ephemeral=True)

    @app_commands.command(name="ticketsetup", description="Set staff role and transcript channel")
    @app_commands.describe(
        staff_role="Role that can see and close tickets",
        transcript_channel="Channel where transcripts are saved (staff only)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketsetup(self, interaction, staff_role: discord.Role, transcript_channel: discord.TextChannel):
        data = load()
        guild = str(interaction.guild_id)
        data.setdefault(guild, {})
        tickets = data[guild].setdefault("tickets", {})
        tickets["staff_role_id"] = staff_role.id
        tickets["transcript_channel_id"] = transcript_channel.id
        save(data)
        await interaction.response.send_message(
            f"Staff: {staff_role.mention}\nTranscripts: {transcript_channel.mention}", ephemeral=True
        )

    @app_commands.command(name="tickettypes", description="List ticket types")
    @app_commands.checks.has_permissions(administrator=True)
    async def tickettypes(self, interaction: discord.Interaction):
        types = get_tickets_cfg(interaction.guild_id).get("types", {})
        if not types:
            return await interaction.response.send_message("None yet.", ephemeral=True)
        lines = [f"**{info['label']}** (`{key}`)" for key, info in types.items()]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))