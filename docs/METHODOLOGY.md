# RigPlan — Methodology and experimental evidence

## Problem and motivation

Physical rig experiments generate large sensor datasets and consume equipment time, energy and engineering effort. Many cycles repeat the same operating conditions. Simply removing similar cycles is risky: repeated runs can capture variability, warmup effects, drift and rare faults. The research question is how to select a smaller campaign while retaining the coverage and statistical information needed for engineering decisions.

The project supports that decision by combining constrained selection with experimental-design information and a separate statistical validation step. It produces reviewable evidence rather than automatically deleting tests.

## Data and what one experiment means

The public [UCI Condition monitoring of hydraulic systems](https://archive.ics.uci.edu/dataset/447) dataset, DOI [10.24432/C5CW21](https://doi.org/10.24432/C5CW21), is attributed to Helwig, Pignanelli and Schütze (2015), CC BY 4.0. The source contains 2,205 measured hydraulic-rig cycles of 60 seconds each. A cycle is a repeated load sequence, not an independent rig asset or a wall-clock timestamp.

Four component conditions vary:

| Factor | Levels | Meaning |
|---|---|---|
| Cooler | 3, 20, 100% | Cooler condition |
| Valve | 73, 80, 90, 100% | Valve switching condition |
| Pump | 0, 1, 2 | Leakage severity class |
| Accumulator | 90, 100, 115, 130 bar | Accumulator condition pressure |

The source also provides a stability flag. The project excludes 756 cycles flagged as not yet stable and retains 1,449 stable cycles spanning 144 setting combinations. These are component/fault conditions, not engine speed/load operating points. The public data are an engineering benchmark, not Volvo measurements.

Seventeen sensor channels include pressures, motor power, flow, temperatures, vibration and virtual efficiency signals. Ingestion extracts each channel's per-cycle mean and population standard deviation, giving 34 summary features. All are retained in the processed artifact. The current response-model benchmark uses five means: PS1 pressure, FS1 flow, TS1 temperature, VS1 vibration and EPS1 motor power. It does not use all 34 features as regression inputs: the predictors are the known component settings.

## Architecture and workflow

```text
Measured source ZIP + source hash
    → validate metadata and sensor values
    → per-cycle sensor summaries in Parquet
    → exclude unstable cycles
    → split by complete condition combination
    → training candidates and requirements
    → minimum-cover MILP
    → rank-aware information augmentation
    → choose available measured repeats
    → fit identical response-model family for each baseline
    → held-out error + uncertainty + release decision
    → dashboard, traceability, schedule and audit exports
```

The later development study branches from the original training partition. Its three inner folds never include the original held-out cycles. The original benchmark had already been evaluated; the study excludes those holdout observations rather than using them again to choose a replacement plan.

## Methods you should be able to explain

**Requirement coverage.** The demonstrator requires coverage of all 14 individual factor levels and 73 observed pairs of factor levels: 87 experimental requirements. A requirement such as cooler=20 and valve=90 is a coverage objective. It is not a safety limit or a legally mandated test. One configuration covers several requirements at once.

**Mixed-integer linear programming (MILP).** Each candidate setting has a binary include/exclude variable. The objective minimises the number of settings while ensuring each declared requirement is covered at least once. SciPy's HiGHS interface solves the cover problem and reports solver status and gap. The minimum-cover seed is distinct from the larger user-chosen information budget.

**Design of Experiments (DoE).** Coverage tells us whether conditions appear; it does not tell us whether model effects can be estimated well. The response model uses categorical main effects and two-factor interactions, producing 48 design columns. The planner first adds directions to improve rank, then greedily improves the regularised information matrix determinant. This is a D-optimal-inspired heuristic; global campaign optimality is not claimed.

**Representative repeats.** Within a selected setting, the requested number of measured cycles is selected at evenly spaced source positions. Responses do not influence selection. Repeated cycles may still be correlated; repeat count does not constitute a reliability or power calculation.

**Ridge response modelling.** A fixed Ridge model with alpha=1 and an unpenalised intercept predicts five sensor-response means from the condition settings. The full-history, reduced-plan and random-plan models use the same model family and final holdout. The fixed penalty's relative effect changes with sample size; investigating sample-size-aware regularisation belongs in future development validation.

**Leakage control.** Randomly splitting individual cycles could put repeats of the same setting in both train and test. RigPlan instead isolates the complete four-factor combination. The original split has 108 training combinations and 36 unseen holdout combinations. This controls one important leakage route but does not establish future-time or cross-rig generalisation.

**Uncertainty quantification.** Each response's error is normalised by its training standard deviation. Errors are averaged within combinations and then equally across combinations and responses. A paired bootstrap resamples condition combinations 2,000 times to estimate the reduced-minus-full error interval. The +0.03 margin is illustrative and applies to the average, not individual engineering acceptance.

**Redundancy review.** A flag requires consecutive available training records with the same setting and an RMS response change below 0.02 training standard deviations. There are 327 flags in the original partition. Flags identify review candidates, not 327 dispensable tests.

**Sequencing.** A nearest-neighbour and open-path 2-opt heuristic reorders selected settings using equal-cost factor changes. Transition time, safety and warmup are not recorded, so the project reports change counts rather than invented setup savings. This ordering is a planning aid; actual execution may require randomisation or blocking to manage drift.

## Actual results and their interpretation

| Original holdout benchmark | Result |
|---|---:|
| Stable training / held-out cycles | 1,089 / 360 |
| Training / held-out combinations | 108 / 36 |
| Reduced plan | 60 settings × 3 repeats = 180 cycles |
| Smaller historical training subset | 83.47% |
| Declared coverage | 87/87 |
| Design rank | 48/48 |
| Full-history normalised MAE | 0.2945 |
| Reduced-plan normalised MAE | 0.3998 |
| Mean of 20 equal-size random plans | 0.4099 |
| Reduced-minus-full bootstrap interval | [0.0409, 0.1646] |
| Original information-preservation gate | FAIL |

The reduced plan's mean error is slightly below the random-plan mean, but statistical superiority has not been established. It is substantially worse than the full-history model. The correct release decision is to retain the reference campaign. Rank and complete experimental coverage alone do not justify test removal.

The follow-up study compares 50%, 75% and 100% of eligible settings, each with 3, 6 or 10 repeats, using three-fold grouped cross-validation within the training partition. The smallest shortlisted scenario under the exploratory +0.03 screen retains all 108 settings with six repeats: **648 projected cycles**, a **40.50% smaller historical subset**. Its development mean error increase is 0.0055 and descriptive bootstrap upper bound is 0.0189.

This is a development candidate, not a validated 40.5% physical-test reduction. Nine scenarios were compared; winner intervals are not post-selection confirmatory evidence. The candidate has not been evaluated on a new independent campaign. The evidence suggests investigating repeat reduction before condition removal for this benchmark; it does not establish a universal rule.

