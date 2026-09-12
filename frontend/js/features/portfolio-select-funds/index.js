import { api } from '../../core/api.js';
// NOTE: Fund Details modal import is intentionally lazy (dynamic import in
// attachResultHandlers) so this page never pulls NAV/detail/category-analysis
// code or triggers expensive requests on initial load.

const STORAGE_KEY = 'portfolio_builder_selected_funds';
const DEBOUNCE_MS = 300;

const state = {
    query: '',
    results: [],
    selected: new Map(),
    loading: false,
    error: null,
    debounceTimer: null,
    initialized: false,
    // Filter states
    fundAge: 'any', // any, 1, 3, 5, 10 (years)
    fundStatus: 'all', // all, active, inactive
};

const $ = (id) => document.getElementById(id);

function loadFromStorage() {
    try {
        var raw = sessionStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        var arr = JSON.parse(raw);
        if (!Array.isArray(arr)) return;
        for (var i = 0; i < arr.length; i++) {
            var f = arr[i];
            if (f && typeof f.scheme_code === 'string') {
                state.selected.set(f.scheme_code, {
                    scheme_code: f.scheme_code,
                    scheme_name: f.scheme_name || f.scheme_code,
                    amc: f.amc || null,
                    category: f.category || null,
                    allocation: (typeof f.allocation === 'number' && isFinite(f.allocation)) ? f.allocation : null,
                });
            }
        }
    } catch (e) {
        console.warn('Failed to load selected funds:', e);
    }
}

function saveToStorage() {
    try {
        var items = [];
        state.selected.forEach(function(v) { items.push(v); });
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
        console.warn('Failed to save selected funds:', e);
    }
}

