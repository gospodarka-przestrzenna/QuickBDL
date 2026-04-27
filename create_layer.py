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


import sqlite3
from .config import DB_PATH
from qgis.core import QgsVectorLayer, QgsField, QgsFeature
from qgis.PyQt.QtCore import QVariant
from .utils.translations import _


class Layer(QgsVectorLayer):
    """
    Represents a QGIS memory layer for managing territorial data.
    Includes methods for adding features, attributes, and processing geometry.
    """
    def __init__(self, layer_name):
        """
        Initializes the layer with default fields and configurations.

        Args:
            layer_name (str): The name of the memory layer.
        """
        super().__init__("MultiPolygon?crs=EPSG:2180", layer_name, "memory")
        self.provider = self.dataProvider()

        # Index to map long unit codes to their corresponding features
        self.feature_index = {}  # {long_code: QgsFeature}

        # Maps column names to their respective index positions
        self.column_index = {
            "short_code": 0,
            "type": 1,
            "name": 2
        }

        # Add default attributes to the layer
        self.provider.addAttributes([
            QgsField(_("short_code"), QVariant.String),
            QgsField(_("type"), QVariant.String),
            QgsField(_("name"), QVariant.String)
        ])
        self.updateFields()

        # Tracks years and their corresponding column indices
        self.year_columns = {}

    def create_new_feature(self, full_code, name, geometry, do_merge):
        """
        Creates a new feature for the specified unit and adds it to the layer.

        Args:
            full_code (str): The full unit code.
            name (str): The name of the unit.
            geometry (QgsGeometry): The geometry of the unit.
            do_merge (bool): Whether to merge rural and urban areas into a single unit.

        Returns:
            bool: True if the feature was created successfully, False otherwise.
        """
        shorter_code = full_code[2:4] + full_code[7:11]
        kind = full_code[11]
        if name is None:
            None
        if geometry is None:
            None

        # Create a new feature and set its attributes
        feature = QgsFeature()
        feature.setGeometry(geometry)
        feature.setAttributes([shorter_code, kind, name])

        # Add the feature to the provider
        self.provider.addFeature(feature)

        # Update the feature index to quick insert data when obtained from
        if do_merge and full_code[-1] == '3':
            self.feature_index[full_code[:-1] + '1'] = feature
            self.feature_index[full_code[:-1] + '2'] = feature

        self.feature_index[full_code] = feature
        return True

    def add_GUS_data(self, unit_id, year, value, column_prefix):
        """
        Adds data for a specific unit and year to the layer.

        Args:
            unit_id (str): The unit identifier.
            year (str): The year for the data.
            value (float): The value to add.
            column_prefix (str): Prefix for the column name.
            get_geom_n_type (function): Geometry and type retrieval function.
        """
        year = str(year)

        if unit_id not in self.feature_index:
            return

        if year not in self.year_columns:
            self.year_columns[year] = []

        column = f"{column_prefix} ({year})"
        if column not in self.column_index:
            self.column_index[column] = len(self.column_index)
            self.provider.addAttributes([QgsField(column, QVariant.Double)])
            self.updateFields()

            for feature in self.feature_index.values():
                feature.resizeAttributes(len(self.column_index))
                self.provider.changeAttributeValues({feature.id(): {self.column_index[column]: value}})

        self.year_columns[year].append(self.column_index[column])
        feature = self.feature_index[unit_id]
        self.provider.changeAttributeValues({feature.id(): {self.column_index[column]: value}})

    def get_name(self, short_code, type):
        """
        Retrieves the name for a specific unit.

        Args:
            short_code (str): Short code of the unit.
            type (str): Type of the unit.

        Returns:
            str: The name of the unit.
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name
                FROM teryt_codes
                WHERE short_code = ?
            """, (short_code + type,))
            result = cursor.fetchone()
            if not result:
                raise ValueError(_("Name not found for code: {short_code} {type}").format(short_code=short_code, type=type))
            return result[0]

    def remove_unwanted_years_columns(self, years):
        """
        Removes columns corresponding to unwanted years.

        Args:
            years (list): List of years to retain.
        """
        to_delete = []
        for year, columns in self.year_columns.items():
            if year not in years:
                to_delete.extend(columns)

        self.year_columns = {year: columns for year, columns in self.year_columns.items() if year in years}
        self.provider.deleteAttributes(to_delete)
        self.updateFields()

        # Rebuild column index after deletion
        self.column_index = {field.name(): index for index, field in enumerate(self.fields())}
