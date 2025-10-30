#!/bin/bash
pip install -r requirements.txt
pip uninstall httpx
pip install httpx==0.27.2
python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0