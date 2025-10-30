#!/bin/bash
set -e
cd /home/site/wwwroot
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run pressm_dashboard.py --server.port 8000 --server.address 0.0.0.0