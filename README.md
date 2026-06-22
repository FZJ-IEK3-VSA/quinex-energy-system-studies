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

### Run as a systemd service

To run the dashboard as a persistent systemd service on a Linux VM:

1. Deploy the service file:

```bash
sudo cp streamlit/deployment/dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
```

2. Start the service:

```bash
sudo systemctl start dashboard.service
```

3. Enable auto-start on boot (optional):

```bash
sudo systemctl enable dashboard.service
```

4. Check service status:

```bash
sudo systemctl status dashboard.service
```

5. View logs:

```bash
tail -f streamlit.log
```

The service will be available at `http://<host-ip>:5001`.

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