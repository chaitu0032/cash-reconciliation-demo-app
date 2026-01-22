#!/usr/bin/env python3
"""Run the Cash Reconciliation UI server."""

import sys
import os

# Fix for weasyprint on macOS with Anaconda
if sys.platform == 'darwin':
    homebrew_lib = '/opt/homebrew/lib'
    if os.path.exists(homebrew_lib):
        current = os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')
        os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = f"{homebrew_lib}:{current}" if current else homebrew_lib

if __name__ == '__main__':
    import uvicorn
    from src_v2.app import app

    print("=" * 60)
    print("  Cash Reconciliation UI")
    print("=" * 60)
    print("\n  Starting server at http://localhost:5002")
    print("\n  Pages:")
    print("    Dashboard:      http://localhost:5002/")
    print("    Auto-Approved:  http://localhost:5002/auto-approved")
    print("    Exceptions:     http://localhost:5002/exceptions")
    print("    Suggestions:    http://localhost:5002/suggestions")
    print("    Manual:         http://localhost:5002/manual")
    print("\n" + "=" * 60)

    uvicorn.run(app, host='0.0.0.0', port=5002)
