# Databricks notebook source
"""Azure Databricks job entry point; validate in your own workspace before production."""
from pathlib import Path
import re
import json
from pyspark.sql import functions as F
from rigplan.data import ingest
from rigplan.pipeline import run

dbutils.widgets.text('root', '/Volumes/main/rigplan/artifacts')
dbutils.widgets.text('catalog', 'main')
dbutils.widgets.text('schema', 'rigplan')
root = Path(dbutils.widgets.get('root'))
catalog = dbutils.widgets.get('catalog')
schema = dbutils.widgets.get('schema')
if not all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value) for value in [catalog, schema]):
    raise ValueError('Use simple catalog/schema identifiers')
if not str(root).startswith('/Volumes/'):
    raise ValueError('Stage data in a Unity Catalog Volume')

# COMMAND ----------
# Bronze: preserve source ZIP in Volume and persist source lineage beside parsed records.
# Pre-stage data/raw/hydraulic.zip for workspaces without public internet egress.
frame = ingest(root)
provenance = json.loads((root/'data/processed/provenance.json').read_text())
bronze = spark.createDataFrame(frame).withColumn('source_sha256', F.lit(provenance['archive_sha256'])).withColumn('ingested_at', F.current_timestamp())
namespace = f'{catalog}.{schema}'
spark.sql(f'CREATE SCHEMA IF NOT EXISTS {namespace}')
bronze.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').saveAsTable(f'{namespace}.bronze_cycles')

# COMMAND ----------
silver = bronze.filter(F.col('unstable') == 0)
assert silver.select('cycle_id').distinct().count() == silver.count()
silver.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').saveAsTable(f'{namespace}.silver_stable_cycles')

# COMMAND ----------
# Small-data optimisation executes on driver; distributed ingestion is separate.
summary = run(root, budget=60, replicates=3)
for file, table in [('selected_cycles.csv', 'gold_selected_cycles'), ('requirements_traceability.csv', 'gold_requirements'), ('split_manifest.csv', 'gold_partitions')]:
    gold = spark.read.option('header', 'true').option('inferSchema', 'true').csv(str(root/'reports'/file))
    gold.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').saveAsTable(f'{namespace}.{table}')
spark.createDataFrame([{'summary_json': json.dumps(summary), 'source_sha256': provenance['archive_sha256']}]).write.format('delta').mode('overwrite').saveAsTable(f'{namespace}.gold_benchmark')
dbutils.notebook.exit(json.dumps({'selected_cycles': summary['selected_cycles'], 'validation_passed': summary['noninferiority_passed']}))
