#!/usr/local/bin/python
python manage.py compilemessages
python manage.py makemigrations users projects dashboard && \
python manage.py migrate && \
python manage.py collectstatic && \
python manage.py compilejsi18n && \
echo 'Updated the open-plan GUI app successfully!!'
