import discord, asyncio, requests, aiohttp, html, json, random, sys
from discord.ext import commands
from bs4 import BeautifulSoup
from utils import *
from gmusicapi import Mobileclient
import urllib.request as request


bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'))

if not discord.opus.is_loaded():
	discord.opus.load_opus('opus')

MOTD_TEXT = ""
VOLUME_LEVEL = .1

async def my_background_task():
	await bot.wait_until_ready()
	channel = discord.Object(id='')
	while not bot.is_closed:
		if MOTD_TEXT:
			await bot.send_message(channel, MOTD_TEXT)
		await asyncio.sleep(60 * 60)

@bot.command(pass_context=True)
async def motd(ctx, *, text):
	global MOTD_TEXT
	MOTD_TEXT = text
	await bot.say("{0.message.author.mention} set the MOTD to '{1}'.".format(ctx, MOTD_TEXT))

class VoiceEntry:
	def __init__(self, message, player, data):
		self.requester = message.author
		self.channel = message.channel
		self.player = player
		self.data = data

	def __str__(self):
		# fmt = '*{0.title}* uploaded by {0.uploader} and requested by {1.display_name}'
		# duration = self.player.duration
		# if duration:
		# 	fmt = fmt + ' [length: {0[0]}m {0[1]}s]'.format(divmod(duration, 60))
		# return fmt.format(self.player, self.requester)
		return "{artist} - {title}".format(**self.data)

class VoiceState:
	def __init__(self, bot):
		self.current = None
		self.voice = None
		self.bot = bot
		self.play_next_song = asyncio.Event()
		self.songs = asyncio.Queue()
		self.skip_votes = set() # a set of user_ids that voted
		self.audio_player = self.bot.loop.create_task(self.audio_player_task())

	def is_playing(self):
		if self.voice is None or self.current is None:
			return False

		player = self.current.player
		return not player.is_done()

	@property
	def player(self):
		return self.current.player

	def skip(self):
		self.skip_votes.clear()
		if self.is_playing():
			self.player.stop()

	def toggle_next(self):
		self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

	async def audio_player_task(self):
		while True:
			self.play_next_song.clear()
			self.current = await self.songs.get()
			await self.bot.send_message(self.current.channel, 'Now playing ' + str(self.current))
			self.current.player.start()
			await self.play_next_song.wait()

