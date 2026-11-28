import discord
from discord import app_commands
from discord.ext import commands

EMOTES = {
    "donut": "🍩",
    "cupcake": "🧁",
    "slice": "🍰",
    "hit": "💥",
    "miss": "🌸",
    "board": "🍰",
    "attack": "🎯",
}

SHIP_TYPES = [
    ("Donut", 4, "donut"),
    ("Cupcake", 3, "cupcake"),
    ("Slice", 2, "slice"),
]

class BakeryGame:
    def __init__(self, p1: discord.Member, p2: discord.Member):
        self.p1 = p1
        self.p2 = p2
        self.turn = 0
        self.boards = {
            p1.id: [[None for _ in range(5)] for _ in range(5)],
            p2.id: [[None for _ in range(5)] for _ in range(5)],
        }
        self.shots = {p1.id: set(), p2.id: set()}
        self.hits_on = {p1.id: set(), p2.id: set()}
        self.placing = {p1.id: 0, p2.id: 0}
        self.place_start = {p1.id: None, p2.id: None}
        self.ready = {p1.id: False, p2.id: False}
        self.ended = False
        self.last_attack = None

    def current(self):
        return self.p1 if self.turn % 2 == 0 else self.p2

    def opponent(self, user):
        return self.p2 if user.id == self.p1.id else self.p1

    def place_ship(self, user_id: int, x1, y1, x2, y2) -> bool:
        if self.placing[user_id] >= len(SHIP_TYPES):
            return False
        length = SHIP_TYPES[self.placing[user_id]][1]
        if abs(x2 - x1) + abs(y2 - y1) + 1 != length or (x1 != x2 and y1 != y2):
            return False
        cells = []
        if x1 == x2:
            for y in range(min(y1, y2), max(y1, y2) + 1):
                cells.append((x1, y))
        else:
            for x in range(min(x1, x2), max(x1, x2) + 1):
                cells.append((x, y1))
        for x, y in cells:
            if not (0 <= x < 5 and 0 <= y < 5) or self.boards[user_id][y][x] is not None:
                return False
        key = SHIP_TYPES[self.placing[user_id]][2]
        for x, y in cells:
            self.boards[user_id][y][x] = EMOTES[key]
        self.placing[user_id] += 1
        if self.placing[user_id] >= len(SHIP_TYPES):
            self.ready[user_id] = True
        return True

    def attack(self, attacker_id: int, x: int, y: int) -> str:
        if (x, y) in self.shots[attacker_id]:
            return "already"
        self.shots[attacker_id].add((x, y))
        target = self.opponent(self.p1 if attacker_id == self.p1.id else self.p2)
        cell = self.boards[target.id][y][x]
        if cell:
            self.hits_on[target.id].add((x, y))
            return "hit"
        return "miss"

class ChallengeView(discord.ui.View):
    def __init__(self, game: BakeryGame):
        super().__init__(timeout=120)
        self.game = game

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.secondary, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.p2.id:
            return await interaction.response.send_message("Only the challenged person can accept.", ephemeral=True)
        await interaction.response.edit_message(
            content=f"Bakery Battle starting! {self.game.p1.mention} {self.game.p2.mention} click **Place Treats** below.",
            view=PlaceButtonView(self.game)
        )

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Bakery Battle cancelled.", view=None)

