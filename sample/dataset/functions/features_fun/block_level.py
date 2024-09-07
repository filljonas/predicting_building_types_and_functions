import sample.db_interaction as db


def block_level():
    query = f'''
        /*
         |---------------------------------------------------------------------------------------------------------------------|
         | Compute block-level features
         |---------------------------------------------------------------------------------------------------------------------|
        */

        CREATE OR REPLACE FUNCTION public.block_level()
            RETURNS void AS $$
                BEGIN
                    /*
                     Create all blocks that belong to the buildings of interest.
                     We have to consider all buildings in the region here.
                     */
                    DROP TABLE IF EXISTS blocks_w_duplicated;
                    CREATE TEMP TABLE blocks_w_duplicated AS
                    (
                        SELECT  ROW_NUMBER() OVER() AS entry_id,
                                block_clusters_w_buffer.id AS block_id,
                                block_clusters_w_buffer.geom AS geom
                        FROM (
                            SELECT ROW_NUMBER() OVER () AS id,
                                   ST_MakeValid(ST_Buffer(geom, 0.17), 'method=structure') AS geom
                            FROM (
                                SELECT UNNEST(ST_ClusterWithin(geom, 0.35)) AS geom
                                FROM (
                                    SELECT geom
                                    FROM buildings
                                ) buildings
                            ) block_clusters
                        ) block_clusters_w_buffer
                        JOIN (
                            SELECT *
                            FROM buildings_with_features
                        ) dataset
                        ON ST_Within(dataset.geom, block_clusters_w_buffer.geom)
                    );

                    DROP TABLE IF EXISTS blocks;
                    CREATE TEMP TABLE blocks AS
                    (
                        SELECT block_id AS id,
                               geom
                        FROM blocks_w_duplicated
                        WHERE entry_id IN (
                            SELECT MIN(entry_id)
                            FROM blocks_w_duplicated
                            GROUP BY block_id)
                    );

                    CREATE INDEX ON blocks USING gist(geom);

                    /*
                     Get all buildings within these blocks
                     */
                    DROP TABLE IF EXISTS all_buildings_within_blocks;
                    CREATE TEMP TABLE all_buildings_within_blocks AS
                    (
                        SELECT a.id,
                               a.geom,
                               ST_Area(a.geom) AS footprint_area,
                               b.id AS block_id
                        FROM (
                            SELECT *
                            FROM buildings
                        ) a
                        JOIN (
                            SELECT *
                            FROM blocks
                            LIMIT (SELECT COUNT(1) FROM blocks)
                        ) b
                        ON ST_Within(a.geom, b.geom)
                    );

                    CREATE INDEX ON all_buildings_within_blocks USING gist(geom);

                    /*
                     Compute shared wall length and number of touching buildings for all buildings in the graphs
                     */
                    DROP TABLE IF EXISTS building_level_features_interacting_blocks;
                    CREATE TEMP TABLE building_level_features_interacting_blocks AS
                    (
                        SELECT  id,
                                CASE
                                    WHEN shared_wall_length IS NULL THEN 0.0
                                    ELSE shared_wall_length
                                END AS shared_wall_length,
                               CASE
                                    WHEN count_touches IS NULL THEN 0.0
                                    ELSE count_touches
                                END AS count_touches
                        FROM (
                            SELECT id
                            FROM buildings_with_features
                        ) a
                        LEFT JOIN (
                            SELECT  a.id,
                                    SUM(ST_Length(ST_Intersection(exterior_ring, b.geom))) AS shared_wall_length,
                                    COUNT(*) AS count_touches
                            FROM (
                                SELECT *, ST_Boundary(ST_Buffer(geom, 0.35)) AS exterior_ring
                                FROM all_buildings_within_blocks
                            ) a
                            LEFT JOIN (
                                SELECT id, geom
                                FROM all_buildings_within_blocks
                            ) b
                            ON ST_Intersects(exterior_ring, b.geom)
                            WHERE a.id <> b.id
                            GROUP BY a.id
                        ) b
                        USING (id)
                    );

                    DROP TABLE IF EXISTS block_level_features_interacting_buildings;
                    CREATE TEMP TABLE block_level_features_interacting_buildings AS
                    (
                        SELECT id,
                               block_id,
                               block_length,
                               av_block_footprint_area,
                               std_block_footprint_area
                        FROM (
                            SELECT *
                            FROM buildings_with_features
                        ) oa
                        JOIN (
                            WITH block_level_statistics AS (
                                SELECT block_id,
                                    count(*) AS block_length,
                                    AVG(footprint_area) AS av_block_footprint_area,
                                    STDDEV_POP(footprint_area) AS std_block_footprint_area
                                FROM  all_buildings_within_blocks
                                GROUP BY block_id
                            )
                            SELECT a.id,
                                   b.block_id,
                                   b.block_length,
                                   b.av_block_footprint_area,
                                   b.std_block_footprint_area
                            FROM (
                                SELECT * FROM all_buildings_within_blocks
                            ) a
                            JOIN (
                                SELECT * FROM block_level_statistics
                            ) b
                            ON a.block_id = b.block_id
                        ) ob
                        USING (id)
                    );

                    DROP TABLE IF EXISTS convex_hulls;
                    CREATE TEMP TABLE convex_hulls AS
                    (
                        SELECT id,
                               ST_ConvexHull(geom) AS convex_hull
                        FROM blocks
                    );

                    DROP TABLE IF EXISTS footprint_area;
                    CREATE TEMP TABLE footprint_area AS
                    (
                        SELECT id,
                               ST_Area(geom) AS footprint_area
                        FROM blocks
                    );

                    DROP TABLE IF EXISTS bounding_box_aux;
                    CREATE TEMP TABLE bounding_box_aux AS (
                        WITH segments AS
                        (
                            SELECT DISTINCT id, ST_Azimuth(sp, ep)::NUMERIC % (0.5 * pi())::NUMERIC AS angle, geom
                            FROM (
                                SELECT id,
                                   ST_PointN(geom, generate_series(1, ST_NPoints(geom)-1)) AS sp,
                                   ST_PointN(geom, generate_series(2, ST_NPoints(geom)  )) AS ep, geom
                                FROM (
                                    SELECT id, ST_ExteriorRing(convex_hull) AS geom
                                    FROM convex_hulls
                                ) AS ls
                            ) AS seg
                        ),
                        envelopes AS
                        (
                            SELECT id, angle, st_envelope(st_rotate(geom, angle)) AS envelope
                            FROM segments
                        ),
                        selectedboundingbox AS
                        (
                            SELECT DISTINCT ON (id) id, angle, envelope, st_area(envelope) AS min_area
                            FROM envelopes
                            ORDER BY id, st_area(envelope) ASC
                        )
                        SELECT id,
                               ST_Rotate(envelope, -angle) AS boundingbox
                        FROM selectedboundingbox
                    );

                    DROP TABLE IF EXISTS exterior_ring_rectangle;
                    CREATE TEMP TABLE exterior_ring_rectangle AS
                    (
                        SELECT id,
                               ST_ExteriorRing(boundingbox) AS exterior_ring_rectangle
                        FROM bounding_box_aux
                    );

                    DROP TABLE IF EXISTS angles;
                    CREATE TEMP TABLE angles AS
                    (
                        SELECT  id,
                                ST_PointN(exterior_ring_rectangle,1) AS angle_1,
                                ST_PointN(exterior_ring_rectangle,2) AS angle_2,
                                ST_PointN(exterior_ring_rectangle,3) AS angle_3,
                                ST_PointN(exterior_ring_rectangle,4) AS angle_4
                        FROM exterior_ring_rectangle
                    );

                    DROP TABLE IF EXISTS length_axis;
                    CREATE TEMP TABLE length_axis AS
                    (
                        SELECT  id,
                                ST_Distance(angle_1, angle_4) AS length_axis_1_to_4,
                                ST_Distance(angle_1, angle_2) AS length_axis_1_to_2
                        FROM angles
                    );

                    DROP TABLE IF EXISTS corners;
                    CREATE TEMP TABLE corners AS
                    (
                        SELECT id,
                               (SELECT count(1)
                                FROM (
                                    WITH corner_points AS (
                                        SELECT *
                                        FROM (
                                            SELECT (ST_DumpPoints(ST_ExteriorRing(ST_Simplify(ia.geom, 0.25)))).geom AS geom,
                                                 (ST_DumpPoints(ST_ExteriorRing(ST_Simplify(ia.geom, 0.25)))).path[1] AS coordinate_pos
                                            FROM blocks ia
                                            WHERE ia.id = a.id
                                    ) ia
                                ),
                                remove_last AS (
                                    SELECT *
                                    FROM corner_points
                                    WHERE coordinate_pos < (SELECT MAX(coordinate_pos) FROM corner_points)
                                ),
                                prev_next AS (
                                    SELECT
                                      geom,
                                      coordinate_pos,
                                      LAG(geom, 1) OVER (ORDER BY coordinate_pos) prev_point,
                                      LEAD(geom, 1) OVER (ORDER BY coordinate_pos) next_point
                                    FROM
                                      remove_last
                                ),
                                first_last AS (
                                    (SELECT *
                                    FROM prev_next
                                    WHERE prev_point IS NOT NULL AND next_point IS NOT NULL)
                                    UNION ALL
                                    (SELECT
                                      geom,
                                      coordinate_pos,
                                      FIRST_VALUE(geom) OVER (ORDER BY coordinate_pos DESC) prev_point,
                                      LEAD(geom, 1) OVER (ORDER BY coordinate_pos) next_point
                                    FROM remove_last
                                    ORDER BY coordinate_pos ASC LIMIT 1)
                                    UNION ALL
                                    (SELECT
                                      geom,
                                      coordinate_pos,
                                      LAG(geom, 1) OVER (ORDER BY coordinate_pos) prev_point,
                                      FIRST_VALUE(geom) OVER (ORDER BY coordinate_pos) next_point
                                    FROM remove_last
                                    ORDER BY coordinate_pos DESC LIMIT 1)
                                )
                                    SELECT degrees(ST_Angle(next_point, geom, prev_point)) AS angle
                                    FROM first_last
                                    ORDER BY coordinate_pos
                                ) ia
                                WHERE angle <= 170 OR angle >= 190) AS corners
                        FROM blocks a
                    );

                    DROP TABLE IF EXISTS block_level_features_for_blocks;
                    CREATE TEMP TABLE block_level_features_for_blocks AS
                    (
                        SELECT  id,
                                footprint_area,
                                ST_Perimeter(geom) AS perimeter,
                                footprint_area / (pow((ST_MinimumBoundingRadius(geom)).radius, 2) * pi()) AS phi,
                                (ST_MinimumBoundingRadius(convex_hull)).radius * 2 AS longest_axis_length,
                                CASE
                                    WHEN length_axis_1_to_4 <= length_axis_1_to_2 THEN length_axis_1_to_4 / length_axis_1_to_2
                                    ELSE length_axis_1_to_2 / length_axis_1_to_4
                                END AS elongation,
                                footprint_area / ST_Area(convex_hull) AS convexity,
                                CASE
                                    WHEN ST_Distance(angle_1, angle_4) <= ST_Distance(angle_1, angle_2) THEN ABS(MOD(((DEGREES(ST_Azimuth(angle_1, angle_2))) + 45)::NUMERIC, 90) - 45)
                                    ELSE ABS(MOD(((DEGREES(ST_Azimuth(angle_1, angle_4))) + 45)::NUMERIC, 90) - 45)
                                END AS orientation,
                                corners AS corners
                        FROM (
                            SELECT * FROM blocks
                        ) bg
                        JOIN (
                            SELECT * FROM convex_hulls
                        ) ch
                        USING (id)
                        JOIN (
                            SELECT * FROM footprint_area
                        ) ar
                        USING (id)
                        JOIN (
                            SELECT * FROM angles
                        ) ang
                        USING (id)
                        JOIN (
                            SELECT * FROM length_axis
                        ) lenax
                        USING (id)
                        JOIN (
                            SELECT * FROM corners
                        ) corn
                        USING (id)
                    );

                    DROP TABLE IF EXISTS block_level_features;
                    CREATE TEMP TABLE block_level_features AS
                    (
                        SELECT  a.id,
                                b.footprint_area AS block_total_footprint_area,
                                b.perimeter AS block_perimeter,
                                b.longest_axis_length AS block_longest_axis_length,
                                b.elongation AS block_elongation,
                                b.convexity AS block_convexity,
                                b.orientation AS block_orientation,
                                b.corners AS block_corners
                        FROM (
                            SELECT * FROM block_level_features_interacting_buildings
                        ) a
                        JOIN (
                            SELECT * FROM block_level_features_for_blocks
                        ) b
                        ON a.block_id = b.id
                    );        
                END;
        $$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)