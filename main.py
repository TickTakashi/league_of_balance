import requests
from datetime import datetime
import time
import sys
import os
import json
import random

from os import path

HEADERS = {
	'X-Riot-Token': 'RGAPI-55e0b534-73e8-4b23-92de-5a77d9ffe8a8',
}

MAX_ATTEMPTS = 5
RANKED_QUEUE_ID = 420 # 420 is Ranked Solo Queue.
PATCH_TIME = 1580900400000 # The time of the patch of interest (in unix milli)
COLLECTION_TIME = 601200000 # How much time either side of patch to collect data (6 days 23 hours in milli, due to 1 week limit on riot api).
seconds_between_requests = 1.2

tiers = ["DIAMOND", "PLATINUM", "GOLD", "SILVER", "BRONZE", "IRON"]
divisions = ["I", "II", "III", "IV"]
reg = "na1"

leagues_5x5_uri = "https://{region}.api.riotgames.com/lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{division}?page={{page_index}}"	
summoner_uri = "https://{region}.api.riotgames.com/lol/summoner/v4/summoners/{summonerId}"
matchlist_uri = "https://{region}.api.riotgames.com/lol/match/v4/matchlists/by-account/{encryptedAccountId}?queue=420&beginTime={beginTime}&endTime={endTime}"
matchdata_uri = "https://{region}.api.riotgames.com/lol/match/v4/matches/{gameId}"

accountIDs_suffix = "_ACCOUNT_IDS"
folder_name = "data"
aggregate_folder = "aggregate"
size_file = "standard_play_league_page_sizes.txt"
page_sizes = {}

max_matchlist_shard_size = 5


RANDOM_SEED = 19930904



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
		stamped_print("Polling page %s of %s" % (index, formatted))

		r = requests.get(formatted.format(page_index=index), headers=HEADERS)
		t0 = datetime.now()

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


def riot_get(uri, attempt=0):
	#stamped_print("Attempting GET %s" % uri)
	if attempt > 0:
		stamped_print("Attempt %s - Backing off for %s seconds" % (attempt + 1, attempt * seconds_between_requests))
		time.sleep(attempt * seconds_between_requests)

	try:
		r = requests.get(uri, headers=HEADERS)
		
		t0 = datetime.now()
		while (datetime.now() - t0).total_seconds() < seconds_between_requests:
			time.sleep(0.05)

		if r.ok and r.text != "[]":
			#print("[%s] - GET Success - code %s" % (datetime.now(), r.status_code))
			return r.text
		else:
			stamped_print("GET FAIL - HTTP Code %s, Content %s" % (r.status_code, r.text))
			if r.status_code == 429 and attempt < MAX_ATTEMPTS:
				return riot_get(uri, attempt + 1)
			else:
				return False
	except:
		stamped_print("UNKNOWN FAIL - Attempting Again...")
		return riot_get(uri, attempt + 1)


def get_division_page(region, tier, division, page_index):
	uri = leagues_5x5_uri.format(region=region, tier=tier, division=division).format(page_index=page_index)
	#print("[%s] - Reading page %s of (%s, %s, %s)" % (datetime.now(), page_index,region, tier, division))
	return riot_get(uri)


def stamped_print(instr):
	print("[%s] - %s" % (datetime.now(), instr))


def discover_page_sizes():
	stamped_print("Reading Page Count File")
	global page_sizes
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
		f = open(size_file, "w+")
		page_sizes = discover_sizes(f)
		stamped_print("Page size file Generated.")
		stamped_print("Page size dictionary\n%s" % page_sizes)
	finally:
		f.close()

	stamped_print("Page Counts Loaded")
	stamped_print(page_sizes)


def download_players():
	if not page_sizes:
		discover_page_sizes()

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
				pagefile_name = os.path.join(division_folder, str(i).zfill(6))

				if os.path.exists(pagefile_name):
					stamped_print("[%s %s (Page %s/%s)] SKIPPED - Page Exists" % (t, d, i, sz))
				else:
					pagestr = get_division_page(reg, t, d, i)

					if pagestr:
						stamped_print("[%s %s (Page %s/%s)] SUCCESS" % (t, d, i, sz))
						f = open(pagefile_name, "w")
						f.write(pagestr)
						f.close()
					else:
						stamped_print("[%s %s (Page %s/%s)] FAIL - QUITTING" % (t, d, i, sz))
						exit()


