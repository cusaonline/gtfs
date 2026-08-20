"""
Created: 9-AUG-2026
Updated: 20-AUG-2026
Contact: admin@cusaonline.ca
"""

import os
import requests
from google.transit import gtfs_realtime_pb2
import json
import zipfile
import sqlite3
import pandas

def gtfs_schedule_request():
    return requests.get("https://oct-gtfs-emasagcnfmcgeham.z01.azurefd.net/public-access/GTFSExport.zip")

# TODO: merge the safe requests dev branch
# format can be 'json' or 'protobuf'
def gtfs_realtime_request(format = 'json'):
    param = {'format': format}
    api_key = os.getenv('OC_API_KEY')
    header = {'Ocp-Apim-Subscription-Key': api_key}

    return requests.get("https://nextrip-public-api.azure-api.net/octranspo/gtfs-rt-tp/beta/v1/TripUpdates",
                        params=param, headers=header)

def gtfs_schedule_update():
    with open('gtfs_static.zip', 'bw+') as s:
        s.write(gtfs_schedule_request().content)

def gtfs_realtime_update():
    with open('gtfs_update.json', 'w+') as r:
        js = json.loads(gtfs_realtime_request('json').content)
        r.write(json.dumps(js, indent=2))

def gtfs_initialize_database():
    gtfs_schedule_update()

    with zipfile.ZipFile('gtfs_static.zip', 'r') as zipf:
        # TODO: maybe clean out the directory before unzipping more files into it
        zipf.extractall('gtfs_static')

    with sqlite3.connect('gtfs.db') as conn:
        for file in os.listdir('gtfs_static'):
            # TODO: maybe fix this so it doesn't need "high-memory mode"
            data = pandas.read_csv('gtfs_static/' + file, low_memory=False)
            data.to_sql(file.split('.')[0], conn, index=False, if_exists='replace')

def gtfs_signboard_update(stop_list):
    with sqlite3.connect('gtfs.db') as conn:
        curr = conn.cursor()
        for stop, name in stop_list.items():
            for row in curr.execute("SELECT * FROM stops WHERE stop_id = :stop", {"stop": stop}):
                print("%s (%s): %s"%(name, row[1] + ("%s"%row[14] if row[14] else "") , "info"))


if __name__ == '__main__':

    # gtfs_initialize_database()
    # gtfs_realtime_update()

    # TODO: stop hardcoding all of these values and filenames
    # how the hell do you make a config file?
    stop_list = {"990": "Teraanga",
               "10737": "Nicole",
               "10738": "Athletics",
               "10147": "Nesbitt",
               "10146": "TT Centre",
               "10145": "Stadium",
               "CG990": "O-Train North",
               "CG995": "O-Train South"}

    gtfs_signboard_update(stop_list)

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(gtfs_realtime_request('protobuf').content)
