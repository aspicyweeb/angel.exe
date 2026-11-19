import json
import traceback
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

class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close_v4")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not isinstance(interaction.channel, discord.Thread):
                return await interaction.response.send_message("Not a ticket.", ephemeral=True)

            await interaction.response.defer(ephemeral=True)

            # Transcript
            lines = []
            async for msg in interaction.channel.history(limit=200, oldest_first=True):
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
                    file = discord.File(
                        fp=transcript.encode(),
                        filename=f"transcript-{interaction.channel.name[:40]}.txt"
                    )
                    e = discord.Embed(
                        title="Ticket Transcript",
                        description=f"Closed by {interaction.user.mention}",
                        color=BLUE,
                    )
                    try:
                        await log.send(embed=e, file=file)
                    except Exception as ex:
                        print("Transcript failed:", ex)

            await interaction.followup.send("Ticket closed.", ephemeral=True)
            await interaction.channel.edit(archived=True, locked=True)

        except Exception as e:
            print("CLOSE ERROR:", e)
            traceback.print_exc()
            try:
                await interaction.followup.send(f"Close failed: {e}", ephemeral=True)
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
        except Exception:
            return await interaction.response.send_message("Invalid.", ephemeral=True)
        thread = interaction.guild.get_thread(thread_id)
        if not thread:
            return await interaction.response.send_message("Ticket gone.", ephemeral=True)
        try:
            await thread.add_user(interaction.user)
            await interaction.response.send_message(f"Joined {thread.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Couldn't join: {e}", ephemeral=True)

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
        return await interaction.response.send_message("Can't create threads.", ephemeral=True)

    await thread.add_user(interaction.user)
    try:
        await thread.edit(topic=f"opener:{interaction.user.id}")
    except Exception:
        pass

    embed = discord.Embed(
        title=info.get("title", f"{info.get('label', key)} Ticket"),
        description=info.get("instructions", "Staff will be with you shortly."),
        color=BLUE,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=f"Opened by {interaction.user}")

    await thread.send(content=interaction.user.mention, embed=embed, view=CloseView())

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
            except Exception:
                pass

    if interaction.response.is_done():
        await interaction.followup.send(f"Ticket opened: {thread.mention}", ephemeral=True)
    else:
        await interaction.response.send_message(f"Ticket opened: {thread.mention}", ephemeral=True)

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(CloseView())
        self.bot.add_view(JoinView())

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        for thread in member.guild.threads:
            if thread.topic and f"opener:{member.id}" in (thread.topic or ""):
                try:
                    await thread.send(f"{member} left. Auto-closing.")
                    await thread.edit(archived=True, locked=True)
                except Exception:
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

    @app_commands.command(name="ticketadd", description="Add a ticket type")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketadd(self, interaction: discord.Interaction, key: str, label: str, title: str, instructions: str, emoji: str | None = None):
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

    @app_commands.command(name="tickettypes", description="List types")
    @app_commands.checks.has_permissions(administrator=True)
    async def tickettypes(self, interaction: discord.Interaction):
        types = get_tickets_cfg(interaction.guild_id).get("types", {})
        if not types:
            return await interaction.response.send_message("None yet.", ephemeral=True)
        lines = [f"**{info['label']}** (`{k}`)" for k, info in types.items()]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
