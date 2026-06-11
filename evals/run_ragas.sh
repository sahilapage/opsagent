#!/bin/bash
source ~/eval_venv/bin/activate
cd ~/Desktop/\$\$\$\$/opsagent
python3 evals/rag_eval.py
deactivate
