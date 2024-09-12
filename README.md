# Predicting Building Types and Functions at Transnational Scale

## Aim of this repository

The repository contains the code from the paper *Predicting Building Types and Functions at Transnational Scale*. First, we provide an instruction for importing the required datasets into a PostgreSQL database. Second, we provide scripts to perform feature engineering and to build a graph-structured building dataset. Third, we provide code to train GNN/ML models on this dataset with *PyTorch Geometric*.

Execution for smaller extracts (like single cities) is straightforward. Execution for larger extracts (like the European pan-European one from the paper) is also possible, but comes with rather high computational costs.

## Installation

### Setup virtual Environment

This repository uses pip for package management. First, create a virtual environment:

`python3 -m venv venv`

Activate virtual environment on Windows:

`venv\Scripts\Activate.ps1`

Activate virtual environment on Linux/MacOS:

`source venv/bin/activate`

Install requirements:

`pip install -r requirements.txt`

### Install PyTorch

CPU version:

`pip3 install torch==2.3.1`

CUDA version:

`pip3 install torch==2.3.1 --index-url https://download.pytorch.org/whl/cu121`

### Install PyTorch Geometric

Dependencies (CPU version):

`pip install pyg_lib torch_scatter torch_sparse torch_cluster torch_spline_conv -f https://data.pyg.org/whl/torch-2.3.0+cpu.html`

Dependencies (CUDA version):

`pip install pyg_lib torch_scatter torch_sparse torch_cluster torch_spline_conv -f https://data.pyg.org/whl/torch-2.3.0+cu121.html`

Library:

`pip install torch_geometric`

## Import datasets to PostgreSQL

The raw data from input datasets (like *OpenStreetMap*) is imported into a PostgreSQL database for preprocessing. In the following, we provide an instruction for importing the datasets. The DEGURBA and country borders datasets are included in this repository. The OSM and land use datasets are not included due to space constraints, we rather provide downloading instructions.

### Import OpenStreetMap data to PostgreSQL

To import *OpenStreetMap (OSM)* data to PostgreSQL, follow these steps:

