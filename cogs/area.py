import io
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw

COLORS = {
    "pink": (250, 128, 177),
    "lavender": (228, 189, 254),
}

class AreaGame:
    def __init__(self, p1: discord.Member, p2: discord.Member):
        self.p1 = p1
        self.p2 = p2
        self.turn = 0
        self.board = [[None for _ in range(10)] for _ in range(10)]
        self.colors = {p1.id: "pink", p2.id: "lavender"}
        self.passed = [False, False]
        self.ended = False

    def current_player(self):
        return self.p1 if self.turn % 2 == 0 else self.p2

    def score(self, user_id):
        color = self.colors[user_id]
        return sum(1 for row in self.board for c in row if c == color)

    def is_full(self):
        return all(c is not None for row in self.board for c in row)

    def place(self, x: int, user_id: int) -> bool:
        color = self.colors[user_id]
        for y in range(10):
            if self.board[y][x] is None:
                self.board[y][x] = color
                return True
        return False

    def render(self) -> io.BytesIO:
        cell = 36
        img = Image.new("RGB", (10 * cell, 10 * cell), (255, 245, 248))
        draw = ImageDraw.Draw(img)
        for y in range(10):
            for x in range(10):
                c = self.board[y][x]
                color = (255, 230, 236) if not c else COLORS[c]
                draw.rectangle(
                    [x * cell, y * cell, (x + 1) * cell - 2, (y + 1) * cell - 2],
                    fill=color,
                    outline=(240, 200, 210)
                )
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf

class AreaView(discord.ui.View):
    def __init__(self, game: AreaGame):
        super().__init__(timeout=None)
        self.game = game

    def make_embed(self):
        p = self.game.current_player()
        p1s = self.game.score(self.game.p1.id)
        p2s = self.game.score(self.game.p2.id)
        total = max(1, p1s + p2s)

        if self.game.ended:
            if p1s > p2s:
                desc = f"**{self.game.p1.display_name}** wins!"
            elif p2s > p1s:
                desc = f"**{self.game.p2.display_name}** wins!"
            else:
                desc = "It's a tie!"
            embed = discord.Embed(title="Area — Game Over", description=desc, color=0xFA80B1)
        else:
            embed = discord.Embed(
                title="Area",
                color=discord.Color.from_rgb(*COLORS[self.game.colors[p.id]])
            )
            embed.set_footer(text=f"It's {p.display_name}'s turn • Place your color or pass")

        embed.add_field(name=self.game.p1.display_name, value=f"`{p1s}` ({p1s / total * 100:.0f}%)", inline=True)
        embed.add_field(name=self.game.p2.display_name, value=f"`{p2s}` ({p2s / total * 100:.0f}%)", inline=True)
        embed.set_image(url="attachment://area.png")
        return embed

    async def refresh(self, interaction: discord.Interaction):
        file = discord.File(self.game.render(), "area.png")
        view = None if self.game.ended else self
        await interaction.response.edit_message(embed=self.make_embed(), attachments=[file], view=view)

    async def check_end(self):
        if self.game.is_full() or all(self.game.passed):
            self.game.ended = True

    @discord.ui.button(label="Place", style=discord.ButtonStyle.primary, emoji="💗")
    async def place_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.ended:
            return await interaction.response.send_message("Game's over.", ephemeral=True)
        if interaction.user.id != self.game.current_player().id:
            return await interaction.response.send_message("Not your turn.", ephemeral=True)

        # Find first available column
        for x in range(10):
            if any(self.game.board[y][x] is None for y in range(10)):
                self.game.place(x, interaction.user.id)
                self.game.passed = [False, False]
                self.game.turn += 1
                await self.check_end()
                return await self.refresh(interaction)

        await interaction.response.send_message("Board is full.", ephemeral=True)

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.secondary)
    async def pass_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.ended:
            return await interaction.response.send_message("Game's over.", ephemeral=True)
        if interaction.user.id != self.game.current_player().id:
            return await interaction.response.send_message("Not your turn.", ephemeral=True)

        self.game.passed[self.game.turn % 2] = True
        self.game.turn += 1
        await self.check_end()
        await self.refresh(interaction)

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