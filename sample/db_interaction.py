"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Interaction with DB
 |---------------------------------------------------------------------------------------------------------------------|
"""

import os
import pandas as pd
import sqlalchemy


def create_sqlalchemy_engine():
    """
    Create engine in SQLAlchemy
    :return: engine
    """
    user = 'postgres'
    password = os.getenv('POSTGRESQL_PASSWORD')
    host = 'localhost'
    port = 5432
    database = 'osm'
    return sqlalchemy.create_engine(f'postgresql://{user}:{password}@{host}:{port}/{database}')


engine = create_sqlalchemy_engine()


def execute_statement(query):
    """
    Execute query (without result)
    :param query: SQL query as string
    """
    query = sqlalchemy.sql.text(query)
    with engine.connect() as connection:
        connection.execute(query)
        connection.commit()


def sql_to_df(query):
    """
    Execute a database query that loads SQL table into Pandas dataframe.
    :param query: SQL query as string
    :return: dataframe containing query result
    """
    query = sqlalchemy.sql.text(query)
    df = pd.read_sql_query(query, engine)
    return df


def sql_to_float(query):
    """
    Execute a database query that returns a single numerical value (like number of rows in a table) as float
    :param query: SQL query as string
    :return: float containing the query result
    """
    query = sqlalchemy.sql.text(query)
    df = pd.read_sql_query(query, engine)
    # Result is a dataframe with one row and one column. Convert this to float.
    lst = df.iloc[:, 0].tolist()
    return float(lst[0])


def sql_to_string(query):
    """
    Execute a database query that returns a single string (like one column value of a specific row)
    :param query: SQL query as string
    :return: string containing the query result
    """
    query = sqlalchemy.sql.text(query)
    df = pd.read_sql_query(query, engine)
    # Result is a dataframe with one row and one column. Convert this to float.
    lst = df.iloc[:, 0].tolist()
    return str(lst[0])


def sql_to_bool(query):
    """
    Execute a database query that returns a single boolean
    :param query: SQL query as string
    :return: bool containing the query result
    """
    query = sqlalchemy.sql.text(query)
    df = pd.read_sql_query(query, engine)
    # Result is a dataframe with one row and one column. Convert this to float.
    lst = df.iloc[:, 0].tolist()
    return bool(lst[0])