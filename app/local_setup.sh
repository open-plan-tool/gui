#!/usr/local/bin/python
python manage.py compilemessages
python manage.py makemigrations users projects dashboard && \
python manage.py migrate && \
python manage.py update_assettype && \
python manage.py update_valuetype && \
python manage.py loaddata 'fixtures/multivector_fixture.json' && \
echo yes | python manage.py collectstatic && \
pre-commit install && \
echo 'Completed Setup Successfully!!'
