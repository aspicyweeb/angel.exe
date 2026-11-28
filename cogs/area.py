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
        self.board = [[None for _ in range(10)] for _ in range(10)]
        self.colors = {p1.id: "pink", p2.id: "lavender"}
        self.selected = None

    def current_player(self):
        return self.p1 if self.turn % 2 == 0 else self.p2

    def render(self) -> io.BytesIO:
        cell = 36
        img = Image.new("RGB", (10 * cell, 10 * cell), (255, 245, 248))
        draw = ImageDraw.Draw(img)
        for y in range(10):
            for x in range(10):
                c = self.board[y][x]
                color = (255, 230, 236) if not c else COLORS.get(c, (200, 200, 200))
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
        p1s = sum(1 for row in self.game.board for c in row if c == "pink")
        p2s = sum(1 for row in self.game.board for c in row if c == "lavender")
        total = max(1, p1s + p2s)
        sel = f" • Selected: {self.game.selected}" if self.game.selected else ""
        embed = discord.Embed(
            title="Area",
            color=discord.Color.from_rgb(*COLORS[self.game.colors[p.id]])
        )
        embed.add_field(
            name=self.game.p1.display_name,
            value=f"`{p1s}` ({p1s / total * 100:.0f}%)",
            inline=True
        )
        embed.add_field(
            name=self.game.p2.display_name,
            value=f"`{p2s}` ({p2s / total * 100:.0f}%)",
            inline=True
        )
        embed.set_footer(text=f"It's {p.display_name}'s turn{sel}")
        embed.set_image(url="attachment://area.png")
        return embed

    async def refresh(self, interaction: discord.Interaction):
        file = discord.File(self.game.render(), "area.png")
        await interaction.response.edit_message(
            embed=self.make_embed(),
            attachments=[file],
            view=self
        )

    @discord.ui.button(label="Pink", style=discord.ButtonStyle.primary, emoji="💗")
    async def pink(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.pick_color(interaction, "pink")

    @discord.ui.button(label="Light Pink", style=discord.ButtonStyle.primary, emoji="🌸")
    async def lightpink(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.pick_color(interaction, "lightpink")

    @discord.ui.button(label="Lavender", style=discord.ButtonStyle.primary, emoji="💜")
    async def lavender(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.pick_color(interaction, "lavender")

    async def pick_color(self, interaction: discord.Interaction, color: str):
        if interaction.user.id != self.game.current_player().id:
            return await interaction.response.send_message("Not your turn.", ephemeral=True)
        self.game.selected = color
        await self.refresh(interaction)

    @discord.ui.button(label="1", style=discord.ButtonStyle.secondary, row=1)
    async def b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_num(interaction, 0)

    @discord.ui.button(label="2", style=discord.ButtonStyle.secondary, row=1)
    async def b2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_num(interaction, 1)

    @discord.ui.button(label="3", style=discord.ButtonStyle.secondary, row=1)
    async def b3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_num(interaction, 2)

    @discord.ui.button(label="4", style=discord.ButtonStyle.secondary, row=1)
    async def b4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_num(interaction, 3)

    @discord.ui.button(label="5", style=discord.ButtonStyle.secondary, row=1)
    async def b5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_num(interaction, 4)

    @discord.ui.button(label="6", style=discord.ButtonStyle.secondary, row=2)
    async def b6(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_num(interaction, 5)

    @discord.ui.button(label="7", style=discord.ButtonStyle.secondary, row=2)
    async def b7(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_num(interaction, 6)

    @discord.ui.button(label="8", style=discord.ButtonStyle.secondary, row=2)
    async def b8(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_num(interaction, 7)

    @discord.ui.button(label="9", style=discord.ButtonStyle.secondary, row=2)
    async def b9(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_num(interaction, 8)

    @discord.ui.button(label="10", style=discord.ButtonStyle.secondary, row=2)
    async def b10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_num(interaction, 9)

    async def place_num(self, interaction: discord.Interaction, n: int):
        if interaction.user.id != self.game.current_player().id:
            return await interaction.response.send_message("Not your turn.", ephemeral=True)
        if not self.game.selected:
            return await interaction.response.send_message("Pick a color first.", ephemeral=True)

        placed = False
        for y in range(10):
            if self.game.board[y][n] is None:
                self.game.board[y][n] = self.game.selected
                placed = True
                break

        if not placed:
            return await interaction.response.send_message("That column is full.", ephemeral=True)

        self.game.selected = None
        self.game.turn += 1
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