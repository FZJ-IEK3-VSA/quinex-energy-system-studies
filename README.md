# quinex_application

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

Application of Quenix on a set of papers

## Project Organization

```
├── README.md          <- The top-level README for developers using this project.
├── data
│   ├── external       <- Data from third party sources.
│   ├── interim        <- Intermediate data that has been transformed.
│   ├── processed      <- The final, canonical data sets for modeling.
│   └── raw            <- The original, immutable data dump.  
│
├── pyproject.toml     <- Project configuration file with package metadata for 
│                         quenix_application and configuration for tools like black
│
├── environment.yml    <- Reproducible Mamba environment
│
└── quinex_application   <- Source code for use in this project.
    │
    ├── __init__.py                 <- Makes quenix_application a Python module
    │
    ├── levenshtein.py              <- Code to calculate levenshtein distance
    │
    ├── mongo_store.py              <- Code to store results in mongodb
    │
    ├── oeoe_data.py                <- Code to load oeo data
    │
    ├── quinex.py                   <- Code to run Quenix
    │
    ├── scopus_data.py              <- Code to load scopus data
    │
    └── visualiation_metadata.py    <- Code to visualize metadata of papers

```

--------

## Setup (Mamba)

1. Create Environment
```bash
mamba env create -f environment.yml