# Parse account IDs from the given tiers of play using the player data downloaded.
def parse_accountIDs(ranked_tiers, sample_percentage=0.10):
	if not page_sizes:
		discover_page_sizes()

	agg_folder = os.path.join(folder_name, aggregate_folder)
	if not os.path.exists(agg_folder):
		os.mkdir(agg_folder)

	summonerIDs = []
	for t in ranked_tiers:
		for d in divisions:			
			sz = page_sizes[(t,d)]
			stamped_print("Downloading Account IDs for %s %s (%s Pages Expected)" % (t, d, sz))
			for i in range(1, sz + 1):
				save_location = os.path.join(folder_name, t, d, str(i).zfill(6))
				if not os.path.exists(save_location):
					stamped_print("[%s %s (Page %s/%s)] FAIL - %s does not exist" % (t, d, i, sz, save_location))
					exit()
				else:
					f = open(save_location, "r")
					page_str = f.read()
					player_list = json.loads(page_str)
					for p in player_list:
						summonerIDs.append(p["summonerId"])

					stamped_print("[%s %s (Page %s/%s)] SUCCESS. Total %s summonerIDs found" % (t, d, i, sz, len(summonerIDs)))


	random.seed(RANDOM_SEED)
	num_to_sample = int(sample_percentage * len(summonerIDs))
	sample = random.sample(summonerIDs, num_to_sample)

	stamped_print("Sampled %s/%s IDs Randomly (Seed: %s)" % (num_to_sample, len(summonerIDs), RANDOM_SEED))

	accs_file = os.path.join(agg_folder, "_".join(ranked_tiers) + "_SUMMONER_IDS")
	f = open(accs_file, "w")
	for sid in sample:
		f.write("%s\n" % sid)
	f.close()

	stamped_print("Saved SummonerIDs to %s" % accs_file)

	accs_file = os.path.join(agg_folder, "_".join(ranked_tiers) + accountIDs_suffix)
	accsname = accs_file
	filecount = 1

	if os.path.exists(accs_file):
		while os.path.exists(accsname):
			accsname = accs_file + "_" + str(filecount)
			filecount += 1

		os.rename(accs_file, accsname)
		stamped_print("File %s exists. Renaming to %s" % (accs_file, accsname))

	f = open(accs_file, "w")
	
	accountIDs = []
	sample_i = 1
	for sid in sample:
		summoner_data = riot_get(summoner_uri.format(region=reg, summonerId=sid))
		try:
			summoner_data = json.loads(summoner_data)
		
			if summoner_data and "accountId" in summoner_data:
				aid = summoner_data["accountId"]
				accountIDs.append(aid)
				f.write("%s\n" % aid)
				stamped_print("SUCCESS (%s/%s) - Fetched AccountID for %s - %s" % (sample_i, len(sample), sid, aid))
			else:
				stamped_print("SKIPPED (%s/%s) - No AccountID for %s" % (sample_i, len(sample), sid))
		except:
			stamped_print("SKIPPED (%s/%s) - JSON Parse Error for %s" % (sample_i, len(sample), sid))

		sample_i += 1

	f.close()

	stamped_print("Saved AccountIDs to %s" % accs_file)


