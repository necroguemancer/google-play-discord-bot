import discord, asyncio, requests, aiohttp, html, json, random, sys, os
from discord.ext import commands
from gmusicapi import Mobileclient
from voice_state import VoiceState
from voice_entry import VoiceEntry
from permissions import Permissions
from bs4 import BeautifulSoup
import urllib.request as request

VOLUME_LEVEL = .1

class Music:

	def __init__(self, bot):
		self.bot = bot
		self.voice_states = {}
		self.api = Mobileclient()
		self.logged_in = self.api.oauth_login(os.environ['HARDWARE_ID'], "{}{}".format(os.environ['CREDENTIALS_FILE_DIR'], os.environ['CREDENTIALS_FILE_NAME']))
		self.permissions = Permissions(os.environ['DEFAULT_ADMIN'])
		self.VOLUME_LEVEL = .1

	def get_voice_state(self, server):
		state = self.voice_states.get(server.id)
		if state is None:
			state = VoiceState(self.bot)
			self.voice_states[server.id] = state

		return state

	def check(self, ctx):
		if self.permissions.check_permission(self.permissions.admin_perm, ctx.message.author.id):
			return True
		return self.permissions.check_permission(ctx.command, ctx.message.author.id)

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
			print(os.getcwd() + '/music/')
			if not os.path.exists(os.getcwd() + '/music/'):
				os.mkdir(os.getcwd() + '/music/')
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
			print("Data from track: %s" % data["artist"])
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

	@commands.command(pass_context=True)
	async def grant(self, ctx, permission, requesting_user):
		try:
			self.permissions.grant_permission(permission, ctx.message.author.id, requesting_user)
		except PermissionError as pe:
			await self.bot.say(pe)

	@commands.command(pass_context=True)
	async def revoke(self, ctx, permission, requesting_user):
		try:
			self.permissions.remove_permission(permission, ctx.message.author.id, requesting_user)
		except PermissionError as pe:
			await self.bot.say(pe)