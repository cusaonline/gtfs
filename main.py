"""
Created: 9-AUG-2026
Updated: 9-AUG-2026
Contact: admin@cusaonline.ca
"""

import os
from wsgiref import headers

import requests

def gtfs_schedule_request():
    return requests.get("https://oct-gtfs-emasagcnfmcgeham.z01.azurefd.net/public-access/GTFSExport.zip")

def gtfs_realtime_request():
    api_key = os.getenv('OC_API_KEY')
    param = {'format': 'json'}
    header = {'Ocp-Apim-Subscription-Key': api_key}

    return requests.get("https://nextrip-public-api.azure-api.net/octranspo/gtfs-rt-tp/beta/v1/TripUpdates",
                        params=param, headers=header)


if __name__ == '__main__':

    with open('gtfsStatic.zip', 'ba+') as s:
        s.write(gtfs_schedule_request().content)

    with open('gtfsUpdate.json', 'ba+') as r:
        r.write(gtfs_realtime_request().content)