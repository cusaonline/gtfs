_RT_BASE_URL: str = 'https://nextrip-public-api.azure-api.net/octranspo'

API_VERSION: int = 1


GTFS_STATIC: str = 'https://oct-gtfs-emasagcnfmcgeham.z01.azurefd.net/public-access/GTFSExport.zip'  # fmt: off
GTFS_RT_TRIP_UPDATE: str = f'{_RT_BASE_URL}/gtfs-rt-tp/beta/v{API_VERSION}/TripUpdates'
GTFS_RT_VEHICLE_POSITION: str = f'{_RT_BASE_URL}/gtfs-rt-vp/beta/v{API_VERSION}/VehiclePositions'  # fmt: off
