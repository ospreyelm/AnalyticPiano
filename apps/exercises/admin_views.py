import html
import time
import threading
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import StreamingHttpResponse
from django.core.management import call_command
from django.contrib.admin.views.decorators import staff_member_required
from apps.exercises.models import Exercise
from django.db.models import Count


class StreamingBuffer:
    """Thread-safe output buffer that captures stdout/stderr and HTML-escapes it."""
    def __init__(self):
        self.queue = []
        self.lock = threading.Lock()

    def write(self, data):
        with self.lock:
            self.queue.append(html.escape(data))

    def flush(self):
        pass

    def read_and_clear(self) -> str:
        with self.lock:
            chunks = self.queue[:]
            self.queue.clear()
            return "".join(chunks)


def command_stream_generator(command_name: str, **kwargs):
    buffer = StreamingBuffer()
    error_container = []
    positional_args = kwargs.pop("_args", [])

    # Yield HTML header and styles first so the browser starts rendering immediately
    yield "<!DOCTYPE html>\n"
    yield "<html>\n"
    yield "<head>\n"
    yield f"  <title>Runner: {command_name} — HarmonyLab Admin</title>\n"
    yield "  <style>\n"
    yield "    body { background-color: #0b0f19; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 2rem; display: flex; flex-direction: column; height: 100vh; box-sizing: border-box; }\n"
    yield "    .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; }\n"
    yield "    .title { font-size: 1.5rem; font-weight: 700; color: #38bdf8; margin: 0; }\n"
    yield "    .status-badge { background-color: #1e293b; color: #94a3b8; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.875rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; transition: background-color 0.3s; }\n"
    yield "    .status-dot { width: 8px; height: 8px; border-radius: 50%; background-color: #10b981; animation: pulse 2s infinite; }\n"
    yield "    .console { flex: 1; background-color: #020617; border: 1px solid #1e293b; border-radius: 8px; padding: 1.5rem; font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace; font-size: 0.9rem; line-height: 1.5; overflow-y: auto; white-space: pre-wrap; word-break: break-all; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5); }\n"
    yield "    .footer { margin-top: 1.5rem; display: flex; align-items: center; justify-content: space-between; font-size: 0.875rem; color: #64748b; }\n"
    yield "    .btn { display: inline-flex; align-items: center; justify-content: center; padding: 0.5rem 1rem; background-color: #0284c7; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; transition: background-color 0.2s; cursor: pointer; }\n"
    yield "    .btn:hover { background-color: #0369a1; }\n"
    yield "    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }\n"
    yield "  </style>\n"
    yield "</head>\n"
    yield "<body>\n"
    
    yield "  <div class='header'>\n"
    yield f"    <h1 class='title'>Executing: {command_name}</h1>\n"
    yield "    <div class='status-badge' id='status-badge'><div class='status-dot'></div><span>RUNNING</span></div>\n"
    yield "  </div>\n"
    
    yield "  <div class='console' id='console-box'>\n"

    # Start the command in a background thread
    def run_command_thread():
        try:
            call_command(command_name, *positional_args, stdout=buffer, stderr=buffer, **kwargs)
        except Exception as e:
            error_container.append(e)

    thread = threading.Thread(target=run_command_thread)
    thread.start()

    # Loop while the thread runs or there are unconsumed messages in the buffer
    while thread.is_alive() or buffer.queue:
        output = buffer.read_and_clear()
        if output:
            yield output
            # Output JS snippet to keep the console scrolled down
            yield "\n<script>const c = document.getElementById('console-box'); c.scrollTop = c.scrollHeight;</script>"
        time.sleep(0.05)

    thread.join()

    yield "  </div>\n"
    
    yield "  <div class='footer' id='footer-section'>\n"
    if error_container:
        err_msg = html.escape(str(error_container[0]))
        yield f"    <span style='color: #ef4444; font-weight: 600;'>Command failed: {err_msg}</span>\n"
        yield "    <script>\n"
        yield "      document.getElementById('status-badge').innerHTML = '<span style=\"color:#ef4444;\">●</span> FAILED';\n"
        yield "      document.getElementById('status-badge').style.backgroundColor = '#450a0a';\n"
        yield "      document.getElementById('status-badge').style.color = '#ef4444';\n"
        yield "    </script>\n"
    else:
        yield "    <span>All tasks finished successfully.</span>\n"
        yield "    <script>\n"
        yield "      document.getElementById('status-badge').innerHTML = '<span style=\"color:#10b981;\">●</span> COMPLETED';\n"
        yield "      document.getElementById('status-badge').style.backgroundColor = '#064e3b';\n"
        yield "      document.getElementById('status-badge').style.color = '#34d399';\n"
        yield "    </script>\n"
        
    yield "    <a href='.' class='btn'>Return to Operations</a>\n"
    yield "  </div>\n"
    yield "</body>\n"
    yield "</html>\n"


