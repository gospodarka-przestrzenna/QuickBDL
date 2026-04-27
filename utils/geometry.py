# -*- coding: utf-8 -*-
###############################################################################
#
# Copyright (C) 2024 Wawrzyniec Zipser, Maciej Kamiński (maciej.kaminski@pwr.edu.pl)
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at https://mozilla.org/MPL/2.0/.
#
###############################################################################
__author__ = 'Wawrzyniec Zipser, Maciej Kamiński Politechnika Wrocławska'

import requests
import sqlite3
import geopandas as gpd
import pandas as pd
from io import BytesIO
from ..config import DB_PATH
import binascii

wfs_url = 'https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries'
class Geometry(object):
    def __init__(self):
        with sqlite3.connect(DB_PATH) as conn:
            
            # if geometries table does not exist just leave
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='geometries';").fetchone() is not None:
                return
            
            # Create the table 'geometries' if it does not exist
            conn.execute("CREATE INDEX idx_code ON geometries (code);")

            # Create a unique index on the pair 'code' and 'type'
            conn.execute("CREATE UNIQUE INDEX idx_code_type ON geometries (code, type);")

    def _hex_to_geometry(self, hex_geom):
        # import QgsGeometry from qgis.core only if needed
        from qgis.core import QgsGeometry
        wkb_hex = hex_geom
        wkb_bytes = binascii.unhexlify(wkb_hex)
        geometry = QgsGeometry()
        geometry.fromWkb(wkb_bytes)
        return geometry
    
    def _get_geometry(self, shorter_code, kind):
        """
        Retrieves the geometry for a given code and kind from the database.

        Args:
            shorter_code (str): The shorter code to get the geometry for.
            kind (str): The type of geometry to retrieve.

        Returns:
            QgsGeometry: The resulting geometry or None if not found.
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT hex(geometry)
                FROM geometries
                WHERE code = ? AND type = ?
            ''', (shorter_code, kind))
            row = cursor.fetchone()
            if not row:
                return None
            hex_geometry = row[0]
            return self._hex_to_geometry(hex_geometry)

    def geometry_from_code(self, shorter_code, kind):
        """
        Retrieves the geometry for a given code and kind. If kind is '5', it computes
        the difference between urban_rural and urban geometries.

        Args:
            shorter_code (str): The shorter code to get the geometry for.
            kind (str): The type of geometry to retrieve.

        Returns:
            QgsGeometry: The resulting geometry or None if not found.
        """
        urban = None

        if kind == '5':
            urban = self._get_geometry(shorter_code, '4')
            if not urban:
                return None
            
        actual_kind = kind if kind != '5' else '3'
        geometry = self._get_geometry(shorter_code, actual_kind)
        if not geometry:
            return None

        if kind == '5':
            return geometry.difference(urban)
        return geometry       

    def _fetch_commune_geometries(self):
        layer_name = 'ms:A03_Granice_gmin'
        params = {
            'service': 'WFS',
            'request': 'GetFeature',
            'version': '2.0.0',
            'typename': layer_name,
            'outputFormat': 'application/gml+xml; version=3.2',

        }
        response = requests.get(wfs_url, params=params, timeout=30)

        if response.status_code != 200:
            print('Failed to fetch geometries')
            return
        # Load the response into a GeoDataFrame
        gdf = gpd.read_file(BytesIO(response.content))

        # drop columns that are not needed
        gdf = gdf[['JPT_KOD_JE', 'geometry']]

        # Create a column 'code' from the first six characters
        gdf['code'] = gdf['JPT_KOD_JE'].str[:6]

        # Create a column 'type' from the seventh character
        gdf['type'] = gdf['JPT_KOD_JE'].str[6]

        # Remove the 'JPT_KOD_JE' column
        gdf = gdf.drop(columns=['JPT_KOD_JE'])
        
        gdf['geometry_wkb'] = gdf['geometry'].apply(lambda geom: geom.wkb)
        gdf = gdf.drop(columns=['geometry'])
        gdf = gdf.rename(columns={'geometry_wkb': 'geometry'})
        gdf_to_save = gdf[['code', 'type', 'geometry']]

        return gdf_to_save  
    
    def _fetch_city_geometries(self):
        layer_name = 'ms:A04_Granice_miast'
        params = {
            'service': 'WFS',
            'request': 'GetFeature',
            'version': '2.0.0',
            'typename': layer_name,
            'outputFormat': 'application/gml+xml; version=3.2',

        }
        response = requests.get(wfs_url, params=params, timeout=30)

        if response.status_code != 200:
            print('Failed to fetch geometries')
            return
        # Load the response into a GeoDataFrame
        gdf = gpd.read_file(BytesIO(response.content))

        # drop columns that are not needed
        gdf = gdf[['KODJEDNO_1', 'geometry']]

        # Create a column 'code' from the first six characters
        gdf['code'] = gdf['KODJEDNO_1'].str[:6]

        # Create a column 'type' from the eight character after _
        gdf['type'] = gdf['KODJEDNO_1'].str[7]

        # Remove the 'KODJEDNO_1' column
        gdf = gdf.drop(columns=['KODJEDNO_1'])
        
        gdf['geometry_wkb'] = gdf['geometry'].apply(lambda geom: geom.wkb)
        gdf = gdf.drop(columns=['geometry'])
        gdf = gdf.rename(columns={'geometry_wkb': 'geometry'})
        gdf_to_save = gdf[['code', 'type', 'geometry']]

        return gdf_to_save  
    
    def _fetch_geometries(self):
        communes = self._fetch_commune_geometries()
        cities = self._fetch_city_geometries()
            # Połącz DataFrame, 'communes' jako pierwszy
        combined_gdf = pd.concat([communes, cities], ignore_index=True)

        # Usuń duplikaty na podstawie 'code' i 'type', zachowując pierwsze wystąpienie (z 'communes')
        combined_gdf = combined_gdf.drop_duplicates(subset=['code', 'type'], keep='first')

        with sqlite3.connect(DB_PATH) as conn:
            combined_gdf.to_sql('geometries', conn, if_exists='replace', index=False)    
            # Utwórz indeks na kolumnie 'code'
            conn.execute("CREATE INDEX idx_code ON geometries (code);")

        # Utwórz unikalny indeks na parze 'code' i 'type'
            conn.execute("CREATE UNIQUE INDEX idx_code_type ON geometries (code, type);")