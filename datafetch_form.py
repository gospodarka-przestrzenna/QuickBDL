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


from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QProgressBar
from PyQt5.QtCore import Qt
from .datafetch_worker import DataFetchWorker
from .utils.translations import _


class DataFetchForm(QDialog):
    """
    A dialog for fetching data from the API with a progress bar and status messages.

    Args:
        do_merge (bool): Whether to merge rural and urban areas.
        units (list): List of selected territorial units.
        variables (list): List of selected variables.
        variables_names (dict): Mapping of variable IDs to user-defined column names.
    """
    def __init__(self, do_merge, units, variables, variables_names):
        super().__init__()

        self.do_merge = do_merge
        self.units = units
        self.variables = variables
        self.variables_names = variables_names
        self.layer = None  # Placeholder for the resulting layer

        # Configure the main dialog window
        self.setWindowTitle(_("Data Fetching"))
        self.resize(600, 150)

        # Progress bar to display the download progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)

        # Label to display status messages
        self.message_label = QLabel(_("Initializing data fetching..."))
        self.message_label.setAlignment(Qt.AlignCenter)

        # Button to cancel or proceed after data fetching
        self.button = QPushButton(_("Finish"))
        self.button.clicked.connect(self.accept)
        self.button.setEnabled(False)  # Initially disabled until fetching is complete

        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.message_label)
        layout.addWidget(self.button)

        self.setLayout(layout)

    def showEvent(self, event):
        """
        Called when the dialog is shown. Initializes and starts the data fetching worker thread.
        """
        self.worker = DataFetchWorker(
            self.do_merge,
            self.units,
            self.variables,
            self.variables_names
        )
        # Connect worker signals
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.data_fetched.connect(self.on_data_fetched)
        self.worker.error_occurred.connect(self.on_error)
        # Start the worker thread
        self.worker.start()

    def update_progress(self, value, unit, variable):
        """
        Updates the progress bar and status label.

        Args:
            value (int): Percentage of completion.
            unit (str): The current unit being processed.
            variable (str): The current variable being processed.
        """
        self.progress_bar.setValue(value)
        short_unit = unit[2:4] + unit[7:11]  # Simplified unit code
        self.message_label.setText(
            _("Fetching data: {value}% complete. (unit: {unit}, variable: {variable})").format(
                value=value, unit=short_unit, variable=variable
            )
        )

    def on_data_fetched(self):
        """
        Called when data fetching is completed successfully.
        Updates the status label and enables the button to proceed.
        """
        self.message_label.setText(_("Data fetching completed successfully."))
        self.layer = self.worker.layer
        self.button.setText(_("Next"))
        self.button.setEnabled(True)

    def on_error(self, message):
        """
        Handles errors during data fetching.

        Args:
            message (str): The error message to display.
        """
        self.message_label.setText(_("Error: {message}").format(message=message))
        self.button.clicked.disconnect()
        self.button.clicked.connect(self.close)
        self.button.setText(_("Close"))
        self.button.setEnabled(True)
        self.worker.quit()

    def closeEvent(self, event):
        """
        Overrides the close event to ensure the dialog rejects properly.

        Args:
            event (QCloseEvent): The close event.
        """
        self.reject()
        event.accept()
