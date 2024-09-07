node_features_sequential_id_n_hop = f'''          
    DROP TABLE IF EXISTS public.node_features_sequential_id;
    CREATE TABLE public.node_features_sequential_id AS (
        SELECT  footprint_area,                                                                          
                perimeter,                                                                               
                phi,                                                                                     
                longest_axis_length,                                                                     
                elongation,                                                                              
                convexity,                                                                               
                orientation,                                                                            
                corners,                                                                                 
                shared_wall_length,                                                                      
                count_touches,                                                                           
                block_length,                                                                            
                av_block_footprint_area,                                                                 
                std_block_footprint_area,                                                                
                block_total_footprint_area,                                                              
                block_perimeter,                                                                         
                block_longest_axis_length,                                                               
                block_elongation,                                                                        
                block_convexity,                                                                         
                block_orientation,                                                                       
                block_corners,                                                                           
                ua_coverage,                                                                             
                land_cover_ua_clc,                                                                       
                degurba,                                                                                 
                country,
                osm_id,                                                                                                                                                                 
                center_mask,
                hops,
                lon,
                lat,                                                                                                                                                                                                                                                                                                                       
                id,
                numerical_label,
                ROW_NUMBER() OVER() - 1 AS new_id
        FROM (
            SELECT *
            FROM public.node_features_with_labels_nhop
            ORDER BY id
        ) a
    );
'''

node_features_sequential_id_circ = f'''
    DROP TABLE IF EXISTS public.node_features_sequential_id;
    CREATE TABLE public.node_features_sequential_id AS (
        WITH new_id_orig AS (
            SELECT id_orig, ROW_NUMBER() OVER () - 1 AS new_id_orig
            FROM (
                SELECT DISTINCT id_orig
                FROM public.node_features_with_labels_circ
                ORDER BY id_orig
            ) ia
        )
        SELECT  footprint_area,                                                                          
                perimeter,                                                                               
                phi,                                                                                     
                longest_axis_length,                                                                     
                elongation,                                                                              
                convexity,                                                                               
                orientation,                                                                            
                corners,                                                                                 
                shared_wall_length,                                                                      
                count_touches,                                                                           
                block_length,                                                                            
                av_block_footprint_area,                                                                 
                std_block_footprint_area,                                                                
                block_total_footprint_area,                                                              
                block_perimeter,                                                                         
                block_longest_axis_length,                                                               
                block_elongation,                                                                        
                block_convexity,                                                                         
                block_orientation,                                                                       
                block_corners,                                                                           
                ua_coverage,                                                                             
                land_cover_ua_clc,                                                                       
                degurba,                                                                                 
                country,
                osm_id,                                                                                                                                                                 
                center_mask,
                c.new_id_orig AS center_id,
                hop,
                lon,
                lat,                                                                                                                                                                                                                                                                                                                       
                b.new_id_orig AS id_orig,
                id,
                numerical_label,
                ROW_NUMBER() OVER() - 1 AS new_id
        FROM (
            SELECT *
            FROM public.node_features_with_labels_circ
            ORDER BY id
        ) a
        /*
        Buildings can occur multiple times due to overlapping subgraphs
        -> make original IDs (there is one id_orig per physical building) sequential
        */
        JOIN new_id_orig b
        ON a.id_orig = b.id_orig
        JOIN new_id_orig c
        ON a.center_id = c.id_orig
    );
'''

edges_sequential_id_n_hop = f'''
    DROP TABLE IF EXISTS public.edges_sequential_id;
    CREATE TABLE public.edges_sequential_id AS (
        SELECT b.new_id AS start_id,
               c.new_id AS end_id,
               a.distance
        FROM public.edges_nhop a
        JOIN (
            SELECT *
            FROM public.node_features_sequential_id
        ) b
        ON a.start_id = b.id
        JOIN (
            SELECT *
            FROM public.node_features_sequential_id
        ) c
        ON a.end_id = c.id
    );
'''

edges_sequential_id_circ = f'''
    DROP TABLE IF EXISTS public.edges_sequential_id;
    CREATE TABLE public.edges_sequential_id AS (
        SELECT b.new_id AS start_id,
               c.new_id AS end_id,
               a.distance
        FROM public.edges_circ a
        JOIN (
            SELECT *
            FROM public.node_features_sequential_id
        ) b
        ON a.start_id = b.id
        JOIN (
            SELECT *
            FROM public.node_features_sequential_id
        ) c
        ON a.end_id = c.id
    );
'''

drop_tables = f'''
    DROP TABLE IF EXISTS public.node_features_sequential_id;
    DROP TABLE IF EXISTS public.edges_sequential_id;
'''
