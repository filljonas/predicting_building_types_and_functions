import sample.db_interaction as db


def create_subgraphs():
    """
    Create subgraphs in 2 different ways:
    -subgraphs are created based on an n_hop neighborhood
    -subgraphs are created based on circular buffers
    """
    query = f'''
CREATE OR REPLACE FUNCTION public.create_subgraphs(n INTEGER, buildings_in_graph INTEGER, n_hop BOOLEAN)
    RETURNS void AS $$
        DECLARE counter INTEGER;
        BEGIN
            IF n_hop = true THEN
                /*
                Create subgraphs with n-hop neighborhoods
                */
                
                /*
                 Table that stores the edges resulting from the triangulation method
                 */
                DROP TABLE IF EXISTS delaunay;
                CREATE TEMP TABLE delaunay
                (
                    start_id                   INTEGER,
                    end_id                     INTEGER,
                    distance                   DOUBLE PRECISION
                );
                
                DROP TABLE IF EXISTS raw_triangulation;
                CREATE TEMP TABLE raw_triangulation AS (
                    SELECT (ST_Dump(ST_DelaunayTriangles(geom, 0.0, 1))).geom as geom
                    FROM (
                        SELECT ST_Union(ST_Centroid(geom)) as geom
                        FROM buildings
                    ) oa
                );
                
                CREATE INDEX ON raw_triangulation USING gist(geom);
                
                DROP TABLE IF EXISTS buildings_centroids;
                CREATE TEMP TABLE buildings_centroids AS
                (
                    SELECT  id,
                            ST_Centroid(geom) AS geom
                    FROM buildings
                );

                CREATE INDEX ON buildings_centroids USING gist(geom);
                
                /*
                 The delaunay triangulation method only gives the geometry of the edges.
                 But we need to know which buildings are connected to which buildings.
                 */
                INSERT INTO delaunay (start_id, end_id, distance)
                SELECT b.id AS start_id,
                       c.id AS end_id,
                       MIN(ST_Length(a.geom)) AS distance
                FROM raw_triangulation a
                JOIN (
                    SELECT  id,
                            geom
                    FROM buildings_centroids
                ) b
                ON b.geom = ST_StartPoint(a.geom)
                JOIN (
                    SELECT  id,
                            geom
                    FROM buildings_centroids
                ) c
                ON c.geom = ST_EndPoint(a.geom)
                GROUP BY start_id, end_id;
                
                /*
                Create subgraphs around sampled nodes
                */
                DROP TABLE IF EXISTS nodes;
                CREATE TEMP TABLE nodes (
                    id                  INTEGER,
                    center_mask         BOOL,
                    hop                 INTEGER,
                    center_id           INTEGER
                );
                
                DROP TABLE IF EXISTS edges;
                CREATE TEMP TABLE edges
                (
                    start_id                    INTEGER,
                    end_id                      INTEGER,
                    distance                    DOUBLE PRECISION,
                    hop                         INTEGER,
                    center_id                   INTEGER
                );
                
                DROP TABLE IF EXISTS cur_nodes;
                CREATE TEMP TABLE cur_nodes AS
                (
                    SELECT id, id AS center_id
                    FROM buildings_subset
                );
                
                INSERT INTO nodes (id, center_mask, hop, center_id)
                SELECT id, true, 0, center_id FROM cur_nodes;
                
                counter := 0;
                LOOP 
                    IF counter = n THEN
                        EXIT;
                    END IF;
                    
                    counter := counter + 1;   
                    
                    DROP TABLE IF EXISTS new_cur_nodes;
                    CREATE TEMP TABLE new_cur_nodes AS
                    (
                        SELECT  a.end_id AS id,
                                b.center_id as center_id
                        FROM delaunay a
                        JOIN cur_nodes b
                        ON a.start_id = b.id
                        UNION
                        SELECT  a.start_id AS id,
                                b.center_id as center_id
                        FROM delaunay a
                        JOIN cur_nodes b
                        ON a.end_id = b.id
                    );
                    
                    INSERT INTO edges(start_id, end_id, distance, hop, center_id)
                    SELECT  a.end_id AS start_id,
                            a.start_id AS end_id,
                            a.distance,
                            counter AS hop,
                            b.center_id AS center_id
                    FROM delaunay a
                    JOIN cur_nodes b
                    ON start_id = b.id
                    UNION
                    SELECT  a.start_id,
                            a.end_id,
                            a.distance,
                            counter AS hop,
                            b.center_id AS center_id
                    FROM delaunay a
                    JOIN cur_nodes b
                    ON a.end_id = b.id;
                    
                    DROP TABLE IF EXISTS unseen_nodes;
                    CREATE TEMP TABLE unseen_nodes AS
                    (
                        SELECT  a.id,
                                a.center_id
                        FROM new_cur_nodes a
                        LEFT JOIN nodes b
                        ON a.id = b.id AND a.center_id = b.center_id
                        WHERE b.id IS NULL
                    );
                    
                    IF (SELECT COUNT(1) FROM unseen_nodes) = 0 THEN
                        EXIT;
                    END IF;
                    
                    INSERT INTO nodes (id, center_mask, hop, center_id)
                    SELECT id, false, counter, center_id FROM unseen_nodes;
                    
                    DROP TABLE IF EXISTS cur_nodes;
                    CREATE TEMP TABLE cur_nodes AS
                    (
                        SELECT id, center_id FROM unseen_nodes
                    );               
                END LOOP;
                
                DROP TABLE IF EXISTS nodes_tmp;
                CREATE TEMP TABLE nodes_tmp AS
                (
                    SELECT * FROM nodes
                );
                
                DROP TABLE IF EXISTS nodes;
                CREATE TEMP TABLE nodes AS
                (
                    SELECT  id,
                            BOOL_OR(center_mask) AS center_mask,
                            ARRAY_AGG(hop) AS hops,
                            ARRAY_AGG(center_id) AS center_ids
                    FROM nodes_tmp
                    GROUP BY id
                );
                
                DROP TABLE IF EXISTS edges_tmp;
                CREATE TEMP TABLE edges_tmp AS
                (
                    SELECT * FROM edges
                );
                
                DROP TABLE IF EXISTS edges;
                CREATE TEMP TABLE edges AS
                (
                    SELECT  start_id,
                            end_id,
                            MIN(distance) AS distance,
                            ARRAY_AGG(hop) AS hops,
                            ARRAY_AGG(center_id) AS center_ids
                    FROM edges_tmp
                    GROUP BY start_id, end_id
                );
            ELSE
            
                /*
                Create subgraphs with circular buffers
                */
                DROP TABLE IF EXISTS nodes;
                CREATE TEMP TABLE nodes (
                    id                  INTEGER,
                    center_mask         BOOL,
                    center_id           INTEGER
                );
                
                DROP TABLE IF EXISTS edges;
                CREATE TEMP TABLE edges
                (
                    start_id                    INTEGER,
                    end_id                      INTEGER,
                    distance                    DOUBLE PRECISION,
                    center_id                   INTEGER
                );
    
    
                /*
                 This table stores the IDs of the buildings that still need a larger buffer, thus further iterative steps.
                 As soon as this table is empty, the iteration ends.
                 It also ends in case the buffer size exceeds 5 km.
                 */
                DROP TABLE IF EXISTS buildings_left;
                CREATE TEMP TABLE buildings_left AS
                (
                    SELECT id AS center_id
                    FROM buildings_subset
                );
    
                DECLARE
                    distance INTEGER;
                BEGIN
                    distance := 10;
                    LOOP
                        /*
                         Breaking conditions
                         */
                        IF COUNT(1) = 0 FROM buildings_left THEN
                            EXIT;
                        END IF;
    
                        /*
                         Build buffer around all buildings for which we wish to compute graphs
                         */
                        DROP TABLE IF EXISTS buffer;
                        CREATE TEMP TABLE buffer AS
                        (
                            SELECT a.id,
                                   b.geom,
                                   ST_Buffer(b.geom, distance) AS buffer
                            FROM (
                                SELECT *
                                FROM buildings_subset
                                WHERE id IN (
                                    SELECT *
                                    FROM buildings_left
                                )
                            ) a
                            JOIN (
                                SELECT *
                                FROM buildings
                            ) b
                            USING(id)  
                        );
    
                        CREATE INDEX ON buffer USING gist(buffer);
    
                        /*
                         Get all buildings that are in the buffers
                         */
                        DROP TABLE IF EXISTS graph_nodes_current;
                        CREATE TEMP TABLE graph_nodes_current AS
                        (
                            SELECT  b.id,
                                    a.id = b.id AS center_mask,
                                    a.id AS center_id
                            FROM (
                                SELECT *
                                FROM buffer
                            ) a
                            JOIN (
                                SELECT *
                                FROM buildings
                            ) b
                            ON ST_Intersects(b.geom, a.buffer)
                        );
    
                        /*
                         Get the number of buildings in each graph
                         */
                        DROP TABLE IF EXISTS graph_nodes_with_count;
                        CREATE TEMP TABLE graph_nodes_with_count AS
                        (
                            SELECT center_id, count
                            FROM (
                                SELECT center_id, COUNT(*) AS count
                                FROM graph_nodes_current
                                GROUP BY center_id
                            ) a
                        );
    
                        /*
                         Get all buildings where the current buffer does not contain a certain minimum number of
                         buildings (ex. 40).
                         We make the buffer larger for these buildings.
                         */
                        DROP TABLE IF EXISTS buildings_left;
                        CREATE TEMP TABLE buildings_left AS
                        (
                            SELECT center_id
                            FROM graph_nodes_with_count
                            WHERE count < buildings_in_graph
                        );
                        
                        IF distance > 20000 THEN
                            /*
                             If graphs get too large in terms of radius, just add all current graphs,
                             even if their number of buildings is not sufficient.
                             */
                            INSERT INTO nodes(id, center_mask, center_id)
                            SELECT *
                            FROM graph_nodes_current
                            WHERE center_id IN (
                                SELECT center_id
                                FROM graph_nodes_with_count
                            );
                            EXIT;
                        END IF;
    
                        /*
                         These graphs have enough nodes and are added to a table that stores the final result
                         */
                        INSERT INTO nodes(id, center_mask, center_id)
                        SELECT *
                        FROM graph_nodes_current
                        WHERE center_id IN (
                            SELECT center_id
                            FROM graph_nodes_with_count
                            WHERE count >= buildings_in_graph
                        );
    
                        distance := distance + 10;
                    END LOOP;
                END;
    
                /*
                 Perform delaunay triangulation for each graph
                 */
                DROP TABLE IF EXISTS raw_triangulation;
                CREATE TEMP TABLE raw_triangulation AS (
                    SELECT oa.center_id,
                           (ST_Dump(ST_DelaunayTriangles(geom, 0.0, 1))).geom as geom
                    FROM (
                        SELECT a.center_id,
                               ST_Union(ST_Centroid(b.geom)) as geom
                        FROM (
                            SELECT *
                            FROM nodes
                        ) a
                        JOIN (
                            SELECT * FROM buildings
                        ) b
                        USING (id)
                        GROUP BY a.center_id
                    ) oa
                );
                
                CREATE INDEX ON raw_triangulation USING gist(geom);
        
                DROP TABLE IF EXISTS buildings_centroids;
                CREATE TEMP TABLE buildings_centroids AS
                (
                    SELECT  a.id,
                            ST_Centroid(b.geom) AS geom
                    FROM (
                        SELECT id
                        FROM nodes
                        GROUP BY id
                    ) a
                    JOIN (
                        SELECT  id,
                                geom
                        FROM buildings
                    ) b
                    USING (id)
                );

                CREATE INDEX ON buildings_centroids USING gist(geom);

               /*
                 The delaunay triangulation method only gives the geometry of the edges.
                 But we need to know which buildings are connected to which buildings.
                 */
                INSERT INTO edges(start_id, end_id, distance, center_id)
                SELECT b.id AS start_id,
                       c.id AS end_id,
                       MIN(ST_Length(a.geom)) AS distance,
                       a.center_id AS center_id
                FROM raw_triangulation a
                JOIN (
                    SELECT  id,
                            geom
                    FROM buildings_centroids
                ) b
                ON b.geom = ST_StartPoint(a.geom)
                JOIN (
                    SELECT  id,
                            geom
                    FROM buildings_centroids
                ) c
                ON c.geom = ST_EndPoint(a.geom)
                GROUP BY start_id, end_id, center_id;
                
                /*
                Make nodes and edges unique
                */
                DROP TABLE IF EXISTS nodes_tmp;
                CREATE TEMP TABLE nodes_tmp AS
                (
                    SELECT * FROM nodes
                );
                
                DROP TABLE IF EXISTS nodes;
                CREATE TEMP TABLE nodes AS
                (
                    SELECT  id,
                            BOOL_OR(center_mask) AS center_mask,
                            ARRAY_AGG(center_id) AS center_ids
                    FROM nodes_tmp
                    GROUP BY id
                );
                
            END IF;
        END;
$$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)