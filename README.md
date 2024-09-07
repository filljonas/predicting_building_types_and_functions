# Predicting Building Types and Functions at Transnational Scale

## Aim of this repository

The repository allows reproducing the feature engineering and ML model training from the paper *Predicting Building Types and Functions at Transnational Scale* First, we provide an instruction for importing the required datasets into a PostgreSQL database. Second, we provide scripts to perform feature engineering and to build a graph-structured building dataset. Third, we provide code to train GNN/ML models on this dataset with *PyTorch Geometric*.

The scripts can be easily executed for smaller extracts (like a single city). For larger extracts or European scope, specialized hardware and/or additional parallelization techniques may be necessary.

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

The raw data from input datasets (like *OpenStreetMap*) is imported into a PostgreSQL database for preprocessing. In the following, we provide an instruction for importing the datasets.

### Import OpenStreetMap data to PostgreSQL

To import *OpenStreetMap (OSM)* data to PostgreSQL, follow these steps:

- Download OSM data for your desired spatial extract from [Geofabrik](https://download.geofabrik.de/europe/germany/bayern.html).
- Download and install [PostgreSQL](https://www.postgresql.org/download/windows/) for your operating system. Make sure to also install *StackBuilder* (it is installed by default together with PostgreSQL).
After the installation wizard finished, launch *StackBuilder* to install PostGIS (Category: Spatial Extensions)
- Download and install [osm2pgsql](https://osm2pgsql.org/doc/install/windows.html) for your operating system. Add an environement variable in order to use the tool in the terminal, as explained [here](https://learnosm.org/en/osm-data/osm2pgsql/).
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

- Download the [Urban Atlas](https://land.copernicus.eu/en/products/urban-atlas/urban-atlas-2018) dataset for the desired area(s). You will obtain a *GeoPackage (GPKG)* file for each area.
- To import a GeoPackage file into PostgreSQL, download and install [QGIS](https://qgis.org/en/site/forusers/download.html). This will also install the *OSGeo4W Shell* on your system. Open the shell and execute the following command:
    
    ```jsx
    ogr2ogr -progress -f "PostgreSQL" PG:"host=localhost  dbname=osm  user=postgres password=<your_superuser_password>" -nln public.urban_atlas <path_to_gpkg>
    ```
    

**Corine Land Cover (CLC):**

In case you want to include areas that are not covered by the Urban Atlas, you can download [CLC](https://land.copernicus.eu/en/products/corine-land-cover/clc2018).

In the follow-up Python scripts, Urban Atlas and CLC are merged. So you will need at least a dummy CLC extract in order for the code to work. CLC can however only be downloaded for the whole of Europe, so it is computationally quite expensive to work with the whole dataset.

For cases were CLC is not needed, we provided a dummy CLC extract *clc.gpkg* in `sample/db_setup`. Just continue with this dummy file and only download the (smaller) UA extracts. It will make handling the data a lot easier.

Regardless of whether you use our dummy or an own CLC file, you need to import it into PostgreSQL with *OSGeo4W Shell*:

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

To perform feature engineering and data preprocessing, execute the script `dataset_pipeline.py` in the folder `sample/dataset`. It executes a couple of SQL-scripts to:

- Compute node features for all OSM buildings
- Arrange buildings/nodes as a graph structure

<aside>
💡 The result from these steps is saved in the form of PostgreSQL tables.
</aside>

The script also creates a graph dataset suitable for *PyTorch Geometric* in the folder `sample/dataset/pyg_ds`.

At the top of the script, you can change the following variables:

- `x_min, x_max, y_min, y_max:` Define the coordinates of your geographic extract you want to consider. Note that all datasets you downloaded/imported must be available for the entire extract.
- `type`: Localized subgraph generation method. `circ`: distance-based subgraphs created with circular buffers, `n_hop`: subgraphs based on N hops in the graph
- `buildings_in_graph:` Setting that applies to the `circ` method. Every graph in the dataset roughly consists of the same number of buildings. Set the minimum number of buildings in a graph. For example, if you set this variable to 20, all graphs will contain at least 20 nodes. Some will contain a bit more (depending on the circular buffers around buildings), but there will not be many graphs with significantly more than 20 nodes.
- `subsample_fraction:` In our approach, graphs are created around labeled OSM buildings. Depending on the size of your extract, you might not want to create graphs around all labeled buildings. Set this variable to a fraction in `(0, 1)` to only create graphs around a random subset of the labeled nodes.
- `num_layers`: Setting that applied to the `n_hop` method. Number of hops the created dataset has.

## Training GNN/Machine Learning models

After you created a dataset, you can train a machine learning classifier on this dataset. For this purpose, we provide the script `train_classifier.py` in the folder `sample/training`.

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

In the folder `sample/training/config` you find JSON-files to control the hyperparameter of the models (and general parameters related to the creation of localized subgraphs).