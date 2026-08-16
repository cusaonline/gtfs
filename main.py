"""
Created: 9-AUG-2026
Updated: 15-AUG-2026
Contact: admin@cusaonline.ca
"""

import os
import requests
from google.transit import gtfs_realtime_pb2

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
    with open('gtfsStatic.zip', 'ba+') as s:
        s.write(gtfs_schedule_request().content)

def gtfs_realtime_update():
    with open('gtfsUpdate.json', 'ba+') as r:
        r.write(gtfs_realtime_request('json').content)

if __name__ == '__main__':

    gtfs_schedule_update()
    gtfs_realtime_update()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(gtfs_realtime_request('protobuf').content)

    for entity in feed.entity:
        if entity.HasField('trip_update'):
            print(entity.trip_update)