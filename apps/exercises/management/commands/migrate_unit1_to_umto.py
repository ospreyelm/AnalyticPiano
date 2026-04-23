import json
from django.core.management.base import BaseCommand
from apps.exercises.models import Exercise
from apps.exercises.umto import UMTO, Metadata, Voices, VoiceEvent, Pitch, GradingSlice, AnalysisSlice, AnalysisLayer

class Command(BaseCommand):
    help = "Migrate legacy Unit 1 identification exercises to UMTO format"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        # Fetch and filter in Python to avoid json vs jsonb operator issues
        all_qs = Exercise.objects.filter(skill_tags__overlap=["unit:1"])
        
        if limit:
            all_qs = all_qs[:limit]

        # Filter in Python
        qs = [ex for ex in all_qs if ex.data.get("type") == "chorale_identification"]
        total = len(qs)
        self.stdout.write(f"Found {total} legacy Unit 1 exercises to migrate.")

        count = 0
        for ex in qs:
            try:
                new_data = self.migrate_exercise(ex)
                if not dry_run:
                    ex.data = new_data
                    ex.save()
                count += 1
                if count % 100 == 0:
                    self.stdout.write(f"Migrated {count}/{total}...")
            except Exception as e:
                self.stderr.write(f"Failed to migrate {ex.id}: {str(e)}")

        self.stdout.write(f"Successfully migrated {count} exercises.")

    def migrate_exercise(self, ex):
        old_data = ex.data
        score = old_data.get("score", {})
        meta = score.get("meta", {})
        
        # 1. Build Metadata
        # Use complexity from model if available, fallback to 1
        complexity = ex.complexity if hasattr(ex, "complexity") else 1
        # For Unit 1, complexity is usually (Stage * 10) + sharps.
        # We'll normalize it to 1 for the 'Note Identification' logic bridge.
        umto_meta = Metadata(
            exercise_id=ex.id,
            source=old_data.get("introText", "Bach Chorale Window"),
            key=meta.get("key", "C"),
            meter=meta.get("time", "4/4"),
            clef=meta.get("clef", "treble"),
            complexity_score=1 # Force to 1 to trigger Note Identification bridge
        )

        # 2. Extract Voices and Build Grading
        voices_dict = {"S": [], "A": [], "T": [], "B": []}
        grading_slices = []
        
        # Mapping legacy staves to UMTO voices
        # Unit 1 is usually single voice, often in 'treble' or 'bass' staff
        staves = score.get("measures", [{}])[0].get("staves", {}).keys()
        primary_staff = list(staves)[0] if staves else "treble"
        umto_voice_id = "S" if primary_staff == "treble" else "B"
        
        current_offset = 0.0
        time_sig = meta.get("time", "4/4")
        try:
            num, den = map(int, time_sig.split("/"))
            measure_ql = num * (4.0 / den)
        except:
            measure_ql = 4.0

        for m_idx, m in enumerate(score.get("measures", [])):
            measure_offset = m_idx * measure_ql
            staff_data = m.get("staves", {}).get(primary_staff, {})
            # Get the first voice in the staff
            voice_list = staff_data.get("voices", [])
            if not voice_list:
                continue
                
            v_items = voice_list[0].get("items", [])
            v_offset = 0.0
            for item in v_items:
                dur = item.get("duration", {})
                ql = self.dur_to_ql(dur)
                
                abs_offset = measure_offset + v_offset
                
                if item.get("kind") == "note":
                    p_data = item.get("pitch", {})
                    pitch = Pitch(
                        step=p_data.get("step", "C"),
                        alter=p_data.get("alter", 0),
                        octave=p_data.get("octave", 4),
                        midi=self.to_midi(p_data)
                    )
                    event = VoiceEvent(
                        kind="note",
                        pitch=pitch,
                        duration=ql,
                        duration_type=dur.get("type", "q"),
                        dots=dur.get("dots", 0),
                        is_target=True
                    )
                    voices_dict[umto_voice_id].append(event)
                    
                    # Add to grading
                    grading_slices.append(GradingSlice(
                        offset=abs_offset,
                        target_midi_pitches=[pitch.midi]
                    ))
                elif item.get("kind") == "rest":
                    event = VoiceEvent(
                        kind="rest",
                        duration=ql,
                        duration_type=dur.get("type", "q"),
                        dots=dur.get("dots", 0),
                        is_target=False
                    )
                    voices_dict[umto_voice_id].append(event)
                
                v_offset += ql

        # 3. Create Analysis Slices (mirroring grading for Unit 1)
        analysis_slices = []
        for g in grading_slices:
            analysis_slices.append(AnalysisSlice(
                offset=g.offset,
                content=AnalysisLayer(), # Empty content triggers Note Name bridge
                unit_tags=[1]
            ))

        # 4. Construct UMTO
        voices = Voices(**{k: v for k, v in voices_dict.items()})
        umto = UMTO(
            metadata=umto_meta,
            voices=voices,
            analysis=analysis_slices,
            grading=grading_slices
        )

        # 5. Generate Frontend Payload
        payload = umto.to_frontend_payload(unit=1)
        return payload

    def dur_to_ql(self, dur):
        base = {"w": 4.0, "h": 2.0, "q": 1.0, "8": 0.5, "16": 0.25, "32": 0.125}.get(dur.get("type", "q"), 1.0)
        dots = dur.get("dots", 0)
        return base * (2.0 - 0.5**dots) if dots else base

    def to_midi(self, p):
        semitones = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        return ((p.get("octave", 4) + 1) * 12) + semitones[p.get("step", "C")] + p.get("alter", 0)
