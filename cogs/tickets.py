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

class TicketPanelView(discord.ui.View):
    def __init__(self, types: dict):
        super().__init__(timeout=None)
        for key, info in types.items():
            self.add_item(TicketOpenButton(key, info))

class TicketOpenButton(discord.ui.Button):
    def __init__(self, key: str, info: dict):
        emoji = info.get("emoji")
        super().__init__(
            label=info.get("label", key),
            style=discord.ButtonStyle.secondary,
            custom_id=f"ticket_open_{key}",
            emoji=emoji if emoji else None,
        )
        self.key = key
        self.info = info

    async def callback(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.key, self.info)

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim_v2")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message("Not a ticket.", ephemeral=True)
        await interaction.response.send_message(f"{interaction.user.mention} claimed this ticket.")
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        try:
            await interaction.message.edit(view=self)
        except:
            pass

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, custom_id="ticket_add_v2")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddUserModal())

    @discord.ui.button(label="Close Request", style=discord.ButtonStyle.secondary, custom_id="ticket_closereq_v2")
    async def close_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CloseRequestModal())

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close_v4")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_close(interaction)

class AddUserModal(discord.ui.Modal, title="Add User"):
    user_input = discord.ui.TextInput(label="User ID or mention", placeholder="123456789012345678")

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            uid = int(raw)
            member = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
            await interaction.channel.add_user(member)
            await interaction.response.send_message(f"Added {member.mention}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("Couldn't add that user.", ephemeral=True)

class CloseRequestModal(discord.ui.Modal, title="Close Request"):
    reason = discord.ui.TextInput(label="Reason (optional)", required=False, style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        view = CloseRequestView()
        await interaction.response.send_message(
            f"{interaction.user.mention} requested to close.\n**Reason:** {self.reason.value or 'None'}",
            view=view,
        )

class CloseRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="closereq_accept_v2")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_close(interaction, reason="Close request accepted")

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="closereq_deny_v2")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Close request denied.", ephemeral=True)
        try:
            await interaction.message.edit(view=None)
        except:
            pass

class JoinView(discord.ui.View):
    def __init__(self, thread_id: int = 0):
        super().__init__(timeout=None)
        if self.children:
            self.children[0].custom_id = f"ticket_join:{thread_id}"

    @discord.ui.button(label="Join Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_join:0")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            await interaction.response.send_message("Couldn't join.", ephemeral=True)

async def create_ticket(interaction: discord.Interaction, key: str, info: dict):
    cfg = get_tickets_cfg(interaction.guild_id)
    notify_id = cfg.get("notify_channel_id")

    try:
        thread = await interaction.channel.create_thread(
            name=f"{info.get('label', key)} • {interaction.user.display_name}",
            type=discord.ChannelType.private_thread,
            invitable=False,
        )
    except discord.Forbidden:
        return await interaction.response.send_message("Can't create threads here.", ephemeral=True)

    await thread.add_user(interaction.user)
    try:
        await thread.edit(topic=f"opener:{interaction.user.id}")
    except:
        pass

    embed = discord.Embed(
        title=info.get("title", f"{info.get('label', key)} Ticket"),
        description=info.get("instructions", "Staff will be with you shortly."),
        color=BLUE,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=f"Opened by {interaction.user}")

    await thread.send(content=interaction.user.mention, embed=embed, view=TicketControlView())

    if notify_id:
        ch = interaction.guild.get_channel(notify_id)
        if isinstance(ch, discord.TextChannel):
            nembed = discord.Embed(
                title="Join Ticket",
                description=f"**{thread.name}** has been opened.\nPress the button below to join it.",
                color=BLUE,
            )
            nembed.add_field(name="Opened By", value=interaction.user.mention, inline=False)
            nembed.add_field(name="Panel", value=info.get("label", key), inline=False)
            try:
                await ch.send(embed=nembed, view=JoinView(thread.id))
            except:
                pass

    await interaction.response.send_message(f"Ticket opened: {thread.mention}", ephemeral=True)

