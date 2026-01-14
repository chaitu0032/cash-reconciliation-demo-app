/**
 * Cash Reconciliation Dashboard - Frontend Logic
 * Financial Terminal Noir Edition
 */

// Exception code descriptions for tooltips
const EXCEPTION_DESCRIPTIONS = {
    'E002': 'Overpayment - Payment amount exceeds invoice amount',
    'E004': 'Duplicate Payment - Invoice already paid, receiving another payment',
    'E005': 'Invalid Invoice - Remittance references invoice not found in system',
    'E007': 'Orphan Bank Transaction - No matching remittance found',
    'E008': 'Duplicate Remittance Match - Bank transaction already matched',
    'E009': 'Customer Not Identified - Cannot identify customer from remittance data'
};

// Helper to get exception description
function getExceptionDescription(code) {
    return EXCEPTION_DESCRIPTIONS[code] || code;
}

// Helper to get exception tooltip with reason
function getExceptionTooltip(code, detail) {
    const description = EXCEPTION_DESCRIPTIONS[code] || code;
    if (detail && detail !== description && detail !== code) {
        return `${description}\n\nReason: ${detail}`;
    }
    return description;
}

// State
let currentData = null;
let invoiceStatusChart = null;
let paymentChart = null;

// DOM Elements
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const loadSampleBtn = document.getElementById('loadSampleBtn');
const loadingState = document.getElementById('loadingState');
const emptyState = document.getElementById('emptyState');
const dashboard = document.getElementById('dashboard');
const modalOverlay = document.getElementById('modalOverlay');
const modalClose = document.getElementById('modalClose');
const modalContent = document.getElementById('modalContent');
const modalTitle = document.getElementById('modalTitle');
const searchInput = document.getElementById('searchInput');
const statusFilter = document.getElementById('statusFilter');

// Tab buttons
const tabBtns = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

// Initialize
document.addEventListener('DOMContentLoaded', init);

function init() {
    // File upload handler
    fileInput.addEventListener('change', handleFileUpload);

    // Load sample data
    loadSampleBtn.addEventListener('click', loadSampleData);

    // Empty state buttons
    const emptyUploadBtn = document.getElementById('emptyUploadBtn');
    const emptyDemoBtn = document.getElementById('emptyDemoBtn');

    if (emptyUploadBtn) {
        const emptyFileInput = emptyUploadBtn.querySelector('input[type="file"]');
        if (emptyFileInput) {
            emptyFileInput.addEventListener('change', handleFileUpload);
        }
    }

    if (emptyDemoBtn) {
        emptyDemoBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            loadSampleData();
        });
    }

    // Tab switching
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Modal close
    modalClose.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) closeModal();
    });

    // Search and filter
    searchInput.addEventListener('input', debounce(applyFilters, 300));
    statusFilter.addEventListener('change', applyFilters);

    // Auto-apply controls
    document.getElementById('selectAllAutoApply').addEventListener('change', handleSelectAllAutoApply);
    document.querySelectorAll('input[name="applyFilter"]').forEach(radio => {
        radio.addEventListener('change', handleApplyFilterChange);
    });
    document.getElementById('writeToErpBtn').addEventListener('click', handleWriteToErp);

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });
}

// Animate number counting up
function animateNumber(element, targetValue, duration = 1000, isPercentage = false) {
    const startValue = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Ease out cubic
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        const currentValue = Math.round(startValue + (targetValue - startValue) * easeProgress);

        element.textContent = isPercentage ? `${currentValue}%` : currentValue;

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

// File Upload
async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    showLoading();

    const formData = new FormData();
    formData.append('file', file);

    try {
        // Start API call
        const responsePromise = fetch('/api/reconcile', { method: 'POST', body: formData });

        // Wait for API response first to get real stats
        const response = await responsePromise;
        if (!response.ok) {
            throw new Error(await response.text());
        }
        const result = await response.json();

        // Now run animation with REAL stats from API
        runLoadingAnimation(result.summary);

        // Load full data while animation plays
        const fullDataPromise = loadFullData();

        // Wait for both animation (10 sec) and data loading to complete
        await Promise.all([
            fullDataPromise,
            new Promise(resolve => setTimeout(resolve, 10000))
        ]);

        // Show dashboard
        renderDashboard(result);
    } catch (error) {
        console.error('Error:', error);
        alert('Error processing file: ' + error.message);
        hideLoading();
    }
}

// Load Sample Data
async function loadSampleData() {
    showLoading();

    try {
        // Start API call
        const responsePromise = fetch('/api/load-sample', { method: 'POST' });

        // Wait for API response first to get real stats
        const response = await responsePromise;
        if (!response.ok) {
            throw new Error(await response.text());
        }
        const result = await response.json();

        // Now run animation with REAL stats from API
        runLoadingAnimation(result.summary);

        // Load full data while animation plays
        const fullDataPromise = loadFullData();

        // Wait for both animation (10 sec) and data loading to complete
        await Promise.all([
            fullDataPromise,
            new Promise(resolve => setTimeout(resolve, 10000))
        ]);

        // Show dashboard
        renderDashboard(result);
    } catch (error) {
        console.error('Error:', error);
        alert('Error loading sample data: ' + error.message);
        hideLoading();
    }
}

