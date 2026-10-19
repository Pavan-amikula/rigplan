# RigPlan benchmark

Reproduce: `rigplan benchmark --budget 60 --replicates 3`. Seed 42; no holdout tuning.

- Measured cycles: 2,205; excluded unstable: 756.
- Training/holdout settings: 108/36; disjoint by all four settings.
- Selected 180 of 1089 historical training cycles (83.5% smaller subset).
- Declared requirement coverage: 87/87.
- Normalised MAE: full 0.2945; optimised 0.3998; random mean 0.4099. Lower is better.
- Paired group-bootstrap difference (optimised minus full): 0.1053, 95% interval [0.0409, 0.1646]. Predeclared margin 0.03; FAIL.
- D-optimal design rank: 48/48.

The gate measures average error across five responses and does not certify individual-response acceptance. A pass is conditional evidence; a failure means the reduced plan needs more work.

## Limits

- Retrospective evidence on one hydraulic rig; no prospective savings or Volvo validation.
- Requirements represent factor/pair coverage, not legislation or measured product acceptance limits.
- Holdout isolates settings, not rig assets or time; drift and serial dependence remain.
- Outcome means discard transient dynamics; three repeats do not establish reliability.
- Motor energy omits auxiliary loads, warmup and setup. No carbon claim.
- Bootstrap groups are condition combinations; uncertainty is conditional on one split and fixed model.
