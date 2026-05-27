# Legacy Exercise JSON Schemas

Machine-oriented JSON Schema files for legacy exercise payloads stored in `Exercise.data`.

## Files

- `legacy-exercise.schema.json` -> umbrella validator (`oneOf` all legacy types)
- `common.schema.json` -> shared `$defs` used by all type schemas
- `matching.schema.json`
- `analytical.schema.json`
- `analytical_pcs.schema.json`
- `figured_bass.schema.json`
- `figured_bass_pcs.schema.json`
- `identification.schema.json`
- `chorale.schema.json`
- `chorale_identification.schema.json`

## Notes

- These schemas are intentionally permissive with `additionalProperties: true` to match legacy payload drift over time.
- They encode parser-facing contracts from:
  - `apps/exercises/models.py`
  - `lab/static/js/src/models/exercise_definition.js`
  - `lab/static/js/src/models/exercise_grader.js`
  - `lab/static/js/src/models/identification_grader.js`

## Example validator usage (Node + Ajv)

```js
import Ajv from "ajv";
import addFormats from "ajv-formats";
import fs from "node:fs";

const ajv = new Ajv({ strict: false, allErrors: true });
addFormats(ajv);

const common = JSON.parse(fs.readFileSync("docs/schemas/legacy/common.schema.json", "utf8"));
const matching = JSON.parse(fs.readFileSync("docs/schemas/legacy/matching.schema.json", "utf8"));
const root = JSON.parse(fs.readFileSync("docs/schemas/legacy/legacy-exercise.schema.json", "utf8"));

ajv.addSchema(common, common.$id);
ajv.addSchema(matching, matching.$id);
const validate = ajv.compile(root);

const payload = JSON.parse(fs.readFileSync("exercise.json", "utf8"));
console.log(validate(payload), validate.errors);
```