class Music:
	def __init__(self, bot):
		self.bot = bot
		self.voice_states = {}
		self.api = Mobileclient()
		self.logged_in = self.api.login('email', 'password', '1234567890abcdef')
		self.VOLUME_LEVEL = .1

	def get_permissions(self):
		permissions = ""
		try:
			with open("permissions.txt", "r") as f:
				permissions = f.read()
		except Exception as e:
			with open("permissions.txt", "a") as f:
				f.write("")

		return permissions

	def get_voice_state(self, server):
		state = self.voice_states.get(server.id)
		if state is None:
			state = VoiceState(self.bot)
			self.voice_states[server.id] = state

		return state

	def check(self, ctx):
		command_text = "!{0}:{1}".format(ctx.command, ctx.message.author.mention)

		if command_text not in self.get_permissions():
			print(command_text, "doesn't have access.")
			self.bot.say('You do not have permissions for this command.')
			return False
		return True

	async def create_voice_client(self, channel):
		voice = await self.bot.join_voice_channel(channel)
		state = self.get_voice_state(channel.server)
		state.voice = voice

	def __unload(self):
		for state in self.voice_states.values():
			try:
				state.audio_player.cancel()
				if state.voice:
					self.bot.loop.create_task(state.voice.disconnect())
			except:
				pass

	@commands.command(pass_context=True, no_pm=True)
	async def join(self, ctx, *, channel : discord.Channel):
		try:
			await self.create_voice_client(channel)
		except discord.ClientException:
			await self.bot.say('Already in a voice channel...')
		except discord.InvalidArgument:
			await self.bot.say('This is not a voice channel...')
		else:
			await self.bot.say('Ready to play audio in ' + channel.name)

	@commands.command(pass_context=True, no_pm=True)
	async def summon(self, ctx):
		if not self.check(ctx): 
			await self.bot.say("You don't have access to that command.")
			return
		"""Summons the bot to join your voice channel."""
		summoned_channel = ctx.message.author.voice_channel

		if summoned_channel is None:
			await self.bot.say('You are not in a voice channel.')
			return False

		state = self.get_voice_state(ctx.message.server)
		if state.voice is None:
			state.voice = await self.bot.join_voice_channel(summoned_channel)
		else:
			await state.voice.move_to(summoned_channel)

		return True

	@commands.command(pass_context=True, no_pm=True)
	async def play(self, ctx, *, song : str):
		# if not self.check(ctx): 
		# 	await self.bot.say("You don't have access to that command.")
		# 	return
		"""Plays a song.
		If there is a song currently in the queue, then it is
		queued until the next song is done playing.
		This command automatically searches as well from YouTube.
		The list of supported sites can be found here:
		https://rg3.github.io/youtube-dl/supportedsites.html
		"""
		state = self.get_voice_state(ctx.message.server)
		opts = {
			'default_search': 'auto',
			'quiet': True,
		}

		if state.voice is None:
			success = await ctx.invoke(self.summon)
			if not success:
				return

		def s():
			results = self.api.search(song, max_results=1)
			with open("output.txt", "wb") as f:
				f.write(str(results["song_hits"]).encode(sys.stdout.encoding, errors='replace'))
			track = results['song_hits'][0]['track']
			song_id = track['storeId']
			artist = track['artist']
			# album = track['album']
			title = track['title']
			# track_nr = track['trackNumber']
			# year = track['year']
			# genre = track['genre']
			# album_artist = track['albumArtist']
			album_art = track['albumArtRef'][0]['url']
			url = self.api.get_stream_url(song_id)
			# print(track, song_id, artist, album, title, track_nr, year, genre, album_artist)
			return url, title, artist, album_art

		try:
			track_url, title, artist, album_art = s()
			track_raw = request.urlopen(track_url)
			import glob
			if "./music/{}_{}.mp3".format(artist, title) not in glob.glob("./music/*.mp3"):
				await self.bot.say("Downloading {}'s {}.mp3".format(artist, title))
				with open("./music/{}_{}.mp3".format(artist, title), "wb") as track_file:
					track_file.write(track_raw.read())
					track_file.close()

			# player = state.voice.create_stream_player(track_raw, after=state.toggle_next)
			player = state.voice.create_ffmpeg_player("./music/{}_{}.mp3".format(artist, title), after=state.toggle_next)
			data = {
				"title": title,
				"artist": artist,
				"album_art": album_art
			}
			# await state.voice.play_audio(open("temp.mp3", "rb"))
			# raise Exception("Not really an error")
		except Exception as e:
			fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
			await self.bot.send_message(ctx.message.channel, fmt.format(type(e).__name__, e))
		else:
			player.volume = self.VOLUME_LEVEL
			entry = VoiceEntry(ctx.message, player, data)
			# await self.bot.say('Enqueued ' + str(entry))
			em = discord.Embed(title=data["artist"], description=data["title"], colour=0xDEADBF)
			em.set_author(name="Queued", icon_url=data["album_art"])
			await self.bot.say("Beamin' up the music.", embed=em)
			await state.songs.put(entry)

	@commands.command(pass_context=True, no_pm=True)
	async def volume(self, ctx, value : int):
		if not self.check(ctx): 
			await self.bot.say("You don't have access to that command.")
			return

		"""Sets the volume of the currently playing song."""

		state = self.get_voice_state(ctx.message.server)
		if state.is_playing():
			player = state.player
			player.volume = value / 100
			self.VOLUME_LEVEL = player.volume
			await self.bot.say('Set the volume to {:.0%}'.format(player.volume))

	@commands.command(pass_context=True, no_pm=True)
	async def pause(self, ctx):
		if not self.check(ctx): 
			await self.bot.say("You don't have access to that command.")
			return

		"""Pauses the currently played song."""
		state = self.get_voice_state(ctx.message.server)
		if state.is_playing():
			player = state.player
			player.pause()

	@commands.command(pass_context=True, no_pm=True)
	async def resume(self, ctx):
		if not self.check(ctx): 
			await self.bot.say("You don't have access to that command.")
			return
		"""Resumes the currently played song."""
		state = self.get_voice_state(ctx.message.server)
		if state.is_playing():
			player = state.player
			player.resume()

	@commands.command(pass_context=True, no_pm=True)
	async def stop(self, ctx):
		if not self.check(ctx): 
			await self.bot.say("You don't have access to that command.")
			return
		"""Stops playing audio and leaves the voice channel.
		This also clears the queue.
		"""
		server = ctx.message.server
		state = self.get_voice_state(server)

		if state.is_playing():
			player = state.player
			player.stop()

		try:
			state.audio_player.cancel()
			del self.voice_states[server.id]
			await state.voice.disconnect()
		except:
			pass

	@commands.command(pass_context=True, no_pm=True)
	async def skip(self, ctx):
		# if not self.check(ctx): 
		# 	await self.bot.say("You don't have access to that command.")
		# 	return
		"""Vote to skip a song. The song requester can automatically skip.
		3 skip votes are needed for the song to be skipped.
		"""

		state = self.get_voice_state(ctx.message.server)
		if not state.is_playing():
			await self.bot.say('Not playing any music right now...')
			return

		num_members = len(ctx.message.server.members)

		voter = ctx.message.author
		if voter == state.current.requester:
			await self.bot.say('Requester requested skipping song...')
			state.skip()
		elif voter.id not in state.skip_votes:
			state.skip_votes.add(voter.id)
			total_votes = len(state.skip_votes)
			if total_votes >= num_members * .5:
				await self.bot.say('Skip vote passed, skipping song...')
				state.skip()
			else:
				await self.bot.say('Skip vote added, currently at [{}/3]'.format(total_votes))
		else:
			await self.bot.say('You have already voted to skip this song.')

	@commands.command(pass_context=True, no_pm=True)
	async def playing(self, ctx):
		if not self.check(ctx): 
			await self.bot.say("You don't have access to that command.")
			return
		"""Shows info about the currently played song."""

		state = self.get_voice_state(ctx.message.server)
		if state.current is None:
			await self.bot.say('Not playing anything.')
		else:
			skip_count = len(state.skip_votes)
			await self.bot.say('Now playing {} [skips: {}/3]'.format(state.current, skip_count))

	# @commands.command(pass_context=True, no_pm=True)
	# async def test(self, ctx):
	# 	em = discord.Embed(title='My Embed Title', description='My Embed Content.', colour=0xDEADBF)
	# 	em.set_author(name='Someone', icon_url=bot.user.default_avatar_url)
	# 	await self.bot.say("test", embed=em)

	@commands.command(pass_context=True)
	async def grant(self, ctx, user, command):
		if not self.check(ctx): 
			await self.bot.say("You don't have access to that command.")
			return
		permissions = self.get_permissions()
		commands = command.split("+")
		for command in commands:
			to_file_text = "!{0}:{1}".format(command, user)

			if to_file_text in permissions:
				permissions = permissions.replace(to_file_text + "\n", "")
				with open("permissions.txt", "w") as f:
					f.write(permissions)
				await self.bot.say("Removed {} access to !{}".format(user, command))
			else:
				with open("permissions.txt", "a") as f:
					f.write(to_file_text + "\n")
				await self.bot.say("Granted {} access to !{}".format(user, command))

