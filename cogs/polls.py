import discord
from discord.ext import commands
from discord import app_commands
import uuid
import json
from pathlib import Path

CONFIG_PATH = Path("poll_config.json")
POLLS_PATH = Path("polls_data.json")


class PollSelect(discord.ui.Select):
    def __init__(self, poll_id: str, options: list[str], max_votes: int):
        super().__init__(
            placeholder=f"Pick up to {max_votes}",
            min_values=1,
            max_values=min(max_votes, len(options)),
            options=[
                discord.SelectOption(label=opt[:100], value=str(i))
                for i, opt in enumerate(options)
            ],
            custom_id=f"pollsel_{poll_id}",
        )
        self.poll_id = poll_id

    async def callback(self, interaction: discord.Interaction):
        cog: Polls = interaction.client.get_cog("Polls")
        poll = cog.polls.get(self.poll_id) if cog else None

        if not poll or poll["closed"]:
            return await interaction.response.send_message("Poll is closed.", ephemeral=True)

        poll["votes"][str(interaction.user.id)] = {
            "choices": [int(v) for v in self.values],
            "name": interaction.user.display_name or interaction.user.name,
        }
        cog.save_polls()
        await interaction.response.send_message("Vote saved.", ephemeral=True)


class PollView(discord.ui.View):
    def __init__(self, poll_id: str, options: list[str], max_votes: int):
        super().__init__(timeout=None)
        self.add_item(PollSelect(poll_id, options, max_votes))


