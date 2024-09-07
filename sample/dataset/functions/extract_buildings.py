import sample.db_interaction as db


def extract_buildings():
    query = f'''
        /*
         |---------------------------------------------------------------------------------------------------------------------|
         | Extract nodes (buildings from OSM) and subsample a fraction of them as center nodes
         |---------------------------------------------------------------------------------------------------------------------|
        */

        CREATE OR REPLACE FUNCTION public.extract_buildings(subsample_fraction DOUBLE PRECISION,
                                                            x_min DOUBLE PRECISION,
                                                            x_max DOUBLE PRECISION,
                                                            y_min DOUBLE PRECISION,
                                                            y_max DOUBLE PRECISION)
            RETURNS void AS $$
                BEGIN
                    /*
                    Extract buildings from OSM
                    */
                    DROP TABLE IF EXISTS buildings;
                    CREATE TEMP TABLE buildings AS
                    (
                        SELECT  ROW_NUMBER() OVER() AS id,
                                a.osm_id,
                                a.building AS building_key,
                                a.tags->'house' AS house,
                                ST_Transform(a.way, 3035) AS geom,
                                f.country_code AS country
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
                        ON ST_Within(a.way, d.geom)
                        JOIN (
                            SELECT code AS country_code,
                                   geom
                            FROM public.countries
                        ) f
                        ON ST_Intersects(a.way, f.geom)
                    );

                    /*
                     In some cases, incoherent buildings form one MultiPolygon in OSM.
                     To make the representation consistent, we convert all MultiPolygons to Polygons.
                     */
                    DROP TABLE IF EXISTS buildings_splitted;
                    CREATE TEMP TABLE buildings_splitted AS
                    (
                        SELECT    ROW_NUMBER() OVER() AS id,
                                  osm_id,
                                  building_key,
                                  house,
                                  (ST_Dump(geom)).geom AS geom,
                                  country
                        FROM buildings
                    );

                    CREATE INDEX ON buildings_splitted USING gist(geom);
                    
                    /*
                     Sometimes, there are building polygons within other buildings. We remove them.
                     */
                    DROP TABLE IF EXISTS buildings_without_inner_buildings;
                    CREATE TEMP TABLE buildings_without_inner_buildings AS (
                        SELECT  ROW_NUMBER() OVER() AS id,
                                osm_id,
                                building_key,
                                house,
                                geom,
                                country
                        FROM buildings_splitted
                        WHERE id NOT IN (
                            SELECT a.id
                            FROM (
                                SELECT * FROM buildings_splitted
                            ) a
                            JOIN (
                                SELECT * FROM buildings_splitted
                            ) b
                            ON a.id <> b.id AND ST_Contains(b.geom, a.geom)
                            GROUP BY a.id
                        )
                    );
        
                    CREATE INDEX ON buildings_without_inner_buildings USING gist(geom);

                    /*
                     Remove buildings with duplicate geometries (they cause problems in graphs)
                     */
                    WITH to_keep AS (
                       SELECT MIN(id) AS id
                       FROM buildings_without_inner_buildings
                       GROUP BY geom
                    )
                    DELETE FROM buildings_without_inner_buildings
                    WHERE id NOT IN (
                        SELECT id
                        FROM to_keep
                    );
                    
                    /*
                     Delete polygons with an area of 1 m^2 or below.
                     There are considered erroneous or not relevant for our use case.
                     */
                    DELETE FROM buildings_without_inner_buildings
                    WHERE ST_Area(geom) <= 1;
                    
                    DROP TABLE IF EXISTS buildings;
                    CREATE TEMP TABLE buildings AS (
                        SELECT *
                        FROM buildings_without_inner_buildings
                    );
                    
                    CREATE INDEX ON buildings USING gist(geom);
                    
                    /*
                     Extract the labeled buildings (contain building class) and store the label
                     */
                    DROP TABLE IF EXISTS buildings_with_labels;
                    CREATE TEMP TABLE buildings_with_labels AS
                    (
                        SELECT  a.id,
                                a.building_key,
                                a.house,
                                b.numerical_label
                        FROM (
                            SELECT * FROM buildings
                        ) a
                        JOIN (
                            SELECT *
                            FROM public.osm_type_matches
                            WHERE numerical_label <> 9
                        ) b
                        ON a.building_key = b.building_key
                    );
                    
                    DELETE FROM buildings_with_labels
                    WHERE   /*
                             Terraced houses can also be labeled with `building=house`and additionally `house=terraced/terrace`
                             according to: https://wiki.openstreetmap.org/wiki/Tag:building%3Dterrace
                             */
                            building_key = 'house' AND  (house IS NULL OR
                                                            (NOT house = ANY(ARRAY['terraced', 'terrace'])));
                    
                    PERFORM SETSEED(0.5);
                    
                    /*
                     Subsample of buildings where we create graphs around.
                     */
                    DROP TABLE IF EXISTS buildings_subset;
                    CREATE TEMP TABLE buildings_subset AS
                    (
                        SELECT id
                        FROM buildings_with_labels
                        ORDER BY RANDOM() LIMIT (
                            SELECT COUNT(1)
                            FROM buildings
                        )::DOUBLE PRECISION * subsample_fraction
                    );
                END;
        $$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)