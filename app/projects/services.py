import logging
from concurrent.futures import ThreadPoolExecutor

from django.contrib import messages
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django_q.models import Schedule

import smtplib
import warnings
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from epa.settings import (
    EXCHANGE_ACCOUNT,
    EXCHANGE_SERVER,
    EXCHANGE_EMAIL,
    RECIPIENTS,
    EXCHANGE_PW,
    EMAIL_SUBJECT_PREFIX,
    TIME_ZONE,
    USE_EXCHANGE_EMAIL_BACKEND,
)
from projects.constants import PENDING
from projects.models import Simulation
from projects.requests import fetch_mvs_simulation_results

logger = logging.getLogger(__name__)

r"""Functions meant to be powered by Django-Q.

Those functions require Django-Q cluster to run along with Django Server.
To achieve this `python manage.py qcluster` command needs to be executed.

"""


def check_simulation_objects(**kwargs):
    pending_simulations = Simulation.objects.filter(status=PENDING)
    if pending_simulations.count() == 0:
        logger.debug(f"No pending simulation found. Deleting Scheduler.")
        Schedule.objects.all().delete()
    # fetch_mvs_simulation_results mostly waits for MVS API to respond, so no ProcessPool is required.
    with ThreadPoolExecutor() as pool:
        pool.map(fetch_mvs_simulation_results, pending_simulations)
    logger.debug(f"Finished round for checking Simulation objects status.")

    logger.debug(f"Finished round for checking Simulation objects status.")


def create_or_delete_simulation_scheduler(**kwargs):
    r"""Initialize a Django-Q Scheduler for all Simulation objects.

    If there are Simulation objects in the database, being in "PENDING" state
    a Scheduler is created to check periodically each Simulation (utilizes MVS API).
    If there is no Simulation is "PENDING" state the Scheduler object is deleted.

    Parameters
    ----------
    **kwargs : dict
        Possible future keyword arguments.

    Returns
    -------
    bool :
        True if Scheduler object is created or False otherwise.

    """
    mvs_token = kwargs.get("mvs_token", "")

    if Schedule.objects.count() == 0:
        logger.info(
            f"No Scheduler found. Creating a new Scheduler to check Simulation {mvs_token}."
        )
        schedule = Schedule.objects.create(
            name=f"djangoQ_Scheduler-{mvs_token}",
            func="projects.services.check_simulation_objects",
            # args='5',
            schedule_type=Schedule.MINUTES,
            minutes=1,
            # kwargs={'test_arg': 1, 'test_arg2': "test"}
        )
        if schedule.id:
            logger.info(
                f"New Scheduler Created to track simulation {mvs_token} objects status."
            )
            return True
        else:
            logger.debug(f"Scheduler already exists for {mvs_token}. Skipping.")
            return False


def send_feedback_email(subject, body):
    send_email(RECIPIENTS, subject, body)


def send_email(to_email, subject, message):
    """Send E-mail via MS Exchange Server using credentials from env vars
    Parameters
    ----------
    to_email : :obj:`str`
        Target mail address
    subject : :obj:`str`
        Subject of mail
    message : :obj:`str`
        Message body of mail
    Returns
    -------
    :obj:`bool`
        Success status (True: successful)
    """
    prefixed_subject = EMAIL_SUBJECT_PREFIX + subject
    if isinstance(to_email, str):
        to_email = [to_email]

    if USE_EXCHANGE_EMAIL_BACKEND is True:
        _message = MIMEMultipart()
        _message["From"] = EXCHANGE_EMAIL
        _message["To"] = ",".join(to_email)
        _message["Subject"] = prefixed_subject
        _message.attach(MIMEText(message, "plain"))
        with smtplib.SMTP(EXCHANGE_SERVER, 587) as server:
            server.starttls()
            try:
                server.login(EXCHANGE_EMAIL, EXCHANGE_PW)
                server.sendmail(EXCHANGE_EMAIL, to_email, _message.as_string())
                return True
            except smtplib.SMTPAuthenticationError as e:
                err_msg = (
                    _("Form - mail sending error:")
                    + f" {e}"
                    + f", {EXCHANGE_EMAIL.replace('@', '')}"
                )
                logger.error(err_msg)
                warnings.warn(str(e), category=UserWarning)
                return False

    elif USE_EXCHANGE_EMAIL_BACKEND is False:
        print(
            "\n",
            "--- No email is send ---",
            "\n\n",
            "To:",
            to_email,
            "\n\n",
            "Subject:",
            prefixed_subject,
            "\n\n",
            "Message:",
            message,
            "\n",
        )
        return True
    else:
        raise ValueError(
            "Email backend not configured.",
            "USE_EXCHANGE_EMAIL_BACKEND must be boolean of either True or False.",
        )
        return False


def excuses_design_under_development(request, link=False):
    if link is False:
        msg = """This page is still under development. What you see is a design draft of how it should look like. If you have ideas or feedback about the design, you are welcome to submit it using the <a href='{url}'>feedback form</a>"""
    else:
        msg = """This website is still under development and not all buttons link to what they should yet. This is the case of the link or button you just clicked on. If you have ideas or feedback on how to improve the design, you are welcome to submit it using the <a href='{url}'>feedback form</a>"""

    url = reverse("user_feedback")
    messages.warning(request, _(mark_safe(msg.format(url=url))))


def get_selected_scenarios_in_cache(request, proj_id):
    """Given a request and the project id returns the list of selected scenarios"""
    if isinstance(proj_id, int):
        proj_id = str(proj_id)
    selected_scenarios_per_project = request.session.get("selected_scenarios", {})
    selected_scenario = selected_scenarios_per_project.get(proj_id, [])
    return [int(scen_id) for scen_id in selected_scenario]
