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
import datetime
from operator import itemgetter

def gtfs_schedule_request():
    return requests.get("https://oct-gtfs-emasagcnfmcgeham.z01.azurefd.net/public-access/GTFSExport.zip")

# TODO: merge the safe requests fork by cutie
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

# TODO: actually integrate schedule data
def gtfs_signboard_update(stop_list):
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(gtfs_realtime_request('protobuf').content)

    with sqlite3.connect('gtfs.db') as conn:
        curr = conn.cursor()
        for stop, name in stop_list.items():
            for row in curr.execute('SELECT * FROM stops WHERE stop_id = :stop', {'stop': stop}):
                print("%s (%s): "%(name, row[1] + ("%s"%row[14] if row[14] else "")), end="")
                info = gtfs_get_info(feed, conn, stop)
                for x in range(len(info)):

                    print("%s %s @ %s"%(info[x][0], info[x][1], datetime.datetime.fromtimestamp(info[x][2]).strftime("%H:%M")), end="")

                    if x == len(info)-1:
                        print(".")
                    else:
                        print(", ", end="")

def gtfs_get_info(feed, conn, stop):
    info = list()
    curr = conn.cursor()
    for entity in feed.entity:
        if entity.HasField('trip_update'):
            for update in entity.trip_update.stop_time_update:
                if update.HasField('stop_id') and update.stop_id == stop:
                    trip_id = entity.trip_update.trip.trip_id
                    route_id = entity.trip_update.trip.route_id
                    # TODO: move this query junk to other function. keep all the squirrels in one place
                    headsign = ""
                    for row in curr.execute('SELECT trip_headsign FROM trips WHERE trip_id = :trip_id',
                                            {'trip_id': trip_id}):
                        headsign = row[0]
                    arrv_time = int()
                    if update.HasField('arrival') and update.arrival.HasField('time'):
                        arrv_time = update.arrival.time
                    dprt_time = int()
                    if update.HasField('departure') and update.departure.HasField('time'):
                        dprt_time = update.departure.time
                    stop_time = max(arrv_time, dprt_time)
                    info.append((route_id, headsign, stop_time))
    info.sort(key=itemgetter(2))
    return info


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
               "10145": "Stadium"}

    gtfs_signboard_update(stop_list)


