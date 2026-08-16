import logging as log
import os
import tempfile
from os import path
from pathlib import Path

import requests

from . import oc_transpo

F_SCHEDULE: Path = Path('gtfs_schedule.zip')
F_REALTIME_UPDATE: Path = Path('gtfs_update.json')


def _pull(
    uri: str | bytes,
    params: requests.sessions._Params | None = None,  # pyright: ignore[reportPrivateUsage]
    headers: requests.api._HeadersMapping | None = None,  # pyright: ignore[reportPrivateUsage]
) -> bytes | None:
    """
    Attempt to safely pull down a resource.
    """
    try:
        resp = requests.get(
            uri,
            params,
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.content
    except (
        requests.exceptions.HTTPError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    ) as err:
        log.error(str(err))
        return None


def gtfs_schedule_request() -> bytes | None:
    return _pull(oc_transpo.GTFS_STATIC)


def gtfs_realtime_request() -> bytes | None:
    api_key = os.getenv('OC_API_KEY')

    if api_key is None:
        return None

    return _pull(
        oc_transpo.GTFS_RT_TRIP_UPDATE,
        {'format': 'json'},
        {'Ocp-Apim-Subscription-Key': api_key},
    )


def run(tmp: Path) -> None:
    if (schedule := gtfs_schedule_request()) is not None:
        with open(path.join(tmp, F_SCHEDULE), 'ba+') as f:
            written = f.write(schedule)

        if written != len(schedule):
            log.error('Failed to write all of schedule to file.')

    if (realtime := gtfs_realtime_request()) is not None:
        with open(path.join(tmp, F_REALTIME_UPDATE), 'ba+') as f:
            written = f.write(realtime)

        if written != len(realtime):
            log.error('Failed to write all of realtime update to file.')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        run(tmp)
