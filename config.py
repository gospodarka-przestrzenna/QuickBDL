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

import os

DB_FILENAME = "data2604.sqlite"

current_dir = os.path.dirname(os.path.realpath(__file__))
DB_PATH = os.path.join(current_dir, DB_FILENAME)

DATABASE_URL = "https://github.com/gospodarka-przestrzenna/QuickBDL/releases/download/database/data2604.sqlite"
