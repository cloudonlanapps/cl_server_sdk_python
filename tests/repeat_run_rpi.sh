LOG_FILE=run_all_rpi.log

# Clear the log file before starting
: > "$LOG_FILE"

for i in {1..1}; do
  echo "==================================================" >> "$LOG_FILE"
  echo "Run $i started at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
  echo "==================================================" >> "$LOG_FILE"

  uv run pytest tests/test_integration/test_full_embedding_flow.py \
    --auth-url=http://192.168.0.105:8010 \
    --compute-url=http://192.168.0.105:8012 \
    --store-url=http://192.168.0.105:8011 \
    --username=admin \
    --password=admin >> "$LOG_FILE" 2>&1

  echo "Run $i finished at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
  echo >> "$LOG_FILE"
grep -E "[0-9]+ passed|[0-9]+ failed|[0-9]+ error" "$LOG_FILE" | tail -n 1
done

# Show the LAST pytest summary line (passed / failed count)
grep -E "[0-9]+ passed|[0-9]+ failed|[0-9]+ error" "$LOG_FILE" 

