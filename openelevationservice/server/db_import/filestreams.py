# -*- coding: utf-8 -*-

from openelevationservice import TILES_DIR, SETTINGS
from openelevationservice.server.sources import PROVIDER_MAPPING
from openelevationservice.server.utils.logger import get_logger
# from openelevationservice.server.db_import import raster_processing

from os import path, environ
import subprocess

log = get_logger(__name__)


def download():
    """
    Downlaods GMTED and SRTM v4.1 tiles as bytestream and saves them to TILES_DIR.
    """

    for table in SETTINGS['tables']:
        for source in SETTINGS['tables'][table]['sources']:
            provider = PROVIDER_MAPPING[source]()
            try:
                provider.download_data()
            except Exception as err:
                log.info(err)


def raster2pgsql():
    """
    Imports SRTM v4.1 tiles to PostGIS.
    
    :raises subprocess.CalledProcessError: Raised when raster2pgsql throws an error.
    """

    pg_settings = SETTINGS['provider_parameters']

    # Copy all env variables and add PGPASSWORD
    env_current = environ.copy()
    env_current['PGPASSWORD'] = pg_settings['password']

    tiles_dir_name = None

    if SETTINGS["sources"][0]["type"] == "cgiar_csi":

        # Tried to import every raster individually by user-specified xyrange
        # similar to download(), but raster2pgsql fuck it up somehow.. The PostGIS
        # raster will not be what one would expect. Instead doing a bulk import of all files.
        cmd_raster2pgsql = r"raster2pgsql -s 4326 -a -C -M -P -t 50x50 {filename} {table_name_srtm} | psql -q -h {host} -p {port} -U {user_name} -d {db_name}"
        # -s: raster SRID
        # -a: append to table (assumes it's been create with 'create()')
        # -C: apply all raster Constraints
        # -P: pad tiles to guarantee all tiles have the same width and height
        # -M: vacuum analyze after import
        # -t: specifies the pixel size of each row. Important to keep low for performance!

        tiles_dir_name = TILES_DIR

    else:
        cmd_raster2pgsql = r"raster2pgsql -s 4326 -a -C -M -P -t 50x50 {filename} {table_name_joerd} | psql -q -h {host} -p {port} -U {user_name} -d {db_name}"

        tiles_dir_name = TILES_DIR

    if path.join(TILES_DIR, '*.tif'):
        cmd_raster2pgsql = cmd_raster2pgsql.format(**{'filename': path.join(tiles_dir_name, '*.tif'), **pg_settings})
    else:
        cmd_raster2pgsql = cmd_raster2pgsql.format(**{'filename': path.join(tiles_dir_name, '*.img'), **pg_settings})

    proc = subprocess.Popen(cmd_raster2pgsql,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            shell=True,
                            env=env_current
                            )

#    for line in proc.stdout:
#        log.debug(line.decode())
#    proc.stdout.close()
    return_code = proc.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd_raster2pgsql)