async def do_close(interaction: discord.Interaction, reason: str = "Closed"):
    if not isinstance(interaction.channel, discord.Thread):
        return await interaction.response.send_message("Not a ticket.", ephemeral=True)

    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    lines = []
    async for msg in interaction.channel.history(limit=300, oldest_first=True):
        t = msg.created_at.strftime("%Y-%m-%d %H:%M")
        c = msg.content or ""
        if msg.embeds:
            c += " [embed]"
        lines.append(f"[{t}] {msg.author}: {c}")
    transcript = "\n".join(lines) or "Empty"

    cfg = get_tickets_cfg(interaction.guild_id)
    log_id = cfg.get("transcript_channel_id")
    if log_id:
        log = interaction.guild.get_channel(log_id)
        if isinstance(log, discord.TextChannel):
            file = discord.File(fp=transcript.encode(), filename=f"transcript-{interaction.channel.name[:40]}.txt")
            e = discord.Embed(
                title="Ticket Transcript",
                description=f"Closed by {interaction.user.mention}\nReason: {reason}",
                color=BLUE,
            )
            try:
                await log.send(embed=e, file=file)
            except:
                pass

    try:
        await interaction.followup.send("Ticket closed.", ephemeral=True)
    except:
        pass
    try:
        await interaction.channel.edit(archived=True, locked=True)
    except:
        pass

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(TicketControlView())
        self.bot.add_view(JoinView())
        self.bot.add_view(CloseRequestView())

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        for thread in member.guild.threads:
            if thread.topic and f"opener:{member.id}" in (thread.topic or ""):
                try:
                    await thread.send(f"{member} left the server. Auto-closing.")
                    await thread.edit(archived=True, locked=True)
                except:
                    pass

    @app_commands.command(name="ticketpanel", description="Send the ticket panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketpanel(self, interaction: discord.Interaction):
        cfg = get_tickets_cfg(interaction.guild_id)
        types = cfg.get("types", {})
        if not types:
            return await interaction.response.send_message("No ticket types yet. Use /ticketadd.", ephemeral=True)
        embed = discord.Embed(title="Tickets", description="Open a ticket below ♡", color=BLUE)
        await interaction.channel.send(embed=embed, view=TicketPanelView(types))
        await interaction.response.send_message("Panel sent.", ephemeral=True)

    @app_commands.command(name="ticketadd", description="Add a ticket type")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketadd(self, interaction: discord.Interaction, key: str, label: str, title: str, instructions: str, emoji: str | None = None):
        data = load()
        g = str(interaction.guild_id)
        data.setdefault(g, {}).setdefault("tickets", {}).setdefault("types", {})[key.lower()] = {
            "label": label,
            "title": title,
            "instructions": instructions,
            "emoji": emoji,
        }
        save(data)
        await interaction.response.send_message(f"Added **{label}**.", ephemeral=True)

    @app_commands.command(name="ticketsetup", description="Set transcript and notify channels")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketsetup(
        self,
        interaction: discord.Interaction,
        transcript_channel: discord.TextChannel,
        notify_channel: discord.TextChannel,
        staff_role: discord.Role | None = None,
    ):
        data = load()
        g = str(interaction.guild_id)
        t = data.setdefault(g, {}).setdefault("tickets", {})
        t["transcript_channel_id"] = transcript_channel.id
        t["notify_channel_id"] = notify_channel.id
        if staff_role:
            t["staff_role_id"] = staff_role.id
        else:
            t.pop("staff_role_id", None)
        save(data)
        await interaction.response.send_message("Setup saved.", ephemeral=True)

    @app_commands.command(name="tag", description="Send a quick reply")
    async def tag(self, interaction: discord.Interaction, name: str):
        tags = {
            "hi": "Hello! How can we help you today?",
            "wait": "Please wait while a staff member reviews your ticket.",
            "closing": "This ticket will be closed shortly if there's nothing else.",
        }
        msg = tags.get(name.lower())
        if not msg:
            return await interaction.response.send_message("Tag not found.", ephemeral=True)
        await interaction.response.send_message(msg)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))