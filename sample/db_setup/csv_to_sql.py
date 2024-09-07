"""
Load OSM, Urban Atlas and CLC class mappings into PostgreSQL
"""

import sys
sys.path.append('../../')

import numpy as np
import pandas as pd
from sqlalchemy.sql import text

import sample.db_interaction as db

engine = db.create_sqlalchemy_engine()

if __name__ == '__main__':
    names = ['osm_type_matches', 'ua_matches', 'clc_matches']
    for name in names:
        table_name = name
        path = f'{name}.csv'
        csv_file_path = f'{path}'
        df = pd.read_csv(csv_file_path, encoding='ISO-8859-1')
        df.to_sql(table_name, engine, index=True, if_exists='replace', schema='public')