import uuid
import json
from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from datetime import timedelta
from django.forms.models import model_to_dict
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


from users.models import CustomUser
from projects.constants import (
    ASSET_CATEGORY,
    ASSET_TYPE,
    COUNTRY,
    CURRENCY,
    ENERGY_VECTOR,
    COP_MODES,
    FLOW_DIRECTION,
    MVS_TYPE,
    SIMULATION_STATUS,
    PENDING,
    TRUE_FALSE_CHOICES,
    BOOL_CHOICES,
    USER_RATING,
)


class Feedback(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=200)
    subject = models.CharField(max_length=200)
    feedback = models.TextField()
    rating = models.PositiveSmallIntegerField(choices=USER_RATING, null=True)


class EconomicData(models.Model):
    duration = models.PositiveSmallIntegerField()
    currency = models.CharField(max_length=3, choices=CURRENCY)
    discount = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    tax = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])


class Viewer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    share_rights = models.CharField(
        max_length=10, choices=(("edit", _("Edit")), ("read", _("Read")))
    )

    def __str__(self):
        return f"{self.user.email} [{self.share_rights}]"


class Project(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=120)
    description = models.TextField()
    country = models.CharField(max_length=50, choices=COUNTRY)
    latitude = models.FloatField()
    longitude = models.FloatField()
    economic_data = models.OneToOneField(
        EconomicData, on_delete=models.SET_NULL, null=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True
    )
    viewers = models.ManyToManyField(Viewer, related_name="viewer_projects")

    def __str__(self):
        return self.name

    def get_scenarios_with_results(self):
        return self.scenario_set.filter(simulation__isnull=False).filter(
            simulation__results__isnull=False
        )

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
        A dict with the parameters describing a scenario model
        """
        dm = model_to_dict(self, exclude=["id", "user", "viewers"])
        dm["economic_data"] = model_to_dict(self.economic_data, exclude=["id"])
        if bind_scenario_data is True:
            scenario_data = []
            for scenario in self.scenario_set.all():
                scenario_data.append(scenario.export())
            dm["scenario_set_data"] = scenario_data
        return dm

    def add_viewer_if_not_exist(self, email=None, share_rights=""):
        user = None
        success = False
        if email is not None:
            users = CustomUser.objects.filter(email=email)
            if users.exists():
                user = users.first()
        else:
            message = _(
                f"No email address provided to find the user to share the project '{self.name}' with"
            )

        if user is not None:
            viewers = Viewer.objects.filter(user=user)
            if viewers.exists():
                viewer = viewers.get()
            else:
                if user == self.user:
                    viewer = None
                    message = _("You cannot share a project with yourself")
                else:
                    viewer = Viewer.objects.create(user=user, share_rights=share_rights)

            if viewer not in self.viewers.all() and viewer is not None:
                self.viewers.add(viewer)
                success = True
                message = _(
                    f"'{email}' belongs to a valid user, they will be able to {share_rights} the project '{self.name}'"
                )
            else:
                if viewer is not None:
                    if viewer.share_rights != share_rights:
                        success = True
                        message = _(
                            f"The share rights of the user registered under {email} for the project '{self.name}' have been changed from '{viewer.share_rights}' to '{share_rights}'"
                        )
                        viewer.share_rights = share_rights
                        viewer.save()
                    else:
                        message = _(
                            f"The user registered under {email} for the project '{self.name}' already have '{share_rights}' access"
                        )

        else:
            message = _(
                f"We could not find a user registered under the email address you provided: {email}"
            )
        return (success, message)

    def revoke_access(self, viewers=None):
        """Given a queryset of viewers or a list of viewers ids, remove those viewers from projects viewers"""
        success = False
        if isinstance(viewers, int):
            viewers = Viewer.objects.filter(id__in=[viewers])
        elif isinstance(viewers, list):
            viewers = Viewer.objects.filter(id__in=viewers)

        if viewers is not None:
            existing_viewers = viewers.intersection(self.viewers.all())
            if existing_viewers.exists():

                for viewer_id in existing_viewers.values_list("id", flat=True):
                    self.viewers.remove(viewer_id)
                success = True
                message = _(
                    f"The user(s) {','.join(existing_viewers.values_list('user__email', flat=True))} rights to the project '{self.name}' have been revoked"
                )
            else:
                message = _(
                    f"The user(s) {','.join(viewers.values_list('user__email', flat=True))} does not belong to the viewers of the project '{self.name}'"
                )
        else:
            message = _(
                "The user(s) you selected seems to not be registered in the open_plan tool"
            )
        return success, message


class Comment(models.Model):
    name = models.CharField(max_length=60)
    body = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name


class Scenario(models.Model):
    name = models.CharField(max_length=60)

    start_date = models.DateTimeField()
    time_step = models.IntegerField(validators=[MinValueValidator(0)])
    capex_fix = models.FloatField(
        validators=[MinValueValidator(0.0)], default=0, blank=True
    )
    # The next 3 fields make no sense for a scenario, they are asset fields.
    # Removing them caused trouble with existing database though, so default values are used instead
    # related to https://github.com/open-plan-tool/gui/issues/32
    capex_var = models.FloatField(
        validators=[MinValueValidator(0.0)], default=0, blank=True
    )
    opex_fix = models.FloatField(
        validators=[MinValueValidator(0.0)], default=0, blank=True
    )
    opex_var = models.FloatField(
        validators=[MinValueValidator(0.0)], default=0, blank=True
    )
    evaluated_period = models.IntegerField(validators=[MinValueValidator(0)])
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name

    def get_timestamps(self, json_format=False):
        answer = []

        n_occurence_per_day = int((24 * 60) / self.time_step)

        for i in range(self.evaluated_period):
            for j in range(n_occurence_per_day):
                iter_date = self.start_date + timedelta(
                    days=i + 1, minutes=self.time_step * (j + 1)
                )
                if json_format is True:
                    iter_date = iter_date.isoformat().replace("T", " ")
                answer.append(iter_date)
        return answer

    def get_currency(self):
        return self.project.economic_data.currency

    @property
    def energy_vectors(self):
        """Return a list of energy vectors used in a scenario"""
        vectors = []
        for vector in self.bus_set.all().values_list("type", flat=True):
            if vector not in vectors:
                vectors.append(vector)
        return vectors

    def export(self, bind_project_data=False):
        """
        Parameters
        ----------
        bind_project_data : bool
            when True, the project data is saved along the scenario data
            Default: False.
        ...
        Returns
        -------
        A dict with the parameters describing a scenario model
        """
        dm = model_to_dict(self, exclude=["id"])
        dm["start_date"] = str(dm["start_date"])
        if bind_project_data is True:
            dm["project"] = self.project.export(bind_scenario_data=False)
        else:
            dm.pop("project")

        energy_model_assets = self.asset_set.all()
        dm["assets"] = []
        for asset in energy_model_assets:
            dm["assets"].append(asset.export())

        clinks = self.connectionlink_set.all()
        bus_ids = list(set(clinks.values_list("bus", flat=True)))
        busses = []
        for bus_id in bus_ids:
            bus = Bus.objects.get(id=bus_id)
            bus_data = model_to_dict(bus, exclude=["id", "parent_asset", "scenario"])
            bus_data["inputs"] = []
            bus_data["outputs"] = []
            for connection in bus.connectionlink_set.all():
                if connection.flow_direction == "A2B":
                    bus_data["inputs"].append(connection.export())
                elif connection.flow_direction == "B2A":
                    bus_data["outputs"].append(connection.export())
            busses.append(bus_data)
        dm["busses"] = busses
        return dm


class AssetType(models.Model):
    asset_type = models.CharField(
        max_length=30, choices=ASSET_TYPE, null=False, unique=True
    )
    asset_category = models.CharField(max_length=30, choices=ASSET_CATEGORY)
    energy_vector = models.CharField(max_length=20, choices=ENERGY_VECTOR)
    mvs_type = models.CharField(max_length=20, choices=MVS_TYPE)
    # TODO Could be listCharField ...
    asset_fields = models.TextField(null=True)
    unit = models.CharField(max_length=30, null=True)

    def export(self):
        """
        Returns
        -------
        A dict with the parameters describing an asset type model
        """
        dm = model_to_dict(self, exclude=["id"])
        return dm

    @property
    def visible_fields(self):
        return self.asset_fields.replace("[", "").replace("]", "").split(",")

    def add_field(self, field_name):
        temp = self.visible_fields
        if field_name not in temp:
            temp.append(field_name)
            self.asset_fields = "[" + ",".join(temp) + "]"

    def remove_field(self, field_name):
        temp = self.visible_fields
        if field_name in temp:
            temp.pop(temp.index(field_name))
            self.asset_fields = "[" + ",".join(temp) + "]"


class TopologyNode(models.Model):
    name = models.CharField(max_length=60, null=False, blank=False)
    pos_x = models.FloatField(default=0.0)
    pos_y = models.FloatField(default=0.0)
    scenario = models.ForeignKey(
        Scenario, on_delete=models.CASCADE, null=False, blank=False
    )
    parent_asset = models.ForeignKey(
        to="Asset", on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        abstract = True


class ValueType(models.Model):
    type = models.CharField(max_length=30, null=False, unique=True)
    unit = models.CharField(max_length=30, null=True)


class Asset(TopologyNode):
    def save(self, *args, **kwargs):
        if self.asset_type.asset_type in ["dso", "gas_dso", "h2_dso", "heat_dso"]:
            self.optimize_cap = False
        super().save(*args, **kwargs)

    unique_id = models.CharField(
        max_length=120, default=uuid.uuid4, unique=True, editable=False
    )
    capex_fix = models.FloatField(
        null=True, blank=False, validators=[MinValueValidator(0.0)]
    )  # development_costs
    capex_var = models.FloatField(
        null=True, blank=False, validators=[MinValueValidator(0.0)]
    )  # specific_costs
    opex_fix = models.FloatField(
        null=True, blank=False, validators=[MinValueValidator(0.0)]
    )  # specific_costs_om
    opex_var = models.FloatField(
        null=True, blank=False, validators=[MinValueValidator(0.0)]
    )  # dispatch_price
    lifetime = models.IntegerField(
        null=True, blank=False, validators=[MinValueValidator(0)]
    )
    input_timeseries = models.TextField(
        null=True, blank=False
    )  # , validators=[validate_timeseries])
    crate = models.FloatField(
        null=True,
        blank=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    efficiency = models.TextField(null=True, blank=False)
    # used in the case of transformers with one input and two outputs
    # or two inputs and one output
    efficiency_multiple = models.TextField(null=True, blank=False)

    soc_max = models.FloatField(
        null=True,
        blank=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    soc_min = models.FloatField(
        null=True,
        blank=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    dispatchable = models.BooleanField(
        null=True, blank=False, choices=TRUE_FALSE_CHOICES, default=None
    )
    maximum_capacity = models.FloatField(
        null=True, blank=False, validators=[MinValueValidator(0.0)]
    )
    energy_price = models.FloatField(
        null=True, blank=False, validators=[MinValueValidator(0.0)]
    )
    feedin_tariff = models.FloatField(
        null=True, blank=False, validators=[MinValueValidator(0.0)]
    )

    feedin_cap = models.FloatField(
        default=None, null=True, blank=False, validators=[MinValueValidator(0.0)]
    )

    peak_demand_pricing = models.FloatField(
        null=True, blank=False, validators=[MinValueValidator(0.0)]
    )
    peak_demand_pricing_period = models.SmallIntegerField(
        null=True, blank=False, validators=[MinValueValidator(0)]
    )
    renewable_share = models.FloatField(
        null=True,
        blank=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    renewable_asset = models.BooleanField(
        null=True, blank=False, choices=TRUE_FALSE_CHOICES, default=None
    )
    asset_type = models.ForeignKey(
        AssetType, on_delete=models.CASCADE, null=False, blank=True
    )
    optimize_cap = models.BooleanField(
        null=True, blank=False, choices=BOOL_CHOICES, default=False
    )
    installed_capacity = models.FloatField(
        null=True, blank=False, validators=[MinValueValidator(0.0)]
    )
    age_installed = models.FloatField(
        null=True, blank=False, validators=[MinValueValidator(0.0)]
    )

    @property
    def fields(self):
        return [f.name for f in self._meta.fields + self._meta.many_to_many]

    @property
    def visible_fields(self):
        visible_fields = self.asset_type.visible_fields
        # renaming the model variable might be too dangerous with existing database
        if "optimize_cap" in visible_fields:
            visible_fields[visible_fields.index("optimize_cap")] = "optimize_capacity"
        return visible_fields

    def has_parameter(self, param_name):
        return param_name in self.visible_fields

    def parameter_path(self, param_name):
        # TODO for storage
        if self.has_parameter(param_name):
            # TODO if (unit, value) formatting, add "value" at the end
            if self.asset_type.asset_category == "energy_provider":
                asset_category = "energy_providers"
            else:
                asset_category = self.asset_type.asset_category
            # renaming the model variable might be too dangerous with existing database
            if param_name == "optimize_cap":
                param_name = "optimize_capacity"
            answer = (asset_category, self.name, param_name)
        else:
            answer = None
        return answer

    @property
    def is_provider(self):
        return self.asset_type.asset_type in ["dso", "gas_dso", "h2_dso", "heat_dso"]

    @property
    def is_storage(self):
        return self.asset_type.asset_category == "energy_storage"

    @property
    def timestamps(self):
        return self.scenario.get_timestamps()

    @property
    def input_timeseries_values(self):
        if self.is_input_timeseries_empty() is False:
            answer = json.loads(self.input_timeseries)
        else:
            answer = []
        return answer

    def export(self):
        """
        Returns
        -------
        A dict with the parameters describing an asset model
        """

        fields = (
            self.asset_type.asset_fields.replace("[", "").replace("]", "").split(",")
        )
        fields += ["name", "pos_x", "pos_y"]
        dm = model_to_dict(self, fields=fields)
        dm["asset_info"] = self.asset_type.export()

        # check for parent assets
        if self.parent_asset is not None:
            dm["parent_asset"] = self.parent_asset.name

        return dm

    def is_input_timeseries_empty(self):
        return self.input_timeseries == ""


# from oemof.thermal
def calc_cops(
    mode, temp_high, temp_low, quality_grade, temp_threshold_icing=2, factor_icing=None
):

    r"""
    Calculates the Coefficient of Performance (COP) of heat pumps and chillers
    based on the Carnot efficiency (ideal process) and a scale-down factor.
    Note
    ----
    Applications of air-source heat pumps should consider icing
    at the heat exchanger at air-temperatures around :math:`2^\circ C` .
    Icing causes a reduction of the efficiency.
    .. calc_cops-equations:
        mode='heat_pump'
        :math:`COP = \eta \cdot \frac{T_\mathrm{high}}{T_\mathrm{high}
        - T_\mathrm{low}}`
        :math:`COP = f_\mathrm{icing} \cdot\eta
        \cdot\frac{T_\mathrm{high}}{T_\mathrm{high} - T_\mathrm{low}}`
        mode='chiller'
        :math:`COP = \eta \cdot \frac{T_\mathrm{low}}{T_\mathrm{high}
        - T_\mathrm{low}}`
    Parameters
    ----------
    temp_high : list or pandas.Series of numerical values
        Temperature of the high temperature reservoir in :math:`^\circ C`
    temp_low : list or pandas.Series of numerical values
        Temperature of the low temperature reservoir in :math:`^\circ C`
    quality_grade : numerical value
        Factor that scales down the efficiency of the real heat pump
        (or chiller) process from the ideal process (Carnot efficiency), where
         a factor of 1 means teh real process is equal to the ideal one.
    factor_icing: numerical value
        Sets the relative COP drop caused by icing, where 1 stands for no
        efficiency-drop.
    mode : string
        Two possible modes: "heat_pump" or "chiller" (default 'None')
    t_threshold:
        Temperature in :math:`^\circ C` below which icing at heat exchanger
        occurs (default 2)
    Returns
    -------
    cops : list of numerical values
        List of Coefficients of Performance (COPs)
    """
    # Check if input arguments have proper type and length
    # if not isinstance(temp_low, (list, pd.Series)):
    if not isinstance(temp_low, list):
        raise TypeError("Argument 'temp_low' is not of type list or pd.Series!")

    # if not isinstance(temp_high, (list, pd.Series)):
    if not isinstance(temp_high, list):
        raise TypeError("Argument 'temp_high' is not of " "type list or pd.Series!")

    if len(temp_high) != len(temp_low):
        if (len(temp_high) != 1) and ((len(temp_low) != 1)):
            raise IndexError(
                "Arguments 'temp_low' and 'temp_high' "
                "have to be of same length or one has "
                "to be of length 1 !"
            )

    # Make temp_low and temp_high have the same length and
    # convert unit to Kelvin.
    length = max([len(temp_high), len(temp_low)])
    if len(temp_high) == 1:
        list_temp_high_K = [temp_high[0] + 273.15] * length
    elif len(temp_high) == length:
        list_temp_high_K = [t + 273.15 for t in temp_high]
    if len(temp_low) == 1:
        list_temp_low_K = [temp_low[0] + 273.15] * length
    elif len(temp_low) == length:
        list_temp_low_K = [t + 273.15 for t in temp_low]

    # Calculate COPs depending on selected mode (without icing).
    if factor_icing is None:
        if mode == "heat_pump":
            cops = [
                quality_grade * t_h / (t_h - t_l)
                for t_h, t_l in zip(list_temp_high_K, list_temp_low_K)
            ]
        elif mode == "chiller":
            cops = [
                quality_grade * t_l / (t_h - t_l)
                for t_h, t_l in zip(list_temp_high_K, list_temp_low_K)
            ]

    # Calculate COPs of a heat pump and lower COP when icing occurs.
    elif factor_icing is not None:
        if mode == "heat_pump":
            cops = []
            for t_h, t_l in zip(list_temp_high_K, list_temp_low_K):
                if t_l < temp_threshold_icing + 273.15:
                    f_icing = factor_icing
                    cops = cops + [f_icing * quality_grade * t_h / (t_h - t_l)]
                if t_l >= temp_threshold_icing + 273.15:
                    cops = cops + [quality_grade * t_h / (t_h - t_l)]
        elif mode == "chiller":
            raise ValueError(
                "Argument 'factor_icing' has " "to be None for mode='chiller'!"
            )
    return cops


class COPCalculator(models.Model):

    scenario = models.ForeignKey(
        Scenario, on_delete=models.CASCADE, null=False, blank=False
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, blank=True)

    temperature_high = models.TextField(null=False, blank=False)
    temperature_low = models.TextField(null=False, blank=False)

    temp_threshold_icing = quality_grade = models.FloatField(
        null=True, default=2, validators=[MinValueValidator(-273.15)]
    )

    quality_grade = models.FloatField(
        null=True,
        default=1,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    factor_icing = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    mode = models.CharField(max_length=20, choices=COP_MODES)

    @property
    def temp_high(self):
        try:
            answer = json.loads(self.temperature_high)
        except json.decoder.JSONDecodeError:
            answer = []
        if isinstance(answer, float):
            answer = [answer]
        return answer

    @property
    def temp_low(self):
        try:
            answer = json.loads(self.temperature_low)
        except json.decoder.JSONDecodeError:
            answer = []
        if isinstance(answer, float):
            answer = [answer]
        return answer

    def calc_cops(self):
        cops = calc_cops(
            temp_high=self.temp_high,
            temp_low=self.temp_low,
            mode=self.mode,
            quality_grade=self.quality_grade,
            factor_icing=self.factor_icing,
            temp_threshold_icing=self.temp_threshold_icing,
        )
        if len(cops) == 1:
            cops = cops[0]
        return cops


class Bus(TopologyNode):
    type = models.CharField(max_length=20, choices=ENERGY_VECTOR)
    # TODO now these parameters are useless ...
    input_ports = models.IntegerField(null=False, default=1)
    output_ports = models.IntegerField(null=False, default=1)


class ConnectionLink(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, null=False)
    bus_connection_port = models.CharField(null=False, max_length=12)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=False)
    flow_direction = models.CharField(max_length=15, choices=FLOW_DIRECTION, null=False)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, null=False)

    def export(self):
        """
        Returns
        -------
        A dict with the parameters describing a connectionlink model
        """
        dm = model_to_dict(self, exclude=["id", "scenario", "bus"])
        dm["asset"] = self.asset.name
        return dm


class Constraint(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, null=False)
    activated = models.BooleanField(
        null=True, blank=False, choices=BOOL_CHOICES, default=False
    )

    class Meta:
        abstract = True


class MinRenewableConstraint(Constraint):
    value = models.FloatField(
        null=False,
        blank=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.2,
    )
    unit = models.CharField(max_length=6, default="factor", editable=False)
    name = models.CharField(
        max_length=30, default="minimal_renewable_factor", editable=False
    )


class MaxEmissionConstraint(Constraint):
    value = models.FloatField(
        null=False, blank=False, validators=[MinValueValidator(0.0)], default=0.0
    )
    unit = models.CharField(max_length=9, default="kgCO2eq/a", editable=False)
    name = models.CharField(max_length=30, default="maximum_emissions", editable=False)


class MinDOAConstraint(Constraint):
    value = models.FloatField(
        null=False,
        blank=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.3,
    )
    unit = models.CharField(max_length=6, default="factor", editable=False)
    name = models.CharField(
        max_length=30, default="minimal_degree_of_autonomy", editable=False
    )


class NZEConstraint(Constraint):
    value = models.BooleanField(
        null=True, blank=False, choices=BOOL_CHOICES, default=False
    )
    unit = models.CharField(max_length=4, default="bool", editable=False)
    name = models.CharField(max_length=30, default="net_zero_energy", editable=False)


class ScenarioFile(models.Model):
    title = models.CharField(max_length=50)
    file = models.FileField(upload_to="tempFiles/", null=True, blank=True)


class AbstractSimulation(models.Model):

    start_date = models.DateTimeField(auto_now_add=True, null=False)
    end_date = models.DateTimeField(null=True)
    elapsed_seconds = models.FloatField(null=True)
    mvs_token = models.CharField(max_length=200, null=True)
    status = models.CharField(
        max_length=20, choices=SIMULATION_STATUS, null=False, default=PENDING
    )
    results = models.TextField(null=True, max_length=30e6)
    errors = models.TextField(null=True)

    class Meta:
        abstract = True
