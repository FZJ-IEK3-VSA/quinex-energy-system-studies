# Automated Extraction of Techno-Economic Data from 76,000 Energy System Studies

This repository processes and analyzes more than 76,000 publications from the large-scale energy systems literature with Quinex. It includes the collection of publications from Scopus and WOS, the processing of them using Quinex and the needed postprocessing steps afterwards.
Furthermore, it provides an interactive Dashboard to inspect mapped entities, properties, metadata, and derived plots.

## Getting Started

Run from the project root to create and install the environment:

```bash
mamba env create -f environment.yml
conda activate quinex_application
pip install -e .
```

## Starting the Dashboard

Create a `.env` file in the project root and add a password:

```bash
STREAMLIT_APP_PASSWORD=your_secure_password
```

Start the dashboard locally:

```bash
streamlit run streamlit/streamlit_app.py
```

Open http://127.0.0.1:8501 in your browser and enter the password when prompted.
