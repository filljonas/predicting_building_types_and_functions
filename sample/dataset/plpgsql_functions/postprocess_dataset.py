import sample.db_interaction as db


def postprocess_dataset():
    query = f'''
        /*
         |---------------------------------------------------------------------------------------------------------------------|
         | Postprocess dataset:
         | - Create ID per graph
         | - Delete duplicate graphs
         | - For each node, mark other graph were the node is contained (needed for train/val/test split)
         |---------------------------------------------------------------------------------------------------------------------|
        */
        
        CREATE OR REPLACE FUNCTION public.postprocess_dataset() RETURNS void AS $$
                BEGIN
                    /*
                    This table assigns each graph a unique ID
                    */
                    DROP TABLE IF EXISTS graph_ids;
                    CREATE TEMP TABLE graph_ids AS
                    (
                        SELECT  ROW_NUMBER() OVER () - 1 AS id,
                                *
                        FROM (
                            SELECT id_region,
                                   center_building_id
                            FROM public.nodes_preliminary
                            GROUP BY id_region, center_building_id
                            ORDER BY id_region, center_building_id
                        ) a
                    );
        
                    DROP TABLE IF EXISTS public.nodes;
                    CREATE TABLE public.nodes AS (
                        SELECT  b.id AS graph_id,
                                a.*
                        FROM public.nodes_preliminary a
                        JOIN graph_ids b
                        ON a.id_region = b.id_region AND a.center_building_id = b.center_building_id
                        ORDER BY graph_id, node_id
                    );
        
                    DROP TABLE IF EXISTS public.edges;
                    CREATE TABLE public.edges AS (
                        SELECT  b.id AS graph_id,
                                a.*
                        FROM public.edges_preliminary a
                        JOIN graph_ids b
                        ON a.id_region = b.id_region AND a.center_building_id = b.center_building_id
                        ORDER BY graph_id
                    );
        
                    /*
                    In rare cases, self loops occur -> delete them
                    */
                    DELETE FROM public.edges
                    WHERE start_node_id = end_node_id;
        
                    DROP TABLE IF EXISTS nodes_preliminary;
                    DROP TABLE IF EXISTS public.nodes_preliminary;
                    DROP TABLE IF EXISTS public.edges_preliminary;
        
                     /*
                      Retrieve all graphs that only appear once
                      */
                    DROP TABLE IF EXISTS nodes_without_duplicates;
                    CREATE TEMP TABLE nodes_without_duplicates AS
                    (
                        WITH neighborhoods_array AS (
                            SELECT graph_id, ARRAY_AGG(building_id ORDER BY building_id) AS building_id_array
                            FROM public.nodes
                            GROUP BY graph_id
                        ),
                        remove_duplicates AS (
                            SELECT DISTINCT ON (building_id_array) graph_id,
                                                building_id_array
                            FROM neighborhoods_array
                            ORDER BY building_id_array, graph_id
                        )
                        SELECT *
                        FROM remove_duplicates
                    );
        
                    /*
                     Delete all graphs that occur multiple times
                     */
                    DELETE FROM public.nodes
                    WHERE graph_id NOT IN (
                        SELECT graph_id
                        FROM nodes_without_duplicates
                    );
        
                    DELETE FROM public.edges
                    WHERE graph_id NOT IN (
                        SELECT graph_id
                        FROM nodes_without_duplicates
                    );
        
                    /*
                     For all buildings, collect all IDs of subgraphs where this building occurs in an array
                    */
                    DROP TABLE IF EXISTS graphs_per_building;
                    CREATE TEMP TABLE graphs_per_building AS
                    (
                        SELECT ob.global_id,
                            ob.id_region,
                            ob.id,
                            ob.graph_id_arr,
                            oa.geom
                        FROM (
                            SELECT *
                            FROM public.building_geoms
                        ) oa
                        JOIN (
                            SELECT a.global_id, a.id_region, a.id, ARRAY_AGG(b.graph_id) AS graph_id_arr
                            FROM (
                                SELECT *
                                FROM public.building_geoms
                            ) a
                            JOIN (
                                SELECT *
                                FROM public.nodes
                            ) b
                            ON a.id_region = b.id_region AND a.id = b.building_id
                            GROUP BY a.global_id, a.id_region, a.id
                        ) ob
                        ON oa.global_id = ob.global_id
                    );
        
                    CREATE INDEX ON graphs_per_building USING gist(geom);
        
                    /*
                     Join nodes table with arrays that contain IDs of subgraphs.
                     So for each node, we know in which other subgraphs the node is located in.
                    */
                    DROP TABLE IF EXISTS nodes_tmp;
                    CREATE TEMP TABLE nodes_tmp AS (
                        SELECT  a.*,
                                b.graph_id_arr
                        FROM (
                            SELECT *
                            FROM public.nodes
                        ) a
                        JOIN (
                            SELECT *
                            FROM graphs_per_building
                        ) b
                        ON a.id_region = b.id_region AND a.building_id = b.id
                    );
        
                    DROP TABLE IF EXISTS public.nodes;
                    CREATE TABLE public.nodes AS (
                        SELECT *
                        FROM nodes_tmp
                    );
        
                    /*
                     Clean tables up
                     */
                    DROP TABLE IF EXISTS nodes_tmp;
                    DROP TABLE IF EXISTS nodes_without_duplicates;
                    DROP TABLE IF EXISTS graphs_per_building;
                    DROP TABLE IF EXISTS mark_duplicated_buildings;
        
                    DROP TABLE IF EXISTS public.block_clusters_w_buffer;
                    DROP TABLE IF EXISTS public.buildings_splitted;
                    DROP TABLE IF EXISTS public.buildings_subset;
                    DROP TABLE IF EXISTS public.graph_nodes;
                    DROP TABLE IF EXISTS public.triangulation_edges;
                END;
        $$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)
    query = f'''
            SELECT public.postprocess_dataset();

            DROP FUNCTION IF EXISTS public.postprocess_dataset;
        '''
    db.execute_statement(query)