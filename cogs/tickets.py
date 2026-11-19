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

# ---------- Views ----------

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
        form = self.info.get("form")
        if form:
            await interaction.response.send_modal(TicketFormModal(self.key, self.info, form))
        else:
            await create_ticket(interaction, self.key, self.info)

class TicketFormModal(discord.ui.Modal, title="Ticket Form"):
    def __init__(self, key: str, info: dict, form: list):
        super().__init__()
        self.key = key
        self.info = info
        self.inputs = []
        for i, field in enumerate(form[:5]):
            inp = discord.ui.TextInput(
                label=field.get("label", f"Field {i+1}"),
                placeholder=field.get("placeholder", ""),
                style=discord.TextStyle.paragraph if field.get("long") else discord.TextStyle.short,
                required=field.get("required", True),
                max_length=field.get("max", 500),
            )
            self.add_item(inp)
            self.inputs.append(inp)

    async def on_submit(self, interaction: discord.Interaction):
        answers = {inp.label: inp.value for inp in self.inputs}
        await create_ticket(interaction, self.key, self.info, answers)

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message("Not a ticket.", ephemeral=True)
        await interaction.response.send_message(f"{interaction.user.mention} claimed this ticket.", )
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, custom_id="ticket_add")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddUserModal())

    @discord.ui.button(label="Close Request", style=discord.ButtonStyle.secondary, custom_id="ticket_closereq")
    async def close_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CloseRequestModal())

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close_final")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_close(interaction)

class AddUserModal(discord.ui.Modal, title="Add User"):
    user_id = discord.ui.TextInput(label="User ID or @mention", placeholder="123456789 or @user")

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            user_id = int(raw)
            member = interaction.guild.get_member(user_id) or await interaction.guild.fetch_member(user_id)
            await interaction.channel.add_user(member)
            await interaction.response.send_message(f"Added {member.mention}", ephemeral=True)
        except:
            await interaction.response.send_message("Couldn't find or add that user.", ephemeral=True)

class CloseRequestModal(discord.ui.Modal, title="Close Request"):
    reason = discord.ui.TextInput(label="Reason (optional)", required=False, style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        view = CloseRequestView()
        await interaction.response.send_message(
            f"{interaction.user.mention} requested to close this ticket.\n**Reason:** {self.reason.value or 'None'}\n\nOpener, please respond:",
            view=view,
        )

class CloseRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="closereq_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_close(interaction, reason="Close request accepted")

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="closereq_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Close request denied.", ephemeral=True)
        await interaction.message.edit(view=None)

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
            return await interaction.response.send_message("Invalid.", ephemeral=True)
        thread = interaction.guild.get_thread(thread_id)
        if not thread:
            return await interaction.response.send_message("Ticket gone.", ephemeral=True)
        try:
            await thread.add_user(interaction.user)
            await interaction.response.send_message(f"Joined {thread.mention}", ephemeral=True)
        except:
            await interaction.response.send_message("Couldn't join.", ephemeral=True)

# ---------- Helpers ----------

async def create_ticket(interaction: discord.Interaction, key: str, info: dict, answers: dict | None = None):
    cfg = get_tickets_cfg(interaction.guild_id)
    notify_id = cfg.get("notify_channel_id")

    try:
        thread = await interaction.channel.create_thread(
            name=f"{info.get('label', key)} • {interaction.user.display_name}",
            type=discord.ChannelType.private_thread,
            invitable=False,
        )
    except discord.Forbidden:
        return await interaction.response.send_message("Can't create threads.", ephemeral=True)

    await thread.add_user(interaction.user)
    try:
        await thread.edit(topic=f"opener:{interaction.user.id}")
    except:
        pass

    desc = info.get("instructions", "Staff will be with you shortly.")
    if answers:
        desc += "\n\n**Form Answers:**\n" + "\n".join(f"**{k}:** {v}" for k, v in answers.items())

    embed = discord.Embed(
        title=info.get("title", f"{info.get('label', key)} Ticket"),
        description=desc,
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

    if interaction.response.is_done():
        await interaction.followup.send(f"Ticket opened: {thread.mention}", ephemeral=True)
    else:
        await interaction.response.send_message(f"Ticket opened: {thread.mention}", ephemeral=True)

async def do_close(interaction: discord.Interaction, reason: str = "Closed"):
    if not isinstance(interaction.channel, discord.Thread):
        return await interaction.response.send_message("Not a ticket.", ephemeral=True)

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
            e = discord.Embed(title="Ticket Transcript", description=f"Closed by {interaction.user.mention}\nReason: {reason}", color=BLUE)
            try:
                await log.send(embed=e, file=file)
            except:
                pass

    await interaction.followup.send("Ticket closed.", ephemeral=True)
    try:
        await interaction.channel.edit(archived=True, locked=True)
    except:
        pass

# ---------- Cog ----------

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
                    await thread.send(f"{member} left. Auto-closing.")
                    await thread.edit(archived=True, locked=True)
                except:
                    pass

    @app_commands.command(name="ticketpanel", description="Send ticket panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketpanel(self, interaction: discord.Interaction):
        cfg = get_tickets_cfg(interaction.guild_id)
        types = cfg.get("types", {})
        if not types:
            return await interaction.response.send_message("No types yet.", ephemeral=True)
        e = discord.Embed(title="Tickets", description="Open a ticket below ♡", color=BLUE)
        await interaction.channel.send(embed=e, view=TicketPanelView(types))
        await interaction.response.send_message("Panel sent.", ephemeral=True)

    @app_commands.command(name="ticketadd", description="Add ticket type")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketadd(self, interaction, key: str, label: str, title: str, instructions: str, emoji: str | None = None):
        data = load()
        g = str(interaction.guild_id)
        data.setdefault(g, {}).setdefault("tickets", {}).setdefault("types", {})[key.lower()] = {
            "label": label, "title": title, "instructions": instructions, "emoji": emoji
        }
        save(data)
        await interaction.response.send_message(f"Added **{label}**.", ephemeral=True)

    @app_commands.command(name="ticketsetup", description="Set channels")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketsetup(self, interaction, transcript_channel: discord.TextChannel, notify_channel: discord.TextChannel, staff_role: discord.Role | None = None):
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

    @app_commands.command(name="tag", description="Send a quick tag")
    async def tag(self, interaction: discord.Interaction, name: str):
        # Simple hardcoded tags — expand as needed
        tags = {
            "hi": "Hello! How can we help you today?",
            "wait": "Please wait while a staff member reviews your ticket.",
        }
        msg = tags.get(name.lower())
        if not msg:
            return await interaction.response.send_message("Tag not found.", ephemeral=True)
        await interaction.response.send_message(msg)

    @app_commands.context_menu(name="Open Ticket")
    async def open_from_message(self, interaction: discord.Interaction, message: discord.Message):
        # Opens a generic ticket linked to the message
        info = {"label": "Message Ticket", "title": "Ticket from Message", "instructions": f"Opened from [message]({message.jump_url})"}
        await create_ticket(interaction, "message", info)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
    bot.tree.add_command(Tickets.open_from_message)
