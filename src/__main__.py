"""
Created: 9-AUG-2026
Updated: 24-AUG-2026
Contact: admin@cusaonline.ca
"""
from dataclasses import dataclass
from operator import itemgetter, truediv
from zoneinfo import ZoneInfo
from google.transit import gtfs_realtime_pb2
from flask import Flask, render_template
from enum import Enum
import datetime
import requests
import sqlite3
import zipfile
import typing
import pandas
import json
import yaml
import os

config = yaml.safe_load(open("config.yaml", 'r'))


class Scheduling(Enum):
    SCHEDULED = 0
    SKIPPED = 1
    NO_DATA = 2
    UNSCHEDULED = 3


@dataclass
class Trip:
    def __init__(self,
                 trip_id: str,
                 headsign: str,
                 bus_num: str,
                 scheduling: int,
                 is_live: bool,
                 bus_time: datetime.datetime
                 ) -> None:
        self.trip_id = trip_id
        self.headsign = headsign
        self.bus_num = bus_num
        self.scheduling = scheduling
        self.is_live = is_live
        self.bus_time = bus_time

    def __eq__(self, other: object) -> bool:
        return self.trip_id == other

    # if live data provided, or if later trip data provided, overwrites trip
    def merge_trip(self, trip: typing.Self) -> None:
        if self == trip and trip.is_live and ((not self.is_live) or (trip.bus_time > self.bus_time)):
            self.trip_id = trip.trip_id
            self.headsign = trip.headsign
            self.bus_num = trip.bus_num
            self.scheduling = trip.scheduling
            self.is_live = trip.is_live
            self.bus_time = trip.bus_time

@dataclass
class Route:
    def __init__(self,
                 route_id: str,
                 trips: list[Trip],
                 route_num: str | None = None,
                 route_dir: int | None = None
                 ) -> None:
        self.route_id = route_id
        self.trips = trips
        with sqlite3.connect(config['path']['data'] + 'gtfs.db') as conn:
            self.route_num = route_num if route_num is not None else \
                e[0][0] if (e := [row for row in conn.execute(
                    'SELECT route_short_name FROM routes WHERE route_id = :route_id',
                    {'route_id': route_id})]) is not None else None
            # self.route_dest = route_dest if route_dest is not None else \
            #     e[0][0] if (e := [row for row in conn.execute(
            #         'SELECT stop_code FROM routes WHERE route_id = :route_id',
            #         {'route_id': route_id})]) is not None else None

    def __iter__(self) -> typing.Iterable[Trip]:
        return iter(self.trips)

    def __eq__(self, other: object) -> bool:
        return self.route_id == other

    # merge trip if pre-existing, otherwise add trip
    def add_trip(self, trip: Trip) -> None:
        for t in self:
            if t == trip:
                t.merge_trip(trip)
                return
        self.trips.append(trip)

@dataclass
class Stop:
    def __init__(self,
                 stop_id: str,
                 stop_num: str | None = None,
                 stop_name: str | None = None,
                 routes: list[Route] | None = None
                 ) -> None:
        self.stop_id = stop_id
        self.routes = routes if routes is not None else []
        with sqlite3.connect(config['path']['data']+'gtfs.db') as conn:
            self.stop_num = stop_num if stop_num is not None else \
                e[0][0] if (e := [row for row in conn.execute(
                    'SELECT stop_code FROM stops WHERE stop_id = :stop_id',
                    {'stop_id': stop_id})]) is not None else None
            self.stop_name = stop_name if stop_name is not None else \
                d if (d := dict((l[0], l[1]) for l in config['signboard']['stops'] if len(l) > 1).get(stop_id)) is not None else \
                e[0][0] if (e := [row for row in conn.execute(
                    'SELECT stop_name FROM stops WHERE stop_id = :stop_id',
                    {'stop_id': stop_id})]) is not None else None

    def __iter__(self) -> typing.Iterable[Route]:
        return iter(self.routes)

    def has_route(self, route_id: str) -> bool:
        return route_id in (r.route_id for r in self.routes)

@dataclass
class Signboard:
    def __init__(self,
                 stops: list[Stop] | None = None,
                 sign_time: datetime.datetime | None = None
                 ) -> None:
        self.stops = stops if stops is not None else []
        self.sign_time = sign_time if sign_time is not None else datetime.datetime.now(tz=get_agency_timezone())

    def has_stop(self, stop_id: str) -> bool:
        return stop_id in (s.stop_id for s in self.stops)

    def add_trip(self, stop_id: str, route_id: str, trip: Trip) -> None:
        pass


app = Flask(__name__)

def get_agency_timezone(agency_id: int = 1) -> datetime.tzinfo | None:
    return ZoneInfo(r[0][0]) if (r := db_query('SELECT agency_timezone FROM agency WHERE agency_id = :a',
                                               {'a': agency_id})) is not None else None

def db_query(query: str, params: dict) -> list[tuple] | None:
    with sqlite3.connect(config['path']['data'] + 'gtfs.db') as conn:
        return list(conn.execute(query, params))

def gtfs_schedule_request():
    return requests.get(config['sources']['schedule'])


