#!/bin/bash
PORT="${PORT:-5000}"
exec gunicorn --bind "0.0.0.0:$PORT" --workers 4 --timeout 120 backend.app:app
