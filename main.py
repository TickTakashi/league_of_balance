import requests
from datetime import datetime
import time
import sys

def find_size(accessor):
	index = 1
	limitFound = False

	while not limitFound:
		limitFound = not accessor(index)
		if not limitFound:
			index *= 2
		
	upperLimit = index
	lowerLimit = int(index / 2)

	discoveredLimit = binary_search(accessor, lowerLimit, upperLimit)

	return discoveredLimit


def safe_accessor(indexable):
	
	def try_access(i):
		try:
			tmp = indexable(i)
			return True
		except Exception as e:
			#print("Index %s returned error %s" % (i, e))
			return False

	return try_access


def binary_search(check, mn, mx):
	mid = mn + int((mx + 1 - mn) / 2)

	if mx <= mn:
		#print("A%s" %mid)
		return mn
	elif check(mid):
		#print("B%s, %s" % (mid, mx))
		return binary_search(check, mid, mx)
	else:
		#print("C%s, %s" % (mn, mid -1))
		return binary_search(check, mn, mid - 1)



def page_poller(uri, **kwargs):
	formatted = uri.format(**kwargs)
	print("Constructing Poll Function for: %s" % formatted)

	HEADERS = {
		'X-Riot-Token': 'RGAPI-e463d50f-3808-4ca5-8b7c-5a0805169c5f',
	}

	def poller(index):
		t0 = datetime.now()
		print("[%s] - Polling page %s of %s" % (t0, index, formatted))

		r = requests.get(formatted.format(page_index=index), headers=HEADERS)
		
		while (datetime.now() - t0).total_seconds() < 1.2:
			time.sleep(0.05)

		if r.ok and r.text != "[]":
			print("[%s] - Polled %s Successfully with code: %s" % (datetime.now(), index, r.status_code))
		else:
			print("[%s] - Code %s and Content %s" % (datetime.now(), r, r.text))

		return r.ok and r.text != "[]"
		
	return poller

# HEADERS = {
# 	'X-Riot-Token': 'RGAPI-e463d50f-3808-4ca5-8b7c-5a0805169c5f',
# }

# size = find_size(page_poller(leagues_5x5_uri, region="euw1", tier="DIAMOND", division="I"))

# print("Discovered Size: %s" % size)

# time.sleep(1.2)

# r = requests.get(leagues_5x5_uri.format(region="euw1", tier="DIAMOND", division="I").format(page_index=size), headers=HEADERS)

# if r.ok and r.text != "[]":
# 	print("SUCCESS: Polled %s Successfully with code: %s, \nContent: %s" % (size, r.status_code, r.text))
# else:
# 	print("FAILED: Code %s and Content %s" % (r, r.text))

filename = "standard_play_league_page_sizes.txt"

if len(sys.argv) > 1:
	filename = sys.argv[1]
	print("Writing to file: %s" % filename)
else:
	print("No filename given, writing to file: %s" % filename)


f = open(filename,"w+")

leagues_5x5_uri = "https://{region}.api.riotgames.com/lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{division}?page={{page_index}}"

division_size_dict = {}

for t in ["DIAMOND", "PLATINUM", "GOLD", "SILVER", "BRONZE", "IRON"]:
	for d in ["I", "II", "III", "IV"]:
		division_size_dict[(t, d)] = find_size(page_poller(leagues_5x5_uri, region="na1", tier=t, division=d))
		print("%s - %s has page size %s" % (t, d, division_size_dict[(t, d)]))
		f.write("[\"%s\", \"%s\", %s]\n" % (t, d, division_size_dict[(t, d)]))

f.close()