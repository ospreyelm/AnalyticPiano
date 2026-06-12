"""GenerationManifest dataclass for declarative exercise generation requests.

This module provides a dataclass that captures a generation request and methods to
dry-run or execute the generation pipeline.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import logging

from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.exercises.models import Exercise, Playlist
from apps.exercises.services.transposition_service import generate_transposed_copies

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass
class GenerationManifest:
    """Captures a declarative generation request.

    Attributes:
        source: Type of source; "bach_riemenschneider" or "played_in".
        source_ref: Source identifier:
            - For bach_riemenschneider: "1-30" (Riemenschneider range)
            - For played_in: exercise_id (string)
        unit: Curriculum unit number (e.g., 9, 11).
        skill_tags: Additional skill tags to stamp on created exercises.
        exercise_types: List of exercise types to generate (e.g., ["play", "roman"]).
        key_set: List of clean key strings (e.g., ["C", "G", "Bb"], or all 12).
        playlist_target: Optional Playlist pk to add exercises to; None = create new.
        is_official: If True, mark created exercises as official.
        author_email: Email of the user to assign as author.
        dry_run: If True, execute() returns dry_run_summary() instead of writing.
    """
    source: str
    source_ref: str
    unit: int
    skill_tags: list[str]
    exercise_types: list[str]
    key_set: list[str]
    playlist_target: int | None
    is_official: bool
    author_email: str
    dry_run: bool = False

    def dry_run_summary(self) -> dict:
        """Return an estimate of exercises that would be created, without DB writes.

        Returns:
            {
                "source": self.source,
                "source_ref": self.source_ref,
                "unit": self.unit,
                "exercise_types": self.exercise_types,
                "key_count": len(self.key_set),
                "estimated_exercises": len(self.exercise_types) * len(self.key_set),
                "is_official": self.is_official,
                "playlist_target": self.playlist_target,
            }
        """
        return {
            "source": self.source,
            "source_ref": self.source_ref,
            "unit": self.unit,
            "exercise_types": self.exercise_types,
            "key_count": len(self.key_set),
            "estimated_exercises": len(self.exercise_types) * len(self.key_set),
            "is_official": self.is_official,
            "playlist_target": self.playlist_target,
        }

    def execute(self) -> list | dict:
        """Execute the manifest and return created Exercise instances or summary dict.

        For bach_riemenschneider source:
            - Calls generate_bach_unit_matrix for each exercise_type
            - Returns empty list (management commands don't easily return Exercise objects)

        For played_in source:
            - Loads the source Exercise
            - Generates transposed copies via generate_transposed_copies()
            - Returns list of created Exercise instances

        If self.dry_run is True:
            - Returns dry_run_summary() dict instead of writing

        Raises:
            ValueError: If source is unknown, author not found, source exercise not found,
                       or source exercise is not UMTO chordal (for played_in).
        """
        # If dry_run mode, return summary without writing
        if self.dry_run:
            return self.dry_run_summary()

        # Resolve author by email
        try:
            author = User.objects.get(email=self.author_email)
        except User.DoesNotExist:
            raise ValueError(f"No user with email '{self.author_email}'.")

        if self.source == "bach_riemenschneider":
            return self._execute_bach_riemenschneider(author)
        elif self.source == "played_in":
            return self._execute_played_in(author)
        else:
            raise ValueError(f"Unknown source: {self.source}")

    def _execute_bach_riemenschneider(self, author: User) -> list:
        """Execute Bach Riemenschneider generation via generate_bach_unit_matrix.

        For each exercise_type, calls the management command. Returns empty list.
        """
        for exercise_type in self.exercise_types:
            logger.info(
                f"Generating Bach Riemenschneider {self.source_ref} "
                f"unit={self.unit} mode={exercise_type}"
            )
            try:
                call_command(
                    "generate_bach_unit_matrix",
                    units=str(self.unit),
                    modes=exercise_type,
                    riemenschneider=self.source_ref,
                    author=self.author_email,
                    public=True,
                    playlist_only=False,
                    skip_refresh=True,
                )
            except Exception as e:
                logger.error(
                    f"Failed to generate Bach Riemenschneider {exercise_type}: {e}"
                )
                raise ValueError(
                    f"Bach generation failed for mode {exercise_type}: {e}"
                )

        logger.info(
            f"Bach Riemenschneider generation complete for unit {self.unit}"
        )
        return []

    def _execute_played_in(self, author: User) -> list:
        """Execute played_in (transposition) generation.

        Loads source exercise, generates transposed copies, and optionally adds to playlist.
        Returns list of created Exercise instances.
        """
        # Load source exercise
        try:
            source_exercise = Exercise.objects.get(id=self.source_ref)
        except Exercise.DoesNotExist:
            raise ValueError(f"Exercise {self.source_ref} not found.")

        # Resolve or create playlist
        playlist = None
        if self.playlist_target:
            try:
                playlist = Playlist.objects.get(pk=self.playlist_target)
            except Playlist.DoesNotExist:
                raise ValueError(f"Playlist {self.playlist_target} not found.")

        # Generate transposed copies
        try:
            created = generate_transposed_copies(
                source_exercise=source_exercise,
                key_set=self.key_set,
                playlist=playlist,
                author=author,
                is_official=self.is_official,
                overwrite=False,
            )
            logger.info(
                f"Created {len(created)} transposed copies of {source_exercise.id} "
                f"in keys {self.key_set}"
            )
            return created
        except ValueError as e:
            # Re-raise validation errors (e.g., not UMTO chordal)
            raise e
        except Exception as e:
            logger.error(f"Transposition generation failed: {e}")
            raise ValueError(f"Transposition generation failed: {e}")
