import io
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw

COLORS = {
    "pink": (250, 128, 177),      # #FA80B1
    "lightpink": (254, 197, 231), # #FEC5E7
    "blush": (253, 226, 228),     # #FDE2E4
    "cream": (255, 241, 230),     # #FFF1E6
    "lavender": (228, 189, 254),  # #E4BDFE
}

class AreaGame:
    def __init__(self, p1: discord.Member, p2: discord.Member):
        self.p1 = p1
        self.p2 = p2
        self.turn = 0
        self.board = [[None for _ in range(12)] for _ in range(12)]
        self.scores = {p1.id: 0, p2.id: 0}
        self.passed = [False, False]
        self.message = None
        self.colors = {
            p1.id: "pink",
            p2.id: "lavender"
        }

    def current_player(self):
        return self.p1 if self.turn % 2 == 0 else self.p2

    def opponent(self):
        return self.p2 if self.turn % 2 == 0 else self.p1

    def color_of(self, user_id):
        return self.colors[user_id]

    def place(self, x: int, y: int, user_id: int) -> bool:
        if not (0 <= x < 12 and 0 <= y < 12):
            return False
        if self.board[y][x] is not None:
            return False

        if self.scores[user_id] == 0:
            if user_id == self.p1.id and y > 5:
                return False
            if user_id == self.p2.id and y < 6:
                return False
            self.board[y][x] = user_id
            self.scores[user_id] += 1
            return True

        corner = False
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < 12 and 0 <= ny < 12 and self.board[ny][nx] == user_id:
                corner = True
                break
        if not corner:
            return False

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < 12 and 0 <= ny < 12 and self.board[ny][nx] == user_id:
                return False

        self.board[y][x] = user_id
        self.scores[user_id] += 1
        return True

    def render(self) -> io.BytesIO:
        cell = 28
        img = Image.new("RGB", (12 * cell + 2, 12 * cell + 2), (255, 245, 248))
        draw = ImageDraw.Draw(img)

        for y in range(12):
            for x in range(12):
                owner = self.board[y][x]
                color = (255, 230, 236)
                if owner:
                    color = COLORS[self.colors[owner]]
                draw.rectangle(
                    [x * cell + 1, y * cell + 1, (x + 1) * cell, (y + 1) * cell],
                    fill=color
                )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

class AreaView(discord.ui.View):
    def __init__(self, game: AreaGame):
        super().__init__(timeout=600)
        self.game = game

    async def update(self, interaction: discord.Interaction):
        player = self.game.current_player()
        p1_score = self.game.scores[self.game.p1.id]
        p2_score = self.game.scores[self.game.p2.id]
        total = max(1, p1_score + p2_score)

        embed = discord.Embed(
            title="Area",
            color=discord.Color.from_rgb(*COLORS[self.game.color_of(player.id)])
        )
        embed.add_field(
            name=f"{self.game.p1.display_name}",
            value=f"`{p1_score}` ({p1_score / total * 100:.0f}%)",
            inline=True
        )
        embed.add_field(
            name=f"{self.game.p2.display_name}",
            value=f"`{p2_score}` ({p2_score / total * 100:.0f}%)",
            inline=True
        )
        embed.set_footer(text=f"It's {player.display_name}'s turn • Place a square that touches your color by a corner")

        file = discord.File(self.game.render(), filename="area.png")
        embed.set_image(url="attachment://area.png")

        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.secondary)
    async def pass_turn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.game.current_player():
            return await interaction.response.send_message("Not your turn.", ephemeral=True)

        self.game.passed[self.game.turn % 2] = True
        self.game.turn += 1

        if all(self.game.passed):
            await self.end_game(interaction)
            return

        await self.update(interaction)

    @discord.ui.button(label="Place", style=discord.ButtonStyle.primary)
    async def place_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.game.current_player():
            return await interaction.response.send_message("Not your turn.", ephemeral=True)

        modal = PlaceModal(self.game, self)
        await interaction.response.send_modal(modal)

    async def end_game(self, interaction: discord.Interaction):
        p1 = self.game.scores[self.game.p1.id]
        p2 = self.game.scores[self.game.p2.id]
        if p1 > p2:
            winner = self.game.p1
        elif p2 > p1:
            winner = self.game.p2
        else:
            winner = None

        embed = discord.Embed(title="Area — Game Over", color=0xFA80B1)
        embed.add_field(name=self.game.p1.display_name, value=str(p1), inline=True)
        embed.add_field(name=self.game.p2.display_name, value=str(p2), inline=True)
        if winner:
            embed.description = f"**{winner.display_name}** wins!"
        else:
            embed.description = "It's a tie!"

        file = discord.File(self.game.render(), filename="area.png")
        embed.set_image(url="attachment://area.png")
        await interaction.response.edit_message(embed=embed, attachments=[file], view=None)

class PlaceModal(discord.ui.Modal, title="Place Square"):
    x = discord.ui.TextInput(label="X (0-11)", placeholder="0")
    y = discord.ui.TextInput(label="Y (0-11)", placeholder="0")

    def __init__(self, game: AreaGame, view: AreaView):
        super().__init__()
        self.game = game
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            x = int(self.x.value)
            y = int(self.y.value)
        except ValueError:
            return await interaction.response.send_message("Invalid coordinates.", ephemeral=True)

        player = self.game.current_player()
        if self.game.place(x, y, player.id):
            self.game.passed = [False, False]
            self.game.turn += 1
            await self.view.update(interaction)
        else:
            await interaction.response.send_message(
                "Invalid placement. Must touch your color by a **corner** and not by an edge.",
                ephemeral=True
            )

class Area(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="area", description="Start an Area game with someone")
    async def area(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot or opponent == interaction.user:
            return await interaction.response.send_message("Invalid opponent.", ephemeral=True)

        game = AreaGame(interaction.user, opponent)
        view = AreaView(game)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Area",
                description=f"{interaction.user.mention} vs {opponent.mention}",
                color=0xFA80B1
            ),
            view=view
        )
        await view.update(await interaction.original_response())

async def setup(bot):
    await bot.add_cog(Area(bot))