bot.add_cog(Music(bot))

@bot.event
async def on_ready():
	print('Logged in as')
	print(bot.user.name)
	print(bot.user.id)
	print('------')

user_agent = get_user_agent()

REDDIT_URL = "https://www.reddit.com/.rss"
get_headers = string_to_dict("""
	Host: www.reddit.com
	Connection: keep-alive
	Cache-Control: max-age=0
	Upgrade-Insecure-Requests: 1
	User-Agent: {user_agent}
	Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8
	Accept-Encoding: gzip, deflate, sdch, br
	Accept-Language: en-US,en;q=0.8
""".format(user_agent = user_agent))

async def get_json(client, url):
	try:
		async with client.get(url) as response:
			print(url)
			assert response.status == 200
			return await response.read()
	except Exception as e:
		return

cache = []
async def get_top_posts(client, subreddit, amount):
	url = "https://reddit.com/r/{}/.json".format(subreddit)
	async with client.get(url = url, headers = get_headers) as r:
		data = await get_json(client, url)
		j = json.loads(data.decode("utf-8"))
		urls = []
		for child in j["data"]["children"]:
			data = child["data"]
			try:
				url = data["url"]
				if "reddit.com" in url:
					url = data["selftext"]
				# if any(_ in url for _ in [".jpg", ".jpeg", ".gif", ".png"]) \
					# and url not in cache:
				if not data["over_18"]:
					urls.append(url)
					cache.append(url)
			except Exception as e:
				print(str(e))
		# return random.choice(urls)
		try:
			resp = random.choice(urls)
			return resp
		except Exception as e:
			print(str(e))
			return "was only {}% shitty, need {}% shitty to shitpost".format(random.randint(1, 100), random.randint(1, 100))

loop = asyncio.get_event_loop()  
client = aiohttp.ClientSession(loop=loop)


# @bot.command(pass_context=True)
# async def join(ctx):
# 	voice = await bot.join_voice_channel(ctx.message.channel)
# 	player = await voice.create_ytdl_player('https://www.youtube.com/watch?v=d62TYemN6MQ')
# 	player.start()

# @bot.command()
# async def shitpost(subreddit="all", amount=1):
# 	try:
# 		for _ in range(amount):
# 			await bot.say(await get_top_posts(client, subreddit, amount))
# 	except Exception as e:
# 		print(e)
# 		await bot.say("i'm broken :(")

# @bot.command(pass_context=True)
# async def purge(ctx):
# 	await bot.purge_from(ctx.message.channel)

# @bot.listen()
# async def on_message(message):
# 	if message.author.bot:
# 		return
# 	print(message.author, "-", message.content)
  
client.loop.create_task(my_background_task())
bot.run("bot-token-here") #NOT MINE
