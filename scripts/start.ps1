$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m streamlit run app.py --server.address 127.0.0.1
