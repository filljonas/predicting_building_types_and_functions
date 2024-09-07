drop_functions = f'''
    DROP FUNCTION IF EXISTS public.extract_buildings;
    DROP FUNCTION IF EXISTS public.create_subgraph;
    DROP FUNCTION IF EXISTS public.building_level;
    DROP FUNCTION IF EXISTS public.block_level;
    DROP FUNCTION IF EXISTS public.land_use;
    DROP FUNCTION IF EXISTS public.degurba;
    DROP FUNCTION IF EXISTS public.features;
    DROP FUNCTION IF EXISTS public.drop_temp_tables;
'''
create_tables_n_hop = f'''
    DROP TABLE IF EXISTS public.node_features_with_labels_n_hop;
    CREATE TABLE public.node_features_with_labels_n_hop (
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
        ua_coverage                                                                             INTEGER,
        land_cover_ua_clc                                                                       TEXT,
        degurba                                                                                 TEXT,
        country                                                                                 VARCHAR(2),
        osm_id                                                                                  INTEGER,
        center_mask                                                                             BOOL,
        hops                                                                                    INTEGER[],
        center_ids                                                                              INTEGER[],
        geom                                                                                    GEOMETRY(POLYGON, 3035),
        lon                                                                                     DOUBLE PRECISION,                                                                  
        lat                                                                                     DOUBLE PRECISION,
        id                                                                                      INTEGER,
        numerical_label                                                                         INTEGER                                                                
    );

    DROP TABLE IF EXISTS public.edges_n_hop;
    CREATE TABLE public.edges_n_hop (
        start_id                    INTEGER,
        end_id                      INTEGER,
        distance                    DOUBLE PRECISION,
        hops                        INTEGER[],
        center_ids                  INTEGER[]
    );
'''
create_tables_circ = f'''
    DROP TABLE IF EXISTS public.node_features_with_labels_circ;
    CREATE TABLE public.node_features_with_labels_circ (
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
        ua_coverage                                                                             INTEGER,
        land_cover_ua_clc                                                                       TEXT,
        degurba                                                                                 TEXT,
        country                                                                                 VARCHAR(2),
        osm_id                                                                                  INTEGER,
        center_mask                                                                             BOOL,
        center_id                                                                               INTEGER,
        hop                                                                                     INTEGER,
        geom                                                                                    GEOMETRY(POLYGON, 3035),
        lon                                                                                     DOUBLE PRECISION,                                                                  
        lat                                                                                     DOUBLE PRECISION,
        id_orig                                                                                 INTEGER,
        id                                                                                      INTEGER,
        numerical_label                                                                         INTEGER                                                                
    );

    DROP TABLE IF EXISTS public.edges_circ;
    CREATE TABLE public.edges_circ (
        start_id                    INTEGER,
        end_id                      INTEGER,
        distance                    DOUBLE PRECISION,
        center_id                   INTEGER                                                           
    );
'''


def perform_computations(subsample_fraction, num_layers, buildings_in_graph, type, x_min, x_max, y_min, y_max):
    computations = f"""   
        SELECT public.extract_buildings({subsample_fraction}, {x_min}, {x_max}, {y_min}, {y_max});
        SELECT public.create_subgraphs({num_layers}, {buildings_in_graph}, {type == "n_hop"});
        SELECT public.features({type == "n_hop"});
        
        INSERT INTO public.node_features_with_labels_{type}
        SELECT * FROM node_features_with_labels;
        
        INSERT INTO public.edges_{type}
        SELECT * FROM edges;
    """
    return computations