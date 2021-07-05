from ctapipe.core import Component
from ctapipe.core.traits import Dict, List, Float, Int
from lstchain.reco.utils import filter_events

import numpy as np
import operator
import astropy.units as u
from pyirf.binning import create_bins_per_decade  # , add_overflow_bins
from pyirf.cuts import calculate_percentile_cut, evaluate_binned_cut


__all__ = ["EventSelector", "DL3FixedCuts", "DataBinning"]


class EventSelector(Component):
    """
    Filter values used for event filters and list of finite parameters are
    taken as inputs and filter_events() is used on a table of events
    called in with the Component.
    """

    filters = Dict(
        help="Dict of event filter parameters",
        default_value={
            "r": [0, 1],
            "wl": [0.01, 1],
            "leakage_intensity_width_2": [0, 1],
            "event_type": [32, 33],
        },
    ).tag(config=True)

    finite_params = List(
        help="List of parameters to ensure finite values",
        default_value=["intensity", "length", "width"],
    ).tag(config=True)

    def filter_cut(self, events):
        return filter_events(events, self.filters, self.finite_params)


class DL3FixedCuts(Component):
    """
    Temporary fixed selection cuts for DL2 to DL3 conversion
    """

    fixed_gh_cut = Float(
        help="Fixed selection cut for gh_score (gammaness)",
        default_value=0.6,
    ).tag(config=True)

    fixed_gh_max_efficiency = Float(
        help="Fixed max gamma efficiency for optimized g/h cuts in %",
        default_value=95,
    ).tag(config=True)

    fixed_theta_containment = Float(
        help="Fixed % containment region for theta cuts",
        default=68,
    ).tag(config=True)

    fixed_theta_cut = Float(
        help="Fixed selection cut for theta",
        default_value=0.2,
    ).tag(config=True)

    allowed_tels = List(
        help="List of allowed LST telescope ids",
        trait=Int(),
        default_value=[1],
    ).tag(config=True)

    def gh_cut(self, data):
        return data[data["gh_score"] > self.fixed_gh_cut]

    def opt_gh_cuts(
        self, data, energy_bins, min_value=0.1,
        max_value=0.99, smoothing=None, min_events=10
    ):
        #To be sure to have the efficiency in between 0 and 100
        if self.fixed_gh_max_efficiency < 1:
            self.fixed_gh_max_efficiency *= 100

        gh_cuts = calculate_percentile_cut(
            data["gh_score"],
            data["reco_energy"],
            bins = energy_bins,
            min_value = min_value,
            max_value = max_value,
            fill_value = data["gh_score"].max(),
            percentile = 100 - self.fixed_gh_max_efficiency,
            smoothing = smoothing,
            min_events = min_events,
        )
        return gh_cuts

    def apply_opt_gh_cuts(self, data, gh_cuts):
        """
        Apply a given energy dependent gh cuts to a data file
        """

        data["selected_gh"] = evaluate_binned_cut(
            data["gh_score"],
            data["reco_energy"],
            gh_cuts,
            operator.ge,
        )
        return data[data["selected_gh"]]

    def theta_cut(self, data):
        return data[data["theta"].to_value(u.deg) < self.fixed_theta_cut]

    def opt_theta_cuts(
        self, data, energy_bins, min_value=0.05 * u.deg,
        fill_value=0.32 * u.deg, max_value=0.32 * u.deg,
        smoothing=None, min_events=10
    ):
        if self.fixed_theta_containment < 1:
            self.fixed_theta_containment *= 100

        theta_cuts = calculate_percentile_cut(
            data["theta"],
            data["reco_energy"],
            bins = energy_bins,
            min_value = min_value,
            max_value = max_value,
            fill_value = fill_value,
            percentile = self.fixed_theta_containment,
            smoothing = smoothing,
            min_events = min_events,
        )

        data["selected_theta"] = evaluate_binned_cut(
            data["theta"],
            data["reco_energy"],
            theta_cuts,
            operator.le,
        )
        return data[data["selected_theta"]], theta_cuts

    def allowed_tels_filter(self, data):
        mask = np.zeros(len(data), dtype=bool)
        for tel_id in self.allowed_tels:
            mask |= data["tel_id"] == tel_id
        return data[mask]


