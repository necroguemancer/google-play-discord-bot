import asyncio
import os

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

	async def clean_song(self):
		try:
			song_info = str(self.current).split(' - ')
			mp3_file = "./music/{}_{}.mp3".format(song_info[0], song_info[1])
			print("Attempting to delete: " + mp3_file)
			if os.path.isfile(mp3_file):
				os.remove(mp3_file)
		except FileNotFoundError:
			print("Couldn't find the file to delete.")

	async def audio_player_task(self):
		while True:
			print("Clearing the song: " + str(self.current))
			self.play_next_song.clear()
			print("Starting the next song: " + str(self.current))
			self.current = await self.songs.get()
			await self.bot.send_message(self.current.channel, 'Now playing ' + str(self.current))
			self.current.player.start()
			print("Started the current song: " + str(self.current))
			await self.play_next_song.wait()
			await self.clean_song()
