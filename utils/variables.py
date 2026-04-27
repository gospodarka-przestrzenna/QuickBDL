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
from .tokens import Tokens
from .subjects import Subjects
from ..config import DB_PATH

# Konfiguracja bazy danych i API
API_BASE_URL_VARIABLES = "https://bdl.stat.gov.pl/api/v1/Variables"
REQUESTS_PER_SECOND_LIMIT = 30
PAGE_SIZE = 100


class Variables(object):
    def __init__(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS variables (
                    id INTEGER,
                    subject_id TEXT,
                    n1 TEXT,
                    n2 TEXT,
                    n3 TEXT,
                    n4 TEXT,
                    n5 TEXT,    
                    language TEXT NOT NULL,
                    level INTEGER,
                    measure_unit_id INTEGER,
                    measure_unit_name TEXT
                );
            ''')
            # Indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS variables_subject_id_idx ON variables (subject_id);
            ''')
            # unique are id with language
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS variables_id_language_idx ON variables (id, language);
            ''')

            conn.commit()

    def add_variable(self, cursor, item,lang):
        cursor.execute('''
            INSERT OR REPLACE INTO variables (id, subject_id, n1, n2, n3, n4, n5, language, level, measure_unit_id, measure_unit_name)
            VALUES                           (?,  ?,          ?,  ?,  ?,  ?,  ?,  ?,        ?,     ?,               ?)
        ''', (
            item["id"],
            item["subjectId"],
            item.get("n1"),
            item.get("n2"),
            item.get("n3"),
            item.get("n4"),
            item.get("n5"),
            lang,
            item["level"],
            item["measureUnitId"],
            item["measureUnitName"]
        ))

    def get_pending_subject_with_variables(self,lang):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                        SELECT subject_code
                        FROM subjects 
                        WHERE 
                           has_variables = 1 AND 
                           children_fetched = 0 AND
                           language = ?
                        LIMIT 1""", (lang,))
            
            subject_code = cursor.fetchone()
            return subject_code[0] if subject_code else None
    
    def fetch_variables_page(self, subject_code, page, lang):
        token = Tokens().get_random_token()
        data = {
            "lang": lang,
            "format": "json",
            "page-size": PAGE_SIZE,
            "page": page,
            "subject-id": subject_code
        }
        headers = {"X-ClientId": token}
        response = requests.get(API_BASE_URL_VARIABLES, headers=headers, params=data, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"ERROR {response.status_code}. TOKEN {token}")
            Tokens().mark_token_failed(token)

    def fetch_and_save_variables(self, subject_code, lang):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            page = 0
            while True:
                data = self.fetch_variables_page(subject_code, page, lang)
                if not data:
                    time.sleep(5)
                    continue
                
                for item in data["results"]:
                    if int(item["level"]) == 6 :
                        self.add_variable(cursor, item,lang)
                if  "next" not in data["links"]:
                    break
                page += 1
                time.sleep(1 / REQUESTS_PER_SECOND_LIMIT)
            print(f"Subject {subject_code} completed")
            Subjects().mark_parent_fetched(cursor, subject_code, lang)

            conn.commit()

    def fetch_and_save_variables_for_subjects(self, lang):
        while True:
            subject_code = self.get_pending_subject_with_variables(lang)
            if not subject_code:
                break
            self.fetch_and_save_variables(subject_code, lang)

    def recreate_variables_table(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DROP TABLE IF EXISTS variables;
            ''')
            conn.commit()
        self.__init__()
        self.fetch_and_save_variables_for_subjects("pl")
        self.fetch_and_save_variables_for_subjects("en")


        #url = f"{API_BASE_URL_VARIABLES}?subject-id={subject_id}&lang=pl&format=json&page-size={PAGE_SIZE}&page={page}"