class PlaceButtonView(discord.ui.View):
    def __init__(self, game: BakeryGame):
        super().__init__(timeout=None)
        self.game = game

    @discord.ui.button(label="Place Treats", style=discord.ButtonStyle.primary, emoji="🍰")
    async def place(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.game.p1.id, self.game.p2.id):
            return await interaction.response.send_message("You're not in this game.", ephemeral=True)
        if self.game.ready[interaction.user.id]:
            return await interaction.response.send_message("You already placed everything.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        view = PlaceView(self.game, interaction.user.id)
        ship = SHIP_TYPES[self.game.placing[interaction.user.id]]
        await interaction.followup.send(
            f"Place your **{ship[0]}** ({ship[1]} squares). Click start, then end.",
            view=view,
            ephemeral=True
        )

class PlaceView(discord.ui.View):
    def __init__(self, game: BakeryGame, user_id: int):
        super().__init__(timeout=300)
        self.game = game
        self.user_id = user_id
        for y in range(5):
            for x in range(5):
                btn = discord.ui.Button(
                    label="·",
                    style=discord.ButtonStyle.secondary,
                    row=y,
                    custom_id=f"place_{user_id}_{x}_{y}"
                )
                btn.callback = self.make_callback(x, y)
                self.add_item(btn)

    def make_callback(self, x, y):
        async def callback(interaction: discord.Interaction):
            await self.handle_cell(interaction, x, y)
        return callback

    async def handle_cell(self, interaction: discord.Interaction, x: int, y: int):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your board.", ephemeral=True)
        start = self.game.place_start[self.user_id]
        if start is None:
            self.game.place_start[self.user_id] = (x, y)
            await interaction.response.send_message(f"Start set at ({x},{y}). Now click the end.", ephemeral=True)
        else:
            x1, y1 = start
            if self.game.place_ship(self.user_id, x1, y1, x, y):
                self.game.place_start[self.user_id] = None
                msg = "Treat placed!"
                if self.game.ready[self.user_id]:
                    msg += " You're done placing!"
                await interaction.response.send_message(msg, ephemeral=True)
                if all(self.game.ready.values()):
                    await interaction.channel.send("Both ready! Bakery Battle starting.", view=GameView(self.game))
            else:
                self.game.place_start[self.user_id] = None
                await interaction.response.send_message("Invalid placement. Try again.", ephemeral=True)

class GameView(discord.ui.View):
    def __init__(self, game: BakeryGame):
        super().__init__(timeout=None)
        self.game = game

    @discord.ui.button(label="Your Board", style=discord.ButtonStyle.secondary)
    async def own(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Your treats and where they got eaten",
            view=OwnBoardView(self.game, interaction.user.id),
            ephemeral=True
        )

    @discord.ui.button(label="Attack Board", style=discord.ButtonStyle.primary)
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.current().id:
            return await interaction.response.send_message("Not your turn.", ephemeral=True)
        await interaction.response.send_message(
            "Choose a spot to eat.",
            view=AttackView(self.game, interaction.user.id),
            ephemeral=True
        )

class OwnBoardView(discord.ui.View):
    def __init__(self, game: BakeryGame, user_id: int):
        super().__init__(timeout=60)
        board = game.boards[user_id]
        hits = game.hits_on[user_id]
        for y in range(5):
            for x in range(5):
                cell = board[y][x]
                if (x, y) in hits:
                    label, style = EMOTES["hit"], discord.ButtonStyle.danger
                elif cell:
                    label, style = cell, discord.ButtonStyle.success
                else:
                    label, style = "·", discord.ButtonStyle.secondary
                self.add_item(discord.ui.Button(label=label, style=style, row=y, disabled=True))

class AttackView(discord.ui.View):
    def __init__(self, game: BakeryGame, attacker_id: int):
        super().__init__(timeout=60)
        self.game = game
        self.attacker_id = attacker_id
        target = game.opponent(game.p1 if attacker_id == game.p1.id else game.p2)
        for y in range(5):
            for x in range(5):
                if (x, y) in game.shots[attacker_id]:
                    result = EMOTES["hit"] if (x, y) in game.hits_on[target.id] else EMOTES["miss"]
                    btn = discord.ui.Button(label=result, style=discord.ButtonStyle.secondary, row=y, disabled=True)
                else:
                    btn = discord.ui.Button(label="?", style=discord.ButtonStyle.primary, row=y, custom_id=f"atk_{x}_{y}")
                    btn.callback = self.make_shoot(x, y)
                self.add_item(btn)

    def make_shoot(self, x, y):
        async def callback(interaction: discord.Interaction):
            result = self.game.attack(self.attacker_id, x, y)
            if result == "already":
                return await interaction.response.send_message("Already shot there.", ephemeral=True)
            self.game.turn += 1
            self.game.last_attack = f"{interaction.user.display_name} {result}!"
            await interaction.response.edit_message(content=f"You {result}!", view=None)
        return callback

class Bakery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setemote", description="Set a custom emote for Bakery Battle")
    @app_commands.describe(slot="Which emote to change", emote="Paste the custom emote")
    @app_commands.choices(slot=[
        app_commands.Choice(name="Donut", value="donut"),
        app_commands.Choice(name="Cupcake", value="cupcake"),
        app_commands.Choice(name="Slice", value="slice"),
        app_commands.Choice(name="Hit", value="hit"),
        app_commands.Choice(name="Miss", value="miss"),
        app_commands.Choice(name="Your Board button", value="board"),
        app_commands.Choice(name="Attack button", value="attack"),
    ])
    async def setemote(self, interaction: discord.Interaction, slot: app_commands.Choice[str], emote: str):
        EMOTES[slot.value] = emote.strip()
        await interaction.response.send_message(f"Set **{slot.name}** to {emote}", ephemeral=True)

    @app_commands.command(name="bakerybattle", description="Challenge someone to Bakery Battle")
    async def bakerybattle(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot or opponent == interaction.user:
            return await interaction.response.send_message("Invalid opponent.", ephemeral=True)
        game = BakeryGame(interaction.user, opponent)
        await interaction.response.send_message(
            f"{opponent.mention}, you are challenged by **{interaction.user.display_name}** to a **Bakery Battle** 🍰. Do you dare?",
            view=ChallengeView(game)
        )

async def setup(bot):
    await bot.add_cog(Bakery(bot))