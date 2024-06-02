/*
 |---------------------------------------------------------------------------------------------------------------------|
 | SQL-Statements that allow visualizing the dataset in QGIS
 |---------------------------------------------------------------------------------------------------------------------|
*/

/*
 Visualize all center nodes of subgraphs
 */
DROP TABLE IF EXISTS public.centers;
CREATE TABLE public.centers AS (
    WITH grouped AS (
        SELECT graph_id
        FROM public.nodes
        GROUP BY graph_id
    )
    SELECT  oa.graph_id,
            oa.id_region,
            ob.id,
            ST_Centroid(ob.geom)::GEOMETRY(POINT, 3035) AS geom
    FROM (
        SELECT a.graph_id,
               b.center_building_id,
               b.id_region
        FROM grouped a
        JOIN public.nodes b
        USING (graph_id)
        GROUP BY a.graph_id, b.center_building_id, b.id_region
    ) oa
    JOIN (
        SELECT *
        FROM public.building_geoms
    ) ob
    ON oa.id_region = ob.id_region AND oa.center_building_id = ob.id
    ORDER BY graph_id
);

/*
 Visualize all nodes of specific subgraph
 */
DROP TABLE IF EXISTS public.nodes_visualize;
CREATE TABLE public.nodes_visualize AS (
    SELECT  a.*,
            b.geom AS geom
    FROM (
        SELECT *
        FROM public.nodes
    ) a
    JOIN (
        SELECT *
        FROM public.building_geoms
    ) b
    ON a.id_region = b.id_region AND a.building_id = b.id
);

/*
 Visualize all edges of specific subgraph
 */
DROP TABLE IF EXISTS public.edges_visualize;
CREATE TABLE public.edges_visualize AS (
    SELECT  a.graph_id,
            a.id_region,
            a.center_building_id,
            a.start_building_id,
            a.end_building_id,
            a.start_node_id,
            a.end_node_id,
            ST_MakeLine(ST_Centroid(b.geom), ST_Centroid(c.geom)) AS geom,
            a.distance
    FROM (
        SELECT *
        FROM public.edges
    ) a
    JOIN (
        SELECT *
        FROM public.building_geoms
    ) b
    ON a.id_region = b.id_region AND a.start_building_id = b.id
    JOIN (
        SELECT *
        FROM public.building_geoms
    ) c
    ON a.id_region = c.id_region AND a.end_building_id = c.id
);