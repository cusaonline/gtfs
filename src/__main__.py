"""
Created: 9-AUG-2026
Updated: 26-AUG-2026
Contact: admin@cusaonline.ca
"""
from dataclasses import dataclass
from operator import itemgetter, truediv
from zoneinfo import ZoneInfo
from google.transit import gtfs_realtime_pb2
from flask import Flask, render_template
from enum import Enum
import datetime as dt
import requests
import sqlite3
import zipfile
import typing
import pandas
import json
import yaml
import os

config = yaml.safe_load(open("config.yaml", 'r'))


class TripType(Enum):
    SCHEDULED = 0
    ADDED = 1  # deprecated
    UNSCHEDULED = 2
    CANCELED = 3
    REPLACEMENT = 5
    DUPLICATED = 6
    DELETED = 7
    NEW = 8


@dataclass
class Trip:
    def __init__(self,
                 trip_id: str,
                 bus_time: dt.datetime,
                 is_live: bool,
                 scheduling: TripType = TripType.SCHEDULED,
                 headsign: str | None = None,
                 bus_num: str | None = None
                 ) -> None:
        self.trip_id = trip_id
        self.bus_time = bus_time
        self.is_live = is_live
        self.scheduling = scheduling
        self.headsign = headsign
        self.bus_num = bus_num

    def __eq__(self, other: object) -> bool:
        return self.trip_id == other

    # if live data provided, or if later trip data provided, overwrites trip
    def merge_trip(self, trip: typing.Self) -> bool:
        if self == trip and trip.is_live and ((not self.is_live) or (trip.bus_time > self.bus_time)):
            # TODO: look for more compact way to copy this info over
            self.trip_id = trip.trip_id
            self.bus_time = trip.bus_time
            self.is_live = trip.is_live
            self.headsign = e if (e := trip.headsign) is not None else self.headsign
            self.scheduling = e if (e := trip.scheduling) is not None else self.scheduling
            self.bus_num = e if (e := trip.bus_num) is not None else self.bus_num
            return True
        else:
            return False


@dataclass
class Route:
    def __init__(self,
                 route_id: str,
                 route_dir: int,
                 route_num: str,
                 trips: list[Trip]
                 ) -> None:
        self.route_id = route_id
        self.route_dir = route_dir
        self.route_num = route_num
        self.trips = trips

    def __eq__(self, other: object) -> bool:
        return (self.route_id, self.route_dir) == other

    def __iter__(self) -> typing.Iterable[Trip]:
        return iter(self.trips)

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
                 stop_num: str,
                 stop_name: str,
                 routes: list[Route]
                 ) -> None:
        self.stop_id = stop_id
        self.stop_num = stop_num
        self.stop_name = stop_name
        self.routes = routes

    def __eq__(self, other: object) -> bool:
        return self.stop_id == other

    def __iter__(self) -> typing.Iterable[Route]:
        return iter(self.routes)


@dataclass
class Signboard:
    def __init__(self,
                 sign_time: dt.datetime,
                 stops: list[Stop]
                 ) -> None:
        self.sign_time = sign_time
        self.stops = stops

    def __iter__(self) -> typing.Iterable[Stop]:
        return iter(self.stops)


app = Flask(__name__)


def get_agency_timezone(agency_id: int = 1) -> dt.tzinfo | None:
    return ZoneInfo(r[0][0]) if (r := db_query('SELECT agency_timezone FROM agency WHERE agency_id = :a',
                                               {'a': agency_id})) is not None else None


