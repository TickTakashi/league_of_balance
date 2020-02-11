import requests
from datetime import datetime
import time
import sys
import os

from os import path

HEADERS = {
	'X-Riot-Token': 'RGAPI-e463d50f-3808-4ca5-8b7c-5a0805169c5f',
}


leagues_5x5_uri = "https://{region}.api.riotgames.com/lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{division}?page={{page_index}}"	

seconds_between_requests = 1.2
tiers = ["DIAMOND", "PLATINUM", "GOLD", "SILVER", "BRONZE", "IRON"]
divisions = ["I", "II", "III", "IV"]
reg = "na1"

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


	def poller(index):
		t0 = datetime.now()
		print("[%s] - Polling page %s of %s" % (t0, index, formatted))

		r = requests.get(formatted.format(page_index=index), headers=HEADERS)
		
		while (datetime.now() - t0).total_seconds() < seconds_between_requests:
			time.sleep(0.05)

		if r.ok and r.text != "[]":
			print("[%s] - Polled %s Successfully with code: %s" % (datetime.now(), index, r.status_code))
		else:
			print("[%s] - Code %s and Content %s" % (datetime.now(), r, r.text))

		return r.ok and r.text != "[]"
		
	return poller


def discover_sizes(file):
	division_size_dict = {}
	for t in tiers:
		for d in divisions:
			division_size_dict[(t, d)] = find_size(page_poller(leagues_5x5_uri, region="na1", tier=t, division=d))
			print("%s - %s has page size %s" % (t, d, division_size_dict[(t, d)]))
			file.write("%s,%s,%s\n" % (t, d, division_size_dict[(t, d)]))
	return division_size_dict


def riot_get(uri):
	t0 = datetime.now()
	#print("[%s] - Attempting GET %s" % (t0, uri))
	
	r = requests.get(uri, headers=HEADERS)
	
	while (datetime.now() - t0).total_seconds() < seconds_between_requests:
		time.sleep(0.05)

	if r.ok and r.text != "[]":
		#print("[%s] - GET Success - code %s" % (datetime.now(), r.status_code))
		return r.text
	else:
		print("[%s] - GET FAIL - HTTP Code %s, Content %s" % (datetime.now(), r.status_code, r.text))
		return False


def get_division_page(region, tier, division, page_index):
	uri = leagues_5x5_uri.format(region=region, tier=tier, division=division).format(page_index=page_index)
	#print("[%s] - Reading page %s of (%s, %s, %s)" % (datetime.now(), page_index,region, tier, division))
	return riot_get(uri)


def stamped_print(instr):
	print("[%s] - %s" % (datetime.now(), instr))
	

folder_name = "data"
size_file = "standard_play_league_page_sizes.txt"

if len(sys.argv) > 1:
	folder_name = sys.argv[1]
	stamped_print("Writing to folder: %s" % folder_name)
else:
	stamped_print("No folder_name given, writing to folder: %s" % folder_name)

if not path.exists(folder_name):
	os.mkdir(folder_name)
else:
	stamped_print("Warning. Path %s exists. Overwriting data inside." % folder_name)


stamped_print("Reading Page Count File")

page_sizes = {}

try:
	f = open(size_file, "r")
	p_size_str = f.read()
	ps = p_size_str.strip().split("\n")
	
	for p_size in ps:
		line = p_size.strip().split(",")
		page_sizes[(line[0], line[1])] = int(line[2])
except IOError:
	stamped_print("Page size file doesn't exist. Generating now...")
	page_sizes = discover_sizes(open(size_file, "w+"))
	stamped_print("Page size file Generated.")
	stamped_print("Page size dictionary\n%s" % page_sizes)
finally:
	f.close()


stamped_print("Page Counts Loaded")
stamped_print(page_sizes)


for t in tiers:
	tier_folder = os.path.join(folder_name, t)
	
	if not os.path.exists(tier_folder):
		os.mkdir(tier_folder)
	
	for d in divisions:
		division_folder = os.path.join(tier_folder, d)
	
		if not os.path.exists(division_folder):
			os.mkdir(division_folder)

		sz = page_sizes[(t,d)]
		stamped_print("Downloading Rankings for %s %s (%s Pages Expected)" % (t, d, sz))
		
		for i in range(1, sz + 1):
			pagestr = get_division_page(reg, t, d, i)
			if pagestr:
				stamped_print("[%s %s (Page %s/%s)] SUCCESS" % (t, d, i, sz))
				
				pagefile_out = os.path.join(division_folder, str(i).zfill(6))

				f = open(pagefile_out, "w")
				f.write(pagestr)
				f.close()
			else:
				stamped_print("[%s %s (Page %s/%s)] FAIL - QUITTING" % (t, d, i, sz))
				exit()
'''



f = open(filename,"w+")

f.write(get_division_page("na1", "GOLD", "I", 1))

f.close()
'''