class Polls(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.polls: dict[str, dict] = {}
        self.number_emotes: list[str] = []
        self.bar_empty: str = "⬜"
        self.bar_fill: str = "🟥"
        self.bar_length: int = 10
        self.load_all()

    def load_all(self):
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text())
                self.number_emotes = data.get("number_emotes", [])
                self.bar_empty = data.get("bar_empty", "⬜")
                self.bar_fill = data.get("bar_fill", "🟥")
                self.bar_length = data.get("bar_length", 10)
            except Exception:
                pass

        if POLLS_PATH.exists():
            try:
                self.polls = json.loads(POLLS_PATH.read_text())
            except Exception:
                self.polls = {}

    def save_config(self):
        CONFIG_PATH.write_text(json.dumps({
            "number_emotes": self.number_emotes,
            "bar_empty": self.bar_empty,
            "bar_fill": self.bar_fill,
            "bar_length": self.bar_length,
        }, indent=2))

    def save_polls(self):
        POLLS_PATH.write_text(json.dumps(self.polls, indent=2))

    def number_emote(self, index: int) -> str:
        if 0 <= index < len(self.number_emotes):
            return self.number_emotes[index]
        return chr(65 + index)

    def progress_bar(self, percent: float, max_percent: float = 100.0) -> str:
        if max_percent <= 0 or self.bar_length <= 0:
            return self.bar_empty * max(1, self.bar_length)
        relative = max(0.0, min(100.0, (percent / max_percent) * 100))
        filled = round(relative / 100 * self.bar_length)
        return self.bar_fill * filled + self.bar_empty * (self.bar_length - filled)

    def results_embed(self, poll: dict) -> discord.Embed:
        total = sum(len(v.get("choices", [])) for v in poll["votes"].values())
        counts = [
            sum(1 for v in poll["votes"].values() if i in v.get("choices", []))
            for i in range(len(poll["options"]))
        ]
        max_count = max(counts) if counts else 0
        max_percent = (max_count / total * 100) if total else 0

        embed = discord.Embed(
            title="Final Result:" if poll["closed"] else "Results:",
            description=poll["question"],
            color=0xAEC6CF,
        )

        lines = []
        for i, name in enumerate(poll["options"]):
            count = counts[i]
            pct = (count / total * 100) if total else 0
            lines.append(
                f"{self.number_emote(i)} • {self.progress_bar(pct, max_percent)}\n"
                f"**{name}** — {pct:.1f}% ({count})"
            )

        embed.description += "\n\n" + "\n\n".join(lines) if lines else "\n\nNo votes yet"
        embed.set_footer(text=f"{total} votes • {len(poll['votes'])} voters • {poll['id']}")
        return embed

    @app_commands.command(name="pollsetnumbers", description="Set custom number emotes (space-separated)")
    @app_commands.describe(emotes="Emotes separated by spaces, in order (A B C …)")
    async def set_numbers(self, interaction: discord.Interaction, emotes: str):
        self.number_emotes = emotes.split()
        self.save_config()
        await interaction.response.send_message(
            f"Set {len(self.number_emotes)} number emotes:\n" + " ".join(self.number_emotes),
            ephemeral=True,
        )

    @app_commands.command(name="pollsetbar", description="Set the progress bar emotes")
    @app_commands.describe(
        empty="Emote used for empty segments",
        fill="Emote used for filled segments",
        length="How many segments wide (1–20)",
    )
    async def set_bar(
        self,
        interaction: discord.Interaction,
        empty: str,
        fill: str,
        length: app_commands.Range[int, 1, 20] = 10,
    ):
        self.bar_empty = empty
        self.bar_fill = fill
        self.bar_length = length
        self.save_config()
        preview = self.progress_bar(60, 100)
        await interaction.response.send_message(
            f"Bar updated.\nEmpty: {empty}\nFill: {fill}\nLength: {length}\nPreview: {preview}",
            ephemeral=True,
        )

    @app_commands.command(name="pollshowconfig", description="Show current emote config")
    async def show_config(self, interaction: discord.Interaction):
        nums = " ".join(self.number_emotes) if self.number_emotes else "(none — using letters)"
        await interaction.response.send_message(
            f"**Numbers:** {nums}\n"
            f"**Bar empty:** {self.bar_empty}\n"
            f"**Bar fill:** {self.bar_fill}\n"
            f"**Bar length:** {self.bar_length}",
            ephemeral=True,
        )

    @app_commands.command(name="poll", description="Create a poll")
    @app_commands.describe(
        question="Poll question",
        options="Options separated by |",
        max_votes="Votes allowed per person",
        blind="Hide results until closed",
    )
    async def create(
        self,
        interaction: discord.Interaction,
        question: str,
        options: str,
        max_votes: app_commands.Range[int, 1, 10] = 3,
        blind: bool = False,
    ):
        raw_opts = [o.strip() for o in options.split("|") if o.strip()]
        if not 2 <= len(raw_opts) <= 25:
            return await interaction.response.send_message("Need 2–25 options.", ephemeral=True)

        resolved = []
        for opt in raw_opts:
            cleaned = opt.replace("<@", "").replace(">", "").replace("!", "")
            if cleaned.isdigit():
                try:
                    user = await interaction.client.fetch_user(int(cleaned))
                    resolved.append(user.display_name or user.name)
                except Exception:
                    resolved.append(opt)
            else:
                resolved.append(opt)

        pid = uuid.uuid4().hex[:8]
        self.polls[pid] = {
            "id": pid,
            "question": question,
            "options": resolved,
            "votes": {},
            "max_votes": max_votes,
            "blind": blind,
            "closed": False,
        }
        self.save_polls()

        embed = discord.Embed(title="Question:", description=question, color=0xAEC6CF)
        embed.add_field(
            name="Choices:",
            value="\n".join(f"{self.number_emote(i)} • {opt}" for i, opt in enumerate(resolved)),
            inline=False,
        )
        embed.add_field(
            name="Settings:",
            value=f"Max votes: **{max_votes}**\nBlind: **{'Yes' if blind else 'No'}**\nID: `{pid}`",
            inline=False,
        )

        await interaction.response.send_message(embed=embed, view=PollView(pid, resolved, max_votes))

    @app_commands.command(name="pollclose", description="Close a poll")
    async def close(self, interaction: discord.Interaction, poll_id: str):
        poll = self.polls.get(poll_id)
        if not poll:
            return await interaction.response.send_message("Not found.", ephemeral=True)
        if poll["closed"]:
            return await interaction.response.send_message("Already closed.", ephemeral=True)

        poll["closed"] = True
        self.save_polls()
        await interaction.response.send_message(embed=self.results_embed(poll))

    @app_commands.command(name="pollresults", description="Show poll results")
    async def results(self, interaction: discord.Interaction, poll_id: str):
        poll = self.polls.get(poll_id)
        if not poll:
            return await interaction.response.send_message("Not found.", ephemeral=True)
        if poll["blind"] and not poll["closed"]:
            return await interaction.response.send_message("Blind poll — results locked until close.", ephemeral=True)

        await interaction.response.send_message(embed=self.results_embed(poll))


async def setup(bot: commands.Bot):
    await bot.add_cog(Polls(bot))
