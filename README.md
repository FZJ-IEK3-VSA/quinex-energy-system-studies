# quinex_application

Application of Quinex for scientific paper data analysis, including postprocessing,
visualization, and an interactive Streamlit dashboard.

## Contents

- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Setup](#setup)
- [Run the Streamlit Dashboard](#run-the-streamlit-dashboard)
- [Run the Notebooks](#run-the-notebooks)
- [Troubleshooting](#troubleshooting)

## Project Structure

```text
.
|-- environment.yml
|-- pyproject.toml
|-- data/
|-- notebooks/
|-- quinex_application/
|   |-- postprocessing/
|   |-- quinex_processing/
|   `-- visualisation/
`-- streamlit/
    |-- streamlit_app.py
    |-- components/
    |-- utils/
    `-- duckdb_data/
```

## Requirements

- Mamba or Conda
- Python 3.10 (see `environment.yml`)

## Setup

Run from the project root:

```bash
mamba env create -f environment.yml
conda activate quinex_application
pip install -e .
```

## Run the Streamlit Dashboard

### Quick start (for first-time users)

1. Create and activate the environment (see "Setup").
2. Create a `.env` file in the project root and add a password:

```bash
STREAMLIT_APP_PASSWORD=your_secure_password
```

3. Start the dashboard locally:

```bash
streamlit run streamlit/streamlit_app.py
```

4. Open `http://127.0.0.1:8501` in your browser and enter the password when prompted.

To make the dashboard reachable on your local network, run:

```bash
streamlit run streamlit/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```
Then open `http://<host-ip>:8501` from another device on the same network.

### How to use the dashboard (first-time walkthrough)

- Login with the password from step 2. The app blocks further access until authenticated.
- Left column: three tabs to define data mappings:
  - `Entity`: create classes (labels) and add keywords that identify matching records.
  - `Property`: create property classes; optionally set `Unit` and `Year` for conversions/plots.
  - `Metadata`: facet-based filters (author origin, publication year, temporal & spatial scope).
- After defining mappings and filters, use the main tabs to inspect results:
  - `Data`: paginated table with download/export options.
  - `Column Frequency`: frequency counts across mappings.
  - `Temporal Plot` / `Spatial Plot`: visual summaries.

Tips:
- Use short, descriptive class labels and multiple keywords to increase match coverage.
- Use `!` or the "Exclude Keywords" field to prevent unwanted matches.
- If a filter makes the dataset empty, check the available facets in the Filters expander.

If you need more detail on the data pipeline or notebooks, see the `notebooks/` folder.

## Run the Notebooks

The project pipeline is documented in the notebooks under `notebooks/`
(for example `Step0_...` to `Step6_...`).

Recommended order:

1. `Step0_DoiCollection.ipynb`
2. `Step1_QuinexPerforming.ipynb`
3. `Step2_QuinexPostprocessing.ipynb`
4. `Step3_RegexMapping.ipynb`
5. `Step4_MetadataVisualisation.ipynb`
6. `Step5_TemporalVisualisation.ipynb`
7. `Step6_SpatialVisualisation.ipynb`

## Troubleshooting

- Port 8501 already in use:
  `streamlit run streamlit/streamlit_app.py --server.port 8502`
- Empty or missing data in the dashboard:
  check whether `streamlit/duckdb_data/data.duckdb` exists.
