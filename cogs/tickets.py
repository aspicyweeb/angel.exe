import json
from pathlib import Path
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
        category_id = cfg.get("category_id")
        staff_role_id = cfg.get("staff_role_id")

        if not category_id:
            return await interaction.response.send_message(
                "Ticket category not set. Ask an admin to run `/ticketsetup`.", ephemeral=True
            )

        category = interaction.guild.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message(
                "Ticket category is invalid.", ephemeral=True
            )

        # Permissions: only opener + staff can see it
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, attach_files=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True, manage_messages=True
            ),
        }
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True, manage_messages=True
                )

        try:
            channel = await interaction.guild.create_text_channel(
                name=f"{self.key}-{interaction.user.name}",
                category=category,
                overwrites=overwrites,
                topic=f"Ticket for {interaction.user} | {self.info.get('label', self.key)}",
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I don't have permission to create channels.", ephemeral=True
            )

        embed = discord.Embed(
            title=self.info.get("title", f"{self.info.get('label', self.key)} Ticket"),
            description=self.info.get("instructions", "Staff will be with you shortly."),
            color=PASTEL_PINK,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"Opened by {interaction.user}")

        await channel.send(
            content=interaction.user.mention + (f" {staff_role.mention}" if staff_role_id and staff_role else ""),
            embed=embed,
            view=CloseView(),
        )

        await interaction.response.send_message(
            f"Ticket opened: {channel.mention}", ephemeral=True
        )

class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only staff or the opener can close
        cfg = get_tickets_cfg(interaction.guild_id)
        staff_role_id = cfg.get("staff_role_id")
        is_staff = staff_role_id and any(r.id == staff_role_id for r in interaction.user.roles)
        is_opener = interaction.channel.topic and str(interaction.user.id) in interaction.channel.topic

        if not (is_staff or interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message(
                "Only staff can close tickets.", ephemeral=True
            )

        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        await interaction.channel.delete(reason=f"Closed by {interaction.user}")

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
            return await interaction.response.send_message(
                "No ticket types yet. Use `/ticketadd` first.", ephemeral=True
            )

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
        key="Short ID (verification / reports / partnerships / contact)",
        label="Button text",
        title="Title inside the ticket",
        instructions="Instructions shown when opened",
        emoji="Custom emoji (optional)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketadd(
        self,
        interaction: discord.Interaction,
        key: str,
        label: str,
        title: str,
        instructions: str,
        emoji: str | None = None,
    ):
        data = load()
        guild = str(interaction.guild_id)
        data.setdefault(guild, {})
        tickets = data[guild].setdefault("tickets", {})
        types = tickets.setdefault("types", {})
        types[key.lower()] = {
            "label": label,
            "title": title,
            "instructions": instructions,
            "emoji": emoji,
        }
        save(data)
        await interaction.response.send_message(f"Added **{label}**.", ephemeral=True)

    @app_commands.command(name="ticketsetup", description="Set category and staff role")
    @app_commands.describe(
        category="Category where tickets will be created",
        staff_role="Role that can see and handle tickets",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketsetup(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
        staff_role: discord.Role,
    ):
        data = load()
        guild = str(interaction.guild_id)
        data.setdefault(guild, {})
        tickets = data[guild].setdefault("tickets", {})
        tickets["category_id"] = category.id
        tickets["staff_role_id"] = staff_role.id
        save(data)
        await interaction.response.send_message(
            f"Category: {category.name}\nStaff role: {staff_role.mention}", ephemeral=True
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