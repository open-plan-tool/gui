import logging
from django.utils.translation import override
from django.utils.translation import gettext as _

from projects.models.base_models import Project, EconomicData
from projects.scenario_topology_helpers import (
    load_project_from_dict,
    load_scenario_from_dict,
)


logger = logging.getLogger(__name__)


class UseCase(Project):
    def assign(self, user, locale_lang="fr"):
        dm = self.export(bind_scenario_data=True)
        proj_id = load_project_from_dict(dm, user)
        # translate here depending on locale
        proj = Project.objects.get(id=proj_id)
        with override(locale_lang):
            for attr in ["name", "description", "country"]:
                setattr(proj, attr, _(getattr(proj, attr)))
            for scen in proj.scenario_set.all():
                for attr in ["name", "description"]:
                    setattr(scen, attr, _(getattr(scen, attr)))
                attr = "name"
                for asset in scen.asset_set.all():
                    setattr(asset, attr, _(getattr(asset, attr)))
                    asset.save()
                for bus in scen.bus_set.all():
                    setattr(bus, attr, _(getattr(bus, attr)))
                    bus.save()
                scen.save()
            proj.save()
        return proj_id

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
