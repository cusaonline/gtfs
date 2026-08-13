"""
Created: 9-AUG-2026
Updated: 13-AUG-2026
Contact: admin@cusaonline.ca
"""

import os
import requests
import json

def gtfs_schedule_request():
    return requests.get("https://oct-gtfs-emasagcnfmcgeham.z01.azurefd.net/public-access/GTFSExport.zip")

def gtfs_realtime_request():
    api_key = os.getenv('OC_API_KEY')
    param = {'format': 'json'}
    header = {'Ocp-Apim-Subscription-Key': api_key}

    return requests.get("https://nextrip-public-api.azure-api.net/octranspo/gtfs-rt-vp/beta/v1/VehiclePositions",
                        params=param, headers=header)


if __name__ == '__main__':

    with open('gtfsStatic.zip', 'wb') as s:
        s.write(gtfs_schedule_request().content)

    with open('gtfsUpdate.json', 'w') as r:
        js = json.loads(gtfs_realtime_request().content)
        r.write(json.dumps(js, indent=2))

    for entity in js["Entity"]:
        if entity["Vehicle"] is None:
            continue
        vehicle = entity["Vehicle"]
        if (vehicle["Vehicle"]["Id"] in ["2126", "2152"]):
            # gus located
            print(f"Gus {vehicle['Vehicle']['Id']} located: {vehicle['Position']['Latitude']}, {vehicle['Position']['Longitude']}")