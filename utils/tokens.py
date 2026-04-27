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
import time
import uuid
import sqlite3
from ..config import DB_PATH

url =  "https://bdl.stat.gov.pl/api/v1/client?lang=pl"

class Tokens(object):
    def __init__(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""CREATE TABLE IF NOT EXISTS tokens (
                                token TEXT PRIMARY KEY,
                                last_failed_time INTEGER
                         );""")
            conn.commit()
    
    def _add_token(self, token):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tokens (token, last_failed_time) VALUES (?, ?);", (token, 0))
            conn.commit()

    def get_random_token(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""SELECT token FROM tokens
                                WHERE last_failed_time < ?
                            ORDER BY RANDOM() LIMIT 1;""",
                            (int(time.time())-900,)) ## 15 minutes
            token = cursor.fetchone()
            return token[0] if token else None
    
    def mark_token_failed(self, token):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tokens SET last_failed_time = ? WHERE token = ?;", (int(time.time()), token))
            conn.commit()
    
    def _create_new_token(self):
        mail_uuid = str(uuid.uuid4())
        response = requests.post(
            url, 
            timeout=30,
            data={"Email": "{token}@uuid.com".format(token=mail_uuid)} # we need to provide an email
        )
        token = response.text.split(": ")[1].split("<")[0]
        
        return token
    

