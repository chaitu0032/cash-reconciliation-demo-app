#!/usr/bin/env python3
"""
Run the Dummy ERP System for Invoice Management (FastAPI).

Usage:
    python run_erp.py

Then open http://localhost:5001 in your browser.

Endpoints:
    Dashboard:           http://localhost:5001/
    Invoice List:        http://localhost:5001/invoices
    Invoice Detail:      http://localhost:5001/invoices/<invoice_number>
    Invoice HTML:        http://localhost:5001/invoices/<invoice_number>/html
    Invoice PDF View:    http://localhost:5001/invoices/<invoice_number>/pdf/view
    Invoice PDF Download: http://localhost:5001/invoices/<invoice_number>/pdf

API Endpoints:
    GET  /api/invoices                  - List all invoices (with filters)
    GET  /api/invoices/<number>         - Get single invoice
    PUT  /api/invoices/<number>/status  - Update invoice status
    GET  /api/invoices/summary          - Get summary statistics

API Docs:
    Swagger UI:          http://localhost:5001/docs
    ReDoc:               http://localhost:5001/redoc
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set library path for weasyprint PDF generation (macOS with Homebrew)
if sys.platform == 'darwin':
    homebrew_lib = '/opt/homebrew/lib'
    if os.path.exists(homebrew_lib):
        current = os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')
        os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = f"{homebrew_lib}:{current}" if current else homebrew_lib

import uvicorn
from erp.app import app

if __name__ == '__main__':
    print("=" * 60)
    print("  Dummy ERP System - Invoice Management (FastAPI)")
    print("=" * 60)
    print("\n  Starting server at http://localhost:5001")
    print("\n  Endpoints:")
    print("    Dashboard:      http://localhost:5001/")
    print("    Invoices:       http://localhost:5001/invoices")
    print("    Invoice HTML:   http://localhost:5001/invoices/<number>/html")
    print("    Invoice PDF:    http://localhost:5001/invoices/<number>/pdf/view")
    print("\n  API Endpoints:")
    print("    GET  /api/invoices")
    print("    GET  /api/invoices/<number>")
    print("    PUT  /api/invoices/<number>/status")
    print("    GET  /api/invoices/summary")
    print("\n  API Documentation:")
    print("    Swagger UI:     http://localhost:5001/docs")
    print("    ReDoc:          http://localhost:5001/redoc")
    print("\n" + "=" * 60)

    uvicorn.run(app, host='0.0.0.0', port=5001)
