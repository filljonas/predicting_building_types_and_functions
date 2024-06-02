"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Create GNN dataset in the form of database tables.
 | After this step, we still need to convert this data to the format readable by PyG.
 |---------------------------------------------------------------------------------------------------------------------|
"""

import sample.db_interaction as db
import sample.dataset.plpgsql_functions.create_graph_nodes as gn
import sample.dataset.plpgsql_functions.compute_node_features as nf
import sample.dataset.plpgsql_functions.compute_delaunay_triangulation as dt
import sample.dataset.plpgsql_functions.postprocess_dataset as pp


def create_database_table(min_nodes_per_graph, subsample_fraction, x_min, x_max, y_min, y_max):
    """

    :param min_nodes_per_graph: minimum nodes that have to occur in each subgraph
    :param subsample_fraction: which fraction of all labeled nodes to include into the dataset (take random subset)
    :param x_min west lat-coordinate
    :param x_max east lat-coordinate
    :param y_min south long-coordinate
    :param y_max north long-coordinate
    """
    query = f"""
        /*
         |-------------------------------------------------------------------------------------------------------------|
         | Create dataset that is used to train the classification models
         |-------------------------------------------------------------------------------------------------------------|
        */
        
        /*
         This table stores the IDs of the center buildings and surrounding buildings of the subgraphs/neighborhoods 
         that are included in the dataset.
         It also stores the node features of all buildings
         */
        DROP TABLE IF EXISTS public.nodes_preliminary;
        CREATE TABLE public.nodes_preliminary (
            id_region                                                                               INTEGER,
            country                                                                                 VARCHAR(5),
            center_building_id                                                                      INTEGER,
            building_id                                                                             INTEGER,
            node_id                                                                                 INTEGER,
            footprint_area                                                                          DOUBLE PRECISION,
            perimeter                                                                               DOUBLE PRECISION,
            phi                                                                                     DOUBLE PRECISION,
            longest_axis_length                                                                     DOUBLE PRECISION,
            elongation                                                                              DOUBLE PRECISION,
            convexity                                                                               DOUBLE PRECISION,
            orientation                                                                             DOUBLE PRECISION,
            corners                                                                                 DOUBLE PRECISION,
            shared_wall_length                                                                      DOUBLE PRECISION,
            count_touches                                                                           DOUBLE PRECISION,
            block_id                                                                                INTEGER,
            block_length                                                                            DOUBLE PRECISION,
            av_block_footprint_area                                                                 DOUBLE PRECISION,
            std_block_footprint_area                                                                DOUBLE PRECISION,
            block_total_footprint_area                                                              DOUBLE PRECISION,
            block_perimeter                                                                         DOUBLE PRECISION,
            block_longest_axis_length                                                               DOUBLE PRECISION,
            block_elongation                                                                        DOUBLE PRECISION,
            block_convexity                                                                         DOUBLE PRECISION,
            block_orientation                                                                       DOUBLE PRECISION,
            block_corners                                                                           DOUBLE PRECISION,
            land_cover                                                                              VARCHAR(50),
            ua_coverage                                                                             SMALLINT,
            land_cover_ua_clc                                                                       VARCHAR(50),
            degurba                                                                                 VARCHAR(30),
            numerical_label                                                                         INTEGER
        );
        
        /*
         This table stores that edges of the graphs computed with triangulation
         */
        DROP TABLE IF EXISTS public.edges_preliminary;
        CREATE TABLE public.edges_preliminary (
            id_region                           INTEGER,
            center_building_id                  INTEGER,
            start_building_id                   INTEGER,
            end_building_id                     INTEGER,
            start_node_id                       INTEGER,
            end_node_id                         INTEGER,
            distance                            DOUBLE PRECISION
        );
        
        /*
         This table assigns each building in the dataset to its corresponding geometry
         */
        DROP TABLE IF EXISTS public.building_geoms;
        CREATE TABLE public.building_geoms (
            global_id                           SERIAL PRIMARY KEY,
            id_region                           INTEGER,
            id                                  INTEGER,
            osm_id                              INTEGER,
            geom                                GEOMETRY(POLYGON, 3035)
        );
        """
    db.execute_statement(query)
    print('Create graph nodes...')
    gn.create_graph_nodes(min_nodes_per_graph, subsample_fraction, x_min, x_max, y_min, y_max)
    print('Compute node features...')
    nf.compute_node_features()
    print('Compute delaunay triangulation...')
    dt.compute_delaunay_triangulation()
    print('Postprocess dataset...')
    pp.postprocess_dataset()