import logging
from concurrent.futures import ThreadPoolExecutor

from epa.celery_config import app

from projects.constants import PENDING
from projects.models import Simulation
from projects.requests import fetch_ezp_simulation_results

logger = logging.getLogger(__name__)


@app.task
def check_simulation_objects():
    pending_simulations = Simulation.objects.filter(status=PENDING)

    if not pending_simulations.exists():
        logger.debug("No pending simulations found.")
        return

    with ThreadPoolExecutor() as pool:
        pool.map(fetch_ezp_simulation_results, pending_simulations)

    logger.debug("Finished round for checking Simulation objects status.")
