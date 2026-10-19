# Research basis and limits

Primary sources checked on 19 October 2026. This independent portfolio project studies rig-test planning with a public hydraulic benchmark. It is not affiliated with Volvo and does not use proprietary Volvo data.

## Dataset choice and provenance

[UCI: Condition monitoring of hydraulic systems, dataset 447](https://archive.ics.uci.edu/dataset/447) describes 2,205 experimentally recorded hydraulic-rig cycles of 60 seconds each. Four component conditions vary: cooler efficiency, valve switching behavior, internal pump leakage, and accumulator pressure. Pressure, flow and temperature measurements connect this benchmark to industrial test-rig analysis. UCI reports no missing values.

The profile labels are:

| Component or flag | Published values |
| --- | --- |
| Cooler efficiency (%) | 3, 20, 100 |
| Valve condition (%) | 73, 80, 90, 100 |
| Pump internal leakage | 0 = none, 1 = weak, 2 = severe |
| Accumulator pressure (bar) | 90, 100, 115, 130 |
| Stability flag | 0 = stable; 1 = static conditions may not yet have been reached |

Source and attribution: Helwig, N., Pignanelli, E., and Schuetze, A. (2015), *Condition monitoring of hydraulic systems*, UCI Machine Learning Repository, [DOI 10.24432/C5CW21](https://doi.org/10.24432/C5CW21). UCI licenses the dataset under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); retain attribution when sharing derived data.

## Combining test aspects through constrained selection

Our implemented formulation is a project design choice: each eligible recorded setting combination is a candidate, and a binary coverage matrix records the demonstrator requirements it exercises. Minimize the number of selected settings subject to each level and observed pair receiving at least one setting. A separately chosen repeat count determines how many measured cycles are sampled per setting. One configuration can contribute to several component-level or observed-pair requirements simultaneously. Weighted run costs and requirement-specific repeat minima would be extensions, not current capabilities.

[SciPy's `milp` reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html) specifies linear objectives, bounded linear constraints, and integrality controls. Binary decisions require integer variables **and bounds [0, 1]**; integrality alone does not make variables binary. The interface wraps HiGHS and exposes solver status, solution, objective, dual bound and MIP gap. Status 0 means an optimal solution was found; status 1 indicates an iteration or time limit; status 2 indicates infeasibility. A limited run must not be reported as proven optimal. Independently recompute constraint satisfaction after solving and retain the status and gap in exported evidence.

Implementation consequence: call an unavailable requirement infeasible rather than silently dropping it. If a heuristic is used as a fallback, identify the algorithm and verify its coverage without claiming minimum cost.

## Experimental design: useful criterion, carefully scoped

[NIST/SEMATECH: D-optimal designs](https://www.itl.nist.gov/div898/handbook/pri/section5/pri521.htm) defines D-optimality through maximizing the determinant of the information matrix `X.T @ X` for a specified model. The criterion reduces generalized coefficient-estimate variance under that model. Its usefulness depends on the assumed model and feasible candidate settings. Computer searches need not find the global D-optimum; randomization is recommended before physically executing the chosen runs.

Project interpretation: use a declared factor coding and a declared model, and expose model rank and conditioning. A greedy log-determinant selection is **D-optimal-inspired**, not a proof of D-optimality. An expression such as `logdet(X.T @ X + lambda * I)` is regularized information; its positive determinant can hide rank deficiency, so report unregularized rank separately. Model factor interactions only when the design has enough independent support. Coverage optimization and information maximization answer different questions and should be compared rather than conflated.

## Retrospective analysis is not a prospective qualification campaign

The following are methodological boundaries of this project, rather than claims that the public dataset establishes:

- Selecting already measured cycles measures retrospective compression of an archive. It does not prove those cycles could have been omitted before observing their sensor outcomes.
- Selection using measured sensor features benefits from information available only after a run. A prospective planner should select from known controllable settings, approved historical evidence, or model predictions, then validate on newly acquired runs.
- A component condition label can support a demonstrator requirement such as observing each recorded condition. It is not an engineering acceptance threshold, a safety requirement, or a regulatory compliance test.
- Covering observed factor pairs does not establish full interaction coverage or cover factor combinations absent from the archive. Count and disclose unsupported combinations rather than manufacturing rows.
- Similar sensor vectors are evidence for a reviewable redundancy candidate. A safe decision to omit a physical test also requires understanding instrumentation, load history, warm-up, drift, failure modes, repeatability, and the test's intended purpose.
- Consecutive cycles may share operating conditions. Random row splits can make validation optimistic. Keep an untouched chronological or condition-group holdout, fit preprocessing on training data only, and compare full-history, random-selection, and optimized-selection training baselines on the identical holdout. Label performance as retrospective benchmark evidence.
- A single holdout score is not a quality guarantee. Report class support, per-condition errors, and repeated baseline variability; unsupported classes should be visible. Do not select a budget by inspecting the final holdout repeatedly.
- Repetition requirements are planning constraints, not a statistical-power calculation. Establish independent variance estimates, acceptable error, and a prospective power or precision target with a domain mentor before replacing a real campaign.
- Multiplying omitted 60-second cycles by a user-supplied cost or energy rate yields an illustrative estimate. Without measured transition, setup, stabilization, fuel, power and emissions data, it is not realized factory savings or verified environmental impact.

## Local-to-Azure Databricks architecture

[Microsoft Learn: medallion lakehouse architecture](https://learn.microsoft.com/en-us/azure/databricks/lakehouse/medallion) describes bronze as preserved raw ingestion, silver as validated and cleaned data, and gold as data products serving analytics and business needs. Keeping original records supports reprocessing and auditing. Microsoft recommends building silver from bronze rather than ingesting directly into silver.

Recommended mapping for this project's migration path:

| Layer | Proposed project artifacts | Evidence to retain |
| --- | --- | --- |
| Bronze | Original UCI archive, sensor files, imported on-prem rig files | Source URI/path, SHA-256, ingestion timestamp, source cycle ID |
| Silver | Validated cycle metadata, aligned sensor summaries, condition labels | Schema version, units, sampling assumptions, quality failures, transformation version |
| Gold | Requirement catalogue, candidate matrix, selected plan, coverage and validation reports | Input fingerprint, configuration, code version, seed, solver result, approval record |

This table is an implementation recommendation inferred from Microsoft's architecture. Local files that follow this layout are a prototype; they do not establish that an Azure deployment, Spark-scale benchmark, streaming integration, access policy, or production service has been tested. Those need a connected workspace and operational verification.

## Thesis discussion and honest resume claims

Useful research questions are: how does budget affect retained predictive quality; when does pairwise coverage outperform level-only coverage; how sensitive are plans to replicate requirements and cost assumptions; and do optimized plans retain rare conditions better than equal-budget random selection?

An accurate resume claim should name the public benchmark, implemented optimization method, tested runtime, and measured result from generated reports. Reserve claims about compliance, physical test elimination, factory savings, production Azure deployment, and Volvo collaboration for work actually validated with the responsible organization.
