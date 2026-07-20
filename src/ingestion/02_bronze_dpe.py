# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze — DPE (S2): schema drift + quarantine
# MAGIC The weekly extracts ADD columns partway through history
# MAGIC (`etiquette_ges`, `cout_chauffage`). `addNewColumns` lets the stream
# MAGIC fail-fast on first sight of new columns, evolve the schema, and resume
# MAGIC on restart — which is why the write is wrapped in a retry.
# MAGIC
# MAGIC Bronze stays permissive (everything lands, strings allowed); rows that
# MAGIC can't even be parsed go to `_rescued_data`. Business-rule quarantine
# MAGIC (bad commune codes, negative surfaces) happens in Silver — but we
# MAGIC MEASURE the damage here, because you can't fix what you don't count.

# COMMAND ----------
from pyspark.sql import functions as F

CATALOG = "energy_pulse"
LANDING = f"/Volumes/{CATALOG}/landing/landing"
BRONZE = f"{CATALOG}.bronze"
CKPT = f"/Volumes/{CATALOG}/landing/_checkpoints"

# COMMAND ----------
def run_dpe_stream():
    return (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .option("cloudFiles.schemaLocation", f"{CKPT}/dpe_schema")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("rescuedDataColumn", "_rescued_data")
        .load(f"{LANDING}/dpe/weekly/")
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_extract_week",
                    F.regexp_extract("_source_file", r"(\d{4}-W\d{2})", 1))
        .writeStream
        .option("checkpointLocation", f"{CKPT}/dpe")
        .option("mergeSchema", "true")
        .trigger(availableNow=True)
        .toTable(f"{BRONZE}.dpe_raw")
        .awaitTermination())

try:
    run_dpe_stream()
except Exception as e:  # schema evolved -> restart once, as designed
    if "UnknownFieldException" in str(type(e)) or "new columns" in str(e):
        print("Schema evolution detected — restarting stream")
        run_dpe_stream()
    else:
        raise

# COMMAND ----------
# MAGIC %md ## Data-quality measurement (feeds the DQ dashboard later)
# COMMAND ----------
dq = spark.sql(f"""
  SELECT _extract_week,
         COUNT(*)                                             AS rows,
         COUNT(*) - COUNT(DISTINCT numero_dpe)                AS dup_or_rediag,
         SUM(CASE WHEN surface_habitable < 0 THEN 1 END)      AS neg_surface,
         SUM(CASE WHEN code_commune NOT RLIKE '^[0-9]{{5}}$'
                  THEN 1 END)                                 AS bad_commune,
         SUM(CASE WHEN _rescued_data IS NOT NULL THEN 1 END)  AS rescued
  FROM {BRONZE}.dpe_raw GROUP BY 1 ORDER BY 1
""")
dq.write.mode("overwrite").saveAsTable(f"{BRONZE}.dpe_dq_metrics")
display(dq)