function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function escapeAttr(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function renderResults() {
        var container = $('pfs-results-section');
        if (!container) return;

        if (state.loading) {
            container.innerHTML =
                '<div class="pfs-loading">' +
                '  <div class="pfs-spinner"></div>' +
                '  <span>Searching funds</span>' +
                '</div>';
            return;
        }

        if (state.error) {
            container.innerHTML =
                '<div class="pfs-error" role="alert">' + escapeHtml(state.error) + '</div>';
            return;
        }

        if (!state.query || state.query.trim().length < 2) {
            container.innerHTML = renderEmptyState(
                'Search for a mutual fund to add to your portfolio',
                'Start typing in the search box above to find funds by name, scheme code, or fund house.'
            );
            return;
        }

        if (state.results.length === 0) {
            container.innerHTML = renderEmptyState(
                'No funds match your search.',
                'Try a different fund name, scheme code, or fund house.'
            );
            return;
        }

        // Apply filters
        var filteredResults = state.results.filter(function(fund) {
            // Fund Age filter
            if (state.fundAge !== 'any') {
                var minYears = parseInt(state.fundAge);
                if (fund.first_nav_date) {
                    // Parse the first_nav_date (YYYY-MM-DD format)
                    var firstDate = new Date(fund.first_nav_date);
                    var today = new Date();
                    var ageInYears = (today - firstDate) / (1000 * 60 * 60 * 24 * 365.25);
                    if (ageInYears < minYears) {
                        return false; // Too young
                    }
                } else {
                    // If we don't have first_nav_date, we can't determine age
                    // Treat as not satisfying the age filter (conservative approach)
                    return false;
                }
            }
            
            // Fund Status filter
            if (state.fundStatus !== 'all') {
                if (state.fundStatus === 'active' && !fund.is_active) {
                    return false; // Not active
                }
                if (state.fundStatus === 'inactive' && fund.is_active) {
                    return false; // Not inactive
                }
            }
            
            return true;
        });

        if (filteredResults.length === 0) {
            container.innerHTML = renderEmptyState(
                'No funds match your search and filter criteria.',
                'Try adjusting your search or filters.'
            );
            return;
        }

        var html = '<ul class="pfs-fund-list" aria-label="Search results">';
        for (var i = 0; i < filteredResults.length; i++) {
            var fund = filteredResults[i];
            var code = fund.scheme_code || '';
            var isSelected = state.selected.has(code);
            var name = fund.scheme_name || 'Unnamed Fund';
            var amc = fund.amc || '—';
            var cat = fund.category || '—';
            var disabledAttr = isSelected ? ' disabled' : '';
            var btnClass = 'pfs-btn-add' + (isSelected ? ' added' : '');
        var btnText = isSelected ? 'Added' : 'Add to Portfolio';

        html += '<li class="pfs-fund-card' + (isSelected ? ' selected' : '') + '" data-scheme-code="' + escapeAttr(code) + '">';
        html += '<div class="pfs-fund-info">';
        html += '<div class="pfs-fund-name">' + escapeHtml(name) + (fund.is_stale ? ' <span class="pfs-fund-legacy-badge" title="AMFI last published a NAV for this scheme on ' + escapeHtml(fund.nav_date || 'an earlier date') + '. A current scheme may exist.">Legacy</span>' : '') + '</div>';
html += '<div class="pfs-fund-meta">';
            html += '<span class="pfs-fund-meta-item"><span class="pfs-fund-meta-label">AMC:</span> ' + escapeHtml(amc) + '</span>';
            html += '<span class="pfs-fund-meta-item"><span class="pfs-fund-meta-label">Category:</span> ' + escapeHtml(cat) + '</span>';
            html += '<span class="pfs-fund-meta-item"><span class="pfs-fund-meta-label">Code:</span> ' + escapeHtml(code) + '</span>';
            
            // Add fund age and status
            var ageHtml = '';
            if (fund.first_nav_date) {
                var firstDate = new Date(fund.first_nav_date);
                var today = new Date();
                var ageInYears = (today - firstDate) / (1000 * 60 * 60 * 24 * 365.25);
                var ageYears = Math.floor(ageInYears);
                var ageDisplay = ageYears + ' year' + (ageYears !== 1 ? 's' : '');
                var sinceDate = firstDate.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
                ageHtml = 'Since ' + sinceDate + ' · ';
            }
            
            var statusHtml = '';
            if (fund.is_active !== undefined) {
                statusHtml = fund.is_active ? 'Active' : 'Inactive';
            }
            
            if (ageHtml || statusHtml) {
                html += '<span class="pfs-fund-meta-item">' + ageHtml + statusHtml + '</span>';
            }
            
            html += '</div>';
        html += '</div>';
        html += '<div class="pfs-fund-actions">';
        html += '<button class="' + btnClass + '" data-action="add" data-scheme-code="' + escapeAttr(code) + '"' + disabledAttr + '>' + btnText + '</button>';
        html += '<button class="pfs-btn-view" data-action="view" data-scheme-code="' + escapeAttr(code) + '" type="button">';
        html += '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
        html += 'View Details';
        html += '</button>';
        html += '</div>';
        html += '</li>';
    }
    html += '</ul>';
    container.innerHTML = html;
    attachResultHandlers(container);
}

function renderEmptyState(title, desc) {
    return (
        '<div class="pfs-empty-state">' +
        '<div class="pfs-empty-icon" aria-hidden="true">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' +
        '<circle cx="11" cy="11" r="8"></circle>' +
        '<line x1="21" y1="21" x2="16.65" y2="16.65"></line>' +
        '</svg>' +
        '</div>' +
        '<h3>' + escapeHtml(title) + '</h3>' +
        '<p>' + escapeHtml(desc) + '</p>' +
        '</div>'
    );
}

function attachResultHandlers(container) {
    var addButtons = container.querySelectorAll('button[data-action="add"]');
    for (var i = 0; i < addButtons.length; i++) {
        (function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                var code = btn.getAttribute('data-scheme-code');
                if (code) handleAddFund(code);
            });
        })(addButtons[i]);
    }

    var viewButtons = container.querySelectorAll('button[data-action="view"]');
    for (var j = 0; j < viewButtons.length; j++) {
        (function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                var code = btn.getAttribute('data-scheme-code');
                var fundName = '';
                for (var k = 0; k < state.results.length; k++) {
                    if (state.results[k].scheme_code === code) {
                        fundName = state.results[k].scheme_name || '';
                        break;
                    }
                }
                // Reuse the existing Fund Details modal from Mutual Fund
                // Analysis — no separate fund-detail implementation.
                // Lazy import keeps initial page load free of detail/NAV code.
                if (code) {
                    import('../mutual-fund-analysis/fund-detail.js')
                        .then(function(mod) { return mod.openFundDetail(code, fundName); })
                        .catch(function(err) { console.error('Failed to open fund details:', err); });
                }
            });
        })(viewButtons[j]);
    }
}

