import sample.db_interaction as db


def compute_delaunay_triangulation():
    query = f'''
        /*
         |---------------------------------------------------------------------------------------------------------------------|
         | Compute delaunay triangulation for set of nodes in a subgraph
         |---------------------------------------------------------------------------------------------------------------------|
        */
        
        CREATE OR REPLACE FUNCTION public.compute_delaunay_triangulation() RETURNS void AS $$
                BEGIN
                     /*
                     Table that stores the edge resulting from the triangulation method
                     */
                    DROP TABLE IF EXISTS public.triangulation_edges;
                    CREATE TABLE public.triangulation_edges
                    (
                        center_building_id                  INTEGER,
                        start_building_id                   INTEGER,
                        end_building_id                     INTEGER,
                        start_node_id                       INTEGER,
                        end_node_id                         INTEGER,
                        distance                            DOUBLE PRECISION
                    );
        
                    /*
                     Perform delaunay triangulation for each graph
                     */
                    DROP TABLE IF EXISTS raw_triangulation;
                    CREATE TEMP TABLE raw_triangulation AS (
                        SELECT oa.center_building_id,
                               (ST_Dump(ST_DelaunayTriangles(geom, 0.0, 1))).geom as geom
                        FROM (
                            SELECT a.center_building_id,
                                   ST_Union(ST_Centroid(b.geom)) as geom
                            FROM (
                                SELECT *
                                FROM public.nodes_preliminary
                                WHERE center_building_id IN (
                                    SELECT id
                                    FROM public.buildings_subset
                                )
                            ) a
                            JOIN (
                                SELECT * FROM public.building_geoms
                            ) b
                            ON a.building_id = b.id
                            GROUP BY a.center_building_id
                        ) oa
                    );
        
                    DROP TABLE IF EXISTS triangulation_edges_geoms;
                    CREATE TEMP TABLE triangulation_edges_geoms AS (
                        SELECT  center_building_id,
                                ST_Buffer(ST_StartPoint(geom), 0.1) AS start_point,
                                ST_Buffer(ST_EndPoint(geom), 0.1) AS end_point,
                                ST_Distance(ST_StartPoint(geom), ST_EndPoint(geom)) AS distance
                        FROM raw_triangulation
                    );
        
                    CREATE INDEX ON triangulation_edges_geoms USING gist(start_point);
                    CREATE INDEX ON triangulation_edges_geoms USING gist(end_point);
        
                    /*
                     Get the centroid points for all buildings in all graphs. This is required for the next step.
                     */
                    DROP TABLE IF EXISTS buildings_centroids;
                    CREATE TEMP TABLE buildings_centroids AS
                    (
                        SELECT  a.*,
                                b.geom
                        FROM (
                            SELECT *
                            FROM public.nodes_preliminary
                            WHERE center_building_id IN (
                                SELECT id
                                FROM public.buildings_subset
                            )
                        ) a
                        JOIN (
                            SELECT  id,
                                    ST_Centroid(geom) AS geom
                            FROM public.building_geoms
                        ) b
                        ON a.building_id = b.id
                    );
        
                    CREATE INDEX ON buildings_centroids USING gist(geom);
        
                    /*
                    The delaunay triangulation method only gives the geometry of the edges.
                    But we need to know which buildings are connected to which buildings.
                    For for example: buildings with IDs 10 and 21 are connected through an edge.
                    Therefore, the edges are joined with the IDs of the starting and ending building.
                    */
                    INSERT INTO public.triangulation_edges (center_building_id, start_building_id, end_building_id, start_node_id, end_node_id, distance)
                    SELECT a.center_building_id,
                           b.building_id AS start_building_id,
                           c.building_id AS end_building_id,
                           b.node_id AS start_node_id,
                           c.node_id AS end_node_id,
                           a.distance
                        FROM triangulation_edges_geoms a
                    JOIN (
                    SELECT  center_building_id,
                            building_id,
                            node_id,
                            geom
                    FROM buildings_centroids
                    ) b
                    ON a.center_building_id = b.center_building_id AND ST_Within(b.geom, a.start_point)
                    JOIN (
                    SELECT  center_building_id,
                            building_id,
                            node_id,
                            geom
                    FROM buildings_centroids
                    ) c
                    ON a.center_building_id = c.center_building_id AND ST_Within(c.geom, a.end_point);
        
                    DROP TABLE IF EXISTS triangulation_edges_geoms;
                    DROP TABLE IF EXISTS buildings_centroids;
        
                    /*
                    Delete duplicate edges, in case there are any.
                    */
                    DROP TABLE IF EXISTS new_edges;
                    CREATE TEMP TABLE new_edges AS
                    (
                        SELECT center_building_id, start_building_id, end_building_id, start_node_id, end_node_id, MIN(distance) AS distance
                        FROM public.triangulation_edges
                        GROUP BY center_building_id, start_building_id, end_building_id, start_node_id, end_node_id
                    );
        
                    DROP TABLE IF EXISTS public.triangulation_edges;
                    CREATE TABLE public.triangulation_edges AS (
                        SELECT * FROM new_edges
                    );
        
                    DROP TABLE IF EXISTS new_edges;
        
                    INSERT INTO public.edges_preliminary (id_region, center_building_id, start_building_id, end_building_id, start_node_id, end_node_id, distance)
                    SELECT 1, *
                    FROM public.triangulation_edges
                    ORDER BY center_building_id;
                END;
        $$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)
    query = f'''
        SELECT public.compute_delaunay_triangulation();
        
        DROP FUNCTION IF EXISTS public.compute_delaunay_triangulation;
    '''
    db.execute_statement(query)