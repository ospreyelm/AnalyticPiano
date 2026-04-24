import pytest
from apps.exercises.umto_factory import NonUMTOExerciseError


def test_non_umto_exercise_error_is_value_error_subclass():
    assert issubclass(NonUMTOExerciseError, ValueError)


def test_non_umto_exercise_error_carries_message():
    err = NonUMTOExerciseError("test message")
    assert str(err) == "test message"
