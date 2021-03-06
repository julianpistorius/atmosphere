#!/usr/bin/env bash

# BEWARE! This script:
# - Drops two databases
# - Deletes a user
# - Overwrites your variables.ini, local.py, secrets.py, etc.
# - Forcibly updates packages in your virtual environment
#
# Read it.

# Usage: ./run_tests_like_travis.sh [cyverse|jetstream]

set -e
set -x

DISTRIBUTION=${1:-cyverse}
VENV_PATH=/opt/env/atmo-test
ATMO_PATH=/opt/dev/atmosphere
SUDO_POSTGRES='sudo -u postgres'  # Leave empty if sudo not required to run dropdb, createdb & psql
PIP_TOOLS_VERSION=1.9.0

cd $ATMO_PATH
if [ ! -d "$VENV_PATH" ]; then
    virtualenv "$VENV_PATH";
fi
source $VENV_PATH/bin/activate

pip install -U pip setuptools pip-tools=="$PIP_TOOLS_VERSION"
pip-sync dev_requirements.txt

${SUDO_POSTGRES} dropdb --if-exists atmosphere_db
${SUDO_POSTGRES} dropdb --if-exists test_atmosphere_db
${SUDO_POSTGRES} dropuser --if-exists atmosphere_db_user
${SUDO_POSTGRES} psql -c "CREATE USER atmosphere_db_user WITH PASSWORD 'atmosphere_db_pass' CREATEDB;" --dbname=postgres
${SUDO_POSTGRES} createdb --owner=atmosphere_db_user atmosphere_db

cp ./variables.ini.dist ./variables.ini
patch variables.ini variables_for_testing_${DISTRIBUTION}.ini.patch
./configure
./travis/check_properly_generated_requirements.sh

python manage.py test --keepdb
rm -f rerun_failing.features
python manage.py behave --keepdb --tags ~@skip-if-${DISTRIBUTION} --format rerun --outfile rerun_failing.features
if [ -f "rerun_failing.features" ]; then python manage.py behave --logging-level DEBUG --capture-stderr --capture --verbosity 3 --keepdb @rerun_failing.features; fi

python manage.py makemigrations --dry-run --check
