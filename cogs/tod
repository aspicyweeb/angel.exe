import random
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

import storage

HEATS = ("chill", "chaotic", "bold")

DECKS: dict[tuple[str, str], tuple[str, ...]] = {
    ("chill", "truth"): (
        "What's a server you lurk in and never type in?",
        "Which notification is actually on, and which one is muted forever?",
        "What's the last message you typed and then deleted?",
        "What song have you had on loop this week?",
        "What's a hill you'll die on that everyone else thinks is stupid?",
        "What's your most-used emoji, and what does it mean when you send it?",
        "Who here would you trust to pick your next profile picture?",
        "What's a show you finished and then pretended you didn't watch?",
        "What time do you actually go to sleep, not the time you claim?",
        "What's an old username you'd rather not claim out loud?",
        "What's the pettiest reason you've muted someone?",
        "What app do you open first when you pick up your phone?",
        "What's a compliment you got online that stuck?",
        "Which channel here do you read and never type in?",
        "What's a food you talk about like you eat it, and you don't?",
        "What's a hobby you picked up because of someone on the internet?",
        "What does your status usually lie about?",
        "What's a meme format you still think is funny?",
        "What's the longest you've gone without opening Discord, and what brought you back?",
        "What's a server rule you secretly think is dumb?",
        "What's the YouTube video you replay when you don't know what else to put on?",
        "What nickname do you wish people here used?",
        "What's a take you posted and then got nervous about the replies?",
        "Which friend of yours would last the longest in this server?",
        "What's something you collect that isn't useful?",
        "What playlist would you put this server on?",
        "What word do you overuse when you're typing fast?",
        "Who here has main-character energy, and why?",
        "What's a trend you refused, even ironically?",
        "What's the smallest thing that ruins your mood online?",
        "What did you want to be at 10, and how far off is it?",
        "What's a server emoji you use wrong on purpose?",
        "What's something you're good at that never comes up in chat?",
        "Who was the last DM you left on read, no name required, and why?",
        "If this server had a yearbook, what's your superlative?",
        "What's your comfort game, show, or album right now?",
        "What does your desktop or home screen say about you? Describe it, don't post it yet.",
        "What's a channel name you've always wanted a server to have?",
        "What's the last thing you laughed at in this server that nobody else seemed to notice?",
        "What would your loading-screen tip be?",
    ),
    ("chill", "dare"): (
        "Change your nickname to your current mood. Ten minutes. Then you can change it back.",
        "Reply to the last message here with at least three emojis and no words.",
        "Send a GIF that sums up your day. No caption.",
        "Type as much of the alphabet as you can without looking. Send it unedited.",
        "Post a photo of your drink, or the closest thing. No face.",
        "Your next five messages in this channel are lowercase only.",
        "React to the last five messages with the same emoji.",
        "Drop the last song you listened to. Link or title.",
        "Review this server in two sentences, like a food critic.",
        "Compliment the last person who typed. Specific. Not 'you're cool.'",
        "Post your current status and leave it up for ten minutes.",
        "Send a message that uses no letter E.",
        "Quote a lyric that fits the last ten messages.",
        "Set your status to a fake confession. Keep it light.",
        "Reply to someone with a haiku about their last message.",
        "Post the third photo in your camera roll. Crop anything you don't want seen.",
        "Your next four messages here are questions.",
        "Rate your day with emojis, then translate them.",
        "Name an underrated channel here and say why in one line.",
        "Write your autobiography in exactly eight words.",
        "Post a screenshot of your new tab page or home screen.",
        "Rename yourself to the last thing you ate. Ten minutes.",
        "Send one message that would make a stranger think this server is wholesome.",
        "Do a text impression of the general vibe of this server. One short paragraph.",
        "Share a win from this week. A tiny one counts.",
        "Post a color. Don't explain it for two minutes.",
        "Send the last meme you saved.",
        "Write fake patch notes for yourself, version today.",
        "Your next three messages use one emoji as the only punctuation.",
        "Post a photo of the ceiling, the desk, or the wall in front of you. No faces.",
        "Give this bot a one-sentence nickname, posted here.",
        "Type a message with your eyes closed. Send it unedited.",
        "Start a two-sentence story. Stop there.",
        "Post your hottest take about a font, a color, or a UI.",
        "Name a song that fits the person directly above you in the member list.",
        "Write a warning label for your profile.",
        "Send a loading-screen tip about this server.",
        "Describe your typing style like a Pokemon entry.",
        "Post a photo of your shoes or your socks. Floor only.",
        "Rank your last three meals, S tier to F tier.",
    ),
    ("chaotic", "truth"): (
        "What's the most unhinged thing in your search history this month that you're willing to describe?",
        "What's a lie you told in a voice chat that is still standing?",
        "Which of your own messages would ruin you if it got screenshotted?",
        "What's a bit you took too far?",
        "What's the pettiest server drama you've enjoyed as a spectator?",
        "What do you pretend to understand in chat and absolutely don't?",
        "What's a habit you have in VC that would annoy you if someone else did it?",
        "What's the last thing you sent, regretted, and left up anyway?",
        "Whose Discord account would you swap with for a day, and what's the first channel you'd open?",
        "What's a rumor you would start about yourself for fun?",
        "What's your most unearned confidence?",
        "What notification have you ignored for over a week?",
        "What bit do you know is annoying, and you're keeping it?",
        "What's the most chaotic server you've stayed in on purpose?",
        "What would your enemies put in your about me?",
        "What rule do you break in every server and hope nobody notices?",
        "What's the last thing you got weirdly competitive about in chat?",
        "What do people assume from your profile that is wrong?",
        "What's a message you've drafted to someone here and never sent?",
        "What's your toxic typing trait?",
        "What's the strangest thing you've become known for in a server?",
        "What would you do with mod powers for one hour if none of it was logged? Keep it reversible.",
        "What's a hill you died on in a server and later found out you were wrong?",
        "What's the most dramatic way you've left a server?",
        "What emoji do you send when you're mad and pretending you're not?",
        "What's the last conversation you lurked that you weren't part of?",
        "What part of your online personality is a character?",
        "What's the pettiest role or badge you've ever wanted?",
        "What would a detective learn from your last twenty messages?",
        "What's a joke you keep making that has never landed?",
        "Who here is your lawyer, your hype person, and your liability? Three names or three descriptions.",
        "What's something you only admit after midnight?",
        "What's the worst autocorrect you've sent and left up?",
        "If your mute list leaked, what would the pattern be?",
        "What's a username you've seen someone defend that still haunts you?",
        "What would the leaked group chat nickname for you be?",
    ),
    ("chaotic", "dare"): (
        "Change your nickname to a spoiler. Don't say what it's from.",
        "Send the next message with your hands shifted one key to the right. No fixing it.",
        "Argue the opposite of what you believe about pineapple on pizza. Four sentences. Commit.",
        "Post a screenshot of your recent emojis.",
        "Your next three messages are in third person.",
        "Write a Yelp review of the last VC you were in. If you haven't been in one, review this channel.",
        "Read the last message like a movie trailer. Voice note, or typed like one.",
        "React to the oldest message you can quickly find here with something unhinged.",
        "Post your most recent screenshot. Crop anything private.",
        "Invent a fake rule and enforce it like a mod for the next five minutes. Don't actually timeout anyone.",
        "Write a dramatic apology to the last emoji you used.",
        "Set your status to the last thing you ate, described like wine.",
        "Tell a story in exactly five one-word messages.",
        "Rank the last three people who typed as if they were houseplants. No comments about bodies.",
        "Write a breakup text to an app you use too much.",
        "Your next two messages are in a fake accent. Spell it out. Commit.",
        "Send the most boring sentence you can.",
        "Nickname yourself 'currently a problem' for ten minutes.",
        "Quote your own last message and drag it.",
        "Start a poll nobody asked for. Two options. Post it.",
        "Describe your desktop wallpaper. Make it sound like a confession.",
        "Write the patch notes for the worst version of yourself.",
        "Your next two replies are GIFs only.",
        "Three emojis for this server. Then defend them.",
        "Pretend you're customer support for this channel and answer the last thing anyone said.",
        "Announce your current status like it's official.",
        "Write a four-line poem that includes the words 'muted' and 'anyway.'",
        "Change your nickname to the last error message you saw.",
        "Send a very polite message in all caps.",
        "Rat yourself out. One thing you did here that nobody noticed.",
        "Pitch a role that should exist. Two sentences. Don't make the role.",
        "Reply to someone with a fun fact about them that is obviously fake.",
        "Type the alphabet backwards until you mess up. Leave the mess.",
        "Send a message that is just the word 'anyway' and then a real sentence.",
        "Describe your last notification like it's breaking news.",
        "Post a tier list of the tabs you currently have open. Describe them.",
    ),
    ("bold", "truth"): (
        "What's something you want credit for that you never asked for?",
        "Who are you jealous of right now, and for what? No comments about bodies.",
        "What's a friendship you let die instead of fixing?",
        "What's the meanest thought you've had in this server and not typed?",
        "What are you avoiding by being online tonight?",
        "What's a promise you made in a DM and didn't keep?",
        "What do you want people here to think about you that isn't quite true?",
        "When did you last make something about you that wasn't?",
        "What are you scared people will notice if they actually pay attention?",
        "What's a grudge you're still holding that you could drop?",
        "What do you do when you're lonely that you don't call lonely?",
        "What conversation are you overdue for?",
        "Who are you performing for in this server?",
        "What did you outgrow that you're still pretending you like?",
        "What's the kindest thing someone here did that you never really answered?",
        "What would you apologize for if you knew it would land okay?",
        "What's a goal you stopped mentioning because nobody asked again?",
        "When did you last feel left out here, even a little?",
        "What's a story you tell about yourself that is edited?",
        "What are you protective of that doesn't need protecting?",
        "What do you need right now that isn't advice?",
        "Who would you be embarrassed to see read your last ten messages?",
        "What standard do you hold other people to and not yourself?",
        "When were you last the problem in a chat?",
        "What do you wish this server did more of?",
        "What's a soft opinion you hide because the loud version gets the attention?",
        "What have you been postponing for more than a month?",
        "What do you miss that you don't talk about?",
        "Who do you owe a real reply?",
        "What would 'enough' look like this week, in one sentence?",
        "What boundary did you let slide recently?",
        "What was the last thing that made you feel actually known?",
        "What are you pretending isn't a big deal?",
        "If you logged off for a week, what would you be afraid to miss, and what would you be relieved to miss?",
        "What quality do you want that you don't practice?",
        "What do you want said back to you the next time you tell the truth?",
    ),
    ("bold", "dare"): (
        "Post one honest sentence. No joke after it.",
        "Thank someone specific for something specific. Only tag them if you mean it.",
        "Admit one thing you've been postponing. You don't have to fix it.",
        "Write the reply you've been sitting on. Post it here. Names optional.",
        "Say what you need tonight in six words.",
        "Give a real compliment you would usually turn into a bit.",
        "Correct something you exaggerated recently.",
        "Name one boundary, plainly.",
        "Write an apology you owe. You don't have to send it to them.",
        "Drop the bit. Your next three messages are normal sentences.",
        "Say one thing you like about this server that isn't a joke.",
        "Tell one small truth you've edited out of the story before.",
        "Ask for help with something small. It has to be real.",
        "Post a win you downplayed.",
        "Change your status to what you're actually doing.",
        "Write what you'd say if you weren't managing the vibe.",
        "Credit someone for an idea you ran with.",
        "Say the quiet standard you wish this chat had.",
        "Admit a grudge, and one reason you could retire it. You don't have to.",
        "Name the last app you opened that says something about your night.",
        "Describe your energy right now. No meme.",
        "Send a message and don't edit it. The typo stays.",
        "Say one thing you want to be known for here.",
        "Rewrite your last message so it's kinder and still honest.",
        "Name a topic you avoid here, and why. One sentence.",
        "Ask someone a real question. Not a bit.",
        "Say what you were about to lurk through.",
        "Post a photo of something ordinary from tonight. Cup, desk, ceiling. No face.",
        "Name one reply you'll actually send after this. Say who, not the drama.",
        "Write a truth this deck should have asked. That's the dare.",
        "Your next message gets no 'lol', no 'idk', and no 'lowkey.'",
        "Say something you appreciate about someone who isn't the loudest here.",
        "Admit where you were unfair this week.",
        "Post a sentence you needed to hear, in the exact wording.",
        "Give your actual opinion on the last topic. Not the fun version.",
        "Say you're done performing for the next ten minutes, then type like it.",
    ),
}


