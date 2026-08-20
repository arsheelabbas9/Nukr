# fix_build.py
import os

# Updated content with the '--break-system-packages' flag
content = b"""#!/bin/bash
# Force install requests and django despite the environment lock
python3 -m pip install -r requirements.txt --break-system-packages

# Run collectstatic
python3 manage.py collectstatic --noinput --clear

# Database migration (Keep disabled until build passes)
# python3 manage.py migrate

echo "BUILD END"
"""

# Write the file in binary mode (Linux format)
with open("build_files.sh", "wb") as f:
    f.write(content)

print("✅ build_files.sh updated with '--break-system-packages' fix.")