// Load full data for tables
async function loadFullData() {
    try {
        const response = await fetch('/api/data');
        if (response.ok) {
            currentData = await response.json();
        }
    } catch (error) {
        console.error('Error loading full data:', error);
    }
}

// Loading Animation State
let loadingAnimationId = null;

// UI States
function showLoading() {
    emptyState.classList.add('hidden');
    dashboard.style.display = 'none';
    loadingState.classList.add('active');
    resetLoadingUI();
}

function hideLoading() {
    loadingState.classList.remove('active');
    if (loadingAnimationId) {
        cancelAnimationFrame(loadingAnimationId);
        loadingAnimationId = null;
    }
}

function showDashboard() {
    hideLoading();
    emptyState.classList.add('hidden');
    dashboard.style.display = 'block';
}

// Reset loading UI
function resetLoadingUI() {
    const progressFill = document.getElementById('progressFill');
    const progressPercent = document.getElementById('progressPercent');
    const steps = document.querySelectorAll('.step');

    if (progressFill) progressFill.style.width = '0%';
    if (progressPercent) progressPercent.textContent = '0%';

    steps.forEach(step => {
        step.classList.remove('active', 'completed');
        const icon = step.querySelector('.step-icon');
        if (icon) icon.textContent = '○';
    });

    document.getElementById('statProcessed').textContent = '0';
    document.getElementById('statMatched').textContent = '0';
    document.getElementById('statExceptions').textContent = '0';
}

// Animated loading sequence (10 seconds)
function runLoadingAnimation(finalStats) {
    const TOTAL_DURATION = 10000; // 10 seconds
    const steps = document.querySelectorAll('.step');
    const progressFill = document.getElementById('progressFill');
    const progressPercent = document.getElementById('progressPercent');
    const statProcessed = document.getElementById('statProcessed');
    const statMatched = document.getElementById('statMatched');
    const statExceptions = document.getElementById('statExceptions');

    const totalSteps = steps.length;
    const stepDuration = TOTAL_DURATION / totalSteps;

    // Final values from actual reconciliation (all from API, no hardcoding)
    const finalProcessed = finalStats.total_bank_transactions || 0;
    const finalMatched = (finalStats.level1_auto_matched || 0) + (finalStats.level1_auto_matched_virtual || 0);
    const finalExceptions = Object.values(finalStats.exceptions_by_code || {}).reduce((a, b) => a + b, 0);

    const startTime = performance.now();

    function animate(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / TOTAL_DURATION, 1);
        const currentStepIndex = Math.min(Math.floor(progress * totalSteps), totalSteps - 1);

        // Update progress bar
        const percent = Math.round(progress * 100);
        progressFill.style.width = `${percent}%`;
        progressPercent.textContent = `${percent}%`;

        // Update steps
        steps.forEach((step, index) => {
            const icon = step.querySelector('.step-icon');
            if (index < currentStepIndex) {
                step.classList.remove('active');
                step.classList.add('completed');
                if (icon) icon.textContent = '✓';
            } else if (index === currentStepIndex) {
                step.classList.add('active');
                step.classList.remove('completed');
                if (icon) icon.textContent = '●';
            } else {
                step.classList.remove('active', 'completed');
                if (icon) icon.textContent = '○';
            }
        });

        // Update stats with easing
        const easeOut = 1 - Math.pow(1 - progress, 3);
        statProcessed.textContent = Math.round(finalProcessed * easeOut);
        statMatched.textContent = Math.round(finalMatched * easeOut);
        statExceptions.textContent = Math.round(finalExceptions * easeOut);

        if (progress < 1) {
            loadingAnimationId = requestAnimationFrame(animate);
        } else {
            // Complete all steps
            steps.forEach(step => {
                step.classList.remove('active');
                step.classList.add('completed');
                const icon = step.querySelector('.step-icon');
                if (icon) icon.textContent = '✓';
            });
        }
    }

    loadingAnimationId = requestAnimationFrame(animate);
}

// Render Dashboard
function renderDashboard(data) {
    showDashboard();

    const summary = data.summary;

    // Animate summary cards
    animateValue('totalBankTxns', summary.total_bank_transactions);

    // Invoice reconciliation rate (invoice-centric metric)
    const invoiceRecRate = summary.invoice_reconciliation_rate || 0;
    animateValue('invoiceRecRate', Math.round(invoiceRecRate), '%');

    // Total invoices
    animateValue('totalInvoices', summary.total_invoices);

    const totalExceptions = Object.values(summary.exceptions_by_code).reduce((a, b) => a + b, 0);
    animateValue('totalExceptions', totalExceptions);

    // Update tab counts
    document.getElementById('invCount').textContent = summary.total_invoices;
    document.getElementById('remCount').textContent = summary.total_remittances;
    document.getElementById('bankCount').textContent = summary.total_bank_transactions;

    // Render charts (need invoice statuses for accurate counts)
    if (currentData) {
        renderInvoiceStatusChart(currentData.invoice_statuses || []);
        renderPaymentChart(summary, currentData.invoice_statuses || []);

        // Render tables (invoices first since it's the primary view)
        renderInvoicesTable(currentData.invoice_statuses || currentData.invoices);
        renderRemittancesTable(currentData.remittances, currentData.virtual_remittances);
        renderBankTable(currentData.results);
    }
}