def _heat_from(message: discord.Message) -> str:
    if message.embeds and message.embeds[0].footer and message.embeds[0].footer.text:
        text = message.embeds[0].footer.text.lower()
        for heat in HEATS:
            if heat in text:
                return heat
    return "chill"


def _panel(heat: str) -> discord.Embed:
    embed = discord.Embed(
        title="Truth or dare",
        description=(
            "You are not in the room with anyone. Dares are things you can do in Discord.\n"
            "A card doesn't come back until every other card in that deck has been used.\n\n"
            "**chill** is low stakes.\n"
            "**chaotic** is unhinged.\n"
            "**bold** is honest. No joke to hide behind."
        ),
        color={"chill": 0x7DDE92, "chaotic": 0xFFB020, "bold": 0xC9A0FF}[heat],
    )
    embed.add_field(name="Heat", value=heat, inline=False)
    embed.set_footer(text=f"heat:{heat}")
    return embed


def _card(user: discord.abc.User, kind: str, heat: str, text: str, left: int, total: int, recycled: bool) -> str:
    if left <= 0:
        tail = f"Last card in this deck. Next {kind} reshuffles. {total} cards."
    else:
        tail = f"{left} left before this {heat} {kind} deck reshuffles."
    lines = [f"{user.mention} · **{kind}** · {heat}", text, tail]
    if recycled:
        lines.append("That deck was empty. Shuffled.")
    return "\n".join(lines)


