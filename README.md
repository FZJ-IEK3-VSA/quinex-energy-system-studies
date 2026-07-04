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

4. Open `http://127.0.0.1:8501` in your browser and enter the password when prompted.

## Run Dashboard as a systemd service

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