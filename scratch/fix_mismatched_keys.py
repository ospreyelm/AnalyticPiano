import os
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'harmony.settings.local')
django.setup()

from apps.exercises.models import Exercise

def fix_ea03lk():
    target_id = 'EA03LK'
    try:
        ex = Exercise.objects.get(id=target_id)
        data = ex.data
        
        main_key = data.get('key')
        main_sig = data.get('keySignature')
        
        print(f"Current main key: {main_key}")
        print(f"Current score meta key: {data.get('score', {}).get('meta', {}).get('key')}")
        
        # Determine correct VexFlow key
        # iG_ -> Gm, jC_ -> C
        vex_key = main_key[1:].replace('_', '')
        if main_key.startswith('i'):
            vex_key += 'm'
        
        print(f"Setting score meta key to: {vex_key}")
        
        data['score']['meta']['key'] = vex_key
        # Also ensure keySignature matches (though VexFlow renderer usually prioritizes meta.key)
        # iG_ signature should be 'bb'
        
        ex.data = data
        ex.save()
        print(f"Successfully fixed {target_id}")
        
    except Exercise.DoesNotExist:
        print(f"Exercise {target_id} not found.")

if __name__ == "__main__":
    fix_ea03lk()