// Animate number value
function animateValue(elementId, value, suffix = '') {
    const element = document.getElementById(elementId);
    const duration = 1000;
    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Easing function
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (value - start) * easeOut);

        element.textContent = current + suffix;

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

// Invoice Status Donut Chart (Reconciled, Partial, Open)
function renderInvoiceStatusChart(invoiceStatuses) {
    const ctx = document.getElementById('invoiceStatusChart').getContext('2d');

    // Destroy existing chart
    if (invoiceStatusChart) {
        invoiceStatusChart.destroy();
    }

    // Count invoices by status
    let reconciled = 0;
    let partial = 0;
    let open = 0;

    invoiceStatuses.forEach(status => {
        const inv = status.invoice || status;
        if (status.is_reconciled) {
            reconciled++;
        } else if (inv.status === 'Partial') {
            partial++;
        } else {
            open++;
        }
    });

    invoiceStatusChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Reconciled', 'Partial Payment', 'Open'],
            datasets: [{
                data: [reconciled, partial, open],
                backgroundColor: [
                    '#039855',  // success8 - green
                    '#1B7DA7',  // primary7 - blue
                    '#FDB022'   // warning6 - yellow/orange
                ],
                borderWidth: 0,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#FFFFFF',
                    titleColor: '#211F26',
                    bodyColor: '#596263',
                    borderColor: '#DFE6E8',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? Math.round((context.raw / total) * 100) : 0;
                            return `${context.label}: ${context.raw} (${percentage}%)`;
                        }
                    }
                }
            },
            animation: {
                animateRotate: true,
                duration: 1000
            }
        }
    });

    // Update legend
    const total = reconciled + partial + open;
    const reconciledPct = total > 0 ? Math.round((reconciled / total) * 100) : 0;
    const partialPct = total > 0 ? Math.round((partial / total) * 100) : 0;
    const openPct = total > 0 ? Math.round((open / total) * 100) : 0;

    const legendHtml = `
        <div class="legend-item">
            <span class="legend-dot" style="background: #039855;"></span>
            <span>Reconciled: ${reconciled} (${reconciledPct}%)</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background: #1B7DA7;"></span>
            <span>Partial: ${partial} (${partialPct}%)</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background: #FDB022;"></span>
            <span>Open: ${open} (${openPct}%)</span>
        </div>
    `;
    document.getElementById('invoiceStatusLegend').innerHTML = legendHtml;
}

// Payment Application Donut Chart (Auto Applied, Needs Review, No Payment)
function renderPaymentChart(summary, invoiceStatuses) {
    const ctx = document.getElementById('paymentChart').getContext('2d');

    // Destroy existing chart
    if (paymentChart) {
        paymentChart.destroy();
    }

    // Count payment application status
    let autoApplied = 0;      // Matched without exceptions
    let needsReview = 0;      // Has exceptions
    let noPayment = 0;        // No payment received

    invoiceStatuses.forEach(status => {
        const inv = status.invoice || status;
        const hasException = status.line_match_exception || status.invoice_exception || status.remittance_exception;
        const hasPayment = status.all_payments && status.all_payments.length > 0;

        if (hasPayment && !hasException) {
            autoApplied++;
        } else if (hasPayment && hasException) {
            needsReview++;
        } else {
            noPayment++;
        }
    });

    paymentChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Auto Applied', 'Needs Review', 'No Payment'],
            datasets: [{
                data: [autoApplied, needsReview, noPayment],
                backgroundColor: [
                    '#039855',  // success8 - green
                    '#F04438',  // error - red
                    '#A8B8BB'   // grey8
                ],
                borderWidth: 0,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#FFFFFF',
                    titleColor: '#211F26',
                    bodyColor: '#596263',
                    borderColor: '#DFE6E8',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? Math.round((context.raw / total) * 100) : 0;
                            return `${context.label}: ${context.raw} (${percentage}%)`;
                        }
                    }
                }
            },
            animation: {
                animateRotate: true,
                duration: 1000
            }
        }
    });

    // Update legend
    const total = autoApplied + needsReview + noPayment;
    const autoPct = total > 0 ? Math.round((autoApplied / total) * 100) : 0;
    const reviewPct = total > 0 ? Math.round((needsReview / total) * 100) : 0;
    const noPmtPct = total > 0 ? Math.round((noPayment / total) * 100) : 0;

    const legendHtml = `
        <div class="legend-item">
            <span class="legend-dot" style="background: #039855;"></span>
            <span>Auto Applied: ${autoApplied} (${autoPct}%)</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background: #F04438;"></span>
            <span>Needs Review: ${needsReview} (${reviewPct}%)</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background: #A8B8BB;"></span>
            <span>No Payment: ${noPayment} (${noPmtPct}%)</span>
        </div>
    `;
    document.getElementById('paymentLegend').innerHTML = legendHtml;
}

