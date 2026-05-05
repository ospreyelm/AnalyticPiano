import json
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from apps.exercises.umto import UMTO

schema = UMTO.model_json_schema()
target = "apps/exercises/umto_schema.json"
with open(target, "w") as f:
    json.dump(schema, f, indent=2)
print(f"Successfully saved UMTO schema to {target}")
