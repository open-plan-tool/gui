#!/usr/local/bin/python
python manage.py compilemessages
python manage.py makemigrations users projects dashboard && \
python manage.py migrate && \
python manage.py update_assettype && \
python manage.py loaddata "fixtures/valuetypes.json" "fixtures/assettypes.json" "fixtures/test_user.json" "fixtures/example_project.json" && \
python manage.py collectstatic --no-input && \
echo 'Completed initial setup of open-plan GUI app successfully!!'
