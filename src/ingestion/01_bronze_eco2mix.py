# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze — éCO2mix (S1)
# MAGIC Two paths into the same Bronze table:
# MAGIC 1. **Backfill**: yearly `;`-separated CSV archives (batch Auto Loader)
# MAGIC 2. **Live**: API JSON pulls via Structured Streaming — overlapping pulls
# MAGIC    and late corrected points are kept AS-IS in Bronze (dedup is Silver's
# MAGIC    job; Bronze is an immutable audit log of what the source sent).

# COMMAND ----------
from pyspark.sql import functions as F

CATALOG = "energy_pulse"
LANDING = f"/Volumes/{CATALOG}/landing/landing"
BRONZE = f"{CATALOG}.bronze"
CKPT = f"/Volumes/{CATALOG}/landing/_checkpoints"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {BRONZE}")

# COMMAND ----------
# MAGIC %md ## 1. Backfill — yearly archives (run once, rerunnable)

# COMMAND ----------
(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("sep", ";")
    .option("header", "true")
    .option("cloudFiles.schemaLocation", f"{CKPT}/eco2mix_archive_schema")
    .option("cloudFiles.inferColumnTypes", "true")
    .load(f"{LANDING}/eco2mix/archive/")
    .withColumn("_ingested_at", F.current_timestamp())
    .withColumn("_source_file", F.col("_metadata.file_path"))
    .writeStream
    .option("checkpointLocation", f"{CKPT}/eco2mix_archive")
    .trigger(availableNow=True)          # batch semantics, streaming engine:
    .toTable(f"{BRONZE}.eco2mix_raw"))   # rerun ingests only NEW files

# COMMAND ----------
# MAGIC %md ## 2. Live API pulls — continuous stream
# MAGIC JSON pulls contain a `records` array -> explode after load.
# MAGIC Note `trigger(availableNow)` here too for scheduled-job mode; switch to
# MAGIC `processingTime="1 minute"` on an always-on cluster to demo true streaming.

# COMMAND ----------
raw = (spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", f"{CKPT}/eco2mix_api_schema")
    .option("cloudFiles.inferColumnTypes", "true")
    .load(f"{LANDING}/eco2mix/api/"))

(raw.select(
        F.col("pull_timestamp"),
        F.explode("records").alias("r"),
        F.current_timestamp().alias("_ingested_at"),
        F.col("_metadata.file_path").alias("_source_file"))
    .select("pull_timestamp", "r.*", "_ingested_at", "_source_file")
    .writeStream
    .option("checkpointLocation", f"{CKPT}/eco2mix_api")
    .trigger(availableNow=True)
    .toTable(f"{BRONZE}.eco2mix_api_raw"))

# COMMAND ----------
# MAGIC %md ## Sanity checks (promote to real tests later)
# COMMAND ----------
display(spark.sql(f"""
  SELECT 'archive' src, COUNT(*) n, MIN(date_heure) mn, MAX(date_heure) mx
  FROM {BRONZE}.eco2mix_raw
  UNION ALL
  SELECT 'api', COUNT(*), MIN(date_heure), MAX(date_heure)
  FROM {BRONZE}.eco2mix_api_raw
"""))
