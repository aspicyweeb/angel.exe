import json
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = Path("/data/config.json")
PASTEL_BLUE = 0xA7C7E7
PASTEL_GREEN = 0xA8E6CF

def load() -> dict:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {}

def save(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def get_confessions_cfg(guild_id: int) -> dict:
    data = load()
    return data.get(str(guild_id), {}).get("confessions", {})

class ConfessionModal(discord.ui.Modal, title="Anonymous Confession"):
    confession = discord.ui.TextInput(
        label="Your confession",
        style=discord.TextStyle.paragraph,
        placeholder="Type your confession here...",
        max_length=1900,
        required=True,
    )

    def __init__(self, reply_to: discord.Message | None = None):
        super().__init__()
        self.reply_to = reply_to

    async def on_submit(self, interaction: discord.Interaction):
        cfg = get_confessions_cfg(interaction.guild_id)
        channel_id = cfg.get("channel_id")
        log_channel_id = cfg.get("log_channel_id")

        if not channel_id:
            return await interaction.response.send_message(
                "Confessions aren't set up yet.", ephemeral=True
            )

        channel = interaction.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "The confession channel is missing.", ephemeral=True
            )

        text = self.confession.value.strip()

        embed = discord.Embed(
            description=text,
            color=PASTEL_BLUE,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name="Anonymous Confession")
        if self.reply_to:
            embed.set_footer(text="Anonymous reply")
        else:
            embed.set_footer(text="Posted anonymously")

        view = ConfessionView()
        try:
            if self.reply_to:
                await self.reply_to.reply(embed=embed, view=view, mention_author=False)
            else:
                await channel.send(embed=embed, view=view)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I don't have permission to post in the confession channel.", ephemeral=True
            )

        # Admin log
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if isinstance(log_channel, discord.TextChannel):
                log_embed = discord.Embed(
                    title="Confession Log",
                    description=f"||{text}||",
                    color=0xFF6B6B,
                    timestamp=discord.utils.utcnow(),
                )
                log_embed.add_field(
                    name="Submitted by",
                    value=f"{interaction.user.mention} (`{interaction.user.id}`)",
                    inline=False,
                )
                if self.reply_to:
                    log_embed.add_field(name="Reply to", value=self.reply_to.jump_url, inline=False)
                try:
                    await log_channel.send(embed=log_embed)
                except discord.Forbidden:
                    pass

        await interaction.response.send_message("Posted anonymously.", ephemeral=True)

class ConfessionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="anon confession",
        style=discord.ButtonStyle.secondary,
        custom_id="confess_new"
    )
    async def confess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfessionModal())

    @discord.ui.button(
        label="anon reply",
        style=discord.ButtonStyle.secondary,
        custom_id="confess_reply"
    )
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfessionModal(reply_to=interaction.message))

    @discord.ui.button(
        label="report",
        style=discord.ButtonStyle.danger,
        custom_id="confess_report"
    )
    async def report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = get_confessions_cfg(interaction.guild_id)
        report_channel_id = cfg.get("report_channel_id")
        if not report_channel_id:
            return await interaction.response.send_message(
                "Reports aren't set up yet.", ephemeral=True
            )

        report_channel = interaction.guild.get_channel(report_channel_id)
        if not isinstance(report_channel, discord.TextChannel):
            return await interaction.response.send_message(
                "Report channel is missing.", ephemeral=True
            )

        embed = discord.Embed(
            title="Confession Reported",
            description=f"A confession was flagged.\n\n[Jump to message]({interaction.message.jump_url})",
            color=PASTEL_GREEN,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Reported by", value=interaction.user.mention, inline=False)
        embed.set_footer(text="Mod alert")

        try:
            await report_channel.send(embed=embed)
            await interaction.response.send_message("Report sent to mods.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Can't send the report.", ephemeral=True)

class Confessions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(ConfessionView())

    @app_commands.command(name="confess", description="Submit an anonymous confession")
    async def confess(self, interaction: discord.Interaction):
        if not get_confessions_cfg(interaction.guild_id).get("channel_id"):
            return await interaction.response.send_message(
                "Confessions aren't set up yet.", ephemeral=True
            )
        await interaction.response.send_modal(ConfessionModal())

    @app_commands.command(name="confessionpanel", description="Send a panel with the Confess button")
    @app_commands.checks.has_permissions(administrator=True)
    async def confessionpanel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Anonymous Confessions",
            description="Click the button below to confess something anonymously.",
            color=PASTEL_BLUE,
        )
        await interaction.channel.send(embed=embed, view=ConfessionView())
        await interaction.response.send_message("Panel sent.", ephemeral=True)

    @app_commands.command(name="confessionsetup", description="Set the channels for anonymous confessions")
    @app_commands.describe(
        channel="Public channel where confessions are posted",
        log_channel="Admin log channel (optional)",
        report_channel="Channel for report alerts (optional)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def confessionsetup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        log_channel: discord.TextChannel | None = None,
        report_channel: discord.TextChannel | None = None,
    ):
        data = load()
        guild = str(interaction.guild_id)
        data.setdefault(guild, {})
        conf = data[guild].setdefault("confessions", {})
        conf["channel_id"] = channel.id
        if log_channel:
            conf["log_channel_id"] = log_channel.id
        if report_channel:
            conf["report_channel_id"] = report_channel.id
        save(data)

        msg = f"Confessions → {channel.mention}"
        if log_channel:
            msg += f"\nLogs → {log_channel.mention}"
        if report_channel:
            msg += f"\nReports → {report_channel.mention}"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="confessionoff", description="Disable anonymous confessions")
    @app_commands.checks.has_permissions(administrator=True)
    async def confessionoff(self, interaction: discord.Interaction):
        data = load()
        guild = str(interaction.guild_id)
        if guild in data and "confessions" in data[guild]:
            del data[guild]["confessions"]
            save(data)
        await interaction.response.send_message("Confessions disabled.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Confessions(bot))