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
from ..config import DB_PATH

# Config
API_BASE_URL_SUBJECTS = "https://bdl.stat.gov.pl/api/v1/subjects"
REQUESTS_PER_SECONDS_LIMIT = 30 # Max 30 requests per minute

class Subjects(object):
    def __init__(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subjects (
                    subject_code TEXT NOT NULL,
                    parent_id TEXT,
                    name TEXT NOT NULL,
                    language TEXT NOT NULL,
                    has_variables BOOLEAN,
                    children_fetched BOOLEAN DEFAULT 0 -- status for children: 0 - not fetched, 1 - fetched
                );
            ''')
            # Indexes
            #the short code is mostly used for searching
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS subjects_subject_code_idx ON subjects (subject_code);
            ''')
            # we will search also by parent_id
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS subjects_parent_id_idx ON subjects (parent_id);
            ''')
            # unique are subject_code with language
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS subjects_subject_code_language_idx ON subjects (subject_code, language);
            ''')
            conn.commit()
    
    def add_subject(self, cursor, subject_code, parent_id, name, lang, has_variables):
        cursor.execute('''
            INSERT INTO subjects (subject_code, parent_id, name, language, has_variables, children_fetched)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (subject_code, parent_id, name, lang, has_variables, 0))


    def fetch_subjects_page(self, parent, page, lang):
        t = Tokens()
        token = t.get_random_token()
        data = {
            "lang": lang,
            "format": "json",
            "page-size": 100,
            "page": page,
            "parent-id": parent
        }
        # Remove parent-id if it's None
        if parent is None:
            data.pop("parent-id")
        # Send request
        headers = {"X-ClientId": token}
        response = requests.get(API_BASE_URL_SUBJECTS, headers=headers, params=data, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"ERROR {response.status_code}. TOKEN {token}")
            t.mark_token_failed(token)
    
    def mark_parent_fetched(self, cursor, parent, lang):
        cursor.execute("""
                    UPDATE subjects 
                    SET children_fetched = 1 
                    WHERE 
                        subject_code = ? AND
                        language = ? """, (parent,lang))

    def fetch_clild_subjects(self, parent, lang):
        """
        Fetch subjects for a given parent ID.
        
        Args:
            parent (str): The parent ID to fetch subjects for.
            lang (str): The language code to fetch subjects in.

        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            page = 0
            while True:
                data = self.fetch_subjects_page(parent, page, lang)
                
                if not data:
                    # token failed
                    time.sleep(5)
                    continue            
                for item in data["results"]:
                    if 6 in item["levels"]:
                        self.add_subject(cursor, item["id"], parent, item["name"], lang, item["hasVariables"])
                if "next" not in data["links"]:
                    break            
                page += 1
            
            self.mark_parent_fetched(cursor, parent, lang)

            conn.commit()
            time.sleep(1/REQUESTS_PER_SECONDS_LIMIT)  # Rate limiting between requests

    def get_uncompleted_parent(self,lang):
        print("Checking for uncompleted parent")
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                        SELECT subject_code 
                        FROM subjects 
                        WHERE 
                            children_fetched = 0 and 
                            language = ? and
                            has_variables = 0 
                        LIMIT 1""", (lang,))
            result = cursor.fetchone()
            return result[0] if result else None

    def uncompleated_subjects(self, lang):
        while parent:
            parent = self.get_uncompleted_parent(lang)
            if not parent:
                break
            
            self.fetch_clild_subjects(parent, lang)
            # gettting next parent

    def recreate_subjects_table(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           DROP TABLE IF EXISTS subjects;
                            ''')
            conn.commit()
        self.__init__()
        self.fetch_clild_subjects(None, "pl")
        self.uncompleated_subjects("pl")
        self.fetch_clild_subjects(None, "en")
        self.uncompleated_subjects("en")
