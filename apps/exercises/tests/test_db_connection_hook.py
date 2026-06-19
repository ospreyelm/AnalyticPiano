"""
Standalone tests for apps/exercises/apps.py.

Run with:
    python3 apps/exercises/tests/test_db_connection_hook.py
"""
import os
import sys
import types
import unittest
from unittest import mock


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from apps.exercises import apps as exercise_apps


class FakePsycopg2Connection:
    __module__ = "psycopg2.extensions"


class FakePsycopg3Connection:
    __module__ = "psycopg.Connection"


class TestRegisterJsonCasting(unittest.TestCase):
    def test_registers_json_handlers_for_psycopg2_connections(self):
        raw_connection = FakePsycopg2Connection()

        with mock.patch("psycopg2.extras.register_default_json") as register_json, mock.patch(
            "psycopg2.extras.register_default_jsonb"
        ) as register_jsonb:
            exercise_apps.register_psycopg_json_casting(raw_connection)

        register_json.assert_called_once()
        register_jsonb.assert_called_once()

    def test_skips_registration_for_non_psycopg2_connections(self):
        raw_connection = FakePsycopg3Connection()
        psycopg_module = types.ModuleType("psycopg")
        psycopg_types_module = types.ModuleType("psycopg.types")
        psycopg_json_module = types.ModuleType("psycopg.types.json")
        set_json_loads = mock.Mock()
        psycopg_json_module.set_json_loads = set_json_loads

        with mock.patch("psycopg2.extras.register_default_json") as register_json, mock.patch(
            "psycopg2.extras.register_default_jsonb"
        ) as register_jsonb, mock.patch.dict(
            sys.modules,
            {
                "psycopg": psycopg_module,
                "psycopg.types": psycopg_types_module,
                "psycopg.types.json": psycopg_json_module,
            },
        ):
            exercise_apps.register_psycopg_json_casting(raw_connection)

        register_json.assert_not_called()
        register_jsonb.assert_not_called()
        set_json_loads.assert_called_once()


if __name__ == "__main__":
    unittest.main()
