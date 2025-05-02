import logging

from projects.models.base_models import Project, EconomicData
from projects.scenario_topology_helpers import (
    load_project_from_dict,
    load_scenario_from_dict,
)


logger = logging.getLogger(__name__)


class UseCase(Project):
    def assign(self, user):
        dm = self.export(bind_scenario_data=True)
        return load_project_from_dict(dm, user)

    def export(self, bind_scenario_data=True):
        """
        Parameters
        ----------
        bind_scenario_data : bool
            when True, the scenarios of the project are saved
            Default: False.
        ...
        Returns
        -------
        A dict with the parameters describing a project model
        """
        dm = super().export(bind_scenario_data)
        dm.pop("project_ptr")
        return dm


def load_usecase_from_dict(model_data):
    """Create a new usecase

    Parameters
    ----------
    model_data: dict
        output produced by the export() method of the Project model
    """
    scenario_set = model_data.pop("scenario_set_data", None)

    economic_data = EconomicData(**model_data["economic_data"])
    economic_data.save()
    model_data["economic_data"] = economic_data
    usecase = UseCase(**model_data)
    usecase.save()

    if scenario_set is not None:
        for scenario_data in scenario_set:
            load_scenario_from_dict(scenario_data, None, usecase)

    return usecase.id
