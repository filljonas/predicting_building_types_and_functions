"""
 |---------------------------------------------------------------------------------------------------------------------|
 | Names of input features
 |---------------------------------------------------------------------------------------------------------------------|
"""

feature_groups_names = {'Auxiliary cols for graphs': ['graph_id', 'node_id'],
                        'Building-level features': ['footprint_area', 'perimeter', 'phi', 'longest_axis_length',
                                                    'elongation','convexity', 'orientation', 'corners',
                                                    'shared_wall_length', 'count_touches'],
                        'Block-level features': ['block_length', 'av_block_footprint_area', 'std_block_footprint_area',
                                                 'block_total_footprint_area', 'block_perimeter',
                                                 'block_longest_axis_length', 'block_elongation', 'block_convexity',
                                                 'block_orientation', 'block_corners'],
                        'UA coverage': ['ua_coverage'],
                        'Land cover indicators': ['agricultural_areas', 'artificial_non_agricultural_vegetated_areas',
                                                  'continuous_urban_fabric', 'discontinuous_dense_medium_urban_fabric',
                                                  'discontinuous_low_urban_fabric',
                                                  'discontinuous_very_low_urban_fabric', 'forest',
                                                  'industrial_commercial_public_private_units', 'isolated_structures',
                                                  'mine_dump_and_construction_sites',
                                                  'open_spaces_with_little_or_no_vegetation',
                                                  'shrub_and_or_herbaceous_vegetation_associations', 'transport_units',
                                                  'water_bodies', 'wetlands'],
                        'Urbanization indicators': ['city', 'town_or_suburb', 'rural_area'],
                        'Country indicators': ['at', 'be', 'bg', 'ch', 'cy', 'cz', 'de', 'dk', 'ee', 'es', 'fi',
                                               'fr', 'gb', 'gr', 'hr', 'hu', 'ie', 'it', 'lt', 'lu', 'lv', 'mt',
                                               'nl', 'no', 'pl', 'pt', 'ro', 'se', 'si', 'sk']}