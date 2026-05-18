import io
import threading
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.management import call_command
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from apps.exercises.models import Exercise
from django.db.models import Count, F

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
        
        out = io.StringIO()
        err = io.StringIO()

        if action == 'generate':
            # Collect kwargs
            kwargs = {}
            for key, value in request.POST.items():
                if key not in ['csrfmiddlewaretoken', 'action', 'command_name'] and value.strip():
                    # Handle lists (like extra-tags which might be space-separated)
                    if key == 'extra_tags':
                        kwargs['extra_tags'] = value.split()
                    elif value == 'on':
                        kwargs[key] = True
                    else:
                        kwargs[key] = value

            # Add author email if applicable
            if command_name in ['import_bach_phrases', 'generate_harmonization'] and 'author' not in kwargs:
                kwargs['author'] = request.user.email

            # Document limitation for long commands
            if command_name in ['import_bach_phrases', 'generate_harmonization']:
                messages.warning(request, f"Running {command_name}. This may take several minutes.")

            try:
                # Some management commands expect certain arg names
                call_command(command_name, stdout=out, stderr=err, **kwargs)
                msg = out.getvalue() or f"Command {command_name} completed successfully."
                messages.success(request, msg)
            except Exception as e:
                messages.error(request, f"Error running {command_name}: {str(e)}\n{err.getvalue()}")

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
            
            try:
                call_command(command_name, stdout=out, stderr=err, **kwargs)
                context['command_output'] = out.getvalue() + err.getvalue()
                messages.success(request, f"Executed {command_name}.")
            except Exception as e:
                messages.error(request, f"Error running {command_name}: {str(e)}\n{err.getvalue()}")

    # Build catalog
    from django.db.models.fields.json import KeyTextTransform
    
    catalog = Exercise.objects.annotate(
        mode=KeyTextTransform('mode', 'data'),
        analysis_type=KeyTextTransform('analysisType', 'data')
    ).values('mode', 'analysis_type').annotate(count=Count('id')).order_by('mode', 'analysis_type')
    
    context['catalog'] = catalog

    return render(request, 'admin/exercises/operations.html', context)