// Bank Transactions Table - Shows remittance match status and exceptions
function renderBankTable(results) {
    const tbody = document.getElementById('bankTableBody');
    tbody.innerHTML = '';

    // Sort: exceptions first, then unmatched
    const sorted = [...results].sort((a, b) => {
        const aHasException = !!a.level1_exception_code;
        const bHasException = !!b.level1_exception_code;

        if (aHasException && !bHasException) return -1;
        if (!aHasException && bHasException) return 1;

        const aMatched = a.level1_outcome === 'AUTO_MATCHED';
        const bMatched = b.level1_outcome === 'AUTO_MATCHED';

        if (!aMatched && bMatched) return -1;
        if (aMatched && !bMatched) return 1;
        return 0;
    });

    sorted.forEach(result => {
        const tr = document.createElement('tr');
        tr.onclick = () => showTransactionDetail(result.bank_id);

        const isMatched = result.level1_outcome === 'AUTO_MATCHED';
        const hasException = !!result.level1_exception_code;

        const statusClass = isMatched ? 'status-matched' : 'status-open';
        const statusText = isMatched ? 'Matched' : 'Open';

        tr.innerHTML = `
            <td><code>${result.bank_id}</code></td>
            <td>$${formatNumber(result.bank_amount)}</td>
            <td>${result.bank_date}</td>
            <td><code>${truncate(result.bank_reference, 15)}</code></td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>${result.level1_remittance_id ?
                `<code>${truncate(result.level1_remittance_id, 12)}</code>` :
                '<span style="color: var(--text-muted);">-</span>'}</td>
            <td>${hasException ?
                `<span class="status-badge status-exception" data-tooltip="${getExceptionTooltip(result.level1_exception_code, result.level1_exception_detail)}">${result.level1_exception_code}</span>` :
                '<span style="color: var(--text-muted);">-</span>'}</td>
        `;

        // Highlight rows with exceptions
        if (hasException) {
            tr.style.background = 'var(--accent-coral-dim)';
        } else if (!isMatched) {
            tr.style.background = 'var(--accent-gold-dim)';
        }

        tbody.appendChild(tr);
    });
}

// Remittances Table - Shows bank match status and exceptions
function renderRemittancesTable(remittances, virtualRemittances) {
    const tbody = document.getElementById('remTableBody');
    tbody.innerHTML = '';

    const allRemittances = [...remittances, ...virtualRemittances];

    // Sort: unmatched/exceptions first
    const sorted = [...allRemittances].sort((a, b) => {
        const aMatched = a.status === 'Matched' || a.matched_bank_transaction_id;
        const bMatched = b.status === 'Matched' || b.matched_bank_transaction_id;

        if (!aMatched && bMatched) return -1;
        if (aMatched && !bMatched) return 1;
        return 0;
    });

    sorted.forEach(rem => {
        const tr = document.createElement('tr');
        tr.onclick = () => showRemittanceDetail(rem.id);

        const isVirtual = rem.source === 'BANK_PARSED' || rem.id.startsWith('VREM-');
        const isMatched = rem.status === 'Matched' || rem.matched_bank_transaction_id;
        const bankTxnId = rem.matched_bank_transaction_id || '-';

        // Check for exceptions (E009 customer not identified)
        const hasException = !rem.customer_id && rem.customer_name;

        const statusClass = isMatched ? 'status-matched' : 'status-open';
        const statusText = isMatched ? 'Matched' : 'Open';

        tr.innerHTML = `
            <td>
                <code>${rem.id}</code>
                ${isVirtual ? '<span class="status-badge" style="background: var(--accent-cyan-dim); color: var(--accent-cyan); margin-left: 0.5rem;">Virtual</span>' : ''}
            </td>
            <td>${truncate(rem.customer_name, 15)}</td>
            <td>$${formatNumber(rem.total_amount)}</td>
            <td>${rem.payment_date}</td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>${bankTxnId !== '-' ?
                `<code>${truncate(bankTxnId, 12)}</code>` :
                '<span style="color: var(--text-muted);">-</span>'}</td>
            <td>${hasException ?
                `<span class="status-badge status-exception" data-tooltip="${getExceptionDescription('E009')}">E009</span>` :
                '<span style="color: var(--text-muted);">-</span>'}</td>
        `;

        // Highlight unmatched rows
        if (!isMatched) {
            tr.style.background = 'var(--accent-gold-dim)';
        }

        tbody.appendChild(tr);
    });
}

