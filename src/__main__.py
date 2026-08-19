"""
Created: 9-AUG-2026
Updated: 19-AUG-2026
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
        zipf.extractall('gtfs_static')

    with sqlite3.connect('gtfs.db') as conn:
        for file in os.listdir('gtfs_static'):
            data = pandas.read_csv('gtfs_static/' + file, low_memory=False)
            data.to_sql(file.split('.')[0], conn, index=False, if_exists='replace')

if __name__ == '__main__':

    gtfs_initialize_database()
    gtfs_realtime_update()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(gtfs_realtime_request('protobuf').content)
