import sample.db_interaction as db


def create_graph_nodes(min_buildings_in_neighborhood, subsample_fraction, x_min, x_max, y_min, y_max):
    query = f'''
        /*
         |---------------------------------------------------------------------------------------------------------------------|
         | Collect nodes (buildings from OSM) and assemble subgraphs with a minimum of n_sub number of nodes
         |---------------------------------------------------------------------------------------------------------------------|
        */
        
        CREATE OR REPLACE FUNCTION public.create_graph_nodes(min_buildings_in_neighborhood INTEGER,
                                                                subsample_fraction DOUBLE PRECISION,
                                                                x_min DOUBLE PRECISION,
                                                                x_max DOUBLE PRECISION,
                                                                y_min DOUBLE PRECISION,
                                                                y_max DOUBLE PRECISION)
            RETURNS void AS $$
                DECLARE
                    distance INTEGER;
                    min_buildings_in_neighborhood INTEGER;
                BEGIN
                    /*
                     |---------------------------------------------------------------------------------------------------------|
                     | Part 1: Extract buildings from OSM
                     |---------------------------------------------------------------------------------------------------------|
                    */
                    DROP TABLE IF EXISTS buildings;
                    CREATE TEMP TABLE buildings AS
                    (
                        SELECT  ROW_NUMBER() OVER() AS id,
                                a.osm_id,
                                a.building AS building_key,
                                a.tags,
                                a.way AS geom,
                                ST_Area(ST_Intersection(a.way, d.geom)) AS intersection_area,
                                e.degurba_label::TEXT AS degurba,
                                f.country_code
                        FROM (
                            SELECT *
                            FROM public.planet_osm_polygon
                            -- Exclude "buildings" that are no real buildings
                            WHERE building IS NOT NULL AND NOT building = ANY(ARRAY['no', 'maybe'])
                         ) a
                        JOIN (
                            SELECT ST_Transform(ST_MakeEnvelope ( x_min, y_min, x_max, y_max, 4326
                                           )::GEOMETRY('POLYGON'), 3035) AS geom
                        ) d
                        ON ST_Intersects(a.way, d.geom)
                       JOIN (
                            SELECT  geom,
                                    degurba_label,
                                    lau_id
                            FROM public.degurba
                        ) e
                        ON ST_Intersects(a.way, e.geom)
                        JOIN (
                            SELECT code AS country_code,
                                   geom
                            FROM public.countries
                        ) f
                        ON ST_Intersects(a.way, f.geom)
                    );
        
                    /*
                     Set DEGURBA label
                     */
                    UPDATE buildings
                    SET degurba = 'city'
                    WHERE degurba = '1';
        
                    UPDATE buildings
                    SET degurba = 'town_or_suburb'
                    WHERE degurba = '2';
        
                    UPDATE buildings
                    SET degurba = 'rural_area'
                    WHERE degurba = '3';
        
                    /*
                     |---------------------------------------------------------------------------------------------------------|
                     | Part 2: Pre-processing of buildings
                     |---------------------------------------------------------------------------------------------------------|
                    */
                    /*
                     Since we joined to the DEGURBA map with an intersects-operation, buildings on borders are
                     assigned to multiple DEGURBA polygons. We just pick one arbitrary one.
                     */
                    WITH to_keep AS (
                       SELECT MIN(id) AS id
                       FROM buildings
                       GROUP BY osm_id
                    )
                    DELETE FROM buildings
                    WHERE id NOT IN (
                        SELECT id
                        FROM to_keep
                    );
        
                    /*
                     In rare cases, incoherent buildings form one MultiPolygon in OSM.
                     To make the representation consistent, we convert all MultiPolygons to Polygons.
                     */
                    DROP TABLE IF EXISTS buildings_splitted;
                    CREATE TEMP TABLE buildings_splitted AS
                    (
                        SELECT    ROW_NUMBER() OVER() AS id,
                                  osm_id,
                                  building_key,
                                  tags,
                                  (ST_Dump(geom)).geom AS geom,
                                  degurba,
                                  country_code
                        FROM buildings
                    );
        
                    /*
                     Sometimes, duplicates of buildings with the same `osm_id` occur in OSM. We remove them.
                     */
                    WITH to_keep AS (
                       SELECT MIN(id) AS id
                       FROM buildings
                       GROUP BY osm_id
                    )
                    DELETE FROM buildings
                    WHERE id NOT IN (
                        SELECT id
                        FROM to_keep
                    );
        
                    /*
                     In rare cases, incoherent buildings form one MultiPolygon in OSM.
                     To make the representation consistent, we convert all MultiPolygons to Polygons.
                     */
                    DROP TABLE IF EXISTS buildings_splitted;
                    CREATE TEMP TABLE buildings_splitted AS
                    (
                        SELECT    ROW_NUMBER() OVER() AS id,
                                  osm_id,
                                  building_key,
                                  tags,
                                  (ST_Dump(geom)).geom AS geom,
                                  degurba,
                                  country_code
                        FROM buildings
                    );
        
                    CREATE INDEX ON buildings_splitted USING gist(geom);
        
                    DROP TABLE IF EXISTS public.buildings_splitted;
                    CREATE TABLE public.buildings_splitted AS (
                        SELECT  ROW_NUMBER() OVER() AS id,
                                osm_id,
                                building_key,
                                tags,
                                geom,
                                degurba,
                                country_code
                        FROM buildings_splitted
                    );
        
                    CREATE INDEX ON public.buildings_splitted USING gist(geom);
        
                    /*
                     Remove buildings with duplicate geometries (they cause problems in graphs)
                     */
                    WITH to_keep AS (
                       SELECT MIN(id) AS id
                       FROM public.buildings_splitted
                       GROUP BY geom
                    )
                    DELETE FROM public.buildings_splitted
                    WHERE id NOT IN (
                        SELECT id
                        FROM to_keep
                    );
        
                    /*
                     Extract the labeled buildings (contain building class) and store the label
                     */
                    DROP TABLE IF EXISTS buildings_with_labels;
                    CREATE TEMP TABLE buildings_with_labels AS
                    (
                        SELECT a.*,
                               b.numerical_label
                        FROM (
                            SELECT * FROM public.buildings_splitted
                        ) a
                        JOIN (
                            SELECT *
                            FROM public.osm_type_matches
                            WHERE numerical_label <> 9
                        ) b
                        ON a.building_key = b.building_key
                    );
        
                    /*
                     Delete buildings that do not fulfill constraints
                     */
                    DELETE FROM buildings_with_labels
                    WHERE   tags->'building:use' IS NOT NULL
                            /*
                             Terraced houses can also be labeled with `building=house`and additionally `house=terraced/terrace`
                             according to: https://wiki.openstreetmap.org/wiki/Tag:building%3Dterrace
                             */
                            OR (building_key = 'house' AND  (tags->'house' IS NULL OR
                                                            (NOT tags->'house' = ANY(ARRAY['terraced', 'terrace']))));
        
                    CREATE INDEX ON buildings_with_labels USING gist(geom);
        
                    DROP TABLE IF EXISTS grid_cell;
                    DROP TABLE IF EXISTS buildings;
                    DROP TABLE IF EXISTS buildings_splitted;
                    /*
                     |---------------------------------------------------------------------------------------------------------|
                     | Part 4: Create graph nodes
                     |---------------------------------------------------------------------------------------------------------|
                    */
        
                    /*
                     Subsample buildings. We create graphs around these buildings.
                     */
                    DROP TABLE IF EXISTS public.buildings_subset;
                    CREATE TABLE public.buildings_subset AS
                    (
                        SELECT a.*
                        FROM buildings_with_labels a
                        ORDER BY RANDOM() LIMIT (
                            SELECT COUNT(1)
                            FROM public.buildings_splitted
                        )::DOUBLE PRECISION * subsample_fraction
                    );
        
                    DROP TABLE IF EXISTS public.graph_nodes;
                    CREATE TABLE public.graph_nodes (
                        center_building_id              INTEGER,
                        building_id                     INTEGER,
                        node_id                         INTEGER
                    );
        
                    DROP TABLE IF EXISTS buildings_left;
                    CREATE TEMP TABLE buildings_left AS
                    (
                        SELECT id AS center_building_id
                        FROM public.buildings_subset
                    );
        
                    distance := 10;
                    min_buildings_in_neighborhood := 20;
        
                    LOOP
                        /*
                         Breaking condition
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
                            SELECT id,
                                   geom,
                                   ST_Buffer(geom, distance) AS buffer
                            FROM public.buildings_subset
                            WHERE id IN (
                                SELECT *
                                FROM buildings_left
                            )
                        );
        
                        CREATE INDEX ON buffer USING gist(buffer);
        
                        /*
                         Get all buildings that intersect the buffers
                         */
                        DROP TABLE IF EXISTS graph_nodes_current;
                        CREATE TEMP TABLE graph_nodes_current AS
                        (
                            SELECT  a.id AS center_building_id,
                                    b.id AS building_id,
                                    /*
                                     This is an ID that identifies the node in each graphs separately.
                                     For example, if the graph has 40 nodes, the IDs range from 0 to 39.
                                     */
                                    ROW_NUMBER() OVER (PARTITION BY a.id ORDER BY b.id) - 1 AS node_id
                            FROM (
                                SELECT *
                                FROM buffer
                            ) a
                            JOIN (
                                SELECT *
                                FROM public.buildings_splitted
                            ) b
                            ON ST_Intersects(b.geom, a.buffer)
                        );
        
                        /*
                         Get the number of buildings in each graph
                         */
                        DROP TABLE IF EXISTS graph_nodes_with_count;
                        CREATE TEMP TABLE graph_nodes_with_count AS
                        (
                            SELECT center_building_id, count
                            FROM (
                                SELECT center_building_id, COUNT(*) AS count
                                FROM graph_nodes_current
                                GROUP BY center_building_id
                            ) a
                        );
        
                        /*
                         Get all graphs where the current buffer does not contain a certain minimum number of
                         buildings (ex. 40).
                         We make the buffer larger for these graphs.
                         */
                        DROP TABLE IF EXISTS buildings_left;
                        CREATE TEMP TABLE buildings_left AS
                        (
                            SELECT center_building_id
                            FROM graph_nodes_with_count
                            WHERE count < min_buildings_in_neighborhood
                        );
        
                        IF distance > 5000 THEN
                            /*
                             If graphs get too large in terms of radius, just add all current graphs,
                             even if their number of buildings is not sufficient.
                             Requirement: graph contains at least 2 buildings.
                             */
                            INSERT INTO public.graph_nodes (center_building_id, building_id, node_id)
                            SELECT *
                            FROM graph_nodes_current
                            WHERE center_building_id IN (
                                SELECT center_building_id
                                FROM graph_nodes_with_count
                                WHERE count >= 2
                            );
                            EXIT;
                        END IF;
        
                        /*
                         These graphs have enough nodes and are added to a table that stores the final result
                         */
                        INSERT INTO public.graph_nodes (center_building_id, building_id, node_id)
                        SELECT *
                        FROM graph_nodes_current
                        WHERE center_building_id IN (
                            SELECT center_building_id
                            FROM graph_nodes_with_count
                            WHERE count >= min_buildings_in_neighborhood
                        );
        
                        DROP TABLE IF EXISTS buffer;
                        DROP TABLE IF EXISTS graph_nodes_current;
                        DROP TABLE IF EXISTS graph_nodes_with_count;
        
                        distance := distance + 10;
                    END LOOP;
        
                    DROP TABLE IF EXISTS buildings_left;
                END;
        $$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)
    query = f'''
            SELECT public.create_graph_nodes({min_buildings_in_neighborhood}, {subsample_fraction}, {x_min}, {x_max}, {y_min}, {y_max});

            DROP FUNCTION IF EXISTS public.create_graph_nodes;
        '''
    db.execute_statement(query)