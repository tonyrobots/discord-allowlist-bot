import os
from discord.ext import commands

bot = commands.Bot(command_prefix="!")
TOKEN = os.getenv("DISCORD_TOKEN")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}({bot.user.id})")

@bot.command()
async def gm(ctx):
    await ctx.send("gm to you, " + command.user.name)

if __name__ == "__main__":
    bot.run(TOKEN)
