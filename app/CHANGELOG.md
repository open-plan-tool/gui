# Changelog

## [Unreleased]
### Added
- Add endpoint to reparse a simulation's results `simulation/reparse-results/<int:sim_id>` [[#597](https://github.com/open-plan-tool/gui/pull/597)]
- Add endpoint to download the results as datapackage (`scenario/results/download_datapackage/<int:scen_id>`) as well as a button to do so [[#597](https://github.com/open-plan-tool/gui/pull/597)]
- KPI in the result table for total dispatch costs over a year (including energy costs) [[#599](https://github.com/open-plan-tool/gui/pull/599)]
- Warn the user if the simulation's results are ill formated that they should reset and re-simulate [[#599](https://github.com/open-plan-tool/gui/pull/599)]

### Changed
- Hide and toggle certain fields depending on storage type [[#596](https://github.com/open-plan-tool/gui/pull/596)]
- Save the graphs, the tables and the results directly as dict into the simulation JSONField's [[#597](https://github.com/open-plan-tool/gui/pull/597)]
### Removed
- Remove buttons to download MVS results in the result view [[#597](https://github.com/open-plan-tool/gui/pull/597)]

## [v1.3.2] – 2026-11-11
### Added
- Display eesyplan results table on results page [[#582](https://github.com/open-plan-tool/gui/pull/582)]
- Enable translation of graph labels [[#588](https://github.com/open-plan-tool/gui/pull/588)]
- Add parameters `investment_fix_cost` and `annual_fix_cost` to `HeatingNetwork` component [[#592](https://github.com/open-plan-tool/gui/pull/592)]
- Add endpoint to reset a simulation and the option to do so in the project's scenarios view[[#479](https://github.com/open-plan-tool/gui/pull/479)]

### Changed
- Allow user to save bus without an output [[#586](https://github.com/open-plan-tool/gui/pull/586)]
- Replace various converter assets with one electrical transformer [[#586](https://github.com/open-plan-tool/gui/pull/586)]
- Sankey diagramm is currently only the aggregated values diagramm [[#479](https://github.com/open-plan-tool/gui/pull/479)]

### Fixed
- Fix automatic simulation status fetching [[#580](https://github.com/open-plan-tool/gui/pull/580)]
- Fix DSO errors on results page [[#583](https://github.com/open-plan-tool/gui/pull/583)]
- Fix server error on simulation page [[#583](https://github.com/open-plan-tool/gui/pull/583)]
- Fix small layout bug on results step ribbon button [[#586](https://github.com/open-plan-tool/gui/pull/586)]
- Fix hover area on duplicate button [[#586](https://github.com/open-plan-tool/gui/pull/586)]
- Label profiles uniquely inside datapackage profiles.csv [[#479](https://github.com/open-plan-tool/gui/pull/479)]
- Fix table styling [[#588](https://github.com/open-plan-tool/gui/pull/588)]

## [v1.3.1] – 2026-11-02

### Added
- Add button to duplicate nodes in scenario [[#562](https://github.com/open-plan-tool/gui/pull/562)]

### Changed
- [eesyplan ](https://github.com/oemof/oemof-eesyplan) is now the default backend simulation server [[#576](https://github.com/open-plan-tool/gui/pull/576)]

## [v1.3.0] – 2026-11-02

### Added
- Component HeatingNetwork [[#492](https://github.com/open-plan-tool/gui/pull/492)]
- Component HeatingPipe [[#492](https://github.com/open-plan-tool/gui/pull/492)]
- Component Commodity [[#492](https://github.com/open-plan-tool/gui/pull/492)]
- Component AuxiliaryHeat [[#492](https://github.com/open-plan-tool/gui/pull/492)]
- Component Sink [[#492](https://github.com/open-plan-tool/gui/pull/492)]
- Component Shortage [[#492](https://github.com/open-plan-tool/gui/pull/492)]
- Component Excess [[#492](https://github.com/open-plan-tool/gui/pull/492)]

### Changed
- CHP component has new fields [[#492](https://github.com/open-plan-tool/gui/pull/492)]
- Storages Component have new fields [[#492](https://github.com/open-plan-tool/gui/pull/492)]
- DSO component's fields were modified, feedin_tariff and energy price are only allowed as scalar for all DSOs except for electricity [[#492](https://github.com/open-plan-tool/gui/pull/492)]
- [[#492](https://github.com/open-plan-tool/gui/pull/492)]

## [v1.2.2] – 2026-10-29
### Changed
- Constraint step (previously step 3) has been hidden until functionality is implemented in new backend [[#564](https://github.com/open-plan-tool/gui/pull/564)]

## [v1.2.1] – 2026-10-14
### Added
- Allow user to get information about usecases's scenarios via endpoint [[#524](https://github.com/open-plan-tool/gui/pull/524)]
### Changed
- Updated courses page with workshop information [[#526](https://github.com/open-plan-tool/gui/pull/526)]
### Fixed
- Fix broken datapackage export [[#522](https://github.com/open-plan-tool/gui/pull/522)]
- Fix bus saving and duplication bug [[#528](https://github.com/open-plan-tool/gui/pull/528)]
- Fix TimeseriesField display and validation [[#539](https://github.com/open-plan-tool/gui/pull/539)]

## [v1.2.0] – 2026-09-16
### Added
- Allow user to generate custom timeseries from eesyplan functions [[#511](https://github.com/open-plan-tool/gui/pull/511)][[#516](https://github.com/open-plan-tool/gui/pull/516)]
### Changed
- Add toggle for fixed capacity vs. optimized instead of allowing both options on a single asset [[#487](https://github.com/open-plan-tool/gui/pull/487)][[#514](https://github.com/open-plan-tool/gui/pull/514)]
### Fixed
- Fix issues with read and edit rights on shared projects [[#478](https://github.com/open-plan-tool/gui/pull/478)]

## [v1.1.4] – 2026-07-01
### Fixed
- Update incorrect or missing translation strings [[#480](https://github.com/open-plan-tool/gui/pull/480)]
- Fix validation error bug on timeseries with constant value [[#486](https://github.com/open-plan-tool/gui/pull/486)]

## [v1.1.3] – 2026-05-20
### Changed
- Remove specific workshop dates from courses site (will be redirected to DGS instead) [[#475](https://github.com/open-plan-tool/gui/pull/475)]

### Fixed
- Fix display on LCOE and percentage values [[#476](https://github.com/open-plan-tool/gui/pull/476)]

## [v1.1.2] – 2026-05-13
### Fixed
- Fix thermal efficiency value display for heat storage on results page [[#451](https://github.com/open-plan-tool/gui/pull/451)]
- Small usability improvements like additional support messages or fixed translations [[#457](https://github.com/open-plan-tool/gui/pull/457)]
- Remove faulty KPIs from results view [[#457](https://github.com/open-plan-tool/gui/pull/457)]
- Fix certain fields in results display appearing blank for Chromium browsers [[#461](https://github.com/open-plan-tool/gui/pull/461)]
- Update scenario simulation status on project overview [[#459](https://github.com/open-plan-tool/gui/pull/459)]
- Improve timeseries file upload display and error handling [[#452](https://github.com/open-plan-tool/gui/pull/452)]
- Fix map on project create not being displayed on small screen sizes [[#463](https://github.com/open-plan-tool/gui/pull/463)]

## [v1.1.1] – 2026-04-15
### Fixed
- Fix datapackage export if scenario name contains slashes [[#455](https://github.com/open-plan-tool/gui/pull/455)]

## [v1.1.0] – 2026-04-14
### Added
- Enable download of datapackage as zip [[#422](https://github.com/open-plan-tool/gui/pull/422)] [[#447](https://github.com/open-plan-tool/gui/pull/447)]

### Changed
- Update Django version and dependencies [[#432](https://github.com/open-plan-tool/gui/pull/432)]

### Fixed
- Fix initial assignment in storage forms [[#435](https://github.com/open-plan-tool/gui/pull/435)]

## [v1.0.1] – 2026-01-27
### Changed
- Updated favicon and project text to all say OpenPlan and use the most current logo.

### Fixed
- Fix project import error caused by duplicate timeseries.
- Fix energy system design window snapping on drag.
- Fix YouTube redirection link.
- Fix field validation error on heat storage.

## [v1.0.0] – 2026-01-12
### Added
- First official versioned release.

### Notes
- This release marks the start of structured versioning.
- The first iteration of this app was developed under the open-plan project, and is now continuing to be developed under the open-plan 2.0 project.
