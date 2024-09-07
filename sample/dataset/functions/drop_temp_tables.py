import sample.db_interaction as db


def drop_temp_tables():
    """
    Drop temporary tables
    """
    query = f'''
        CREATE OR REPLACE FUNCTION public.drop_temp_tables()
            RETURNS void AS $$
                BEGIN
                    DROP TABLE IF EXISTS buildings;
                    DROP TABLE IF EXISTS buildings_splitted;
                    DROP TABLE IF EXISTS buildings_without_inner_buildings;
                    DROP TABLE IF EXISTS buildings;
                    
                    DROP TABLE IF EXISTS delaunay;
                    DROP TABLE IF EXISTS raw_triangulation;
                    DROP TABLE IF EXISTS buildings_centroids;
                    
                    DROP TABLE IF EXISTS buffer;
                    DROP TABLE IF EXISTS graph_nodes_current;
                    DROP TABLE IF EXISTS graph_nodes_with_count;
                    
                    DROP TABLE IF EXISTS buildings_with_labels;
                    DROP TABLE IF EXISTS buildings_subset;
                    DROP TABLE IF EXISTS nodes;
                    DROP TABLE IF EXISTS nodes_n_hop;
                    DROP TABLE IF EXISTS nodes_circ;
                    DROP TABLE IF EXISTS edges;
                    DROP TABLE IF EXISTS edges_n_hop;
                    DROP TABLE IF EXISTS edges_circ;
                    DROP TABLE IF EXISTS cur_nodes;
                    DROP TABLE IF EXISTS new_cur_nodes;
                    DROP TABLE IF EXISTS cur_nodes;
                    DROP TABLE IF EXISTS nodes_tmp;
                    DROP TABLE IF EXISTS nodes;
                    DROP TABLE IF EXISTS edges_tmp;
                    DROP TABLE IF EXISTS edges;
                    
                    DROP TABLE IF EXISTS buildings_with_features;
                    DROP TABLE IF EXISTS node_features;
                    DROP TABLE IF EXISTS node_features_with_labels_tmp;
                    DROP TABLE IF EXISTS node_features_with_labels;
                    
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
                    DROP TABLE IF EXISTS convex_hulls;
                    DROP TABLE IF EXISTS footprint_area;
                    DROP TABLE IF EXISTS bounding_box_aux;
                    DROP TABLE IF EXISTS exterior_ring_rectangle;
                    DROP TABLE IF EXISTS angles;
                    DROP TABLE IF EXISTS length_axis;
                    DROP TABLE IF EXISTS corners;
                    DROP TABLE IF EXISTS block_level_features_for_blocks;
                    DROP TABLE IF EXISTS block_level_features;
                    
                    DROP TABLE IF EXISTS ua_extract;
                    DROP TABLE IF EXISTS urban_atlas_category;
                    DROP TABLE IF EXISTS clc_extract;
                    DROP TABLE IF EXISTS clc_category;
                    DROP TABLE IF EXISTS land_cover_category;
                    
                    DROP TABLE IF EXISTS degurba_category;
                END;
        $$ LANGUAGE plpgsql;
    '''
    db.execute_statement(query)