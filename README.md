# Cash Reconciliation Demo App

A 3-phase cash reconciliation system that automatically matches bank transactions to invoices using remittance advice, direct references, and intelligent flow-based algorithms.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ERP System    │     │  Reconciliation │     │   Data Files    │
│   (Port 5001)   │◄───►│   UI (Port 5002)│◄───►│   (data/*.json) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

- **ERP System**: Simulated invoice management system (FastAPI)
- **Reconciliation UI**: Main reconciliation dashboard with 3-phase matching (FastAPI)
- **Data Files**: JSON files containing bank transactions, invoices, and remittances

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the ERP System (Terminal 1)

```bash
python erp/app.py
```

ERP runs at: http://localhost:5001

### 3. Start the Reconciliation UI (Terminal 2)

```bash
python src_v2/app.py
```

Reconciliation UI runs at: http://localhost:5002

## Application URLs

### Reconciliation UI (http://localhost:5002)

| Page | URL | Description |
|------|-----|-------------|
| Landing | `/` | Upload bank statement (mock) |
| Dashboard | `/dashboard` | Overview with statistics |
| Auto-Approved | `/auto-approved` | High-confidence matches |
| Exceptions | `/exceptions` | Matches requiring review |
| Suggestions | `/suggestions` | AI-suggested matches |
| Manual | `/manual` | Unmatched transactions |
| Match Detail | `/match/{bank_id}` | Detailed match view with PDF |
| Remittance | `/remittances/{id}` | Remittance detail with PDF |

### ERP System (http://localhost:5001)

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Invoice overview |
| Invoices | `/invoices` | Invoice listing |
| Invoice Detail | `/invoices/{number}` | Single invoice view |
| Invoice PDF | `/invoices/{number}/pdf` | Download invoice PDF |

## 3-Phase Matching Algorithm

### Phase 1: Remittance-Backed Matching
- Matches bank transactions to remittance advice
- Links remittance line items to invoices
- Highest confidence (auto-approved if validated)

### Phase 2: Direct Reference Matching
- Extracts invoice references from bank descriptions
- Matches by invoice number patterns
- High confidence for exact matches

### Phase 3: Intelligent Suggestions
- **Single Invoice**: Customer has exactly one open invoice (95% confidence)
- **Unique Amount**: Bank amount uniquely matches one invoice (90% confidence)
- **Unique Combination**: Bank amount matches sum of 2-4 invoices (85% confidence)
- **Flow Match**: Network flow algorithm for complex scenarios (50-80% confidence)

## Data Files

All data is stored in the `data/` directory:

| File | Description |
|------|-------------|
| `bank_transactions.json` | Bank statement transactions |
| `invoices.json` | Customer invoices |
| `remittances.json` | Remittance advice documents |

### Reset Data

When the ERP app starts, all invoice statuses are automatically reset to `OPEN`.

## Key Features

### Reconciliation UI
- **Approve All**: Bulk approve all auto-approved matches
- **Approve Individual**: Approve single matches (sets invoice to CLOSED in ERP)
- **Match Detail View**: See bank transaction, remittance PDF, and linked invoices
- **Clickable Links**: Invoice links open ERP, remittance links show PDF

### Exception Handling
- Amount Mismatch (WARNING/CRITICAL)
- Customer Mismatch (WARNING)
- Invoice Not Found (WARNING)
- Duplicate Payment (CRITICAL)
- Overpayment (WARNING)
- Line Items Sum Mismatch (WARNING)

## Project Structure

```
cash-reconciliation-demo-app/
├── data/                       # JSON data files
│   ├── bank_transactions.json
│   ├── invoices.json
│   └── remittances.json
├── erp/                        # ERP System
│   ├── app.py                  # FastAPI app
│   └── templates/              # ERP HTML templates
├── src_v2/                     # Reconciliation Engine
│   ├── app.py                  # FastAPI app
│   ├── engine.py               # Main reconciliation engine
│   ├── config.py               # Configuration
│   ├── data_loader.py          # Data loading utilities
│   ├── models/                 # Data models
│   │   ├── bank.py
│   │   ├── invoice.py
│   │   ├── remittance.py
│   │   ├── match.py
│   │   └── exception.py
│   ├── matching/               # Matching algorithms
│   │   ├── phase1_remittance.py
│   │   ├── phase2_reference.py
│   │   └── phase3_suggestions.py
│   ├── templates/              # UI HTML templates
│   └── utils/                  # Utility functions
├── output/                     # Generated files
│   └── remittances/
│       └── pdf/                # Remittance PDFs
├── scripts/                    # Utility scripts
│   ├── generate_remittance.py  # Generate remittance HTML/PDF
│   ├── add_exception_data.py   # Add test exception data
│   └── add_suggestion_data.py  # Add test suggestion data
├── static/                     # Static assets (CSS)
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Test Data Scripts

### Add Exception Test Data
```bash
python scripts/add_exception_data.py
```
Adds scenarios that trigger various exception types.

### Add Suggestion Test Data
```bash
python scripts/add_suggestion_data.py
```
Adds scenarios for rules-based and flow-based suggestions.

### Regenerate Remittance HTML
```bash
python scripts/generate_remittance.py data/remittances.json --all --output-dir output/remittances
```

## API Endpoints

### Reconciliation API (Port 5002)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/summary` | Reconciliation statistics |
| GET | `/api/auto-approved` | Auto-approved matches |
| GET | `/api/exceptions` | Exception matches |
| GET | `/api/suggestions` | Suggested matches |
| GET | `/api/manual` | Manual review items |
| GET | `/api/match/{bank_id}` | Match detail |
| POST | `/api/approve/{bank_id}` | Approve match (update ERP) |
| POST | `/api/parse-bank-statement` | Mock bank statement parsing |

### ERP API (Port 5001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/invoices` | List invoices |
| GET | `/api/invoices/{number}` | Get invoice |
| PUT | `/api/invoices/{number}/status` | Update invoice status |
| GET | `/api/invoices/summary` | Invoice statistics |

## Configuration

Edit `src_v2/config.py` to adjust:

```python
amount_tolerance_percent: 0.5    # Amount match tolerance (%)
amount_tolerance_absolute: 10    # Amount match tolerance ($)
date_tolerance_days: 14          # Date match tolerance (days)
min_suggestion_confidence: 0.50  # Minimum suggestion confidence
```

## Requirements

- Python 3.9+
- FastAPI
- Uvicorn
- Jinja2
- httpx
- NetworkX (for flow-based matching)
- WeasyPrint (optional, for PDF generation)