function renderSelected() {
    var container = $('pfs-selected-section');
    var list = $('pfs-selected-list');
    var empty = $('pfs-selected-empty');
    var continueSection = $('pfs-continue-section');
    var countEl = $('pfs-selected-count');
    if (!container) return;

    var count = state.selected.size;

    if (count === 0) {
        container.classList.add('hidden');
        if (empty) empty.classList.remove('hidden');
        if (continueSection) continueSection.classList.add('hidden');
        if (countEl) countEl.textContent = '';
        if (list) list.innerHTML = '';
        return;
    }

    container.classList.remove('hidden');
    if (empty) empty.classList.add('hidden');
    if (continueSection) continueSection.classList.remove('hidden');
    if (countEl) countEl.textContent = '(' + count + ')';

    if (!list) return;

    var codes = [];
    state.selected.forEach(function(v) { codes.push(v.scheme_code); });

    var html = '<ul class="pfs-selected-list" aria-label="Selected funds">';
    for (var i = 0; i < codes.length; i++) {
        var code = codes[i];
        var fund = state.selected.get(code);
        var name = fund ? fund.scheme_name : code;

        html += '<li class="pfs-selected-item" data-scheme-code="' + escapeAttr(code) + '">';
        html += '<div class="pfs-selected-item-info">';
        html += '<span class="pfs-selected-item-name" title="' + escapeAttr(name) + '">' + escapeHtml(name) + '</span>';
        html += '<span class="pfs-selected-item-meta">Scheme ' + escapeHtml(code) + '</span>';
        html += '</div>';
        html += '<button class="pfs-btn-remove" data-action="remove" data-scheme-code="' + escapeAttr(code) + '" type="button" title="Remove" aria-label="Remove ' + escapeAttr(name) + '">';
        html += '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">';
        html += '<line x1="18" y1="6" x2="6" y2="18"></line>';
        html += '<line x1="6" y1="6" x2="18" y2="18"></line>';
        html += '</svg>';
        html += '</button>';
        html += '</li>';
    }
    html += '</ul>';
    list.innerHTML = html;
    attachSelectedHandlers(list);
}

function attachSelectedHandlers(list) {
    var removeButtons = list.querySelectorAll('button[data-action="remove"]');
    for (var i = 0; i < removeButtons.length; i++) {
        (function(btn) {
            btn.addEventListener('click', function() {
                var code = btn.getAttribute('data-scheme-code');
                if (code) handleRemoveFund(code);
            });
        })(removeButtons[i]);
    }
}

function renderContinueBtn() {
    var btn = $('pfs-continue-btn');
    var hint = $('pfs-continue-hint');
    if (!btn) return;

    var count = state.selected.size;

    if (count > 0) {
        btn.classList.remove('pfs-continue-disabled');
        btn.setAttribute('aria-disabled', 'false');
        btn.textContent = 'Continue to Allocation (' + count + ' selected)';
        if (hint) hint.classList.add('hidden');
    } else {
        btn.classList.add('pfs-continue-disabled');
        btn.setAttribute('aria-disabled', 'true');
        btn.textContent = 'Continue to Allocation';
        if (hint) hint.classList.remove('hidden');
    }
}

function handleAddFund(code) {
    if (state.selected.has(code)) {
        flashCard(code);
        return;
    }

    for (var i = 0; i < state.results.length; i++) {
        if (state.results[i].scheme_code === code) {
            var fund = state.results[i];
            state.selected.set(code, {
                scheme_code: fund.scheme_code,
                scheme_name: fund.scheme_name || fund.scheme_code,
                amc: fund.amc || null,
                category: fund.category || null,
            });
            saveToStorage();
            renderResults();
            renderSelected();
            renderContinueBtn();

            var statusInline = $('pfs-search-status-inline');
            if (statusInline) {
                statusInline.textContent = 'Added: ' + (fund.scheme_name || code);
                statusInline.classList.remove('hidden');
                setTimeout(function() { statusInline.classList.add('hidden'); }, 3000);
            }
            return;
        }
    }
}

