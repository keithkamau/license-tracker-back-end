#!/usr/bin/env python3
import os
import sys
import django

def main():
    """Check Django setup."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    
    try:
        django.setup()
        print("✓ Django setup successful")
        
        # Check apps
        from django.apps import apps
        for app in apps.get_app_configs():
            print(f"  ✓ App: {app.name}")
        
        # Check database connection
        from django.db import connections
        for conn in connections.all():
            print(f"  ✓ Database connection: {conn.alias}")
        
        # Check URLs
        from django.urls import get_resolver
        resolver = get_resolver()
        print(f"  ✓ URL patterns loaded: {len(resolver.url_patterns)}")
        
        print("\n✓ All checks passed!")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()