class DataBinning(Component):
    """
    Collects information on generating energy and angular bins for
    generating IRFs as per pyIRF requirements.
    """

    true_energy_min = Float(
        help="Minimum value for True Energy bins in TeV units",
        default_value=0.01,
    ).tag(config=True)

    true_energy_max = Float(
        help="Maximum value for True Energy bins in TeV units",
        default_value=100,
    ).tag(config=True)

    true_energy_n_bins_per_decade = Float(
        help="Number of edges per decade for True Energy bins",
        default_value=5.5,
    ).tag(config=True)

    reco_energy_min = Float(
        help="Minimum value for Reco Energy bins in TeV units",
        default_value=0.01,
    ).tag(config=True)

    reco_energy_max = Float(
        help="Maximum value for Reco Energy bins in TeV units",
        default_value=100,
    ).tag(config=True)

    reco_energy_n_bins_per_decade = Float(
        help="Number of edges per decade for Reco Energy bins",
        default_value=5.5,
    ).tag(config=True)

    energy_migration_min = Float(
        help="Minimum value of Energy Migration matrix",
        default_value=0.2,
    ).tag(config=True)

    energy_migration_max = Float(
        help="Maximum value of Energy Migration matrix",
        default_value=5,
    ).tag(config=True)

    energy_migration_n_bins = Int(
        help="Number of bins in log scale for Energy Migration matrix",
        default_value=31,
    ).tag(config=True)

    fov_offset_min = Float(
        help="Minimum value for FoV Offset bins",
        default_value=0.1,
    ).tag(config=True)

    fov_offset_max = Float(
        help="Maximum value for FoV offset bins",
        default_value=1.1,
    ).tag(config=True)

    fov_offset_n_edges = Int(
        help="Number of edges for FoV offset bins",
        default_value=9,
    ).tag(config=True)

    bkg_fov_offset_min = Float(
        help="Minimum value for FoV offset bins for Background IRF",
        default_value=0,
    ).tag(config=True)

    bkg_fov_offset_max = Float(
        help="Maximum value for FoV offset bins for Background IRF",
        default_value=10,
    ).tag(config=True)

    bkg_fov_offset_n_edges = Int(
        help="Number of edges for FoV offset bins for Background IRF",
        default_value=21,
    ).tag(config=True)

    source_offset_min = Float(
        help="Minimum value for Source offset for PSF IRF",
        default_value=0.0001,
    ).tag(config=True)

    source_offset_max = Float(
        help="Maximum value for Source offset for PSF IRF",
        default_value=1.0001,
    ).tag(config=True)

    source_offset_n_edges = Int(
        help="Number of edges for Source offset for PSF IRF",
        default_value=1000,
    ).tag(config=True)

    def true_energy_bins(self):
        """
        Creates bins per decade for true MC energy using pyirf function.

        The overflow binning added is not needed at the current stage
        It can be used as - add_overflow_bins(***)[1:-1]
        """
        true_energy = create_bins_per_decade(
            self.true_energy_min * u.TeV,
            self.true_energy_max * u.TeV,
            self.true_energy_n_bins_per_decade,
        )
        return true_energy

    def reco_energy_bins(self):
        """
        Creates bins per decade for reconstructed MC energy using pyirf function.

        The overflow binning added is not needed at the current stage
        It can be used as - add_overflow_bins(***)[1:-1]
        """
        reco_energy = create_bins_per_decade(
            self.reco_energy_min * u.TeV,
            self.reco_energy_max * u.TeV,
            self.reco_energy_n_bins_per_decade,
        )
        return reco_energy

    def energy_migration_bins(self):
        """
        Creates bins for energy migration.
        """
        energy_migration = np.geomspace(
            self.energy_migration_min,
            self.energy_migration_max,
            self.energy_migration_n_bins,
        )
        return energy_migration

    def fov_offset_bins(self):
        """
        Creates bins for single/multiple FoV offset
        """
        fov_offset = (
            np.linspace(
                self.fov_offset_min,
                self.fov_offset_max,
                self.fov_offset_n_edges,
            )
            * u.deg
        )
        return fov_offset

    def bkg_fov_offset_bins(self):
        """
        Creates bins for FoV offset for Background IRF,
        Using the same binning as in pyirf example.
        """
        background_offset = (
            np.linspace(
                self.bkg_fov_offset_min,
                self.bkg_fov_offset_max,
                self.bkg_fov_offset_n_edges,
            )
            * u.deg
        )
        return background_offset

    def source_offset_bins(self):
        """
        Creates bins for source offset for generating PSF IRF.
        Using the same binning as in pyirf example.
        """

        source_offset = (
            np.linspace(
                self.source_offset_min,
                self.source_offset_max,
                self.source_offset_n_edges,
            )
            * u.deg
        )
        return source_offset
