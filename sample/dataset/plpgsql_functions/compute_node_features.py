import sample.db_interaction as db


def compute_node_features():
    query = f'''
        /*
         |---------------------------------------------------------------------------------------------------------------------|
         | Compute node features for set of buildings
         |---------------------------------------------------------------------------------------------------------------------|
        */
        
        CREATE OR REPLACE FUNCTION public.compute_node_features() RETURNS void AS $$
                BEGIN
                         /*
                         Get the buildings in all graphs. We have to compute features for these buildings.
                         */
                        DROP TABLE IF EXISTS public.buildings_with_features;
                        CREATE TABLE public.buildings_with_features AS
                        (
                            SELECT  ROW_NUMBER() OVER() AS id_for_parser,
                                    ob.id,
                                    ob.osm_id,
                                    ob.geom,
                                    ob.degurba,
                                    ob.country_code
                            FROM (
                                SELECT a.building_id
                                FROM (
                                    SELECT * FROM public.graph_nodes
                                ) a
                                JOIN (
                                    SELECT * FROM public.buildings_subset
                                ) b
                                ON a.center_building_id = b.id
                                GROUP BY a.building_id
                            ) oa
                            JOIN (
                                SELECT * FROM public.buildings_splitted
                            ) ob
                            ON oa.building_id = ob.id
                        );
        
                        DROP TABLE IF EXISTS public.block_clusters_w_buffer;
                        CREATE TABLE public.block_clusters_w_buffer AS (
                            SELECT ROW_NUMBER() OVER () AS id,
                                   ST_MakeValid(ST_Buffer(geom, 0.17), 'method=structure') AS geom
                            FROM (
                                SELECT UNNEST(ST_ClusterWithin(geom, 0.35)) AS geom
                                FROM (
                                    SELECT geom
                                    FROM public.buildings_splitted
                                ) buildings
                            ) block_clusters
                        );
        
                        /*
                         In the following, the shape indicators (like area, perimeter...) are computed
                         */
                        DROP TABLE IF EXISTS convex_hulls;
                        CREATE TEMP TABLE convex_hulls AS
                        (
                            SELECT id,
                                   ST_ConvexHull(geom) AS convex_hull
                            FROM public.buildings_with_features
                        );
        
                        DROP TABLE IF EXISTS footprint_area;
                        CREATE TEMP TABLE footprint_area AS
                        (
                            SELECT id,
                                   ST_Area(geom) AS footprint_area
                            FROM public.buildings_with_features
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
                                SELECT id, angle, ST_Envelope(ST_Rotate(geom, angle)) AS envelope
                                FROM segments
                            ),
                            selectedboundingbox AS
                            (
                                SELECT DISTINCT ON (id) id, angle, envelope, ST_Area(envelope) AS min_area
                                FROM envelopes
                                ORDER BY id, ST_Area(envelope) ASC
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
                                                FROM public.buildings_with_features ia
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
                            FROM public.buildings_with_features a
                        );
        
                        DROP TABLE IF EXISTS building_level_features;
                        CREATE TEMP TABLE building_level_features AS
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
                                SELECT * FROM public.buildings_with_features
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
        
                        /*
                         Compute building-level features interacting with blocks
                         */
        
                        /*
                         Create all blocks that belong to the buildings of interest.
                         We have to consider all buildings in the region here.
                         => if building A is in graph, but its adjacent buildings B is not, we would get wrong block-level
                         features if we would only consider buildings in the graph.
                         */
                        DROP TABLE IF EXISTS blocks_w_duplicated;
                        CREATE TEMP TABLE blocks_w_duplicated AS
                        (
                            SELECT  ROW_NUMBER() OVER() AS entry_id,
                                    block_clusters_w_buffer.id AS block_id,
                                    block_clusters_w_buffer.geom AS geom
                            FROM public.block_clusters_w_buffer block_clusters_w_buffer
                            JOIN (
                                SELECT *
                                FROM public.buildings_with_features
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
                                FROM public.buildings_splitted
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
                                FROM public.buildings_with_features
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
        
                        /*
                         Compute block-level features interacting with buildings
                         */
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
                                FROM public.buildings_with_features
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
        
                        /*
                         Compute block-level features
                         */
                        DROP TABLE IF EXISTS convex_hulls_blocks;
                        CREATE TEMP TABLE convex_hulls_blocks AS
                        (
                            SELECT id,
                                   ST_ConvexHull(geom) AS convex_hull
                            FROM blocks
                        );
        
                        DROP TABLE IF EXISTS footprint_area_blocks;
                        CREATE TEMP TABLE footprint_area_blocks AS
                        (
                            SELECT id,
                                   ST_Area(geom) AS footprint_area
                            FROM blocks
                        );
        
                        DROP TABLE IF EXISTS bounding_box_aux_blocks;
                        CREATE TEMP TABLE bounding_box_aux_blocks AS (
                            WITH segments AS
                            (
                                SELECT DISTINCT id, ST_Azimuth(sp, ep)::NUMERIC % (0.5 * pi())::NUMERIC AS angle, geom
                                FROM (
                                    SELECT id,
                                       ST_PointN(geom, generate_series(1, ST_NPoints(geom)-1)) AS sp,
                                       ST_PointN(geom, generate_series(2, ST_NPoints(geom)  )) AS ep, geom
                                    FROM (
                                        SELECT id, ST_ExteriorRing(convex_hull) AS geom
                                        FROM convex_hulls_blocks
                                    ) AS ls
                                ) AS seg
                            ),
                            envelopes AS
                            (
                                SELECT id, angle, ST_Envelope(ST_Rotate(geom, angle)) AS envelope
                                FROM segments
                            ),
                            selectedboundingbox AS
                            (
                                SELECT DISTINCT ON (id) id, angle, envelope, ST_Area(envelope) AS min_area
                                FROM envelopes
                                ORDER BY id, ST_Area(envelope) ASC
                            )
                            SELECT id,
                                   ST_Rotate(envelope, -angle) AS boundingbox
                            FROM selectedboundingbox
                        );
        
                        DROP TABLE IF EXISTS exterior_ring_rectangle_blocks;
                        CREATE TEMP TABLE exterior_ring_rectangle_blocks AS
                        (
                            SELECT id,
                                   ST_ExteriorRing(boundingbox) AS exterior_ring_rectangle
                            FROM bounding_box_aux_blocks
                        );
        
                        DROP TABLE IF EXISTS angles_blocks;
                        CREATE TEMP TABLE angles_blocks AS
                        (
                            SELECT  id,
                                    ST_PointN(exterior_ring_rectangle,1) AS angle_1,
                                    ST_PointN(exterior_ring_rectangle,2) AS angle_2,
                                    ST_PointN(exterior_ring_rectangle,3) AS angle_3,
                                    ST_PointN(exterior_ring_rectangle,4) AS angle_4
                            FROM exterior_ring_rectangle_blocks
                        );
        
                        DROP TABLE IF EXISTS length_axis_blocks;
                        CREATE TEMP TABLE length_axis_blocks AS
                        (
                            SELECT  id,
                                    ST_Distance(angle_1, angle_4) AS length_axis_1_to_4,
                                    ST_Distance(angle_1, angle_2) AS length_axis_1_to_2
                            FROM angles_blocks
                        );
        
                        DROP TABLE IF EXISTS corners_blocks;
                        CREATE TEMP TABLE corners_blocks AS
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
                                SELECT * FROM convex_hulls_blocks
                            ) ch
                            USING (id)
                            JOIN (
                                SELECT * FROM footprint_area_blocks
                            ) ar
                            USING (id)
                            JOIN (
                                SELECT * FROM angles_blocks
                            ) ang
                            USING (id)
                            JOIN (
                                SELECT * FROM length_axis_blocks
                            ) lenax
                            USING (id)
                            JOIN (
                                SELECT * FROM corners_blocks
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
        
        
                        /*
                         Compute land use class from CLC.
                         */
                        DROP TABLE IF EXISTS clc_category;
                        CREATE TEMP TABLE clc_category AS (
                            WITH spatial_join AS (
                                SELECT *
                                FROM (
                                    SELECT a.id,
                                           c.*,
                                           ST_Area(ST_Intersection(a.geom, b.geom)) as intersection_area
                                    FROM (
                                        SELECT *
                                        FROM public.buildings_with_features
                                    ) a
                                    JOIN (
                                        SELECT *
                                        FROM public.clc
                                        /*
                                         Do not consider these two land use types as they lead to bad performance
                                         and are not relevant for building functions
                                         */
                                        WHERE NOT clc_code = ANY(ARRAY[511, 211])
                                    ) b
                                    ON ST_Intersects(a.geom, b.geom)
                                    JOIN (
                                        SELECT *
                                        FROM public.clc_matches
                                    ) c
                                    ON b.clc_code = c.clc_code
                                ) oa
                            ),
                            largest_intersection AS (
                                SELECT id, MAX(intersection_area) AS max_intersection_area
                                FROM spatial_join
                                GROUP BY id
                            ),
                            matched AS (
                                SELECT a.*
                                FROM (
                                    SELECT *
                                    FROM spatial_join
                                ) a
                                JOIN (
                                    SELECT *
                                    FROM largest_intersection
                                ) b
                                ON a.id = b.id AND a.intersection_area = b.max_intersection_area
                            )
                            SELECT  id,
                                    CASE
                                        /*
                                         Buildings that were not assigned to one of the relevant land cover classes are
                                         assigned to class ''agricultural''.
                                         */
                                        WHEN b.clc IS NULL THEN 'agricultural_areas'
                                        ELSE b.clc
                                    END AS land_cover
                            FROM (
                                SELECT *
                                FROM public.buildings_with_features
                            ) a
                            LEFT JOIN (
                                SELECT *
                                FROM matched
                            ) b
                            USING (id)
                        );
        
        
                        /*
                        Compute land use class from urban atlas
                         */
                        DROP TABLE IF EXISTS urban_atlas_category;
                        CREATE TEMP TABLE urban_atlas_category AS
                        (
                            WITH spatial_join AS (
                                SELECT *
                                FROM (
                                    SELECT a.id,
                                           c.*,
                                           ST_Area(ST_Intersection(a.geom, b.geom)) as intersection_area
                                    FROM (
                                        SELECT * FROM public.buildings_with_features LIMIT (SELECT COUNT(1) FROM public.buildings_with_features)
                                    ) a
                                    JOIN (
                                        SELECT *
                                        FROM public.urban_atlas
                                        WHERE NOT code_2018 = ANY(ARRAY['12210', '12220'])
                                    ) b
                                    ON ST_Intersects(a.geom, b.geom)
                                    JOIN (
                                        SELECT *
                                        FROM public.ua_matches
                                    ) c
                                    ON b.code_2018::INTEGER = c.ua_code
                                ) oa
                            ),
                            largest_intersection AS (
                                SELECT id, MAX(intersection_area) AS max_intersection_area
                                FROM spatial_join
                                GROUP BY id
                            ),
                            matched AS (
                                SELECT a.*
                                FROM (
                                    SELECT *
                                    FROM spatial_join
                                ) a
                                JOIN (
                                    SELECT *
                                    FROM largest_intersection
                                ) b
                                ON a.id = b.id AND a.intersection_area = b.max_intersection_area
                            )
                            SELECT  id,
                                    ob.ua AS land_cover_ua_clc,
                                    CASE
                                        WHEN ob.ua IS NULL THEN 0
                                        ELSE 1
                                    END AS ua_coverage
                            FROM (
                                SELECT *
                                FROM public.buildings_with_features
                            ) a
                            LEFT JOIN (
                                SELECT *
                                FROM matched
                            ) ob
                            USING (id)
                        );
        
                        /*
                         Aggregate the results from both land cover maps.
                         */
                        DROP TABLE IF EXISTS land_cover_category;
                        CREATE TEMP TABLE land_cover_category AS (
                            SELECT  id,
                                    land_cover,
                                    ua_coverage,
                                    CASE
                                        WHEN land_cover_ua_clc IS NULL THEN land_cover
                                        ELSE land_cover_ua_clc
                                    END AS land_cover_ua_clc
                            FROM (
                                SELECT *
                                FROM urban_atlas_category
                            ) a
                            JOIN (
                                SELECT *
                                FROM clc_category
                            ) b
                            USING (id)
                        );
        
                        /*
                         Create table that contains all node features.
                         */
                        DROP TABLE IF EXISTS all_node_features;
                        CREATE TEMP TABLE all_node_features AS
                        (
                            SELECT *
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
                                SELECT id, degurba, country_code FROM public.buildings_with_features
                            ) f
                            USING (id)
                        );
        
                        DROP TABLE IF EXISTS all_node_features_with_labels;
                        CREATE TEMP TABLE all_node_features_with_labels AS
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
                            FROM all_node_features a
                            LEFT JOIN buildings_with_labels b
                            USING (id)
                        );
        
                        INSERT INTO public.nodes_preliminary (id_region, country, center_building_id, building_id, node_id, footprint_area, perimeter, phi, longest_axis_length, elongation, convexity, orientation, corners, shared_wall_length, count_touches, block_id, block_length, av_block_footprint_area, std_block_footprint_area, block_total_footprint_area, block_perimeter, block_longest_axis_length, block_elongation, block_convexity, block_orientation, block_corners, land_cover, ua_coverage, land_cover_ua_clc, degurba, numerical_label)
                        SELECT 1,
                               country_code AS country,
                               center_building_id, id, node_id, footprint_area, perimeter, phi, longest_axis_length, elongation, convexity, orientation, corners, shared_wall_length, count_touches, block_id, block_length, av_block_footprint_area, std_block_footprint_area, block_total_footprint_area, block_perimeter, block_longest_axis_length, block_elongation, block_convexity, block_orientation, block_corners, land_cover, ua_coverage, land_cover_ua_clc, degurba, numerical_label
                        FROM (
                            SELECT center_building_id,
                                   building_id AS id,
                                   node_id
                            FROM public.graph_nodes
                        ) a
                        JOIN all_node_features_with_labels b
                        USING (id)
                        ORDER BY center_building_id, node_id;
        
                        INSERT INTO public.building_geoms (id_region, id, osm_id, geom)
                        SELECT 1,
                               id,
                               osm_id,
                               geom
                        FROM public.buildings_with_features;
        
                        DROP TABLE IF EXISTS public.buildings_with_features;
                        DROP TABLE IF EXISTS convex_hulls;
                        DROP TABLE IF EXISTS footprint_area;
                        DROP TABLE IF EXISTS bounding_box_aux;
                        DROP TABLE IF EXISTS exterior_ring_rectangle;
                        DROP TABLE IF EXISTS angles;
                        DROP TABLE IF EXISTS length_axis;
                        DROP TABLE IF EXISTS corners;
                        DROP TABLE IF EXISTS building_level_features;
                        DROP TABLE IF EXISTS blocks_w_duplicated;
                        DROP TABLE IF EXISTS blocks;
                        DROP TABLE IF EXISTS all_buildings_within_blocks;
                        DROP TABLE IF EXISTS building_level_features_interacting_blocks;
                        DROP TABLE IF EXISTS block_level_features_interacting_buildings;
                        DROP TABLE IF EXISTS convex_hulls_blocks;
                        DROP TABLE IF EXISTS footprint_area_blocks;
                        DROP TABLE IF EXISTS bounding_box_aux_blocks;
                        DROP TABLE IF EXISTS exterior_ring_rectangle_blocks;
                        DROP TABLE IF EXISTS angles_blocks;
                        DROP TABLE IF EXISTS length_axis_blocks;
                        DROP TABLE IF EXISTS corners_blocks;
                        DROP TABLE IF EXISTS block_level_features_for_blocks;
                        DROP TABLE IF EXISTS block_level_features;
                        DROP TABLE IF EXISTS clc_category;
                        DROP TABLE IF EXISTS urban_atlas_category;
                        DROP TABLE IF EXISTS land_cover_category;
                        DROP TABLE IF EXISTS all_node_features;
                        DROP TABLE IF EXISTS all_node_features_with_labels;
        
                        /*
                        Create new node IDs because some nodes are lost during feature computation.
                        */
                        DROP TABLE IF EXISTS nodes_preliminary_new;
                        CREATE TEMP TABLE nodes_preliminary_new AS
                        (
                            SELECT *,
                                   ROW_NUMBER() OVER (PARTITION BY center_building_id ORDER BY node_id) - 1 AS node_id_new
                            FROM public.nodes_preliminary
                        );
        
                        DROP TABLE IF EXISTS public.nodes_preliminary;
                        CREATE TABLE public.nodes_preliminary AS (
                            SELECT id_region, country, center_building_id, building_id, node_id_new AS node_id, footprint_area, perimeter, phi, longest_axis_length, elongation, convexity, orientation, corners, shared_wall_length, count_touches, block_id, block_length, av_block_footprint_area, std_block_footprint_area, block_total_footprint_area, block_perimeter, block_longest_axis_length, block_elongation, block_convexity, block_orientation, block_corners, land_cover, ua_coverage, land_cover_ua_clc, degurba, numerical_label
                            FROM nodes_preliminary_new
                        );
                END;
        $$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)
    query = f'''
            SELECT public.compute_node_features();

            DROP FUNCTION IF EXISTS public.compute_node_features;
        '''
    db.execute_statement(query)