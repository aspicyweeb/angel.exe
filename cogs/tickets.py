import json
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = Path("/data/config.json")
BLUE = 0xA7C7E7

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
        notify_channel_id = cfg.get("notify_channel_id")

        try:
            thread = await interaction.channel.create_thread(
                name=f"{self.info.get('label', self.key)} • {interaction.user.display_name}",
                type=discord.ChannelType.private_thread,
                invitable=False,
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I can't create threads here.", ephemeral=True
            )

        await thread.add_user(interaction.user)
        try:
            await thread.edit(topic=f"opener:{interaction.user.id}")
        except:
            pass

        embed = discord.Embed(
            title=self.info.get("title", f"{self.info.get('label', self.key)} Ticket"),
            description=self.info.get("instructions", "Staff will be with you shortly."),
            color=BLUE,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"Opened by {interaction.user}")

        await thread.send(
            content=interaction.user.mention,
            embed=embed,
            view=CloseView(),
        )

        if notify_channel_id:
            notify_channel = interaction.guild.get_channel(notify_channel_id)
            if isinstance(notify_channel, discord.TextChannel):
                notify_embed = discord.Embed(
                    title="Join Ticket",
                    description=f"**{thread.name}** has been opened.\nPress the button below to join it.",
                    color=BLUE,
                    timestamp=discord.utils.utcnow(),
                )
                notify_embed.add_field(name="Opened By", value=interaction.user.mention, inline=False)
                notify_embed.add_field(name="Panel", value=self.info.get("label", self.key), inline=False)
                notify_embed.add_field(name="Staff In Ticket", value="0", inline=True)

                view = JoinView(thread.id)
                try:
                    await notify_channel.send(embed=notify_embed, view=view)
                except:
                    pass

        await interaction.response.send_message(
            f"Ticket opened: {thread.mention}", ephemeral=True
        )

class JoinView(discord.ui.View):
    def __init__(self, thread_id: int = 0):
        super().__init__(timeout=None)
        self.thread_id = thread_id
        # Store thread id in custom_id so it survives restarts
        self.children[0].custom_id = f"ticket_join:{thread_id}"

    @discord.ui.button(label="Join Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_join:0")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Extract thread id from custom_id
        try:
            thread_id = int(button.custom_id.split(":")[1])
        except:
            return await interaction.response.send_message("Invalid ticket.", ephemeral=True)

        thread = interaction.guild.get_thread(thread_id)
        if not thread:
            return await interaction.response.send_message("Ticket no longer exists.", ephemeral=True)
        try:
            await thread.add_user(interaction.user)
            await interaction.response.send_message(f"Joined {thread.mention}", ephemeral=True)
        except:
            await interaction.response.send_message("Couldn't join the ticket.", ephemeral=True)

class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close_v3")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message("This isn't a ticket.", ephemeral=True)

        cfg = get_tickets_cfg(interaction.guild_id)
        staff_role_id = cfg.get("staff_role_id")
        is_staff = interaction.user.guild_permissions.administrator
        if staff_role_id:
            is_staff = is_staff or any(r.id == staff_role_id for r in interaction.user.roles)

        if not is_staff:
            return await interaction.response.send_message("Only staff can close tickets.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        transcript_lines = []
        async for msg in interaction.channel.history(limit=200, oldest_first=True):
            time = msg.created_at.strftime("%Y-%m-%d %H:%M")
            content = msg.content or ""
            if msg.embeds:
                content += " [embed]"
            transcript_lines.append(f"[{time}] {msg.author}: {content}")

        transcript = "\n".join(transcript_lines) or "No messages."

        log_channel_id = cfg.get("transcript_channel_id")
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if isinstance(log_channel, discord.TextChannel):
                file = discord.File(
                    fp=transcript.encode(),
                    filename=f"transcript-{interaction.channel.name[:40]}.txt"
                )
                embed = discord.Embed(
                    title="Ticket Transcript",
                    description=f"Closed by {interaction.user.mention}\n{interaction.channel.name}",
                    color=BLUE,
                    timestamp=discord.utils.utcnow(),
                )
                try:
                    await log_channel.send(embed=embed, file=file)
                except:
                    pass

        await interaction.followup.send("Ticket closed.", ephemeral=True)
        try:
            await interaction.channel.edit(archived=True, locked=True)
        except:
            pass

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(CloseView())
        self.bot.add_view(JoinView())  # register the join view too

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        for thread in member.guild.threads:
            if thread.topic and f"opener:{member.id}" in (thread.topic or ""):
                try:
                    await thread.send(f"{member} left the server. Ticket auto-closed.")
                    await thread.edit(archived=True, locked=True)
                except:
                    pass

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
            color=BLUE,
        )
        await interaction.channel.send(embed=embed, view=TicketView(types))
        await interaction.response.send_message("Panel sent.", ephemeral=True)

    @app_commands.command(name="ticketadd", description="Add a ticket type")
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

    @app_commands.command(name="ticketedit", description="Edit a ticket type")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketedit(
        self,
        interaction: discord.Interaction,
        key: str,
        new_key: str | None = None,
        label: str | None = None,
        title: str | None = None,
        instructions: str | None = None,
        emoji: str | None = None,
    ):
        data = load()
        guild = str(interaction.guild_id)
        types = data.get(guild, {}).get("tickets", {}).get("types", {})
        key = key.lower()
        if key not in types:
            return await interaction.response.send_message(f"No type `{key}`.", ephemeral=True)

        if new_key:
            new_key = new_key.lower()
            if new_key != key and new_key in types:
                return await interaction.response.send_message(f"`{new_key}` already exists.", ephemeral=True)
            types[new_key] = types.pop(key)
            key = new_key

        if label is not None:
            types[key]["label"] = label
        if title is not None:
            types[key]["title"] = title
        if instructions is not None:
            types[key]["instructions"] = instructions
        if emoji is not None:
            types[key]["emoji"] = emoji.strip() or None

        save(data)
        await interaction.response.send_message(f"Updated `{key}`.", ephemeral=True)

    @app_commands.command(name="ticketremove", description="Remove a ticket type")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketremove(self, interaction: discord.Interaction, key: str):
        data = load()
        guild = str(interaction.guild_id)
        types = data.get(guild, {}).get("tickets", {}).get("types", {})
        key = key.lower()
        if key not in types:
            return await interaction.response.send_message(f"No type `{key}`.", ephemeral=True)
        del types[key]
        save(data)
        await interaction.response.send_message(f"Removed `{key}`.", ephemeral=True)

    @app_commands.command(name="ticketsetup", description="Set staff role, transcript channel, and notify channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketsetup(
        self,
        interaction: discord.Interaction,
        staff_role: discord.Role,
        transcript_channel: discord.TextChannel,
        notify_channel: discord.TextChannel,
    ):
        data = load()
        guild = str(interaction.guild_id)
        data.setdefault(guild, {})
        tickets = data[guild].setdefault("tickets", {})
        tickets["staff_role_id"] = staff_role.id
        tickets["transcript_channel_id"] = transcript_channel.id
        tickets["notify_channel_id"] = notify_channel.id
        save(data)
        await interaction.response.send_message(
            f"Staff: {staff_role.mention}\nTranscripts: {transcript_channel.mention}\nNotifications: {notify_channel.mention}",
            ephemeral=True,
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
