"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Create tables with node features and edges in database
 |---------------------------------------------------------------------------------------------------------------------|
"""

import time
import datetime as dt

import sample.db_interaction as db
import sample.dataset.functions.extract_buildings as ex
import sample.dataset.functions.create_subgraphs as cs
import sample.dataset.functions.features as fe
import sample.dataset.functions.features_fun.building_level as bl
import sample.dataset.functions.features_fun.block_level as bc
import sample.dataset.functions.features_fun.land_use as lu
import sample.dataset.functions.features_fun.degurba as dg
import sample.dataset.functions.drop_temp_tables as dr
import sample.dataset.sql_queries.sql_create_dataset as sqlds


def create_functions():
    ex.extract_buildings()
    cs.create_subgraphs()
    fe.features()
    bl.building_level()
    bc.block_level()
    lu.land_use()
    dg.degurba()
    dr.drop_temp_tables()


def drop_functions():
    db.execute_statement(sqlds.drop_functions)


def create_tables(type):
    """
    Tables were results from all regions are aggregated
    """
    if type == 'n_hop':
        db.execute_statement(sqlds.create_tables_n_hop)
    elif type == 'circ':
        db.execute_statement(sqlds.create_tables_circ)


def create_dataset():
    type = 'circ'
    subsample_fraction = 0.004
    num_layers = 4
    buildings_in_graph = 20
    x_min, x_max, y_min, y_max = 11.53187, 11.6785, 48.1599, 48.23839
    # Create functions
    create_functions()
    # Create tables
    create_tables(type)
    # Perform computations
    db.execute_statement(sqlds.perform_computations(subsample_fraction, num_layers, buildings_in_graph, type,
                                                    x_min, x_max, y_min, y_max))
    drop_functions()


if __name__ == '__main__':
    start = time.time()
    create_dataset()
    end = time.time()
    formatted_time = str(dt.timedelta(seconds=end - start))
    print(f'Time to create dataset: {formatted_time}')

