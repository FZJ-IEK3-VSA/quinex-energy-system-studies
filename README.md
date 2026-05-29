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

### Run locally

From the project root:

```bash
streamlit run streamlit/streamlit_app.py
```

Open in your browser:

- `http://127.0.0.1:8501`

### Run for network access

```bash
streamlit run streamlit/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

Then open it via the host IP, for example `http://<your-ip>:8501`.

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