// Track selected invoices for ERP export
let selectedInvoices = new Set();

// Invoices Table - Invoice-centric view with full reconciliation chain
function renderInvoicesTable(invoiceStatuses) {
    const tbody = document.getElementById('invTableBody');
    tbody.innerHTML = '';
    selectedInvoices.clear();
    updateSelectedCount();

    // Sort: auto-apply eligible first (Closed without exceptions), then Partial, then Open, then exceptions
    const sorted = [...invoiceStatuses].sort((a, b) => {
        const aInv = a.invoice || a;
        const bInv = b.invoice || b;
        const aHasException = a.line_match_exception || a.invoice_exception;
        const bHasException = b.line_match_exception || b.invoice_exception;
        const aStatus = aInv.status || 'Open';
        const bStatus = bInv.status || 'Open';

        // Auto-apply eligible (Closed, no exception) first
        const aAutoApply = aStatus === 'Closed' && !aHasException;
        const bAutoApply = bStatus === 'Closed' && !bHasException;
        if (aAutoApply && !bAutoApply) return -1;
        if (!aAutoApply && bAutoApply) return 1;

        // Then Partial without exception
        const aPartialOk = aStatus === 'Partial' && !aHasException;
        const bPartialOk = bStatus === 'Partial' && !bHasException;
        if (aPartialOk && !bPartialOk) return -1;
        if (!aPartialOk && bPartialOk) return 1;

        // Exceptions last
        if (aHasException && !bHasException) return 1;
        if (!aHasException && bHasException) return -1;

        return 0;
    });

    sorted.forEach(item => {
        const tr = document.createElement('tr');

        // Handle both invoice_statuses format and plain invoices format
        const inv = item.invoice || item;
        const status = inv.status || 'Open';

        const statusClass = status === 'Open' ? 'status-open' :
            status === 'Closed' ? 'status-closed' : 'status-partial';

        // Line-level exception
        const lineException = item.line_match_exception;
        const lineExceptionDetail = item.line_match_exception_detail;
        const hasException = !!(lineException || item.invoice_exception);

        // Determine if this invoice can be auto-applied
        const hasPayment = item.all_payments && item.all_payments.length > 0;
        const canAutoApply = hasPayment && !hasException && (status === 'Closed' || status === 'Partial');
        const isFullPayment = status === 'Closed';

        // Store auto-apply eligibility on the row
        tr.dataset.invoiceId = inv.invoice_id;
        tr.dataset.canAutoApply = canAutoApply ? 'true' : 'false';
        tr.dataset.isFullPayment = isFullPayment ? 'true' : 'false';

        // Checkbox cell
        const checkboxDisabled = !canAutoApply;
        const checkboxHtml = `
            <td class="checkbox-col" onclick="event.stopPropagation();">
                <input type="checkbox" class="row-checkbox"
                    data-invoice-id="${inv.invoice_id}"
                    ${checkboxDisabled ? 'disabled' : ''}
                    onchange="handleRowCheckbox(this)">
            </td>
        `;

        tr.innerHTML = checkboxHtml + `
            <td><code>${inv.invoice_id}</code></td>
            <td>${truncate(inv.customer_id, 12)}</td>
            <td>$${formatNumber(inv.amount)}</td>
            <td>$${formatNumber(inv.pending_amount)}</td>
            <td><span class="status-badge ${statusClass}">${status}</span></td>
            <td>${hasException ?
                `<span class="status-badge status-exception" data-tooltip="${getExceptionTooltip(lineException, lineExceptionDetail)}">${lineException || item.invoice_exception}</span>` :
                '<span style="color: var(--text-muted);">-</span>'}</td>
        `;

        // Style rows based on status
        if (hasException) {
            tr.style.background = 'var(--accent-coral-dim)';
        } else if (canAutoApply) {
            tr.classList.add('selectable');
        }

        // Make row clickable (except checkbox)
        tr.style.cursor = 'pointer';
        tr.onclick = (e) => {
            if (e.target.type !== 'checkbox') {
                showInvoiceDetail(inv.invoice_id, item);
            }
        };

        tbody.appendChild(tr);
    });
}

// Handle individual row checkbox
function handleRowCheckbox(checkbox) {
    const invoiceId = checkbox.dataset.invoiceId;
    const row = checkbox.closest('tr');

    if (checkbox.checked) {
        selectedInvoices.add(invoiceId);
        row.classList.add('selected');
    } else {
        selectedInvoices.delete(invoiceId);
        row.classList.remove('selected');
        // Uncheck "Select All" if any row is unchecked
        document.getElementById('selectAllAutoApply').checked = false;
    }
    updateSelectedCount();
}

// Update selected count and button state
function updateSelectedCount() {
    const count = selectedInvoices.size;
    document.getElementById('selectedCount').textContent = `${count} selected`;
    document.getElementById('writeToErpBtn').disabled = count === 0;
}

