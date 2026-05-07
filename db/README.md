# Database

Local database name: `uni_pass`

## Create from scratch

```bash
createdb -h localhost -p 5432 uni_pass
psql -h localhost -p 5432 -d uni_pass -f db/schema.sql
```

## Required PostgreSQL extensions

The schema enables these extensions:

- `pgcrypto`
- `pg_trgm`
- `unaccent`
- `vector` from `pgvector`

On macOS/Homebrew, install `pgvector` first if `CREATE EXTENSION vector` fails:

```bash
brew install pgvector
```
