# Template for the local database passwords.
#
# 1. Copy this file to secrets.sh (git ignores secrets.sh, so it is never committed):
#        cp secrets.example.sh secrets.sh
# 2. Open secrets.sh and replace the placeholders with your real passwords.
# 3. Load it into your Git Bash terminal (after activating the virtual environment):
#        source secrets.sh
#
# Every program started from that terminal afterwards (e.g. the project's Python
# scripts) inherits these variables. Use `source`, not `bash secrets.sh`: running it
# with `bash` sets the variables in a separate shell that disappears straight away.

# Password of the PostgreSQL "postgres" user (read automatically by PostgreSQL/psycopg)
export PGPASSWORD='your-postgres-password'

# Password of the Neo4j "neo4j" user (read by the project's scripts)
export NEO4J_PASSWORD='your-neo4j-password'