- Download OSM data for the desired spatial extract from [Geofabrik](https://download.geofabrik.de/europe/germany/bayern.html).
- Download and install [PostgreSQL](https://www.postgresql.org/download/windows/). Also install *StackBuilder* (it is installed by default together with PostgreSQL).
After the installation wizard finished, launch *StackBuilder* to install PostGIS (Category: Spatial Extensions)
- Download and install [osm2pgsql](https://osm2pgsql.org/doc/install/windows.html). Add an environement variable in order to use the tool in the terminal, as explained [here](https://learnosm.org/en/osm-data/osm2pgsql/).
- Create a database named `osm` in PostgreSQL (e.g. as explained [here](https://learnosm.org/en/osm-data/postgresql/)) and create the extensions `postgis` and `hstore` for this database.
- Run the following command in order to import OSM data into the PostgreSQL database:
    
    ```jsx
    osm2pgsql -c -d osm -U postgres -H localhost --proj=3035 --hstore --password -S <path_to_style_file> <path_to_geofabrik_file>
    ```
    
    - `<path_to_geofabrik_file>`: Path to file downloaded from Geofabrik in .pbf format
    - `<path_to_style_file>`: Path to [default.style](http://default.style) file that can be found in the program folder of *osm2pgsql*
    
    This leads to the following tables being created in the *public* PostgreSQL schema:
    
    - `planet_osm_point`
    - `planet_osm_line`
    - `planet_osm_polygon`
    - `planet_osm_roads`

### Import Land use data to PostgreSQL

**Urban Atlas (UA):**

Land use data from the *Urban Atlas* is available in many large cities and urban areas in Europe. To import UA data to PostgreSQL, follow these steps:

- Download the [Urban Atlas](https://land.copernicus.eu/en/products/urban-atlas/urban-atlas-2018) dataset for the desired area(s). One will obtain a *GeoPackage (GPKG)* file for each area.
- To import a GeoPackage file into PostgreSQL, download and install [QGIS](https://qgis.org/en/site/forusers/download.html). This will also install the *OSGeo4W Shell* on the system. Open the shell and execute the following command:
    
    ```jsx
    ogr2ogr -progress -f "PostgreSQL" PG:"host=localhost  dbname=osm  user=postgres password=<your_superuser_password>" -nln public.urban_atlas <path_to_gpkg>
    ```
    

**Corine Land Cover (CLC):**

In case one wants to include areas that are not covered by the Urban Atlas, download [CLC](https://land.copernicus.eu/en/products/corine-land-cover/clc2018).

For cases where CLC is not needed, we provide a dummy CLC extract *clc.gpkg* in `sample/db_setup` (as the follow-up scripts require that a CLC database table exists).

Regardless of whether one uses the dummy or the original CLC file, it is required to import it into PostgreSQL with *OSGeo4W Shell*:

```jsx
ogr2ogr -progress -f "PostgreSQL" PG:"host=localhost  dbname=osm  user=postgres password=<your_superuser_password>" -nln public.clc <path_to_gpkg>
```

### Import Degree of Urbanization data (DEGURBA) to PostgreSQL

The repository comes with a GeoPackage file named *degurba.gpkg* (found in folder `sample/db_setup`) which contains the DEGURBA dataset for the whole of Europe.

It can be imported into PostgreSQL via the following command in *OSGeo4W Shell*:

```jsx
ogr2ogr -progress -f "PostgreSQL" PG:"host=localhost  dbname=osm  user=postgres password=<your_superuser_password>" -nln public.degurba <path_to_gpkg>
```

### Country borders

The repository comes with a GeoPackage file named *countries.gpkg* (found in folder `sample/db_setup`) which contains the OSM country borders for the whole of Europe.

It can be imported into PostgreSQL via the following command in *OSGeo4W Shell*:

```jsx
ogr2ogr -progress -f "PostgreSQL" PG:"host=localhost  dbname=osm  user=postgres password=<your_superuser_password>" -nln public.countries -nlt MULTIPOLYGON <path_to_gpkg>
```

### Import mapping tables to PostgreSQL

This study uses a mapping from OSM building classes and UA/CLC land use classes to custom classes. In the folder `sample/db_setup` we provide a script `csv_to_sql.py` that loads the CSV-files with the mappings into PostgreSQL.

**This script needs to be executed for the rest of the code to run.**

## Feature engineering

To perform feature engineering and data preprocessing, execute the script `dataset_pipeline.py` in the folder `sample/dataset`. It executes a couple of SQL-statements to:

- Compute node features for all OSM buildings
- Arrange buildings/nodes as a graph structure

The result from these steps is saved in the form of PostgreSQL tables.

The script also creates a graph dataset suitable for *PyTorch Geometric* in *.pt*-format that is saved in the folders `sample/dataset/circ` or `sample/dataset/circ` (depending on `type` which is described in the listing below).

At the top of the script, one can change the following variables:

- `x_min, x_max, y_min, y_max:` Define the coordinates of the geographic extract one wants to consider. Note that all datasets must be available for the entire extract.
- `type`: Localized subgraph generation method. `circ`: distance-based subgraphs created with circular buffers, `n_hop`: subgraphs based on N hops in the graph
- `buildings_in_graph:` Setting that only applies to the `circ` method. Every graph in the dataset roughly consists of the same number of buildings. Set the minimum number of buildings in a graph. For example, if set to 20, all graphs will contain at least 20 nodes.
- `subsample_fraction:` In our approach, graphs are created around labeled OSM buildings. Depending on the size of the extract, one might not want to create graphs around all labeled buildings. Set this variable to a fraction in `(0, 1)` to only create graphs around a random subset of the labeled nodes.
- `hops`: Setting that only applies to the `n_hop` method. Number of hops for the subgraphs.

## Training GNN/Machine Learning models

After the *.pt* dataset file was created, one can train a machine learning classifier. For this purpose, we provide the script `train_classifier.py` in the folder `sample/training`.

Run it on Windows via:

`python .\sample\training\train_classifier.py <model_type>`

Run it on Linux/MacOS via:

`python3 ./sample/training/train_classifier.py <model_type>`

The parameter `<model_type>` changes the classifier model used for training. We support the following model types:

- `dt` (Decision tree)
- `rf` (Random forest)
- `fcnn` (Fully connected neural network)
- `gcn` (Graph convolutional network)
- `sage` (GraphSAGE)
- `gat` (Graph attention network)
- `transformer` (Graph transformer)

The script will:

- Split the dataset into a training, validation and test set
- Remove some of the labels from validation and test set as described in Section 5.1.3. in the paper
- Train a GNN or classical ML model

In the folder `sample/training/config` one finds JSON-files to control the hyperparameter of the models.

The file `sample/training/config/general.json` is particularly important as it is used to set the localized subgraph generation method. One can change the following parameters:

- `subgraph_type`: Must correspond to the `type` used in the previous step. If a dataset was created for both subgraph generation methods, any `type` can be used.
- `hops`: Setting that only applies to the `n_hop` method. Supported numbers of hops: 2 and 4. But has to be less than or equal to the number of hops used when creating the dataset.
- `only_center_labels`: Determines whether only center node labels or all labels are considered when computing the loss.