function handleRemoveFund(code) {
    state.selected.delete(code);
    saveToStorage();
    renderResults();
    renderSelected();
    renderContinueBtn();
}

function flashCard(code) {
    var cards = document.querySelectorAll('.pfs-fund-card[data-scheme-code="' + code.replace(/"/g, '\\"') + '"]');
    for (var i = 0; i < cards.length; i++) {
        var el = cards[i];
        el.style.transition = 'background-color 0.15s ease';
        el.style.backgroundColor = 'var(--color-gold-100)';
        (function(el2) {
            setTimeout(function() { el2.style.backgroundColor = ''; }, 600);
        })(el);
    }
}

function performSearch(query) {
        var trimmed = (query || '').trim();
        state.query = trimmed;
        if (trimmed.length < 2) {
            state.results = [];
            state.error = null;
            var statusEmpty = $('pfs-search-status');
            if (statusEmpty) { statusEmpty.classList.add('hidden'); statusEmpty.textContent = ''; }
            renderResults();
            return;
        }

        state.loading = true;
        state.error = null;
        renderResults();

        // Build query parameters
        var params = new URLSearchParams();
        params.append('q', trimmed);
        // Request a larger number of results to enable accurate local filtering
        // The backend allows up to 5000 results per request
        params.append('limit', '5000');

        api.get('/mutual-funds/search?' + params.toString())
            .then(function(data) {
                state.results = Array.isArray(data.results) ? data.results : [];
                var status = $('pfs-search-status');
                if (status) {
                    var countText = state.results.length === 1 ? '1 fund' : state.results.length + ' funds';
                    var totalText = data.total !== undefined ? data.total : 'unknown';
                    if (data.total !== undefined && state.results.length < data.total) {
                        status.textContent = 'Showing ' + state.results.length + ' of ' + data.total + ' matching "' + trimmed + '"';
                    } else {
                        status.textContent = state.results.length > 0 ? 'Found ' + countText + ' matching "' + trimmed + '"' : '';
                    }
                }
                state.error = null;
            })
            .catch(function(err) {
                state.results = [];
                state.error = err && err.message ? err.message : 'Search failed. Please try again.';
                console.error('Fund search failed:', err);
            })
            .finally(function() {
                state.loading = false;
                renderResults();
            });
    }

function onSearchInput(e) {
    var value = e.target.value;
    state.query = value;
    if (state.debounceTimer) clearTimeout(state.debounceTimer);
    state.debounceTimer = setTimeout(function() {
        performSearch(value);
    }, DEBOUNCE_MS);
}

function initSearch() {
        var input = $('pfs-search-input');
        var clearBtn = $('pfs-search-clear');
        if (!input) return;

        input.addEventListener('input', function(e) {
            onSearchInput(e);
            if (clearBtn) {
                if (e.target.value.trim().length > 0) {
                    clearBtn.classList.remove('hidden');
                } else {
                    clearBtn.classList.add('hidden');
                }
            }
        });

        // Initialize filter dropdowns
        var ageFilter = $('pfs-fund-age-filter');
        var statusFilter = $('pfs-fund-status-filter');
        
        if (ageFilter) {
            ageFilter.value = state.fundAge;
            ageFilter.addEventListener('change', function(e) {
                state.fundAge = e.target.value;
                renderResults();
            });
        }
        
        if (statusFilter) {
            statusFilter.value = state.fundStatus;
            statusFilter.addEventListener('change', function(e) {
                state.fundStatus = e.target.value;
                renderResults();
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                input.value = '';
                state.query = '';
                if (state.debounceTimer) clearTimeout(state.debounceTimer);
                state.results = [];
                state.error = null;
                renderResults();
                input.focus();
            });
        }
    }

export function initPortfolioSelectFunds() {
    if (state.initialized) return;
    state.initialized = true;
    state.selected = new Map();
    loadFromStorage();
    initSearch();
    var continueBtn = $('pfs-continue-btn');
    if (continueBtn) {
        continueBtn.addEventListener('click', function(e) {
            if (state.selected.size === 0) e.preventDefault();
        });
    }
    renderSelected();
    renderContinueBtn();
    renderResults();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPortfolioSelectFunds);
} else {
    initPortfolioSelectFunds();
}