async def draw(guild_id: int, kind: str, heat: str) -> tuple[str, int, int, bool]:
    deck = DECKS[(heat, kind)]
    async with storage.lock:
        data = storage.load_obj("tod.json")
        guild = data.setdefault(str(guild_id), {})
        if not isinstance(guild, dict):
            guild = {}
            data[str(guild_id)] = guild
        key = f"{heat}:{kind}"
        raw = guild.get(key)
        used: set[int] = set()
        if isinstance(raw, list):
            for item in raw:
                try:
                    number = int(item)
                except (TypeError, ValueError):
                    continue
                if 0 <= number < len(deck):
                    used.add(number)
        left = [index for index in range(len(deck)) if index not in used]
        recycled = False
        if not left:
            left = list(range(len(deck)))
            used = set()
            recycled = True
        pick = random.choice(left)
        used.add(pick)
        guild[key] = sorted(used)
        storage.save("tod.json", data)
    return deck[pick], len(left) - 1, len(deck), recycled


class TodView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _pull(self, interaction: discord.Interaction, kind: str) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message("Use this in the server.", ephemeral=True)
            return
        if kind == "random":
            kind = random.choice(("truth", "dare"))
        heat = _heat_from(interaction.message) if interaction.message else "chill"
        try:
            text, left, total, recycled = await draw(interaction.guild_id, kind, heat)
        except storage.DataError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.send_message(_card(interaction.user, kind, heat, text, left, total, recycled))

    @discord.ui.button(label="Truth", style=discord.ButtonStyle.primary, custom_id="tod:truth", row=0)
    async def truth(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._pull(interaction, "truth")

    @discord.ui.button(label="Dare", style=discord.ButtonStyle.danger, custom_id="tod:dare", row=0)
    async def dare(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._pull(interaction, "dare")

    @discord.ui.button(label="Random", style=discord.ButtonStyle.secondary, custom_id="tod:random", row=0)
    async def random_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._pull(interaction, "random")

    async def _set_heat(self, interaction: discord.Interaction, heat: str) -> None:
        if interaction.message is None:
            await interaction.response.send_message("That board is gone.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=_panel(heat), view=self)

    @discord.ui.button(label="Chill", style=discord.ButtonStyle.success, custom_id="tod:chill", row=1)
    async def chill(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_heat(interaction, "chill")

    @discord.ui.button(label="Chaotic", style=discord.ButtonStyle.secondary, custom_id="tod:chaotic", row=1)
    async def chaotic(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_heat(interaction, "chaotic")

    @discord.ui.button(label="Bold", style=discord.ButtonStyle.secondary, custom_id="tod:bold", row=1)
    async def bold(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_heat(interaction, "bold")


class Tod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TodView())

    @app_commands.command(name="tod", description="Truth or dare that stays in Discord")
    @app_commands.guild_only()
    @app_commands.describe(kind="Leave this empty to post the buttons", heat="Deck to pull from")
    async def tod(
        self,
        interaction: discord.Interaction,
        kind: Optional[Literal["truth", "dare", "random"]] = None,
        heat: Literal["chill", "chaotic", "bold"] = "chill",
    ):
        if interaction.guild_id is None:
            await interaction.response.send_message("Use this in the server.", ephemeral=True)
            return
        if kind is None:
            await interaction.response.send_message(embed=_panel(heat), view=TodView())
            return
        pulled = kind
        if pulled == "random":
            pulled = random.choice(("truth", "dare"))
        try:
            text, left, total, recycled = await draw(interaction.guild_id, pulled, heat)
        except storage.DataError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.send_message(_card(interaction.user, pulled, heat, text, left, total, recycled))

    @app_commands.command(name="todreset", description="Shuffle every truth or dare deck")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def todreset(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            await interaction.response.send_message("Use this in the server.", ephemeral=True)
            return
        async with storage.lock:
            data = storage.load_obj("tod.json")
            data[str(interaction.guild_id)] = {}
            storage.save("tod.json", data)
        await interaction.response.send_message("Decks shuffled. Every card is back in.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tod(bot))