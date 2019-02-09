import discord, asyncio, aiohttp, os
from music import Music
from discord.ext import commands
from utils import *

MOTD_TEXT = "2 + 2 is 4. Minus 1 that's 3, quick maffs."
if not discord.opus.is_loaded():
	discord.opus.load_opus('opus')

bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'))
bot.add_cog(Music(bot))
server = None
user_agent = get_user_agent()
loop = asyncio.get_event_loop()  
client = aiohttp.ClientSession(loop=loop)

async def my_background_task():
	await bot.wait_until_ready()
	channel = discord.Object(os.environ['MOTD_CHANNEL_ID'])
	while not bot.is_closed:
		if MOTD_TEXT:
			await bot.send_message(channel, MOTD_TEXT)
		await asyncio.sleep(60 * 60 * 24)

@bot.command(pass_context=True)
async def motd(ctx, *, text):
	global MOTD_TEXT
	MOTD_TEXT = text
	await bot.say("{0.message.author.mention} set the MOTD to '{1}'.".format(ctx, MOTD_TEXT))

@bot.event
async def on_ready():
	print('Logged in as')
	print(bot.user.name)
	print(bot.user.id)
	print('------')
	server = bot.get_server(os.environ['DISCORD_SERVER_ID'])

@bot.listen()
async def on_message(message):
	if message.author.bot:
		return
	print(message.author, "-", message.content)

if __name__ == "__main__":
	client.loop.create_task(my_background_task())
	bot.run(os.environ['DISCORD_BOT_TOKEN']) #NOT MINE
