from collections import defaultdict, deque
import argparse
from sqlalchemy.exc import IntegrityError
import random
import inspect
from typing import Type, List, Any

from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql.sqltypes import (
    String,
    Integer,
    Boolean,
    DateTime,
    Enum as SqlEnum,
    Text,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID
import os
import enum
import domains  # domains is module contain metadata tables

faker = Faker("en_US")
DATABASE_URL = ""
os.environ["POSTGRES_HOST"] = "localhost"
engine = create_engine(DATABASE_URL or "")

COLUMN_TO_ENUM = {
    # Add more mappings if needed
}


# Global cache to track unique values per model and column
UNIQUE_VALUE_CACHE = defaultdict(lambda: defaultdict(set))


def load_existing_unique_values(session, model_class):
    unique_cols = [col.name for col in model_class.__mapper__.columns if col.unique]
    for col_name in unique_cols:
        try:
            query = session.query(getattr(model_class, col_name))
            values = {row[0] for row in query.all() if row[0] is not None}
            UNIQUE_VALUE_CACHE[model_class][col_name].update(values)
        except Exception as e:
            print(
                f"Warning: failed loading unique values for {model_class.__name__}.{col_name}: {e}"
            )


def build_dependency_graph(models: List[Type[DeclarativeBase]]) -> dict:
    graph = defaultdict(set)
    tablename_to_model = {m.__tablename__: m for m in models}

    for model in models:
        for attr in model.__mapper__.column_attrs:
            for fk in attr.columns[0].foreign_keys:
                referred_table = fk.column.table.name
                referred_model = tablename_to_model.get(referred_table)
                if referred_model:
                    graph[referred_model].add(model)
    return graph


def topological_sort_models(
    models: List[Type[DeclarativeBase]],
) -> List[Type[DeclarativeBase]]:
    graph = build_dependency_graph(models)
    in_degree = {model: 0 for model in models}
    for deps in graph.values():
        for dep in deps:
            in_degree[dep] += 1

    zero_in_degree = deque([m for m in models if in_degree[m] == 0])
    sorted_models = []

    while zero_in_degree:
        current = zero_in_degree.popleft()
        sorted_models.append(current)
        for dependent in graph.get(current, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                zero_in_degree.append(dependent)

    if len(sorted_models) != len(models):
        raise RuntimeError("Cycle detected or missing models in dependency graph.")

    return sorted_models


def get_all_models() -> List[Type[DeclarativeBase]]:
    return [
        obj
        for name, obj in inspect.getmembers(domains)
        if inspect.isclass(obj)
        and hasattr(obj, "__tablename__")
        and issubclass(obj, DeclarativeBase)
    ]


def generate_fake_value(column, model_class=None) -> Any:
    col_type = column.type
    name = column.name.lower()
    table_column_key = (
        f"{model_class.__tablename__}.{column.name}" if model_class else None
    )

    if table_column_key in COLUMN_TO_ENUM:
        enum_class = COLUMN_TO_ENUM[table_column_key]
        enum_value = random.choice(list(enum_class))
        return enum_value.value if hasattr(enum_value, "value") else str(enum_value)

    if not column.nullable:
        if isinstance(col_type, String):
            max_len = getattr(col_type, "length", None)
            if "name" in name:
                value = faker.name()
            elif "email" in name:
                value = faker.email()
            elif "phone" in name:
                value = faker.phone_number()
            elif "address" in name:
                value = faker.address()
            elif "password" in name or "hash" in name:
                value = faker.sha256()
            elif "uuid" in name or "external_id" in name:
                value = str(faker.uuid4())
            else:
                value = faker.word()
            return value[:max_len] if max_len else value

        elif isinstance(col_type, UUID):
            return str(faker.uuid4())

        elif isinstance(col_type, Integer):
            return random.randint(1, 100)

        elif isinstance(col_type, Float):
            return round(random.uniform(1.0, 1000.0), 2)

        elif isinstance(col_type, Boolean):
            return faker.boolean()

        elif isinstance(col_type, DateTime):
            return faker.date_time()

        elif isinstance(col_type, SqlEnum):
            enum_class = getattr(col_type, "enum_class", None)
            if enum_class:
                enum_members = list(enum_class)
                if enum_members:
                    chosen = random.choice(enum_members)
                    return chosen.value if hasattr(chosen, "value") else str(chosen)
                else:
                    print(f"WARNING: Enum {column.name} has no members.")
                    return faker.word()
            else:
                print(f"WARNING: No enum_class found for {column.name}.")
                return faker.word()

        elif isinstance(col_type, Text):
            return faker.text()

        else:
            print(
                f"WARNING: Unknown type for {column.name}. Defaulting to faker.word()."
            )
            return faker.word()

    # Nullable column: 30% chance of being None
    if random.random() < 0.3:
        return None
    else:
        mock_col = type(
            "FakeCol", (), {"type": col_type, "name": name, "nullable": False}
        )()
        return generate_fake_value(mock_col, model_class)


def create_tables():
    models = get_all_models()
    if models:
        metadata = models[0].metadata
        metadata.create_all(engine)
        print(f"Tables created for {len(models)} models.")


def seed_model(
    model_class: Type[DeclarativeBase], session: Session, count: int = 5
) -> int:
    inserted = 0

    # Find columns that have unique constraint
    load_existing_unique_values(session, model_class)

    unique_cols = [col.name for col in model_class.__mapper__.columns if col.unique]

    for _ in range(count):
        data = {}
        skip_instance = False
        for attr in model_class.__mapper__.column_attrs:
            column = attr.columns[0]
            col_name = column.name

            if column.primary_key or col_name in {"id", "created_at", "updated_at"}:
                continue

            if column.foreign_keys:
                fk = list(column.foreign_keys)[0]
                ref_table = fk.column.table.name
                try:
                    from sqlalchemy.sql import text

                    query = text(
                        f"SELECT id FROM {ref_table} ORDER BY random() LIMIT 1"
                    )
                    fk_id = session.execute(query).scalar()
                except Exception as e:
                    print(f"Error selecting FK from {ref_table}: {e}")
                    fk_id = None

                if fk_id:
                    data[col_name] = fk_id
                else:
                    print(
                        f"No {ref_table} records to link to {col_name}. Skipping instance."
                    )
                    skip_instance = True
                    break
            else:
                value = generate_fake_value(column, model_class)

                # Handle uniqueness
                if col_name in unique_cols:
                    existing_values = UNIQUE_VALUE_CACHE[model_class][col_name]

                    base_value = value
                    suffix_count = 1
                    while value in existing_values:
                        if isinstance(value, str):
                            value = f"{base_value}_u{suffix_count}"
                        else:
                            value = f"{base_value}{suffix_count}"
                        suffix_count += 1

                    existing_values.add(value)

                data[col_name] = value

        if skip_instance:
            continue

        try:
            instance = model_class(**data)
            session.add(instance)
            session.flush()
            inserted += 1
        except IntegrityError as e:
            print(f"Integrity error (likely duplicate) for {model_class.__name__}: {e}")
            session.rollback()
        except Exception as e:
            print(
                f"Failed to create {model_class.__name__} instance with data {data}: {e}"
            )
            session.rollback()

    try:
        session.commit()
    except Exception as e:
        print(f"Commit failed for {model_class.__name__}: {e}")
        session.rollback()
        return 0

    return inserted


def seed_all(session: Session, count_per_model: int = 100):
    models = get_all_models()
    sorted_models = topological_sort_models(models)

    result = {}
    for model in sorted_models:
        print(f"\nSeeding {model.__name__}...")
        count = seed_model(model, session, count_per_model)
        result[model.__name__] = count
    return result


def main():
    parser = argparse.ArgumentParser(description="Seed database with fake data.")
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=1,
        help="Number of records to generate per table (default: 1)",
    )
    args = parser.parse_args()

    session = Session(engine)
    try:
        create_tables()
        result = seed_all(session, count_per_model=args.number)
        print("\nSeed summary:")
        for model_name, count in result.items():
            print(f"{model_name}: {count}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
