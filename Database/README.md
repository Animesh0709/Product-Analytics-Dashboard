# Database/

`analytics.db` is intentionally NOT shipped in this repository/zip (it's a
100MB+ generated artifact). It is created automatically the first time you
run either:

```bash
python Dashboard/database.py
# or simply:
streamlit run Dashboard/streamlit_app.py
```

`Dashboard/database.py` imports `Dataset/user_events.csv` into this SQLite
database and builds indexes on the columns used across `sql_engine.py`.
