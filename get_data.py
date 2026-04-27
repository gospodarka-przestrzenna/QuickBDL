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

from PyQt5.QtWidgets import QAction, QDialog
from qgis.core import QgsProject
import os
from .utils.translations import _
from .config import DB_PATH, DATABASE_URL
from .subjects_form import SubjectsForm
from .units_form import UnitsForm
from .years_form import YearsForm
from .datafetch_form import DataFetchForm
from .approach_form import ApproachForm
from .initialization_form import DataInitializationDialog


class GetBDLData(QAction):
    """
    GetData class manages the main logic and workflow of the plugin,
    connecting various forms and data fetching functionalities.
    """

    def __init__(self, plugin):
        """
        Initialize the GetData class, setting up the main plugin action.

        Parameters:
            plugin (QgsPlugin): Reference to the main plugin instance.
        """
        super(GetBDLData, self).__init__(plugin.icon('ico1.png'), _("Fetch GUS data"), plugin.iface.mainWindow())
        self.triggered.connect(self.run)

        # Assign plugin references
        self.plugin = plugin
        self.iface = plugin.iface

        # Initialize data containers
        self.do_merge = False
        self.variables = []
        self.units = []
        self.variableNames = {}
        self.layer = None

    def run(self):
        """
        Initiates the plugin by resetting data and launching the first form.
        """
        # Clear previous session data
        self.variables.clear()
        self.units.clear()

        self.layer = None

        # before first ever run we need to download the database
        # chech if the database exists
        if not os.path.exists(DB_PATH):
            # if not exists we need to download it
            dialog = DataInitializationDialog(DB_PATH, DATABASE_URL)
            if dialog.exec_() != QDialog.Accepted:
                os.remove(DB_PATH)
                return

        # Launch the first form
        self.show_approach_form()

    def show_approach_form(self):
        """
        Displays the approach selection form and connects its completion
        to the next form (subjects selection).
        """
        self.approach_form = ApproachForm()
        result = self.approach_form.exec_()
        if result == QDialog.Rejected:
            # If the dialog is closed, terminate the plugin
            return
        self.do_merge = self.approach_form.option2.isChecked()
        self.show_units_form()

    def show_units_form(self):
        """
        Displays the units selection form after the approach form 
        and connects its completion to the subjects form.
        """
        self.units_form = UnitsForm(self.do_merge)

        result = self.units_form.exec_()
        if result == QDialog.Rejected:
            # If the dialog is closed, terminate the plugin
            return
        self.units = self.units_form.full_code_list
        self.show_subjects_form()

    def show_subjects_form(self):
        """
        Displays the subjects selection form and connects its completion
        to the data fetching form.
        """
        self.subjects_form = SubjectsForm(self.variableNames)
        result = self.subjects_form.exec_()
        if result == QDialog.Rejected:
            # If the dialog is closed, terminate the plugin
            return
        self.variables = self.subjects_form.selected_codes
        self.variableNames = self.subjects_form.variableNames
        self.show_datafetch_form()

    def show_datafetch_form(self):
        """
        Displays the data fetching form, initiates API requests, 
        and tracks progress for data retrieval.
        """        
        self.datafetch_form = DataFetchForm(
            self.do_merge,
            self.units,
            self.variables,
            self.variableNames,
        )
        result = self.datafetch_form.exec_()
        if result == QDialog.Rejected:
            # If the dialog is closed, terminate the plugin
            return
        self.show_years_form()
        
    def show_years_form(self):
        """
        Displays the years selection form after data fetching and 
        connects its completion to data processing.
        """

        # Get the fetched data layer from the data fetching form
        self.layer = self.datafetch_form.worker.layer

        self.years_form = YearsForm(self.layer.year_columns.keys())
        result = self.years_form.exec_()
        if result == QDialog.Rejected:
            # If the dialog is closed, terminate the plugin
            return
        self.process_data()
        

    def process_data(self):
        """
        Finalizes data retrieval and processing by removing 
        unnecessary columns and adding the processed data to QGIS as a layer.
        """        
        self.layer.remove_unwanted_years_columns(self.years_form.selected_years)
        QgsProject.instance().addMapLayer(self.layer)
        