# TODO: merge the safe requests fork by cutie
# format can be 'json' or 'protobuf'
def gtfs_realtime_request(format='json'):
    param = {'format': format}
    api_key = os.getenv('OC_API_KEY')
    header = {'Ocp-Apim-Subscription-Key': api_key}

    return requests.get(config['sources']['realtime'], params=param, headers=header)


def gtfs_schedule_update():
    with open(config['path']['data']+'gtfs_static.zip', 'bw+') as s:
        s.write(gtfs_schedule_request().content)


def gtfs_realtime_update():
    with open(config['path']['data']+'gtfs_update.json', 'w+') as r:
        js = json.loads(gtfs_realtime_request('json').content)
        r.write(json.dumps(js, indent=2))


def gtfs_initialize_database():
    gtfs_schedule_update()

    with zipfile.ZipFile(config['path']['data']+'gtfs_static.zip', 'r') as zipf:
        # TODO: maybe clean out the directory before unzipping more files into it
        zipf.extractall(config['path']['data']+'gtfs_static')

    with sqlite3.connect(config['path']['data']+'gtfs.db') as conn:
        for file in os.listdir(config['path']['data']+'gtfs_static'):
            # TODO: maybe fix this so it doesn't need "high-memory mode"
            data = pandas.read_csv(config['path']['data']+'gtfs_static/' + file, low_memory=False)
            data.to_sql(file.split('.')[0], conn, index=False, if_exists='replace')


# TODO: actually integrate schedule data
def gtfs_signboard_update(stop_list):
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(gtfs_realtime_request('protobuf').content)

    # TODO: un-kludge solution to output to webpage
    output = ""

    with sqlite3.connect(config['path']['data']+'gtfs.db') as conn:
        curr = conn.cursor()
        for stop, name in stop_list.items():
            for row in curr.execute('SELECT * FROM stops WHERE stop_id = :stop', {'stop': stop}):
                output += "%s (%s): " % (name, row[1] + ("%s" % row[14] if row[14] else ""))
                info = gtfs_get_info(feed, conn, stop)
                for x in range(len(info)):

                    output += "%s %s @ %s" % (info[x][0], info[x][1],
                                              datetime.datetime.fromtimestamp(info[x][2]).strftime("%H:%M"))

                    if x == len(info) - 1:
                        output += ".\n"
                    else:
                        output += ", "
    return output


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
                    if stop_time > datetime.datetime.now().timestamp():
                        info.append((route_id, headsign, stop_time))
    info.sort(key=itemgetter(2))
    return info


def signboard_from_schedule() -> Signboard:
    return Signboard(stops=[],
                     sign_time=datetime.datetime.now(tz=get_agency_timezone()))


def signboard_from_realtime() -> Signboard:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(gtfs_realtime_request('protobuf').content)

    sign = Signboard()

    for entity in feed.entity:
        if entity.HasField('trip_update'):
            for update in entity.trip_update.stop_time_update:
                if update.HasField('stop_id') and update.stop_id in (i[0] for i in config['signboard']['stops']):
                    trip_id, route_id, scheduled, arrival, departure = None, None, 0, 0, 0
                    if entity.trip_update.trip.HasField('route_id'):
                        route_id = entity.trip_update.trip.route_id
                    if entity.trip_update.trip.HasField('trip_id'):
                        trip_id = entity.trip_update.trip.trip_id
                    if entity.trip_update.trip.HasField('schedule_relationship'):
                        scheduled = entity.trip_update.trip.schedule_relationship
                    if update.HasField('arrival') and update.arrival.HasField('time'):
                        arrival = update.arrival.time
                    if update.HasField('departure') and update.departure.HasField('time'):
                        departure = update.departure.time

                    stop_time = max(arrival, departure)

                    sign.add_trip((trip_id, route_id, scheduled))
    return sign


@app.route('/')
def index() -> str:
    return render_template('index.html', signboard=signboard_from_realtime())


if __name__ == '__main__':
    # gtfs_initialize_database()
    # gtfs_realtime_update()

    # app.run()

    trip_a = Trip('1', '2220', Scheduling.SCHEDULED.value, False, datetime.datetime.now())
    trip_b = Trip('2', '4520', Scheduling.SCHEDULED.value, True, datetime.datetime.now() + datetime.timedelta(hours=1))
    trip_c = Trip('3', '6520', Scheduling.SCHEDULED.value, True, datetime.datetime.now() + datetime.timedelta(hours=2))
    trip_d = Trip('1', '2220', Scheduling.SCHEDULED.value, True, datetime.datetime.now() + datetime.timedelta(hours=3))

    route_a = Route('10', [trip_a, trip_b])

    print('route a', [x.bus_time for x in route_a])

    route_a.add_trip(trip_d)



    print(trip_b in route_a)
    print(trip_c in route_a)
    print(trip_d in route_a)

    print('route a', [x.bus_time for x in route_a])

    print(get_agency_timezone(1))

    print(db_query('SELECT agency_timezone FROM agency WHERE agency_id = :a',{'a': 1})[0][0])

    print(type(db_query('SELECT agency_timezone FROM agency WHERE agency_id = :a',{'a': 1})[0][0]))

    pass