// Handle "Select All Auto-Apply" checkbox
function handleSelectAllAutoApply() {
    const selectAllCheckbox = document.getElementById('selectAllAutoApply');
    const includePartial = document.querySelector('input[name="applyFilter"]:checked').value === 'partial';

    const checkboxes = document.querySelectorAll('.row-checkbox:not(:disabled)');

    checkboxes.forEach(checkbox => {
        const row = checkbox.closest('tr');
        const isFullPayment = row.dataset.isFullPayment === 'true';

        // If "Full Payment Only" is selected, only select full payment rows
        const shouldSelect = includePartial || isFullPayment;

        if (selectAllCheckbox.checked && shouldSelect) {
            checkbox.checked = true;
            selectedInvoices.add(checkbox.dataset.invoiceId);
            row.classList.add('selected');
        } else if (!selectAllCheckbox.checked) {
            checkbox.checked = false;
            selectedInvoices.delete(checkbox.dataset.invoiceId);
            row.classList.remove('selected');
        }
    });

    updateSelectedCount();
}

// Handle filter change (Full Payment Only vs Include Partial)
function handleApplyFilterChange() {
    // If "Select All" is checked, reapply selection with new filter
    const selectAllCheckbox = document.getElementById('selectAllAutoApply');
    if (selectAllCheckbox.checked) {
        // First uncheck all, then reapply
        selectedInvoices.clear();
        document.querySelectorAll('.row-checkbox').forEach(cb => {
            cb.checked = false;
            cb.closest('tr').classList.remove('selected');
        });
        handleSelectAllAutoApply();
    }
}

// Write to ERP
function handleWriteToErp() {
    if (selectedInvoices.size === 0) return;

    const count = selectedInvoices.size;
    const overlay = document.getElementById('erpModalOverlay');
    const content = document.getElementById('erpModalContent');

    // Show success screen
    content.innerHTML = `
        <div class="erp-complete">
            <div class="erp-complete-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 6L9 17l-5-5"/>
                </svg>
            </div>
            <h3>Written to ERP</h3>
            <p>${count} invoice${count > 1 ? 's' : ''} successfully exported</p>
        </div>
        <div class="erp-actions">
            <button class="erp-btn-secondary" onclick="closeErpModal()">Close</button>
        </div>
    `;

    overlay.classList.add('active');

    // Clear selection
    selectedInvoices.clear();
    document.querySelectorAll('.row-checkbox').forEach(cb => {
        cb.checked = false;
        cb.closest('tr')?.classList.remove('selected');
    });
    document.getElementById('selectAllAutoApply').checked = false;
    updateSelectedCount();
}

function closeErpModal() {
    document.getElementById('erpModalOverlay').classList.remove('active');
}

