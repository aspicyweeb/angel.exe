import io
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw

COLORS = {
    "pink": (250, 128, 177),
    "lightpink": (254, 197, 231),
    "blush": (253, 226, 228),
    "cream": (255, 241, 230),
    "lavender": (228, 189, 254),
}

class AreaGame:
    def __init__(self, p1: discord.Member, p2: discord.Member):
        self.p1 = p1
        self.p2 = p2
        self.turn = 0
        self.board = [[None for _ in range(12)] for _ in range(12)]
        self.scores = {p1.id: 0, p2.id: 0}
        self.passed = [False, False]
        self.colors = {p1.id: "pink", p2.id: "lavender"}

    def current_player(self):
        return self.p1 if self.turn % 2 == 0 else self.p2

    def color_of(self, user_id):
        return self.colors[user_id]

    def place(self, x: int, y: int, user_id: int) -> bool:
        if not (0 <= x < 12 and 0 <= y < 12) or self.board[y][x] is not None:
            return False

        if self.scores[user_id] == 0:
            if (user_id == self.p1.id and y > 5) or (user_id == self.p2.id and y < 6):
                return False
            self.board[y][x] = user_id
            self.scores[user_id] += 1
            return True

        corner = any(
            0 <= x+dx < 12 and 0 <= y+dy < 12 and self.board[y+dy][x+dx] == user_id
            for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1)]
        )
        if not corner:
            return False

        edge = any(
            0 <= x+dx < 12 and 0 <= y+dy < 12 and self.board[y+dy][x+dx] == user_id
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]
        )
        if edge:
            return False

        self.board[y][x] = user_id
        self.scores[user_id] += 1
        return True

    def render(self) -> io.BytesIO:
        cell = 28
        img = Image.new("RGB", (12*cell+2, 12*cell+2), (255, 245, 248))
        draw = ImageDraw.Draw(img)
        for y in range(12):
            for x in range(12):
                owner = self.board[y][x]
                color = (255, 230, 236) if not owner else COLORS[self.colors[owner]]
                draw.rectangle([x*cell+1, y*cell+1, (x+1)*cell, (y+1)*cell], fill=color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

class AreaView(discord.ui.View):
    def __init__(self, game: AreaGame):
        super().__init__(timeout=600)
        self.game = game

    def make_embed(self):
        player = self.game.current_player()
        p1s = self.game.scores[self.game.p1.id]
        p2s = self.game.scores[self.game.p2.id]
        total = max(1, p1s + p2s)
        embed = discord.Embed(title="Area", color=discord.Color.from_rgb(*COLORS[self.game.color_of(player.id)]))
        embed.add_field(name=self.game.p1.display_name, value=f"`{p1s}` ({p1s/total*100:.0f}%)", inline=True)
        embed.add_field(name=self.game.p2.display_name, value=f"`{p2s}` ({p2s/total*100:.0f}%)", inline=True)
        embed.set_footer(text=f"It's {player.display_name}'s turn")
        embed.set_image(url="attachment://area.png")
        return embed

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.secondary)
    async def pass_turn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.game.current_player():
            return await interaction.response.send_message("Not your turn.", ephemeral=True)
        self.game.passed[self.game.turn % 2] = True
        self.game.turn += 1
        if all(self.game.passed):
            return await self.end_game(interaction)
        file = discord.File(self.game.render(), "area.png")
        await interaction.response.edit_message(embed=self.make_embed(), attachments=[file], view=self)

    @discord.ui.button(label="Place", style=discord.ButtonStyle.primary)
    async def place_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.game.current_player():
            return await interaction.response.send_message("Not your turn.", ephemeral=True)
        await interaction.response.send_modal(PlaceModal(self.game, self))

    async def end_game(self, interaction: discord.Interaction):
        p1s = self.game.scores[self.game.p1.id]
        p2s = self.game.scores[self.game.p2.id]
        winner = self.game.p1 if p1s > p2s else self.game.p2 if p2s > p1s else None
        embed = discord.Embed(title="Area — Game Over", color=0xFA80B1)
        embed.add_field(name=self.game.p1.display_name, value=str(p1s), inline=True)
        embed.add_field(name=self.game.p2.display_name, value=str(p2s), inline=True)
        embed.description = f"**{winner.display_name}** wins!" if winner else "It's a tie!"
        file = discord.File(self.game.render(), "area.png")
        embed.set_image(url="attachment://area.png")
        await interaction.response.edit_message(embed=embed, attachments=[file], view=None)

class PlaceModal(discord.ui.Modal, title="Place Square"):
    x = discord.ui.TextInput(label="X (0-11)")
    y = discord.ui.TextInput(label="Y (0-11)")

    def __init__(self, game, view):
        super().__init__()
        self.game = game
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            x, y = int(self.x.value), int(self.y.value)
        except ValueError:
            return await interaction.response.send_message("Invalid coordinates.", ephemeral=True)

        if self.game.place(x, y, self.game.current_player().id):
            self.game.passed = [False, False]
            self.game.turn += 1
            file = discord.File(self.game.render(), "area.png")
            await interaction.response.edit_message(embed=self.view.make_embed(), attachments=[file], view=self.view)
        else:
            await interaction.response.send_message("Invalid placement (must touch your color by a corner, not an edge).", ephemeral=True)

class Area(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="area", description="Start an Area game")
    async def area(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot or opponent == interaction.user:
            return await interaction.response.send_message("Invalid opponent.", ephemeral=True)

        game = AreaGame(interaction.user, opponent)
        view = AreaView(game)
        file = discord.File(game.render(), "area.png")
        await interaction.response.send_message(embed=view.make_embed(), file=file, view=view)

async def setup(bot):
    await bot.add_cog(Area(bot))