"""Run with: streamlit run app.py"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import streamlit as st

from rigplan.data import FACTORS, OUTCOMES, SENSORS
from rigplan.design import minimum_cover, plan, representative_cycles, requirements
from rigplan.pipeline import candidate_settings, split_data
from rigplan.schedule import sequence

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="RigPlan | Experimental intelligence", page_icon="◈", layout="wide")
st.markdown("""<style>
.block-container{padding-top:4.5rem;max-width:1450px}h1{letter-spacing:-1.8px;font-weight:650!important}
[data-testid=stMetric]{background:#14232f;border:1px solid #29404e;border-radius:12px;padding:16px}
[data-testid=stMetricValue]{color:#8be0b4} .eyebrow{color:#8be0b4;letter-spacing:3px;font-size:12px}
.intro{color:#a6b8c5;font-size:18px;max-width:860px}.note{border-left:3px solid #8be0b4;padding:12px 20px;background:#14232f;color:#b9ccd6}
@media(max-width:900px){[data-testid="stHorizontalBlock"]{flex-wrap:wrap}[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 100%;width:100%;min-width:0}[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"])>[data-testid="stColumn"]{flex:1 1 45%;width:45%}[data-testid="stMetricValue"]{font-size:1.7rem}}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="eyebrow">RIGPLAN / EXPERIMENTAL INTELLIGENCE</div>', unsafe_allow_html=True)
st.title("More evidence. Fewer rig cycles.")
st.markdown('<p class="intro">Explore measured test-rig data, assemble a requirement-aware campaign, and audit the evidence behind every selected experiment.</p>', unsafe_allow_html=True)

if not (ROOT / "reports/summary.json").exists():
    st.info("Prepare the benchmark first: python -m rigplan.cli benchmark")
    st.stop()

@st.cache_data
def load(fingerprint):
    return pd.read_parquet(ROOT / "data/processed/cycles.parquet"), json.loads((ROOT / "reports/summary.json").read_text())

data, summary = load(((ROOT / 'reports/summary.json').stat().st_mtime_ns, (ROOT / 'data/processed/cycles.parquet').stat().st_mtime_ns))
train, holdout = split_data(data)
with st.sidebar:
    st.header("◈ RigPlan")
    st.caption("TEST FACILITY / PLANNING LAB")
    st.divider()
    st.markdown("**Measured public rig data**")
    st.caption("UCI · Hydraulic systems · CC BY 4.0")
    st.metric("Recorded cycles", f"{len(data):,}")
    st.metric("Stable cycles", f"{summary['stable_rows']:,}")
    st.caption("Historical replay. No live rig is connected.")
    st.link_button("Dataset & attribution ↗", "https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems")
    st.caption("Independent portfolio project. No Volvo affiliation or proprietary data.")

tabs = st.tabs(["Campaign overview", "Design a campaign", "Evidence & validation", "Cycle replay", "Data & deployment"])
with tabs[0]:
    a,b,c,d = st.columns(4)
    a.metric("Subset reduction", f"{summary['retrospective_cycle_reduction_pct']:.1f}%")
    b.metric("Selected cycles", f"{summary['selected_cycles']} / {summary['historical_training_cycles']}")
    c.metric("Declared coverage", f"{summary['covered_requirements']} / {summary['total_requirements']}")
    d.metric("Quality gate", "PASS" if summary['noninferiority_passed'] else "REVIEW")
    st.markdown("<p class='note'>Retrospective selection from a hydraulic rig. Coverage refers to declared factor levels and observed pairs. Physical savings and product compliance require prospective validation.</p>", unsafe_allow_html=True)
    left,right = st.columns([1.5,1])
    with left:
        st.subheader("The experimental landscape")
        st.caption("Stable cycle counts by cooler and valve settings. Other factors vary within each cell.")
        st.bar_chart(data.loc[data.unstable.eq(0)].groupby(["cooler", "valve"]).size().unstack(), stack=False)
    with right:
        st.subheader("From requirement to evidence")
        st.markdown("1. **Ingest** — validate real cycle records and isolate unstable operation.\n2. **Cover** — solve a binary requirement-cover problem.\n3. **Inform** — add settings using regularised D-optimal design.\n4. **Challenge** — evaluate unseen combinations against full and random baselines.")
        st.caption(f"{summary['excluded_unstable']} unstable cycles excluded. Holdout: {summary['holdout_settings']} combinations, untouched during selection.")
    st.download_button("Download benchmark report", (ROOT / "reports/BENCHMARK.md").read_text(), "BENCHMARK.md")

with tabs[1]:
    st.subheader("Build a traceable experiment plan")
    st.caption("Uses training settings only. Preview changes do not alter the saved benchmark or its validation result.")
    col1,col2,col3 = st.columns(3)
    reps = col1.number_input("Measured repeats per setting", 1, 10, 3)
    pairwise = col2.toggle("Cover observed factor pairs", value=True)
    candidates = candidate_settings(train, reps)
    cover_seed, cover_status = minimum_cover(candidates, pairwise)
    budget = col3.slider("Setting budget", len(cover_seed), len(candidates), min(60, len(candidates)))
    indices, trace, diagnostics = plan(candidates, budget, pairwise)
    chosen = representative_cycles(train, candidates.iloc[indices].condition_id.tolist(), reps)
    a,b,c = st.columns(3)
    a.metric("Physical cycle count in plan", len(chosen))
    b.metric("Cycle duration only", f"{len(chosen) / 60:.1f} h")
    c.metric("Design rank", f"{diagnostics['unregularised_rank']} / {diagnostics['model_columns']}")
    if diagnostics['unregularised_rank'] < diagnostics['model_columns']:
        st.warning("This plan is rank deficient for the interaction model. Coverage alone does not make every model effect estimable.")
    st.caption("Duration assumes 60-second recorded cycles; excludes warmup, transitions and setup. Repeat count is a scenario, not a reliability guarantee.")
    left,right = st.columns([1,1.3])
    with left:
        st.markdown("**Selected configurations**")
        st.dataframe(candidates.iloc[indices][FACTORS + ["size"]], hide_index=True, width='stretch')
    with right:
        st.markdown("**Requirement traceability**")
        st.dataframe(trace, hide_index=True, width='stretch')
    st.download_button("Export selected cycle manifest", chosen[["cycle_id", "condition_id"] + FACTORS].to_csv(index=False), "campaign_cycles.csv", "text/csv")
    st.download_button("Export coverage matrix", trace.to_csv(index=False), "requirements.csv", "text/csv")
    schedule = sequence(candidates.iloc[indices])
    with st.expander("Sequence the campaign to reduce setting changes"):
        st.caption("Nearest-neighbour + open-path 2-opt heuristic; equal weight for each factor change. Safety, warmup and transition constraints require engineering input. No optimality claim.")
        st.metric("Factor changes between settings", int(schedule.factor_changes_from_previous.sum()))
        st.dataframe(schedule, hide_index=True, width='stretch')
        st.download_button("Export scheduled settings", schedule.to_csv(index=False), "campaign_schedule.csv", "text/csv")

with tabs[2]:
    st.subheader("Does the smaller plan preserve useful information?")
    st.caption("Fixed ridge model with categorical main effects and pair interactions. Lower prediction error is better; no holdout tuning.")
    metrics = pd.read_csv(ROOT / "reports/outcome_metrics.csv")
    normalised = metrics.set_index("outcome")[["full_MAE", "optimised_MAE", "random_mean_MAE"]].div(metrics.set_index("outcome").training_std, axis=0)
    st.bar_chart(normalised, stack=False)
    st.dataframe(metrics, hide_index=True, width='stretch')
    ci = summary["error_difference_bootstrap"]
    st.info(f"Average normalised MAE difference vs full: {ci['mean']:.4f}; paired condition-bootstrap 95% interval [{ci['lower_95']:.4f}, {ci['upper_95']:.4f}]. Predeclared margin: +0.030. Gate: {'PASS' if summary['noninferiority_passed'] else 'FAIL'}. This is an average-response gate, not individual acceptance.")
    if not summary['noninferiority_passed']:
        st.error("Decision: retain the reference campaign. The reduced plan is not approved to replace it. Revise using development data, then validate independently.")
    st.caption(f"Same held-out {ci['groups']} configurations for all methods. {summary['random_runs']} random plans with equal settings and repeats. Bootstrap uncertainty is conditional on one split; repeat cycles are dependent.")
    with st.expander("Assumptions and failure modes", expanded=True):
        for item in summary["limitations"]:
            st.markdown(f"- {item}")
    st.download_button("Download per-response metrics", metrics.to_csv(index=False), "outcome_metrics.csv")
    if (ROOT/'reports/development_study.csv').exists():
        st.subheader("Budget and repeat sensitivity — development data only")
        study = pd.read_csv(ROOT/'reports/development_study.csv')
        st.caption("Three-fold cross-validation inside the original training partition. Compares nine budget/repeat scenarios; the original holdout is excluded. Intervals are descriptive after scenario comparison.")
        st.scatter_chart(study, x='projected_cycles', y='development_normalised_MAE', color='repeats')
        st.dataframe(study[['projected_settings', 'repeats', 'projected_cycles', 'development_normalised_MAE', 'delta', 'upper_95', 'within_exploratory_margin']], hide_index=True, width='stretch')
        st.download_button("Download development sensitivity study", study.to_csv(index=False), "development_study.csv", "text/csv")
        st.caption("Any shortlisted scenario is a candidate for independent validation, not a released replacement campaign.")

with tabs[3]:
    st.subheader("Historical cycle replay")
    st.caption("Browse recorded cycle summaries in acquisition order. Cycle IDs are not wall-clock timestamps.")
    cycle = st.slider("Cycle ID", 1, len(data), 1000)
    row = data.loc[data.cycle_id.eq(cycle)].iloc[0]
    cols = st.columns(4)
    for col,factor in zip(cols,FACTORS):
        col.metric(factor.capitalize(), int(row[factor]))
    st.caption(f"Stability: {'not yet stable — excluded' if row.unstable else 'stable'} · Condition {row.condition_id} · Run {row.run_id}")
    signal = st.selectbox("Sensor", list(SENSORS), index=6)
    window = data.loc[data.cycle_id.between(max(1, cycle-50), min(len(data), cycle+50))].set_index("cycle_id")
    st.line_chart(window[[f"{signal}_mean"]], y_label=SENSORS[signal])
    st.caption("Per-cycle means, not a raw waveform. Replay is static; no hardware connection or streaming latency claim.")
    review = pd.read_parquet(ROOT / "reports/redundancy_review.parquet")
    st.markdown(f"**{summary['near_repeat_review_flags']} near-repeat review flags** in the training partition")
    st.caption("Same consecutive settings and RMS response change below 0.02 training standard deviations. Flags support engineering review; none are automatically deleted or used to select the plan.")
    st.dataframe(review.loc[review.review_repeat, ["cycle_id", "condition_id", "response_distance_to_previous", "selected"]].head(100), hide_index=True)

with tabs[4]:
    st.subheader("An auditable path from on-premise files to analytics")
    st.code("On-prem rig files → Bronze raw + SHA-256\n                 → Silver cycle summaries + stability checks\n                 → Gold plans + coverage + holdout evaluation\n                 → Engineering review → Prospective validation")
    provenance = json.loads((ROOT / "data/processed/provenance.json").read_text())
    st.json(provenance)
    st.markdown("**Databricks:** the repository includes a parameterised Delta ingestion notebook, a job bundle and validation notes. Cloud deployment requires your Azure workspace; it has not been executed in Azure.")
    st.markdown("**Domain transfer:** replace the illustrative factor/pair requirements with signed requirements, measured acceptance criteria, mandatory repeats, safety constraints and transition costs before a production pilot.")
    st.download_button("Download audit summary", json.dumps(summary, indent=2), "summary.json", "application/json")