// Invoice Detail Modal - Shows payments received for an invoice
function showInvoiceDetail(invoiceId, invoiceStatus) {
    const inv = invoiceStatus.invoice || invoiceStatus;
    const status = inv.status || 'Open';

    modalTitle.textContent = `Invoice ${invoiceId}`;

    // Invoice details section
    let html = `
        <div class="detail-section">
            <div class="detail-title">INVOICE DETAILS</div>
            <div class="detail-grid">
                <div class="detail-item">
                    <span class="detail-label">Invoice ID</span>
                    <span class="detail-value"><code>${inv.invoice_id}</code></span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Customer</span>
                    <span class="detail-value">${inv.customer_id}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Amount</span>
                    <span class="detail-value" style="color: var(--accent-gold);">$${formatNumber(inv.amount)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Pending</span>
                    <span class="detail-value">$${formatNumber(inv.pending_amount)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Due Date</span>
                    <span class="detail-value">${inv.due_date || '-'}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Status</span>
                    <span class="detail-value">
                        <span class="status-badge ${status === 'Closed' ? 'status-closed' : status === 'Partial' ? 'status-partial' : 'status-open'}">${status}</span>
                    </span>
                </div>
            </div>
        </div>
    `;

    // Payments Received section
    const allPayments = invoiceStatus.all_payments || [];
    if (allPayments.length > 0) {
        html += `
            <div class="detail-section">
                <div class="detail-title">PAYMENTS RECEIVED (${allPayments.length})</div>
                <table class="data-table" style="margin-top: 0.5rem; white-space: nowrap;">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Remittance</th>
                            <th>Invoice Ref</th>
                            <th>Amount</th>
                            <th>Bank Verified</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        allPayments.forEach((payment, idx) => {
            // Line match status
            let lineStatusHtml;
            if (payment.outcome === 'AUTO_MATCHED') {
                lineStatusHtml = '<span class="status-badge status-matched">Matched</span>';
            } else if (payment.outcome === 'EXCEPTION' && payment.exception_code) {
                lineStatusHtml = `<span class="status-badge status-exception" data-tooltip="${getExceptionTooltip(payment.exception_code, payment.exception_detail)}">${payment.exception_code}</span>`;
            } else {
                lineStatusHtml = '<span class="status-badge status-open">Pending</span>';
            }

            // Bank verification status
            let bankVerifiedHtml;
            if (payment.bank_transaction_id) {
                bankVerifiedHtml = `
                    <span class="status-badge status-matched" title="Remittance verified against bank transaction">✓</span>
                    <code style="margin-left: 0.25rem;">${payment.bank_transaction_id}</code>
                `;
            } else {
                bankVerifiedHtml = '<span class="status-badge status-open">Not Verified</span>';
            }

            html += `
                <tr>
                    <td style="white-space: nowrap;">${idx + 1}</td>
                    <td style="white-space: nowrap;">
                        <code>${payment.remittance_id || '-'}</code>
                        <span style="color: var(--text-muted); font-size: 0.75rem; display: block;">Pay Ref: ${payment.remittance_reference || '-'}</span>
                    </td>
                    <td style="white-space: nowrap;"><code>${payment.line_ref || '-'}</code></td>
                    <td style="white-space: nowrap; color: var(--accent-gold);">$${formatNumber(payment.amount || 0)}</td>
                    <td style="white-space: nowrap;">${bankVerifiedHtml}</td>
                    <td style="white-space: nowrap;">${lineStatusHtml}</td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;
    } else {
        html += `
            <div class="detail-section">
                <div class="detail-title">PAYMENTS RECEIVED</div>
                <div style="text-align: center; color: var(--text-muted); padding: 1.5rem;">
                    No payments received for this invoice
                </div>
            </div>
        `;
    }

    // Exceptions section
    const invoiceException = invoiceStatus.invoice_exception;
    const remittanceException = invoiceStatus.remittance_exception;
    const bankException = invoiceStatus.bank_exception;
    const hasException = invoiceException || remittanceException || bankException;

    if (hasException) {
        html += `
            <div class="detail-section">
                <div class="detail-title">EXCEPTIONS</div>
                <div class="detail-grid">
        `;

        if (invoiceException) {
            html += `
                    <div class="detail-item">
                        <span class="detail-label">Invoice Level</span>
                        <span class="detail-value">
                            <span class="status-badge status-exception">${invoiceException}</span>
                            <span style="margin-left: 0.5rem; color: var(--text-muted); font-size: 0.8rem;">${getExceptionDescription(invoiceException)}</span>
                        </span>
                    </div>
            `;
        }
        if (remittanceException) {
            html += `
                    <div class="detail-item">
                        <span class="detail-label">Remittance Level</span>
                        <span class="detail-value">
                            <span class="status-badge status-exception">${remittanceException}</span>
                            <span style="margin-left: 0.5rem; color: var(--text-muted); font-size: 0.8rem;">${getExceptionDescription(remittanceException)}</span>
                        </span>
                    </div>
            `;
        }
        if (bankException) {
            html += `
                    <div class="detail-item">
                        <span class="detail-label">Bank Level</span>
                        <span class="detail-value">
                            <span class="status-badge status-exception">${bankException}</span>
                            <span style="margin-left: 0.5rem; color: var(--text-muted); font-size: 0.8rem;">${getExceptionDescription(bankException)}</span>
                        </span>
                    </div>
            `;
        }

        html += `
                </div>
            </div>
        `;
    }

    // Reconciliation status
    const isReconciled = invoiceStatus.is_reconciled;
    const statusText = isReconciled ? 'RECONCILED' : (invoiceStatus.reconciliation_status || 'NOT RECONCILED');
    const statusStyle = isReconciled ?
        'background: var(--accent-emerald-dim); color: var(--accent-emerald);' :
        'background: var(--accent-coral-dim); color: var(--accent-coral);';

    html += `
        <div class="detail-section" style="text-align: center; padding: 1rem; background: var(--bg-primary); border-radius: 6px;">
            <span style="font-size: 0.85rem; font-weight: 600; padding: 0.5rem 1.5rem; ${statusStyle} border-radius: 4px;">
                ${statusText}
            </span>
        </div>
    `;

    modalContent.innerHTML = html;
    openModal();
}

// Tab Switching
function switchTab(tabId) {
    tabBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    tabContents.forEach(content => {
        content.classList.toggle('active', content.id === tabId + 'Tab');
    });
}

// Filter/Search
function applyFilters() {
    const searchTerm = searchInput.value.toLowerCase();
    const statusValue = statusFilter.value;

    // Get active tab
    const activeTab = document.querySelector('.tab-content.active');
    const rows = activeTab.querySelectorAll('tbody tr');

    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        const matchesSearch = text.includes(searchTerm);

        let matchesStatus = true;
        if (statusValue) {
            const statusBadge = row.querySelector('.status-badge');
            if (statusBadge) {
                const badgeText = statusBadge.textContent.toLowerCase();
                if (statusValue === 'matched') {
                    matchesStatus = badgeText.includes('matched') || badgeText.includes('reconciled');
                } else if (statusValue === 'unmatched') {
                    matchesStatus = badgeText.includes('unmatched');
                } else if (statusValue === 'exception') {
                    matchesStatus = badgeText.startsWith('e0');
                }
            }
        }

        row.style.display = matchesSearch && matchesStatus ? '' : 'none';
    });
}

