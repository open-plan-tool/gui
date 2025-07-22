#!/usr/local/bin/python
python manage.py compilemessages
python manage.py makemigrations users projects dashboard && \
python manage.py migrate && \
python manage.py update_assettype && \
python /src/manage.py update_valuetype && \
python manage.py loaddata 'fixtures/multivector_fixture.json' && \
python manage.py collectstatic --no-input && \
echo 'Completed initial setup of open-plan GUI app successfully!!'