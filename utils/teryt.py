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
import time

from .geometry import Geometry
from .tokens import Tokens
from ..config import DB_PATH 
from .translations import _,gus_language

# Configuration
API_BASE_URL = "https://bdl.stat.gov.pl/api/v1/units"
REQUESTS_PER_SECOND_LIMIT = 30  # maksymalnie 10 zapytania na sekundę


class Teryt(object):
    def __init__(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teryt_codes (
                    short_code TEXT NOT NULL,
                    full_code TEXT NOT NULL,
                    parent_code TEXT,
                    name TEXT NOT NULL,
                    kind TEXT,
                    level INTEGER NOT NULL,
                    language TEXT NOT NULL
                );
            ''')
            # Indexes
            #the short code is mostly used for searching
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS teryt_codes_short_code_idx ON teryt_codes (short_code);
            ''')
            # we will search also by parent_code that is search for children
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS teryt_codes_parent_code_idx ON teryt_codes (parent_code);
            ''')    
            # unique are fullcode with language
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS teryt_codes_full_code_language_idx ON teryt_codes (full_code, language);
            ''')
            conn.commit()

    def _add_teryt_code(self, short_code, full_code, parent_code, name, kind, level, lang):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO teryt_codes (short_code, full_code, parent_code, name, kind, level, language)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (short_code, full_code, parent_code, name, kind, level, lang))
            conn.commit()

    def _fetch_teryt_page(self,page,lang):
        
        token = Tokens().get_random_token()
        params = {
            "format": "json",
            "page": page,
            "lang": lang,
            "page-size": 100
        }
        headers = {"X-ClientId": token}
        response = requests.get(API_BASE_URL, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"ERROR {response.status_code}.TOKEN {token}")
            Tokens().mark_token_failed(token)

    def _fetch_and_save_teryt_codes(self,lang):
        page = 0
        while True:
            data = self._fetch_teryt_page(page,lang)
            if not data:
                
                time.sleep(5)
                continue
            for code in data["results"]:
                full_code = code.get("id")
                short_code = full_code[2:4]+full_code[7:11]
                if short_code.startswith('1431'):
                    continue #skip this code this is old capital city code
                parent_code = code.get("parentId", None)
                name = code.get("name")
                kind = code.get("kind", None)
                level = code.get("level")
                self._add_teryt_code(short_code, full_code, parent_code, name, kind, level, lang)
            if "next" not in data["links"]:
                break
            page += 1
            time.sleep(1 / REQUESTS_PER_SECOND_LIMIT)
    
    def code_to_name(self,shorter_code, kind, lang):
        """
        Returns a human-readable name based on the code.

        Args:
            kind (str): The shorter code to get the name for without type.
            lang (str): The language code to get the name in.

        Returns:
            str: The human-readable name of the code. If the code is not found, returns None.
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM teryt_codes WHERE short_code = ? AND kind = ? AND language = ?", (shorter_code, kind, lang))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_type_name(self, level, kind):
        """
        Returns a human-readable type name based on the level and kind.
        """
        if level == 2:
            return _("Voivodeship")
        elif level == 4:
            return _("Subregion")
        elif level == 5:
            return _("County")
        elif level == 6:
            return {
                '1': _("City"),
                '2': _("Rural commune"),
                '3': _("Urban-rural commune"),
                '4': _("City in urban-rural commune"),
                '5': _("Rural area in urban-rural commune"),
                '8': _("City district"),
            }.get(kind, _("Unknown type"))
        return _("Unknown type")


    def _recreate_teryt_table(self):
        """
        Recreates the TERYT table.
        Do not use this method unless you know what you are doing.
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DROP TABLE IF EXISTS teryt_codes;
            ''')
            conn.commit()
        self.__init__()
        self.fetch_and_save_teryt_codes("pl")
        self.fetch_and_save_teryt_codes("en")
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # as a final step we have to remove the old capital city code
            # and every kind 2 that we have kind 3 for 
            cursor.execute('''
                DELETE FROM 
                           teryt_codes as t1 
                WHERE t1.short_code LIKE '1431%' OR (
                    t1.kind = '2' AND
                    EXISTS (
                            SELECT name FROM teryt_codes as t2
                            WHERE t1.short_code = t2.short_code AND
                            t2.kind = '3'
                           )
                    )''');      
            conn.commit()
