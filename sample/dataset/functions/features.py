import sample.db_interaction as db


def features():
    query = f'''
/*
 |---------------------------------------------------------------------------------------------------------------------|
 | Compute node features
 |---------------------------------------------------------------------------------------------------------------------|
*/

CREATE OR REPLACE FUNCTION public.features(n_hop BOOLEAN)
    RETURNS void AS $$
        DECLARE counter INTEGER;
        BEGIN
            IF n_hop = true THEN
                DROP TABLE IF EXISTS buildings_with_features;
                CREATE TEMP TABLE buildings_with_features AS
                (
                    SELECT  a.id,
                            a.center_mask,
                            a.hops,
                            a.center_ids,
                            b.geom,
                            b.country,
                            b.osm_id
                    FROM (
                        SELECT * FROM nodes
                    ) a
                    JOIN (
                        SELECT * FROM buildings
                    ) b
                    USING (id)
                );
            ELSE
                DROP TABLE IF EXISTS buildings_with_features;
                CREATE TEMP TABLE buildings_with_features AS
                (
                    SELECT  a.id,
                            a.center_mask,
                            a.center_ids,
                            b.geom,
                            b.country,
                            b.osm_id
                    FROM (
                        SELECT * FROM nodes
                    ) a
                    JOIN (
                        SELECT * FROM buildings
                    ) b
                    USING (id)
                );
            END IF;

            CREATE INDEX ON buildings_with_features USING gist(geom);
            
            PERFORM public.building_level();
            PERFORM public.block_level();
            PERFORM public.land_use();
            PERFORM public.degurba();
            
            IF n_hop = true THEN
                DROP TABLE IF EXISTS aux_tab;
                CREATE TEMP TABLE aux_tab AS
                (
                    SELECT  id,
                            country,
                            osm_id,
                            center_mask,
                            hops,
                            center_ids,
                            geom,
                            ST_X(ST_PointOnSurface(ST_Transform(geom, 4326))) AS lon,
                            ST_Y(ST_PointOnSurface(ST_Transform(geom, 4326))) AS lat
                    FROM buildings_with_features
                );
            ELSE
                DROP TABLE IF EXISTS aux_tab;
                CREATE TEMP TABLE aux_tab AS
                (
                    SELECT  id,
                            country,
                            osm_id,
                            center_mask,
                            center_ids,
                            geom,
                            ST_X(ST_PointOnSurface(ST_Transform(geom, 4326))) AS lon,
                            ST_Y(ST_PointOnSurface(ST_Transform(geom, 4326))) AS lat
                    FROM buildings_with_features
                );
            END IF;
            
            DROP TABLE IF EXISTS node_features;
            CREATE TEMP TABLE node_features AS
            (
                SELECT  *
                FROM (
                    SELECT * FROM building_level_features
                ) a
                JOIN (
                    SELECT * FROM building_level_features_interacting_blocks
                ) b
                USING (id)
                JOIN (
                    SELECT * FROM block_level_features_interacting_buildings
                ) c
                USING (id)
                JOIN (
                    SELECT * FROM block_level_features
                ) d
                USING (id)
                JOIN (
                    SELECT * FROM land_cover_category
                ) e
                USING (id)
                JOIN (
                    SELECT * FROM degurba_category
                ) f
                USING (id)
                JOIN (
                    SELECT  *
                    FROM aux_tab
                ) g
                USING (id)
            );
            
            ALTER TABLE node_features
            DROP COLUMN block_id;
            
            
            IF n_hop = true THEN
                /*
                Switch order of columns
                */
                DROP TABLE IF EXISTS node_features_tmp;
                CREATE TEMP TABLE node_features_tmp AS
                (
                    SELECT  *
                    FROM node_features
                );
                
                DROP TABLE IF EXISTS node_features;
                CREATE TEMP TABLE node_features AS
                (
                    SELECT  footprint_area, perimeter, phi, longest_axis_length, elongation, convexity, orientation, corners, shared_wall_length, count_touches,
                            block_length, av_block_footprint_area, std_block_footprint_area, block_total_footprint_area, block_perimeter, block_longest_axis_length, block_elongation, block_convexity, block_orientation, block_corners,
                            ua_coverage, land_cover_ua_clc, degurba, country, osm_id, center_mask, hops, center_ids,
                            geom, lon, lat, id
                    FROM node_features_tmp
                );
            ELSE
                DROP TABLE IF EXISTS node_features_unnested;
                CREATE TEMP TABLE node_features_unnested AS
                (
                    SELECT  footprint_area, perimeter, phi, longest_axis_length, elongation, convexity, orientation, corners, shared_wall_length, count_touches,
                            block_length, av_block_footprint_area, std_block_footprint_area, block_total_footprint_area, block_perimeter, block_longest_axis_length, block_elongation, block_convexity, block_orientation, block_corners,
                            ua_coverage, land_cover_ua_clc, degurba, country, osm_id, center_mask,
                            UNNEST(center_ids) AS center_id,
                            geom, lon, lat, id
                    FROM node_features
                );
                
                UPDATE node_features_unnested
                SET center_mask = false
                WHERE center_id <> id;
                
                DROP TABLE IF EXISTS node_features_tmp;
                CREATE TEMP TABLE node_features_tmp AS
                (
                    SELECT  *,
                            -- Sequential ID that only numbers the buildings actually considered in the dataset
                            ROW_NUMBER() OVER() - 1 AS new_id
                    FROM node_features_unnested
                );
                
                DROP TABLE IF EXISTS edges_tmp;
                CREATE TEMP TABLE edges_tmp AS
                (
                    SELECT * FROM edges
                );
                
                DROP TABLE IF EXISTS edges;
                CREATE TEMP TABLE edges AS
                (
                    SELECT  b.new_id AS start_id,
                            c.new_id AS end_id,
                            a.distance AS distance,
                            a.center_id AS center_id
                    FROM edges_tmp a
                    JOIN (
                        SELECT *
                        FROM node_features_tmp
                    ) b
                    ON a.center_id = b.center_id AND a.start_id = b.id
                    JOIN (
                        SELECT *
                        FROM node_features_tmp
                    ) c
                    ON a.center_id = c.center_id AND a.end_id = c.id
                );
                
                /*
                Mark hops of nodes (from center node of subgraph)
                */
                DROP TABLE IF EXISTS nodes_hops;
                CREATE TEMP TABLE nodes_hops
                (
                    id                  INTEGER,
                    hop                 INTEGER
                );
                
                DROP TABLE IF EXISTS cur_nodes;
                CREATE TEMP TABLE cur_nodes AS
                (
                    SELECT new_id AS id
                    FROM node_features_tmp
                    WHERE center_mask = true
                );
                
                INSERT INTO nodes_hops (id, hop)
                SELECT id, 0 FROM cur_nodes;
                
                counter := 0;
                LOOP 
                    
                    counter := counter + 1;   
                    
                    DROP TABLE IF EXISTS new_cur_nodes;
                    CREATE TEMP TABLE new_cur_nodes AS
                    (
                        SELECT end_id AS id
                        FROM edges
                        WHERE start_id IN (SELECT id FROM cur_nodes)
                        UNION
                        SELECT start_id AS id
                        FROM edges
                        WHERE end_id IN (SELECT id FROM cur_nodes)
                    );
                    
                    DROP TABLE IF EXISTS unseen_nodes;
                    CREATE TEMP TABLE unseen_nodes AS
                    (
                        SELECT id
                        FROM new_cur_nodes
                        WHERE id NOT IN (
                            SELECT id
                            FROM nodes_hops
                        )
                    );
                    
                    IF (SELECT COUNT(1) FROM unseen_nodes) = 0 THEN
                        EXIT;
                    END IF;

                    INSERT INTO nodes_hops(id, hop)
                    SELECT id, counter FROM new_cur_nodes
                    WHERE id IN (SELECT id FROM unseen_nodes);
                    
                    DROP TABLE IF EXISTS cur_nodes;
                    CREATE TEMP TABLE cur_nodes AS
                    (
                        SELECT id FROM new_cur_nodes
                    );             
                END LOOP;
                
                DROP TABLE IF EXISTS node_features;
                CREATE TEMP TABLE node_features AS
                (
                    SELECT  footprint_area, perimeter, phi, longest_axis_length, elongation, convexity, orientation, corners, shared_wall_length, count_touches,
                            block_length, av_block_footprint_area, std_block_footprint_area, block_total_footprint_area, block_perimeter, block_longest_axis_length, block_elongation, block_convexity, block_orientation, block_corners,
                            ua_coverage, land_cover_ua_clc, degurba, country, osm_id, center_mask, center_id,
                            hop, geom, lon, lat, a.id, new_id
                    FROM node_features_tmp a
                    JOIN (
                        SELECT  id,
                                hop
                        FROM nodes_hops
                    ) b
                    ON a.new_id = b.id
                );
                
                
            END IF;
            
            DROP TABLE IF EXISTS node_features_with_labels;
            CREATE TEMP TABLE node_features_with_labels AS
            (
                SELECT  a.*,
                        CASE
                            /*
                             The graphs also contain buildings without labels.
                             These buildings get the label "9" to avoid working with NULL-values in the table.
                             */
                            WHEN b.numerical_label IS NULL THEN 9
                            ELSE b.numerical_label
                        END AS numerical_label
                FROM node_features a
                LEFT JOIN buildings_with_labels b
                USING (id)
            );
        END;
$$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)