import sample.db_interaction as db


def degurba():
    query = f'''
        /*
         |---------------------------------------------------------------------------------------------------------------------|
         | Compute degurba labels
         |---------------------------------------------------------------------------------------------------------------------|
        */

        CREATE OR REPLACE FUNCTION public.degurba()
            RETURNS void AS $$
                BEGIN
                    DROP TABLE IF EXISTS degurba_category;
                    CREATE TEMP TABLE degurba_category AS
                    (
                        SELECT  ROW_NUMBER() OVER() AS id_new,
                                a.id,
                                b.degurba_label::TEXT AS degurba
                        FROM (
                            SELECT *
                            FROM buildings_with_features
                        ) a
                        LEFT JOIN (
                            SELECT  geom,
                                    degurba_label,
                                    lau_id
                            FROM public.degurba
                        ) b
                        ON ST_Intersects(a.geom, b.geom)
                    );
                    
                    /*
                     Some buildings are not assigned to a DEGURBA region (e.g. they are near a lake).
                     Assume these are rural areas.
                     */
                    UPDATE degurba_category a
                    SET degurba = '3'
                    WHERE degurba IS NULL;
                        
        
                    /*
                     Set DEGURBA label
                     */
                    UPDATE degurba_category
                    SET degurba = 'city'
                    WHERE degurba = '1';
        
                    UPDATE degurba_category
                    SET degurba = 'town_or_suburb'
                    WHERE degurba = '2';
        
                    UPDATE degurba_category
                    SET degurba = 'rural_area'
                    WHERE degurba = '3';
                    
                    /*
                     Since we joined to the DEGURBA and country maps with an intersects-operation, buildings on borders are
                     assigned to multiple DEGURBA or country polygons. We just pick one arbitrary one.
                     */
                    WITH to_keep AS (
                       SELECT MIN(id_new) AS id_new
                       FROM degurba_category
                       GROUP BY id
                    )
                    DELETE FROM degurba_category
                    WHERE id_new NOT IN (
                        SELECT id_new
                        FROM to_keep
                    );
                    
                    ALTER TABLE degurba_category 
                    DROP COLUMN id_new;
                END;
        $$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)