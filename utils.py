from time import sleep, strftime
from datetime import datetime
# from requests.packages.urllib3.exceptions import InsecureRequestWarning
import requests, random
try:
	from faker import Faker
	fake = Faker()
except Exception:
	print("Run \"pip install Faker\" using the correct pip path and you should be fine.")
	# import sys; sys.exit(1)

def string_to_dict(headers):
	headers_dict = {}
	for line in headers.split("\n"):
		if not line: continue
		line = line.strip()
		key, *values = line.split(" ")
		key = key[:-1]
		if not (key and values): continue
		headers_dict[key] = " ".join(values)
	return headers_dict

def get_time():
    return "[" + strftime("%m/%d %H:%M:%S") + "]"

def dump(r):
	with open("dump.html", "w") as f:
		f.write(str(r))

def clean(text):
	return ''.join([i if ord(i) < 128 else ' ' for i in text])

class ThreadManager(object):
	"""docstring for ThreadManager"""
	def __init__(self, MAX_THREADS = 30, MESSAGES = False, TIME = True):
		super(ThreadManager, self).__init__()
		self.MAX_THREADS = MAX_THREADS
		self.MESSAGES = MESSAGES
		self.TIME = TIME
		self.threads = []

	def load(self, thread):
		self.threads.append(thread)

	def clear(self):
		self.threads = []

	def start(self):
		start_time = datetime.now()
		THREAD_COUNT = 0

		for t in self.threads:
			t.daemon = True
			t.start()
			THREAD_COUNT += 1
			if THREAD_COUNT >= self.MAX_THREADS:
				if self.MESSAGES:
					print("Waiting for a thread to end.")
				t.join()
				if self.MESSAGES:
					print("Starting a new thread now.")
				THREAD_COUNT -= 1

		if self.MESSAGES:
			print("Waiting for all threads to end.")
		
		for t in self.threads:
			t.join()

		if self.TIME:
			print(datetime.now() - start_time)		

def get_user_agent():
	return fake.user_agent()

def get_random_name():
	return "{}{}{}".format(fake.first_name(), fake.last_name(), random.randint(1, 100))

# requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
