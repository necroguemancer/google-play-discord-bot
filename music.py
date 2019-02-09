import discord, asyncio, requests, aiohttp, html, json, random, sys, os, glob, traceback
from discord.ext import commands
from gmusicapi import Mobileclient
from voice_state import VoiceState
from voice_entry import VoiceEntry
from bs4 import BeautifulSoup
import urllib.request as request

VOLUME_LEVEL = .1

class Music:

	def __init__(self, bot, permissions):
		self.bot = bot
		self.voice_states = {}
		self.api = Mobileclient()
		self.logged_in = self.api.oauth_login(os.environ['HARDWARE_ID'], "{}{}".format(os.environ['CREDENTIALS_FILE_DIR'], os.environ['CREDENTIALS_FILE_NAME']))
		self.permissions = permissions
		self.VOLUME_LEVEL = .1
		if not os.path.exists(os.getcwd() + '/music/'):
				os.mkdir(os.getcwd() + '/music/')

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

	def song_search(self, song, max_results=2):
		results = self.api.search(song, max_results=max_results)
		print("Results from api: " + json.dumps(results, indent=4))
		found_songs = []
		for index in range(0, max_results):
			track = results.get('song_hits', [])[index].get('track', '')
			found_songs.append({
				"track": track,
				"song_id": track.get('storeId', ''),
				"artist": track.get('artist', ''),
				"title": track.get('title', ''),
				"album_art": track.get('albumArtRef', [])[0].get('url', ''),
				"url": self.api.get_stream_url(track.get('storeId', '')),
				"explicit_type": track.get('explicitType', "1")
			})
		found_songs = list(filter(lambda x: x.get('explicit_type') is "1", found_songs))
		if max_results is 2 and len(found_songs) is 2:
			del found_songs[1]
		return found_songs

	async def song_download(self, artist, title, track_url):
		track_raw = request.urlopen(track_url)
		if "./music/{}_{}.mp3".format(artist, title) not in glob.glob("./music/*.mp3"):
			await self.bot.say("Downloading {}'s {}.mp3".format(artist, title))
			with open("./music/{}_{}.mp3".format(artist, title), "wb") as track_file:
				track_file.write(track_raw.read())
				track_file.close()

	async def prep_ffmpeg(self, state, song_info_list):
		song_data_list = []
		player_list = []
		for song in song_info_list:
			artist = song.get('artist')
			title = song.get('title')
			await self.song_download(artist, title, song.get('url'))
			player_list.append(state.voice.create_ffmpeg_player("./music/{}_{}.mp3".format(artist, title), after=state.toggle_next))
			song_data_list.append({
				"title": title,
				"artist": artist,
				"album_art": song.get('album_art')
			})
		return player_list, song_data_list

	async def beam_music(self, ctx, state, players, data_list):
		for index in range(0, len(players)):
			players[index].volume = self.VOLUME_LEVEL
			entry = VoiceEntry(ctx.message, players[index], data_list[index])
			em = discord.Embed(title=data_list[index].get("artist"), description=data_list[index].get("title"), colour=0xDEADBF)
			em.set_author(name="Queued", icon_url=data_list[index].get("album_art"))
			await self.bot.say("Beamin' up the music.", embed=em)
			await state.songs.put(entry)

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
		state = self.get_voice_state(ctx.message.server)
		opts = {
			'default_search': 'auto',
			'quiet': True,
		}

		if state.voice is None:
			success = await ctx.invoke(self.summon)
			if not success:
				return

		try:
			song_info_list = self.song_search(song)
			players, data_list = await self.prep_ffmpeg(state, song_info_list)
		except Exception as e:
			fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
			await self.bot.send_message(ctx.message.channel, fmt.format(type(e).__name__, e))
		else:
			await self.beam_music(ctx, state, players, data_list)

	@commands.command(pass_context=True, no_pm=True)
	async def playlist(self, ctx, *, song : str):
		state = self.get_voice_state(ctx.message.server)
		opts = {
			'default_search': 'auto',
			'quiet': True,
		}

		if state.voice is None:
			success = await ctx.invoke(self.summon)
			if not success:
				return

		try:
			song_info_list = self.song_search(song, max_results=10)
			players, data_list = await self.prep_ffmpeg(state, song_info_list)
		except Exception as e:
			traceback.print_exc()
			fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
			await self.bot.send_message(ctx.message.channel, fmt.format(type(e).__name__, e))
		else:
			await self.beam_music(ctx, state, players, data_list)

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
		if voter == state.current.requester or self.permissions.check_permission(self.permissions.admin_perm, ctx.message.author.id):
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