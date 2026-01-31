#!/bin/bash
# Run from net12/ or pocket_noc/backend/
cd "$(dirname "$0")/../.."
python -m pocket_noc.backend.api 2>/dev/null || python pocket_noc/backend/api.py
