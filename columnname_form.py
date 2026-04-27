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
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QLineEdit
from .utils.translations import _, gus_language
from .config import DB_PATH


class ChooseColumnName(QDialog):
    """
    A dialog window for choosing column names for selected variables.

    This dialog is displayed after the user selects variables and allows the user
    to input a column name for the variable that adheres to constraints like
    maximum length and uniqueness within the dataset.
    """

    def __init__(self, variable, variableNames):
        """
        Initialize the ChooseColumnName dialog.

        Args:
            variable (str): The ID of the variable for which a column name is being chosen.
            variableNames (dict): A dictionary to store user-defined column names for variables.
        """
        super().__init__()
        self.variableNames = variableNames

        self.max_length = 20  # Maximum length for column names
        self.variable = variable

        # Set up the window title
        self.setWindowTitle(_("Choose Column Name"))

        # Label explaining column naming constraints
        self.label = QLabel(_("Choose a column name for the variable (up to {length} characters):").format(length=self.max_length))

        # Retrieve a suggested name for the column or generate one if unavailable
        name = self.variableNames.get(variable)
        if name is None or len(name) < 2:
            name = self.get_example_column_name(variable)

        # Input field for column name
        self.column_name = QLineEdit(name)
        self.column_name.textChanged.connect(self.on_text_changed)

        # Confirmation button
        self.button = QPushButton(_("Confirm"))
        self.button.clicked.connect(self.accept)
        self.on_text_changed()  # Initialize button state based on constraints

        # Main layout setup
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.column_name)
        layout.addWidget(self.button)

        self.setLayout(layout)
        self.resize(600, 100)

    def on_text_changed(self):
        """
        Enable or disable the "Confirm" button based on input validation.
        """
        # let's make a copy of the variableNames dictionary and remove the current variable from it
        other_names = dict(self.variableNames)
        if self.variable in other_names:
            del other_names[self.variable]

        self.button.setEnabled(
            # Column name length is within the allowed limit
            # column name must not appear in other_names dictionary it must be unique
            len(self.column_name.text()) <= self.max_length and self.column_name.text() not in other_names.values()
        )
        self.variableNames[self.variable] = self.column_name.text()

    def closeEvent(self, event):
        """
        Handle the dialog close event.

        Rejects the dialog and ensures any cleanup is done.
        """
        self.reject()
        event.accept()

    def get_example_column_name(self, variable_id):
        """
        Generate an example column name based on the variable's metadata from the database.

        Args:
            variable_id (str): The ID of the variable.

        Returns:
            str: A suggested column name based on the variable and subject metadata.
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Fetch variable details
            cursor.execute("""
                SELECT subject_id, n1, n2, n3, n4, n5, measure_unit_name
                FROM variables
                WHERE id = ? and language = ?
            """, (variable_id, gus_language))

            result = cursor.fetchone()
            if not result:
                raise ValueError(_("No name found for variable ID: {id}").format(id=variable_id))

            subject_id, n1, n2, n3, n4, n5, measure_unit_name = result
            name = " ".join([x for x in [n1, n2, n3, n4, n5] if x is not None])

            # Fetch parent subject name
            cursor.execute("""
                SELECT name
                FROM subjects
                WHERE subject_code = ? and language = ?
            """, (subject_id, gus_language))

            result = cursor.fetchone()
            if not result:
                raise ValueError(_("No name found for variable ID: {id}").format(id=variable_id))

            parent_name, = result

            return f"{parent_name} {name} ({measure_unit_name})"
