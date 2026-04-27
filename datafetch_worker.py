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
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from .create_layer import Layer
from .utils.translations import _
from .config import DB_PATH
import urllib3
import time
from .utils.expander import Expander
from .utils.tokens import Tokens

class DataFetchWorker(QThread):
    """
    Worker thread for fetching data from the API. Handles progress updates, error handling,
    and data processing, while emitting relevant signals.
    """
    progress_updated = pyqtSignal(int, str, str)  # Signal for progress updates (progress, unit, variable)
    data_fetched = pyqtSignal()  # Signal emitted after data fetching is complete
    error_occurred = pyqtSignal(str)  # Signal emitted when an error occurs

    def __init__(self, do_merge, units, variables, variables_names):
        """
        Initialize the worker.

        Args:
            do_merge (bool): Whether to merge rural and urban areas into a single unit.
            units (list): List of unit codes to fetch data for.
            variables (list): List of variable IDs to fetch data for.
            variables_names (dict): Mapping of variable IDs to their user-defined column names.
        """
        super().__init__()
        
        # Initialize urllib3 connection pool
        self.http = urllib3.PoolManager()
        
        # Create a new layer to store fetched data
        self.layer = Layer(_("GUS data layer"))

        self.do_merge = do_merge
        self.units = units
        self.variables = variables
        self.variables_names = variables_names        

        for full_code,name,geometry in Expander().codes_name_geometry(self.units,do_merge):
            self.layer.create_new_feature(full_code,name,geometry,do_merge)

    def run(self):
        """
        Main execution function for the worker thread. Handles data fetching and
        updates the progress accordingly.
        """
        total_requests = 2 * len(self.units) * len(self.variables)
        completed_requests = 0
        
        for variable in self.variables:
            for unit in self.units:
                # Update progress before each request
                completed_requests += 1
                progress = int((completed_requests / total_requests) * 100)
                self.progress_updated.emit(progress, unit, variable)

                # Fetch data for the current variable-unit pair
                success = self.fetch_data(variable, unit)
                if not success:
                    self.error_occurred.emit(_("Error while fetching data. D1"))
                    return

                # Update progress after successful fetch
                completed_requests += 1
                progress = int((completed_requests / total_requests) * 100)
                self.progress_updated.emit(progress, unit, variable)
        
        # Emit signal once all data is fetched
        self.data_fetched.emit()

    def fetch_data(self, variable, unit):
        """
        Fetch data from the API for a specific variable and unit, handling pagination.

        Args:
            variable (str): The variable ID to fetch data for.
            unit (str): The unit code to fetch data for.

        Returns:
            bool: True if the data was fetched successfully, False otherwise.
        """
        page = 0
        while True:
            # Get a valid token for the request
            token = Tokens().get_random_token()

            if not token:
                self.error_occurred.emit(_("No available tokens. D2"))
                print("No available tokens. D2")  # Debugging output
                return False
            
            url = f"https://bdl.stat.gov.pl/api/v1/data/by-variable/{variable}"
            params = {
                "unit-parent-id": unit,
                "unit-level": 6,
                "page": page,
                "page-size": 100
            }
            headers = {
                "X-ClientId": token,
                "User-Agent": "curl/7.64.1",
                "Accept": "*/*"
            }
            
            # Build full URL with params
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{query_string}"
                        
            try:
                response = self.http.request(
                    'GET',
                    full_url,
                    headers=headers,
                    timeout=urllib3.Timeout(connect=10, read=30)
                )
                
                # Check rate limit headers
                rate_limit_remaining = response.headers.get('X-Rate-Limit-Remaining')
                rate_limit_reset = response.headers.get('X-Rate-Limit-Reset')
                
                
                if response.status == 200:
                    import json
                    data = json.loads(response.data.decode('utf-8'))

                    # Process the response and add data to the layer
                    self.process_response(data)

                    # Stop if there's no next page
                    if "links" not in data or "next" not in data["links"]:
                        break

                    page += 1
                    time.sleep(1)  # Rate limiting between requests
                elif rate_limit_remaining is not None and int(rate_limit_remaining) == 0:
                    # token has hit the rate limit - mark it as failed and try again with a different token
                    print(f"Invalid token ({response.status}) for {variable} and {unit}")
                    Tokens().mark_token_failed(token)   
                    continue
                else:
                    # Other HTTP errors - try again with different token
                    print(f"HTTP {response.status} for {variable} and {unit} - retrying with different token")
                    continue
            except urllib3.exceptions.TimeoutError:
                print(f"Timeout while fetching data for {variable} and {unit} - retrying with different token")
                continue
            except Exception as e:
                print(f"Exception: {e} - retrying with different token")
                continue
        return True


    def process_response(self, data):
        """
        Process the API response and add data to the layer.

        Args:
            data (dict): The JSON response from the API.
        """
        
        variable_id = str(data["variableId"])
        
        for result in data.get("results", []):
            unit_id = str(result["id"])
            
            for value in result["values"]:
                year = str(value["year"])
                val = value["val"]
                
                self.layer.add_GUS_data(
                    unit_id,
                    year,
                    val,
                    self.variables_names[variable_id]
                )
