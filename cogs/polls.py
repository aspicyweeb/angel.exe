import discord
from discord.ext import commands
from discord import app_commands
import uuid
from datetime import datetime
from typing import Optional

# ── Edit these with your custom emotes (emptiest → fullest) ──
HEART_STAGES = [
    "🤍",   # 0-20%
    "🩷",   # 20-40%
    "❤️",   # 40-60%
    "💖",   # 60-80%
    "💗",   # 80-100%
]


def get_heart_progress(percentage: float, stages: list[str] = HEART_STAGES) -> str:
    if not stages:
        return ""
    percentage = max(0.0, min(100.0, percentage))
    index = int((percentage / 100) * (len(stages) - 1))
    index = min(index, len(stages) - 1)
    return stages[index]


class PollSelect(discord.ui.Select):
    def __init__(self, poll_id: str, options: list[str], max_votes: int):
        select_options = [
            discord.SelectOption(label=opt[:100], value=str(i), description=f"Option {chr(65+i)}")
            for i, opt in enumerate(options)
        ]
        super().__init__(
            placeholder=f"Vote (up to {max_votes})",
            min_values=1,
            max_values=min(max_votes, len(options)),
            options=select_options,
            custom_id=f"poll_select_{poll_id}",
        )
        self.poll_id = poll_id

    async def callback(self, interaction: discord.Interaction):
        cog: "Polls" = interaction.client.get_cog("Polls")
        if not cog:
            return await interaction.response.send_message("Poll system offline.", ephemeral=True)

        poll = cog.polls.get(self.poll_id)
        if not poll or poll["closed"]:
            return await interaction.response.send_message("This poll is closed.", ephemeral=True)

        user_id = interaction.user.id
        chosen = [int(v) for v in self.values]

        # Store / overwrite their votes
        poll["votes"][user_id] = chosen
        await interaction.response.send_message(
            f"Voted for {len(chosen)} option(s). You can change your vote anytime until it closes.",
            ephemeral=True,
        )


class PollView(discord.ui.View):
    def __init__(self, poll_id: str, options: list[str], max_votes: int):
        super().__init__(timeout=None)
        self.add_item(PollSelect(poll_id, options, max_votes))


class Polls(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.polls: dict[str, dict] = {}  # poll_id -> data

    def _build_results_embed(self, poll: dict) -> discord.Embed:
        total_votes = sum(len(v) for v in poll["votes"].values())
        embed = discord.Embed(
            title="Final Result" if poll["closed"] else "Current Results",
            description=poll["question"],
            color=discord.Color.magenta(),
        )

        lines = []
        for i, name in enumerate(poll["options"]):
            count = sum(1 for votes in poll["votes"].values() if i in votes)
            percent = (count / total_votes * 100) if total_votes else 0
            heart = get_heart_progress(percent)
            letter = chr(65 + i)
            lines.append(f"**{letter}** {heart} {name} — {percent:.1f}% ({count})")

        embed.add_field(name="Results", value="\n".join(lines) or "No votes yet", inline=False)
        embed.set_footer(text=f"{total_votes} votes from {len(poll['votes'])} users • Poll ID: {poll['id']}")
        return embed

    @app_commands.command(name="poll_create", description="Create a multi-choice poll")
    @app_commands.describe(
        question="The poll question",
        options="Options separated by | (max 25)",
        max_votes="How many options each person can pick (default 3)",
        blind="Hide results until closed",
    )
    async def poll_create(
        self,
        interaction: discord.Interaction,
        question: str,
        options: str,
        max_votes: app_commands.Range[int, 1, 10] = 3,
        blind: bool = False,
    ):
        opts = [o.strip() for o in options.split("|") if o.strip()]
        if len(opts) < 2 or len(opts) > 25:
            return await interaction.response.send_message("Need 2–25 options.", ephemeral=True)

        poll_id = str(uuid.uuid4())[:8]
        self.polls[poll_id] = {
            "id": poll_id,
            "question": question,
            "options": opts,
            "votes": {},          # user_id: list of option indices
            "max_votes": max_votes,
            "blind": blind,
            "closed": False,
            "created": datetime.utcnow(),
        }

        embed = discord.Embed(
            title="Question",
            description=question,
            color=discord.Color.dark_magenta(),
        )
        choice_text = "\n".join(f"**{chr(65+i)}** {opt}" for i, opt in enumerate(opts))
        embed.add_field(name="Choices", value=choice_text, inline=False)
        embed.add_field(
            name="Settings",
            value=f"Max votes per person: **{max_votes}**\nBlind voting: **{'Yes' if blind else 'No'}**\nPoll ID: `{poll_id}`",
            inline=False,
        )
        embed.set_footer(text="Please don’t vote for yourself if you’re an option")

        view = PollView(poll_id, opts, max_votes)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="poll_close", description="Close a poll and show final results")
    @app_commands.describe(poll_id="The poll ID")
    async def poll_close(self, interaction: discord.Interaction, poll_id: str):
        poll = self.polls.get(poll_id)
        if not poll:
            return await interaction.response.send_message("Poll not found.", ephemeral=True)
        if poll["closed"]:
            return await interaction.response.send_message("Already closed.", ephemeral=True)

        poll["closed"] = True
        embed = self._build_results_embed(poll)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="poll_results", description="Show current or final results")
    @app_commands.describe(poll_id="The poll ID")
    async def poll_results(self, interaction: discord.Interaction, poll_id: str):
        poll = self.polls.get(poll_id)
        if not poll:
            return await interaction.response.send_message("Poll not found.", ephemeral=True)

        if poll["blind"] and not poll["closed"]:
            return await interaction.response.send_message("This poll is blind. Results unlock when it closes.", ephemeral=True)

        embed = self._build_results_embed(poll)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Polls(bot))
