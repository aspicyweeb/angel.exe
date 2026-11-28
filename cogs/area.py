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
        img = Image.new("RGB", (10*cell, 10*cell), (255, 245, 248))
        draw = ImageDraw.Draw(img)
        for y in range(10):
            for x in range(10):
                c = self.board[y][x]
                color = (255, 230, 236) if not c else COLORS.get(c, (200,200,200))
                draw.rectangle([x*cell, y*cell, (x+1)*cell-2, (y+1)*cell-2], fill=color, outline=(240, 200, 210))
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
        embed = discord.Embed(title="Area", color=discord.Color.from_rgb(*COLORS[self.game.colors[p.id]]))
        embed.add_field(name=self.game.p1.display_name, value=f"`{p1s}` ({p1s/total*100:.0f}%)", inline=True)
        embed.add_field(name=self.game.p2.display_name, value=f"`{p2s}` ({p2s/total*100:.0f}%)", inline=True)
        embed.set_footer(text=f"It's {p.display_name}'s turn • Pick a color then a number")
        embed.set_image(url="attachment://area.png")
        return embed

    async def refresh(self, interaction: discord.Interaction):
        file = discord.File(self.game.render(), "area.png")
        await interaction.response.edit_message(embed=self.make_embed(), attachments=[file], view=self)

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
        await interaction.response.send_message(f"Selected **{color}**. Now pick a number.", ephemeral=True)

    @discord.ui.button(label="1", style=discord.ButtonStyle.secondary, row=1)
    async def b1(self, i, b): await self.place_num(i, 0)
    @discord.ui.button(label="2", style=discord.ButtonStyle.secondary, row=1)
    async def b2(self, i, b): await self.place_num(i, 1)
    @discord.ui.button(label="3", style=discord.ButtonStyle.secondary, row=1)
    async def b3(self, i, b): await self.place_num(i, 2)
    @discord.ui.button(label="4", style=discord.ButtonStyle.secondary, row=1)
    async def b4(self, i, b): await self.place_num(i, 3)
    @discord.ui.button(label="5", style=discord.ButtonStyle.secondary, row=1)
    async def b5(self, i, b): await self.place_num(i, 4)

    @discord.ui.button(label="6", style=discord.ButtonStyle.secondary, row=2)
    async def b6(self, i, b): await self.place_num(i, 5)
    @discord.ui.button(label="7", style=discord.ButtonStyle.secondary, row=2)
    async def b7(self, i, b): await self.place_num(i, 6)
    @discord.ui.button(label="8", style=discord.ButtonStyle.secondary, row=2)
    async def b8(self, i, b): await self.place_num(i, 7)
    @discord.ui.button(label="9", style=discord.ButtonStyle.secondary, row=2)
    async def b9(self, i, b): await self.place_num(i, 8)
    @discord.ui.button(label="10", style=discord.ButtonStyle.secondary, row=2)
    async def b10(self, i, b): await self.place_num(i, 9)

    async def place_num(self, interaction: discord.Interaction,