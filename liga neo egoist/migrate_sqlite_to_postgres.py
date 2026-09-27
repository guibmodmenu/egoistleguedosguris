"""One-time, guarded import of the legacy SQLite database into PostgreSQL.

Dry-run is the default. Use --apply only after reviewing the counts and backing up
both databases. This script never runs as part of application startup/redeploy.
"""
import argparse
import os
import sys

from sqlalchemy import MetaData, Table, create_engine, func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

# Import all ORM models so db.metadata contains the complete application schema.
import models  # noqa: F401
from config import BASE_DIR, DATABASE_URI
from models import db


def is_postgresql(url):
    return url.startswith(('postgresql://', 'postgresql+psycopg2://'))


def validate_source_schema(source_engine, metadata):
    source_inspector = inspect(source_engine)
    source_names = set(source_inspector.get_table_names()) - {'sqlite_sequence'}
    model_names = set(metadata.tables)
    unknown = sorted(source_names - model_names)
    if unknown:
        raise ValueError(
            'The SQLite database contains tables not represented by this version '
            f'of the app: {", ".join(unknown)}. Migration stopped to avoid omitting data.'
        )

    reflected = MetaData()
    source_tables = {}
    counts = {}
    for table in metadata.sorted_tables:
        if table.name not in source_names:
            continue
        source_table = Table(table.name, reflected, autoload_with=source_engine)
        source_tables[table.name] = source_table
        source_columns = {column.name for column in source_table.columns}
        target_columns = {column.name for column in table.columns}
        source_only = sorted(source_columns - target_columns)
        if source_only:
            raise ValueError(
                f"Table '{table.name}' has SQLite-only columns: {', '.join(source_only)}. "
                'Migration stopped rather than discard them.'
            )
        missing = [column for column in table.columns if column.name not in source_columns]
        required_missing = [
            column.name for column in missing
            if not column.nullable and column.default is None
            and column.server_default is None
            and not (column.primary_key and column.autoincrement is not False)
        ]
        if required_missing:
            raise ValueError(
                f"Table '{table.name}' is missing required columns: "
                f"{', '.join(required_missing)}. Migrate the schema before copying data."
            )
        with source_engine.connect() as connection:
            counts[table.name] = connection.execute(
                select(func.count()).select_from(source_table)
            ).scalar_one()
    return source_tables, counts


def target_row_counts(target_engine, metadata):
    existing_names = set(inspect(target_engine).get_table_names())
    counts = {}
    with target_engine.connect() as connection:
        for table in metadata.sorted_tables:
            if table.name in existing_names:
                counts[table.name] = connection.execute(
                    select(func.count()).select_from(table)
                ).scalar_one()
    return counts


def ensure_target_empty(target_engine, metadata):
    populated = {name: count for name, count in target_row_counts(target_engine, metadata).items() if count}
    if populated:
        summary = ', '.join(f'{name}={count}' for name, count in sorted(populated.items()))
        raise ValueError(
            'The PostgreSQL database already contains application data '
            f'({summary}). This importer never merges or overwrites records.'
        )


def sync_postgres_sequences(connection, metadata):
    quote = connection.dialect.identifier_preparer.quote
    for table in metadata.sorted_tables:
        column = getattr(table, 'autoincrement_column', None)
        if column is None:
            continue
        sequence_name = connection.execute(
            text('SELECT pg_get_serial_sequence(:table_name, :column_name)'),
            {'table_name': table.name, 'column_name': column.name},
        ).scalar_one_or_none()
        if not sequence_name:
            continue
        table_name = quote(table.name)
        column_name = quote(column.name)
        maximum = connection.execute(
            text(f'SELECT MAX({column_name}) FROM {table_name}')
        ).scalar_one_or_none()
        if maximum is not None:
            connection.execute(
                text('SELECT setval(CAST(:sequence_name AS regclass), :value, true)'),
                {'sequence_name': sequence_name, 'value': maximum},
            )


def main():
    parser = argparse.ArgumentParser(
        description='Import all known records from the local SQLite database into an empty PostgreSQL database.'
    )
    parser.add_argument(
        '--source',
        default=os.path.join(BASE_DIR, 'database', 'league.db'),
        help='SQLite source file (default: database/league.db)',
    )
    parser.add_argument(
        '--apply', action='store_true',
        help='perform the import; without this flag, run a read-only dry-run',
    )
    parser.add_argument('--batch-size', type=int, default=500)
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error('--batch-size must be greater than zero')
    if not is_postgresql(DATABASE_URI):
        parser.error('DATABASE_URL must point to PostgreSQL; no data was changed.')
    source_path = os.path.abspath(args.source)
    if not os.path.isfile(source_path):
        parser.error(f'SQLite source file does not exist: {source_path}')

    source_engine = create_engine(f'sqlite:///{source_path}')
    target_engine = create_engine(DATABASE_URI, pool_pre_ping=True)
    try:
        # Establish both connections and validate every source table/column before any write.
        with target_engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        with source_engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        source_tables, source_counts = validate_source_schema(source_engine, db.metadata)
        ensure_target_empty(target_engine, db.metadata)

        total_rows = sum(source_counts.values())
        print(f'SQLite source: {source_path}')
        print('PostgreSQL target: connection validated (URL hidden)')
        print('Rows by table:')
        for table in db.metadata.sorted_tables:
            if table.name in source_counts:
                print(f'  {table.name}: {source_counts[table.name]}')
        print(f'Total rows to import: {total_rows}')

        if not args.apply:
            print('DRY RUN ONLY: no tables or records were written. Review counts, back up the databases, then rerun with --apply.')
            return 0

        # create_all creates missing tables only; it does not drop or rewrite existing records.
        db.metadata.create_all(target_engine)
        ensure_target_empty(target_engine, db.metadata)

        with source_engine.connect() as source_connection, target_engine.begin() as target_connection:
            for table in db.metadata.sorted_tables:
                source_table = source_tables.get(table.name)
                if source_table is None or source_counts.get(table.name, 0) == 0:
                    continue
                result = source_connection.execute(select(source_table))
                target_column_names = {column.name for column in table.columns}
                while True:
                    rows = result.mappings().fetchmany(args.batch_size)
                    if not rows:
                        break
                    payload = [
                        {key: value for key, value in row.items() if key in target_column_names}
                        for row in rows
                    ]
                    target_connection.execute(table.insert(), payload)
            sync_postgres_sequences(target_connection, db.metadata)

        print('Import complete. All copied records were committed in one PostgreSQL transaction.')
        return 0
    except ValueError as error:
        print(f'Migration stopped safely: {error}', file=sys.stderr)
        return 2
    except SQLAlchemyError as error:
        # Avoid printing exception details, which can include connection metadata.
        print(
            f'Migration failed safely ({type(error).__name__}); the active transaction was rolled back. '
            'Check database connectivity and schema, then retry after review.',
            file=sys.stderr,
        )
        return 1
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
