#!/bin/bash
# Force install requests and django despite the environment lock
python3 -m pip install -r requirements.txt --break-system-packages

# Run collectstatic
python3 manage.py collectstatic --noinput --clear

# Database migration (Keep disabled until build passes)
# python3 manage.py migrate

echo "BUILD END"