def datetime_from_iso(iso_time: str, day: dt.date = dt.date.today()) -> dt.datetime:
    hour, minute, second = str.split(iso_time, ':')
    offset = dt.timedelta(days=int(hour) // 24, hours=int(hour) % 24, minutes=int(minute), seconds=int(second))
    return dt.datetime.combine(day, dt.time()) + offset


def db_query(query: str, params: dict) -> list[tuple] | None:
    with sqlite3.connect(config['path']['data'] + 'gtfs.db') as conn:
        return list(conn.execute(query, params))


def scheduled_trip_from_id(trip_id: str, stop_id: str) -> Trip:
    arrival, departure = \
    db_query('SELECT arrival_time, departure_time FROM stop_times WHERE trip_id = :trip_id AND stop_id = :stop_id',
             {'trip_id': trip_id, 'stop_id': stop_id})[0]
    headsign, = db_query('SELECT trip_headsign FROM trips WHERE trip_id = :trip_id',
                         {'trip_id': trip_id})[0]
    return Trip(trip_id, max(datetime_from_iso(arrival), datetime_from_iso(departure)), False, TripType.SCHEDULED,
                headsign)


def route_from_trip(trip: Trip) -> Route:
    route_id, direction = db_query('SELECT route_id, direction_id FROM trips WHERE trip_id = :trip_id',
                                   {'trip_id': trip.trip_id})[0]
    route_name, = db_query('SELECT route_short_name FROM routes WHERE route_id = :route_id',
                           {'route_id': route_id})[0]
    return Route(route_id, direction, route_name, [trip])


def stop_from_id(stop_id: str) -> Stop:
    stop_num, stop_name = db_query('SELECT stop_code, stop_name FROM stops WHERE stop_id = :stop_id',
                                   {'stop_id': stop_id})[0]
    name_overrides = dict((l[0], l[1]) for l in config['signboard']['stops'] if len(l) > 1)
    if stop_id in name_overrides:
        stop_name = name_overrides[stop_id]
    return Stop(stop_id, stop_num, stop_name, [])


def signboard_from_realtime(stop_list: list[str]) -> Signboard:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(gtfs_realtime_request('protobuf').content)

    rt_signboard = Signboard(dt.datetime.now(tz=get_agency_timezone()), [])

    for entity in feed.entity:
        if entity.HasField('trip_update'):
            for update in entity.trip_update.stop_time_update:
                if update.HasField('stop_id') and update.stop_id in stop_list:
                    rt_stop_id = update.stop_id
                    print(entity.trip_update.trip.HasField('trip_id'))
                    print(entity.trip_update.trip.trip_id)
                    rt_trip_id = entity.trip_update.trip.trip_id
                    rt_scheduled = TripType(entity.trip_update.trip.schedule_relationship)

                    print(rt_stop_id, rt_trip_id)
                    scheduled_trip = scheduled_trip_from_id(rt_trip_id, rt_stop_id)

                    rt_headsign = scheduled_trip.headsign
                    rt_bus_time = scheduled_trip.bus_time
                    rt_bus_num = None
                    if entity.trip_update.HasField('vehicle') and entity.trip_update.vehicle.HasField('id'):
                        bus_num = entity.trip_update.vehicle.id

                    if update.HasField('arrival') and update.arrival.HasField('time'):
                        bus_time = dt.datetime.fromtimestamp(update.arrival.time, get_agency_timezone())
                    if update.HasField('departure') and update.departure.HasField('time'):
                        bus_time = dt.datetime.fromtimestamp(update.arrival.time, get_agency_timezone())

                    trip_to_add = Trip(rt_trip_id, rt_bus_time, True, rt_scheduled, rt_headsign, rt_bus_num)
                    route_to_add = route_from_trip(trip_to_add)

                    for stop in rt_signboard:
                        if stop == rt_stop_id:
                            if route_to_add not in stop:
                                stop.routes.append(route_to_add)
                            else:
                                for route in stop:
                                    if route == route_to_add:
                                        route.add_trip(trip_to_add)
                                        break

    return rt_signboard


# TODO: implement
def signboard_from_schedule() -> Signboard:
    pass
    # return Signboard(stops=[],
    #                  sign_time=dt.datetime.now(tz=get_agency_timezone()))


# TODO: merge or modernize functions south of this line
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
    with open(config['path']['data'] + 'gtfs_static.zip', 'bw+') as s:
        s.write(gtfs_schedule_request().content)


def gtfs_realtime_update():
    with open(config['path']['data'] + 'gtfs_update.json', 'w+') as r:
        js = json.loads(gtfs_realtime_request('json').content)
        r.write(json.dumps(js, indent=2))


def gtfs_initialize_database():
    gtfs_schedule_update()

    with zipfile.ZipFile(config['path']['data'] + 'gtfs_static.zip', 'r') as zipf:
        # TODO: maybe clean out the directory before unzipping more files into it
        zipf.extractall(config['path']['data'] + 'gtfs_static')

    with sqlite3.connect(config['path']['data'] + 'gtfs.db') as conn:
        for file in os.listdir(config['path']['data'] + 'gtfs_static'):
            # TODO: maybe fix this so it doesn't need "high-memory mode"
            data = pandas.read_csv(config['path']['data'] + 'gtfs_static/' + file, low_memory=False)
            data.to_sql(file.split('.')[0], conn, index=False, if_exists='replace')


# TODO: actually integrate schedule data
def gtfs_signboard_update(stop_list):
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(gtfs_realtime_request('protobuf').content)

    # TODO: un-kludge solution to output to webpage
    output = ""

    with sqlite3.connect(config['path']['data'] + 'gtfs.db') as conn:
        curr = conn.cursor()
        for stop, name in stop_list.items():
            for row in curr.execute('SELECT * FROM stops WHERE stop_id = :stop', {'stop': stop}):
                output += "%s (%s): " % (name, row[1] + ("%s" % row[14] if row[14] else ""))
                info = gtfs_get_info(feed, conn, stop)
                for x in range(len(info)):

                    output += "%s %s @ %s" % (info[x][0], info[x][1],
                                              dt.datetime.fromtimestamp(info[x][2]).strftime("%H:%M"))

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
                    if stop_time > dt.datetime.now().timestamp():
                        info.append((route_id, headsign, stop_time))
    info.sort(key=itemgetter(2))
    return info


@app.route('/')
def index() -> str:
    return render_template('index.html',
                           signboard=signboard_from_realtime([i[0] for i in config['signboard']['stops']]))


if __name__ == '__main__':
    # gtfs_initialize_database()
    gtfs_realtime_request('json')

    sign_a = signboard_from_realtime([i[0] for i in config['signboard']['stops']])

    print(sign_a.sign_time)
    print(sign_a.stops[0].stop_id)
    print(sign_a.stops[0].routes[0].route_id)
    print(sign_a.stops[0].routes[0].trips[0].trip_id)
    print(sign_a.stops[0].routes[0].trips[0].bus_time)

    app.run()
