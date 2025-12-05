#!/bin/bash
cd frontend && npm install && npm run build && cd ..
cd backend && pip install -r requirements.txt 
python main.py --host 0.0.0.0 --port 8000