// Transaction Detail Modal
async function showTransactionDetail(bankId) {
    try {
        const response = await fetch(`/api/transaction/${bankId}`);
        if (!response.ok) throw new Error('Transaction not found');

        const data = await response.json();
        const txn = data.transaction;

        modalTitle.textContent = `${bankId} Details`;

        let html = `
            <div class="detail-section">
                <div class="detail-title">BANK TRANSACTION</div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <span class="detail-label">ID</span>
                        <span class="detail-value"><code>${txn.bank_id}</code></span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Amount</span>
                        <span class="detail-value" style="color: var(--accent-gold);">$${formatNumber(txn.bank_amount)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Date</span>
                        <span class="detail-value">${txn.bank_date}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Reference</span>
                        <span class="detail-value"><code>${txn.bank_reference}</code></span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Description</span>
                        <span class="detail-value">${txn.bank_description}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Matched</span>
                        <span class="detail-value">
                            <span class="status-badge ${txn.level1_remittance_id ? 'status-matched' : 'status-open'}">
                                ${txn.level1_remittance_id ? 'Yes - ' + txn.level1_remittance_id : 'No'}
                            </span>
                        </span>
                    </div>
                </div>
            </div>
        `;

        modalContent.innerHTML = html;
        openModal();
    } catch (error) {
        console.error('Error loading transaction:', error);
        alert('Error loading transaction details');
    }
}

// Remittance Detail Modal
function showRemittanceDetail(remId) {
    const allRemittances = [
        ...(currentData?.remittances || []),
        ...(currentData?.virtual_remittances || [])
    ];
    const rem = allRemittances.find(r => r.id === remId);

    if (!rem) return;

    modalTitle.textContent = `${remId} Details`;

    let html = `
        <div class="detail-section">
            <div class="detail-title">REMITTANCE</div>
            <div class="detail-grid">
                <div class="detail-item">
                    <span class="detail-label">ID</span>
                    <span class="detail-value"><code>${rem.id}</code></span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Customer</span>
                    <span class="detail-value">${rem.customer_name}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Total Amount</span>
                    <span class="detail-value" style="color: var(--accent-gold);">$${formatNumber(rem.total_amount)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Date</span>
                    <span class="detail-value">${rem.payment_date}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Pay Ref</span>
                    <span class="detail-value"><code>${rem.payment_reference}</code></span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Matched</span>
                    <span class="detail-value">
                        <span class="status-badge ${rem.matched_bank_transaction_id ? 'status-matched' : 'status-open'}">
                            ${rem.matched_bank_transaction_id ? 'Yes - ' + rem.matched_bank_transaction_id : 'No'}
                        </span>
                    </span>
                </div>
            </div>
        </div>
    `;

    if (rem.line_items && rem.line_items.length > 0) {
        // Build lookup for line item match status from results
        const lineMatchStatus = {};
        if (currentData?.results) {
            currentData.results.forEach(result => {
                if (result.level2_matches) {
                    result.level2_matches.forEach(l2 => {
                        if (l2.remittance_id === rem.id) {
                            lineMatchStatus[l2.line_index] = {
                                outcome: l2.outcome,
                                invoice_id: l2.invoice_id,
                                exception_code: l2.exception_code,
                                exception_detail: l2.exception_detail
                            };
                        }
                    });
                }
            });
        }

        html += `
            <div class="detail-section">
                <div class="detail-title">LINE ITEMS (${rem.line_items.length})</div>
                <table class="data-table" style="margin-top: 0.5rem;">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Invoice Ref</th>
                            <th>Amount</th>
                            <th>Inv Match Status</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        rem.line_items.forEach((li, idx) => {
            const match = lineMatchStatus[idx];
            let matchHtml;
            if (match?.outcome === 'AUTO_MATCHED') {
                matchHtml = '<span class="status-badge status-matched">Matched</span>';
            } else if (match?.outcome === 'EXCEPTION' && match.exception_code) {
                matchHtml = `<span class="status-badge status-exception" data-tooltip="${getExceptionTooltip(match.exception_code, match.exception_detail)}">${match.exception_code}</span>`;
            } else {
                matchHtml = '<span class="status-badge status-open">Unmatched</span>';
            }

            html += `
                <tr>
                    <td>${idx + 1}</td>
                    <td><code>${li.invoice_number}</code></td>
                    <td>$${formatNumber(li.amount)}</td>
                    <td>${matchHtml}</td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;
    }

    modalContent.innerHTML = html;
    openModal();
}

// Modal functions
function openModal() {
    modalOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    modalOverlay.classList.remove('active');
    document.body.style.overflow = '';
}

// Utility functions
function formatNumber(num) {
    return parseFloat(num).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function truncate(str, length) {
    if (!str) return '-';
    return str.length > length ? str.substring(0, length) + '...' : str;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