# Download matchlists from the given time period for all account IDs.
def download_matchlists(ranked_tiers):
	accountIDs_filename = os.path.join(folder_name, aggregate_folder, "_".join(ranked_tiers) + accountIDs_suffix)
	f = open(accountIDs_filename, "r")
	account_file_str = f.read()
	accountIDs = account_file_str.strip().split("\n")
	f.close()

	matchlists = {}

	matchlist_folder = os.path.join(folder_name, aggregate_folder, "_".join(ranked_tiers) + "_matches")
	if not os.path.exists(matchlist_folder):
		os.mkdir(matchlist_folder)
		stamped_print("Creating Folder %s for shards" % matchlist_folder)
	else:
		stamped_print("Folder %s exists. Please manually backup existing folder and delete it before continuing" % matchlist_folder)
		exit()

	shard_matches = []
	shard_index = 0

	aid_index = 1
	for aid in accountIDs:
		stamped_print("(%s/%s) Getting Matches for %s" % (aid_index, len(accountIDs), aid))
		# get the matchlist from the before time interval
		matchlist_before_data = riot_get(matchlist_uri.format(region=reg, encryptedAccountId=aid, beginTime=(PATCH_TIME - COLLECTION_TIME), endTime=PATCH_TIME))
		if matchlist_before_data:
			stamped_print("\tSTEP 1 SUCCESS - Retrieved Pre-patch matches")
		else:
			stamped_print("\tSTEP 1 FAILED - Unable to Retrieve matches in this timeframe (Pre Patch)")
			
		# get the matchlist from the after time interval
		matchlist_after_data = riot_get(matchlist_uri.format(region=reg, encryptedAccountId=aid, beginTime=(PATCH_TIME - COLLECTION_TIME), endTime=PATCH_TIME))
		if matchlist_after_data:
			stamped_print("\tSTEP 2 SUCCESS - Retrieved Post-patch matches")
		else:
			stamped_print("\tSTEP 2 FAILED - Unable to Retrieve matches in this timeframe (Post Patch)")

		# combine matchlists
		combined_matchlist = []

		try:
			combined_matchlist = json.loads(matchlist_before_data)["matches"] + json.loads(matchlist_after_data)["matches"]
			stamped_print("\tSTEP 3 - Parsed and combined matchlists")
		except:
			stamped_print("\tSTEP 3 FAILED - Error Parsing Matchlist for %s." % aid)

		matchlists[aid] = combined_matchlist

		stamped_print("\tSTEP 4 - Begin fetching %s matches for %s" % (len(combined_matchlist), aid))

		match_count = 0
		# get each match from the combined matchlist
		for match in combined_matchlist:
			match_count += 1
			matchdata = riot_get(matchdata_uri.format(region=reg, gameId=match["gameId"]))
			
			if matchdata:
				# add each match to the shard
				shard_matches.append(matchdata)
				stamped_print("\t\t SUCCESS (%s/%s)" % (match_count, len(combined_matchlist)))


				# if shard is oversize then save to disk and start new shard
				if len(shard_matches) > max_matchlist_shard_size:
					next_shard_filename = os.path.join(matchlist_folder, "MATCHES_" + str(shard_index).zfill(6))
					try:
						current_shard = open(next_shard_filename, "w")
						for smd in shard_matches:
							match_dict = json.loads(smd)

							small_match_dict = {}
							small_match_dict["gameVersion"] = match_dict["gameVersion"]
							small_match_dict["gameId"] = match_dict["gameId"]
							small_match_dict["gameCreation"] = match_dict["gameCreation"]
							small_match_dict["gameDuration"] = match_dict["gameDuration"]
							small_match_dict["teams"] = []

							for tm in match_dict["teams"]:
								small_team_dict = {}
								small_team_dict["win"] = tm["win"]
								small_team_dict["teamId"] = tm["teamId"]
								small_team_dict["bans"] = []
								for bn in tm["bans"]:
									small_team_dict["bans"].append(bn["championId"])

								small_match_dict["teams"].append(small_team_dict)

							small_match_dict["participants"] = []
							for ps in match_dict["participants"]:
								small_part_dict = {}
								small_part_dict["participantId"] = ps["participantId"]
								small_part_dict["championId"] = ps["championId"]
								small_part_dict["teamId"] = ps["teamId"]
								small_match_dict["participants"].append(small_part_dict)

							small_json = json.dumps(small_match_dict)
							current_shard.write(small_json + "\n")
							
						stamped_print("MATCH SHARD FILE %s WRITTEN" % next_shard_filename)
						current_shard.close()
					except:
						stamped_print("Could not save Shard File. This is Really bad.")

					shard_index += 1
					shard_matches = []
			else:
				stamped_print("\t\t SKIPPED (%s/%s)" % (match_count, len(combined_matchlist)))

		aid_index += 1

	if len(shard_matches) > 0:
		next_shard_filename = os.path.join(matchlist_folder, "MATCHES_" + str(shard_index).zfill(6))
		current_shard = open(next_shard_filename, "w")
		current_shard.write(json.dumps(shard_matches))
		stamped_print("FINAL MATCH SHARD FILE %s WRITTEN" % next_shard_filename)
		current_shard.close()

	try:
		master_matchlist_filename = os.path.join(matchlist_folder, "MASTER_MATCHLIST")
		f = open(master_matchlist_filename)
		f.write(json.dumps(matchlists))
		f.close()

		stamped_print("Master matchlist saved as %s" % master_matchlist_filename)
	except:
		stamped_print("Failed to save master matchlist")






# Download match data for all matchIDs in the matchlists.
def download_match_data():
	pass



if len(sys.argv) > 1:
	folder_name = sys.argv[1]
	stamped_print("Writing to folder: %s" % folder_name)
else:
	stamped_print("No folder_name given, writing to folder: %s" % folder_name)

if not path.exists(folder_name):
	os.mkdir(folder_name)
else:
	stamped_print("Warning. Path %s exists. Overwriting data inside." % folder_name)


#parse_accountIDs(["DIAMOND", "PLATINUM"])
download_matchlists(["DIAMOND", "PLATINUM"])

'''



f = open(filename,"w+")

f.write(get_division_page("na1", "GOLD", "I", 1))

f.close()
'''