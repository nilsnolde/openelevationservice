# -*- coding: utf-8 -*-

from openelevationservice import SETTINGS
from openelevationservice.server.utils.logger import get_logger
from openelevationservice.server.db_import.models import db, Cgiar, SwissAlti, Copernicus
from openelevationservice.server.api.api_exceptions import InvalidUsage

from geoalchemy2.functions import ST_DumpPoints, ST_Dump, ST_Value, ST_Intersects, ST_X, ST_Y, ST_Transform, ST_SnapToGrid
from sqlalchemy import func, Integer
from sqlalchemy.orm.exc import NoResultFound
import json

log = get_logger(__name__)

coord_precision = SETTINGS['coord_precision']


def _getModel(dataset):
    """
    Choose model based on dataset parameter
    
    :param dataset: elevation dataset to use for querying
    :type dataset: string
    
    :returns: database model
    :rtype: SQLAlchemy model
    """
    if dataset == 'srtm':
        model = Cgiar
    elif dataset == 'swissalti':
        model = SwissAlti
    elif dataset == 'copernicus':
        model = Copernicus
    else:
        raise InvalidUsage(400, error_code=4000, message="dataset can only be copernicus, swissalti, srtm")
    
    return model


def _get_crs(dataset):

    input_crs = 0
    if dataset == 'srtm':
        input_crs = 4326
    elif dataset == 'swissalti':
        input_crs = 2056
    elif dataset == 'copernicus':
        input_crs = 3035

    return input_crs


def line_elevation(geometry, format_out, dataset):
    """
    Performs PostGIS query to enrich a line geometry.
    
    :param geometry: Input 2D line to be enriched with elevation
    :type geometry: Shapely geometry
    
    :param format_out: Specifies output format. One of ['geojson', 'polyline',
        'encodedpolyline']
    :type format_out: string
    
    :param dataset: Elevation dataset to use for querying
    :type dataset: string
    
    :raises InvalidUsage: internal HTTP 500 error with more detailed description. 
        
    :returns: 3D line as GeoJSON or WKT
    :rtype: string
    """
    
    Model = _getModel(dataset)
    input_crs = _get_crs(dataset)
    
    if geometry.geom_type == 'LineString':
        query_points2d = db.session\
                            .query(ST_Transform(func.ST_SetSRID(ST_DumpPoints(geometry.wkt).geom, 4326), input_crs) \
                            .label('geom')) \
                            .subquery().alias('points2d')

        query_getelev = db.session \
                            .query(ST_Transform(query_points2d.c.geom, 4326).label('geom'),
                                   ST_Value(Model.rast, query_points2d.c.geom, False).label('z')) \
                            .filter(ST_Intersects(Model.rast, query_points2d.c.geom)) \
                            .subquery().alias('getelevation')

        query_points3d = db.session \
                            .query(func.ST_MakePoint(ST_X(query_getelev.c.geom),
                                                                     ST_Y(query_getelev.c.geom),
                                                                     query_getelev.c.z.cast(Integer)
                                                     ).label('geom')) \
                            .subquery().alias('points3d')

        if format_out == 'geojson':
            # Return GeoJSON directly in PostGIS
            query_final = db.session \
                              .query(func.ST_AsGeoJson(func.ST_MakeLine(ST_SnapToGrid(query_points3d.c.geom, coord_precision))))
            
        else:
            # Else return the WKT of the geometry
            query_final = db.session \
                              .query(func.ST_AsText(func.ST_MakeLine(ST_SnapToGrid(query_points3d.c.geom, coord_precision))))
    else:
        raise InvalidUsage(400, 4002, "Needs to be a LineString, not a {}!".format(geometry.geom_type))

    try:
        result = query_final.one()
    except NoResultFound:
        raise InvalidUsage(404, 4002,
                           f'{tuple(geometry.coords)[0]} has no elevation value in {dataset}')

    return result[0]


def point_elevation(geometry, format_out, dataset):
    """
    Performs PostGIS query to enrich a point geometry.
    
    :param geometry: Input point to be enriched with elevation
    :type geometry: shapely.geometry.Point
    
    :param format_out: Specifies output format. One of ['geojson', 'point']
    :type format_out: string
    
    :param dataset: Elevation dataset to use for querying
    :type dataset: string
    
    :raises InvalidUsage: internal HTTP 500 error with more detailed description.
    
    :returns: 3D Point as GeoJSON or WKT
    :rtype: string
    """
    
    Model = _getModel(dataset)
    input_crs = _get_crs(dataset)
    
    if geometry.geom_type == "Point":
        query_point2d = db.session \
                            .query(ST_Transform(func.ST_SetSRID(func.St_PointFromText(geometry.wkt), 4326), input_crs).label('geom')) \
                            .subquery() \
                            .alias('points2d')
        
        query_getelev = db.session \
                            .query(ST_Transform(query_point2d.c.geom, 4326).label('geom'),
                                   ST_Value(Model.rast, query_point2d.c.geom, False).label('z')) \
                            .filter(ST_Intersects(Model.rast, query_point2d.c.geom)) \
                            .subquery().alias('getelevation')
        
        if format_out == 'geojson': 
            query_final = db.session \
                .query(func.ST_AsGeoJSON(ST_SnapToGrid(func.ST_MakePoint(ST_X(query_getelev.c.geom),
                                                                                           ST_Y(query_getelev.c.geom),
                                                                                           query_getelev.c.z.cast(Integer)),
                                                                        coord_precision)))
        else:
            query_final = db.session \
                                .query(func.ST_AsText(ST_SnapToGrid(func.ST_MakePoint(ST_X(query_getelev.c.geom),
                                                                                       ST_Y(query_getelev.c.geom),
                                                                                       query_getelev.c.z.cast(Integer)),
                                                                    coord_precision)))
    else:
        raise InvalidUsage(400, 4002, "Needs to be a Point, not {}!".format(geometry.geom_type))

    try:
        result = query_final.one()
        return result[0]
    except NoResultFound:
        raise InvalidUsage(404, 4002,
                           f'{tuple(geometry.coords)[0]} has no elevation value in {dataset}')
