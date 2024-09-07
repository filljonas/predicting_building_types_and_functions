import sample.db_interaction as db


def land_use():
    query = f'''
        /*
         |---------------------------------------------------------------------------------------------------------------------|
         | Compute land use features
         |---------------------------------------------------------------------------------------------------------------------|
        */

        CREATE OR REPLACE FUNCTION public.land_use()
            RETURNS void AS $$
                BEGIN
                     /*
                     Compute land use class from urban atlas
                     */
                    DROP TABLE IF EXISTS ua_extract;
                    CREATE TEMP TABLE ua_extract AS (
                        SELECT *
                        FROM (
                            SELECT a.code_2018,
                                   a.geom
                            FROM public.urban_atlas a
                            -- Unimportant transport units that lead to bad performance -> exclude them
                            WHERE NOT code_2018 = ANY(ARRAY['12210', '12220'])
                        ) oa
                        WHERE ST_GeometryType(geom) = 'ST_Polygon'
                    );
                    
                    CREATE INDEX ON ua_extract USING gist(geom);
                    
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
                                    SELECT * FROM buildings_with_features LIMIT (SELECT COUNT(1) FROM buildings_with_features)
                                ) a
                                JOIN (
                                    SELECT *
                                    FROM ua_extract
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
                                ob.ua AS land_cover_ua,
                                CASE
                                    WHEN ob.ua IS NULL THEN 0
                                    ELSE 1
                                END AS ua_coverage
                        FROM (
                            SELECT *
                            FROM buildings_with_features
                        ) a
                        LEFT JOIN (
                            SELECT *
                            FROM matched
                        ) ob
                        USING (id)
                    );
                    
                    DROP TABLE IF EXISTS clc_extract;
                    CREATE TEMP TABLE clc_extract AS (
                        SELECT *
                        FROM (
                            SELECT a.clc_code,
                                   a.geom
                            FROM public.clc a
                        ) oa
                        WHERE ST_GeometryType(geom) = 'ST_Polygon'
                    );
                    
                    CREATE INDEX ON clc_extract USING gist(geom);
                    
                    /*
                     Compute land use class from CLC
                     */
                    DROP TABLE IF EXISTS clc_category;
                    CREATE TEMP TABLE clc_category AS (
                        WITH missing_buildings AS (
                            SELECT *
                            FROM buildings_with_features
                            WHERE id IN (SELECT id FROM urban_atlas_category WHERE ua_coverage = 0)
                        ),
                        spatial_join AS (
                            SELECT *
                            FROM (
                                SELECT a.id,
                                       c.*,
                                       ST_Area(ST_Intersection(a.geom, b.geom)) as intersection_area
                                FROM (
                                    SELECT *
                                    FROM missing_buildings
                                ) a
                                JOIN (
                                    SELECT *
                                    FROM clc_extract
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
                                b.clc AS land_cover_clc
                        FROM (
                            SELECT *
                            FROM missing_buildings
                        ) a
                        LEFT JOIN (
                            SELECT *
                            FROM matched
                        ) b
                        USING (id)
                    );

                    /*
                     Aggregate the results from both land cover maps
                     */
                    DROP TABLE IF EXISTS land_cover_category;
                    CREATE TEMP TABLE land_cover_category AS (
                        SELECT  id,
                                ua_coverage,
                                CASE
                                    WHEN land_cover_ua IS NULL THEN land_cover_clc
                                    ELSE land_cover_ua
                                END AS land_cover_ua_clc
                        FROM (
                            SELECT *
                            FROM urban_atlas_category
                        ) a
                        LEFT JOIN (
                            SELECT *
                            FROM clc_category
                        ) b
                        USING (id)
                    );
                    
                    /*
                    Spitzbergen is not covered by CLC
                    => set missing buildings to 'discontinuous_very_low_urban_fabric'
                    */
                    UPDATE land_cover_category
                    SET land_cover_ua_clc = 'discontinuous_very_low_urban_fabric'
                    WHERE land_cover_ua_clc IS NULL;
                END;
        $$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)