@staff_member_required
def operations_view(request):
    if not request.user.has_perm('exercises.add_exercise'):
        messages.error(request, "Permission denied.")
        return redirect('admin:index')

    context = {
        'title': 'Exercise Operations',
        'is_popup': False,
        'has_permission': True,
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        command_name = request.POST.get('command_name')

        if action == 'generate':
            # Collect kwargs
            kwargs = {}
            int_kwargs = {
                'unit', 'min_voices', 'max_voices', 'voice_count', 'max_displacement',
                'min_measures', 'count', 'measures', 'level', 'limit',
                'max_per_stage', 'intervals_per_exercise', 'max_per_playlist',
            }
            for key, value in request.POST.items():
                if key not in ['csrfmiddlewaretoken', 'action', 'command_name'] and value.strip():
                    if key == 'extra_tags':
                        kwargs['extra_tags'] = value.split()
                    elif value == 'on':
                        kwargs[key] = True
                    elif key in int_kwargs:
                        kwargs[key] = int(value)
                    else:
                        kwargs[key] = value

            if command_name == "duplicate_chorale_as_identification" and kwargs.get("exercise_id"):
                kwargs["_args"] = [kwargs.pop("exercise_id")]

            # Add author email to generator commands that create exercises.
            no_default_author_commands = {"generate_unit2_meter_reference"}
            if 'author' not in kwargs and command_name not in no_default_author_commands:
                kwargs['author'] = request.user.email

            # Stream response in real-time
            return StreamingHttpResponse(
                command_stream_generator(command_name, **kwargs),
                content_type="text/html"
            )

        elif action == 'refresh':
            kwargs = {}
            if request.POST.get('dry_run') == 'on':
                kwargs['dry_run'] = True
            
            if command_name == 'recompute_chorale_analysis':
                if request.POST.get('tag'): kwargs['tag'] = request.POST.get('tag')
                if request.POST.get('riem'): kwargs['riem'] = request.POST.get('riem')
            elif command_name == 'recompute_harmonization_targets':
                if request.POST.get('tag'): kwargs['tag'] = request.POST.get('tag')
                if request.POST.get('resync_from_source'): kwargs['resync_from_source'] = True
            elif command_name == 'backfill_skill_tags':
                if request.POST.get('all'): kwargs['all'] = True

            # Stream response in real-time
            return StreamingHttpResponse(
                command_stream_generator(command_name, **kwargs),
                content_type="text/html"
            )

    # Build catalog
    from django.db.models.fields.json import KeyTextTransform
    
    catalog = Exercise.objects.annotate(
        mode=KeyTextTransform('mode', 'data'),
        analysis_type=KeyTextTransform('analysisType', 'data')
    ).values('mode', 'analysis_type').annotate(count=Count('id')).order_by('mode', 'analysis_type')
    
    context['catalog'] = catalog

    return render(request, 'admin/exercises/operations.html', context)
