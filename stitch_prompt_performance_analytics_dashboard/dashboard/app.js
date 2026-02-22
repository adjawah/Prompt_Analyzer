/**
 * Dashboard — Frontend Logic
 * Fetches data from /dashboard/* API endpoints and renders charts + tables.
 */

const API = window.location.origin;

let currentPage = 0;
const PAGE_SIZE = 20;
let allInteractions = [];
let trendChart = null;
let mistakesChart = null;

// ── Initialize ────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    refreshAll();
});

async function refreshAll() {
    await Promise.all([
        loadOverview(),
        loadTrends(),
        loadMistakes(),
        loadInteractions(),
        loadAgents(),
    ]);
}

// ── Overview KPIs ─────────────────────────────────────────────

async function loadOverview() {
    try {
        const res = await fetch(`${API}/dashboard/overview`);
        const data = await res.json();

        document.getElementById('kpi-total').textContent = data.total_interactions.toLocaleString();
        document.getElementById('kpi-avg-score').textContent = `${data.avg_overall_score}%`;
        document.getElementById('kpi-savings').textContent = `${data.avg_token_savings}%`;
        document.getElementById('kpi-rewrite').textContent = `${data.rewrite_acceptance_rate}%`;
        document.getElementById('kpi-split').textContent = `${data.human_count}H / ${data.agent_count}A`;

        document.getElementById('kpi-total-tokens').textContent = data.total_tokens.toLocaleString();
        document.getElementById('kpi-avg-tokens').textContent = Math.round(data.avg_tokens_per_prompt).toLocaleString();
    } catch (e) {
        console.error('Failed to load overview:', e);
    }
}

// ── Trends Chart ──────────────────────────────────────────────

async function loadTrends(params = {}) {
    try {
        const url = new URL(`${API}/dashboard/trends`);
        if (params.hours) {
            url.searchParams.set('hours', params.hours);
        } else {
            url.searchParams.set('days', params.days || 30);
        }
        const res = await fetch(url);
        const data = await res.json();

        if (!data || data.length === 0) {
            document.getElementById('trend-chart').style.display = 'none';
            document.getElementById('trend-empty').classList.remove('hidden');
            return;
        }

        document.getElementById('trend-chart').style.display = 'block';
        document.getElementById('trend-empty').classList.add('hidden');

        const ctx = document.getElementById('trend-chart').getContext('2d');

        if (trendChart) trendChart.destroy();

        // Format labels based on whether data is hourly or daily
        const labels = data.map(d => {
            if (d.date && d.date.includes(':')) {
                // Hourly format: show time
                const parts = d.date.split(' ');
                return parts.length > 1 ? parts[1] : d.date;
            }
            return d.date;
        });

        // Calculate max interactions for axis scaling
        const maxCount = Math.max(...data.map(d => d.count), 1);

        trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Avg Quality Score',
                    data: data.map(d => d.avg_score),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: '#3b82f6',
                }, {
                    label: 'Interactions',
                    data: data.map(d => d.count),
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                    fill: false,
                    tension: 0.4,
                    pointRadius: 3,
                    pointBackgroundColor: '#8b5cf6',
                    yAxisID: 'y1',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        labels: { color: '#8899b4', font: { family: 'Inter', size: 12 } }
                    },
                },
                scales: {
                    x: {
                        ticks: { color: '#5a6a85', font: { size: 11 }, maxRotation: 45 },
                        grid: { color: 'rgba(42, 52, 82, 0.5)' },
                    },
                    y: {
                        min: 0, max: 100,
                        ticks: { color: '#5a6a85', font: { size: 11 } },
                        grid: { color: 'rgba(42, 52, 82, 0.5)' },
                    },
                    y1: {
                        position: 'right',
                        min: 0,
                        suggestedMax: maxCount + 1,
                        ticks: {
                            color: '#5a6a85',
                            font: { size: 11 },
                            stepSize: 1,
                            precision: 0,
                        },
                        grid: { display: false },
                    },
                },
            },
        });
    } catch (e) {
        console.error('Failed to load trends:', e);
    }
}

function setTrendFilter(btn) {
    // Update active state
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // Build params
    const params = {};
    if (btn.dataset.hours) {
        params.hours = parseInt(btn.dataset.hours);
    } else if (btn.dataset.days) {
        params.days = parseInt(btn.dataset.days);
    }

    loadTrends(params);
}

// ── Mistakes Chart ────────────────────────────────────────────

async function loadMistakes() {
    try {
        const res = await fetch(`${API}/dashboard/mistakes?limit=6`);
        const data = await res.json();

        if (!data || data.length === 0) {
            document.getElementById('mistakes-chart').style.display = 'none';
            document.getElementById('mistakes-empty').classList.remove('hidden');
            return;
        }

        document.getElementById('mistakes-chart').style.display = 'block';
        document.getElementById('mistakes-empty').classList.add('hidden');

        const ctx = document.getElementById('mistakes-chart').getContext('2d');

        if (mistakesChart) mistakesChart.destroy();

        const colors = ['#ef4444', '#f59e0b', '#3b82f6', '#8b5cf6', '#06b6d4', '#10b981'];

        mistakesChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(d => formatMistakeType(d.type)),
                datasets: [{
                    data: data.map(d => d.count),
                    backgroundColor: colors.slice(0, data.length),
                    borderColor: '#1a2235',
                    borderWidth: 3,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { color: '#8899b4', font: { family: 'Inter', size: 11 }, padding: 12 },
                    },
                },
            },
        });
    } catch (e) {
        console.error('Failed to load mistakes:', e);
    }
}

// ── Interactions Feed ─────────────────────────────────────────

async function loadInteractions() {
    try {
        const projectFilter = document.getElementById('feed-filter').value.trim() || null;
        const url = new URL(`${API}/dashboard/interactions`);
        url.searchParams.set('limit', PAGE_SIZE);
        url.searchParams.set('offset', currentPage * PAGE_SIZE);
        if (projectFilter) url.searchParams.set('project_id', projectFilter);

        const res = await fetch(url);
        const data = await res.json();

        allInteractions = data.interactions;
        const total = data.total;

        renderFeed(allInteractions);

        // Pagination
        const totalPages = Math.ceil(total / PAGE_SIZE) || 1;
        document.getElementById('page-info').textContent = `Page ${currentPage + 1} of ${totalPages}`;
        document.getElementById('prev-btn').disabled = currentPage === 0;
        document.getElementById('next-btn').disabled = (currentPage + 1) * PAGE_SIZE >= total;

    } catch (e) {
        console.error('Failed to load interactions:', e);
    }
}

function renderFeed(rows) {
    const tbody = document.getElementById('feed-body');

    if (!rows || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="feed-empty">No interactions yet — go analyze some prompts!</td></tr>';
        return;
    }

    tbody.innerHTML = rows.map(row => {
        const score = row.overall_score;
        const scoreClass = score >= 85 ? 'excellent' : score >= 65 ? 'good' : score >= 40 ? 'fair' : 'poor';
        const source = row.source_agent
            ? `<span class="source-badge">🤖 ${escapeHtml(row.source_agent)}</span>`
            : '<span class="source-badge">👤 Human</span>';
        const preview = escapeHtml((row.original_prompt || '').substring(0, 60)) + (row.original_prompt && row.original_prompt.length > 60 ? '...' : '');
        const rewrite = row.rewrite_used === 1 ? '✅' : row.rewrite_used === 0 ? '❌' : '—';
        const time = formatTime(row.timestamp);

        return `
            <tr>
                <td>${time}</td>
                <td>${source}</td>
                <td>${escapeHtml(row.project_id || '—')}</td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;font-family:var(--font-mono);font-size:12px;">${preview}</td>
                <td><span class="score-badge ${scoreClass}">${score}</span></td>
                <td>${row.mistake_count}</td>
                <td>${row.token_savings_percent}%</td>
                <td>${rewrite}</td>
                <td><button class="view-btn" onclick='viewDetail(${row.id})'>View</button></td>
            </tr>
        `;
    }).join('');
}

function filterFeed() {
    currentPage = 0;
    loadInteractions();
}

function prevPage() {
    if (currentPage > 0) { currentPage--; loadInteractions(); }
}

function nextPage() {
    currentPage++;
    loadInteractions();
}

// ── Agent Leaderboard ─────────────────────────────────────────

async function loadAgents() {
    try {
        const res = await fetch(`${API}/dashboard/agents`);
        const data = await res.json();

        const tbody = document.getElementById('agent-body');

        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="feed-empty">No agent data yet</td></tr>';
            return;
        }

        tbody.innerHTML = data.map((agent, i) => {
            const scoreClass = agent.avg_score >= 85 ? 'excellent' : agent.avg_score >= 65 ? 'good' : agent.avg_score >= 40 ? 'fair' : 'poor';
            return `
                <tr>
                    <td style="font-weight:700;">#${i + 1}</td>
                    <td>🤖 ${escapeHtml(agent.agent_id)}</td>
                    <td>${agent.total_prompts}</td>
                    <td><span class="score-badge ${scoreClass}">${agent.avg_score}</span></td>
                    <td>${agent.improvement_trend}</td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.error('Failed to load agents:', e);
    }
}

// ── Detail Modal ──────────────────────────────────────────────

async function viewDetail(id) {
    // Find the row in current data
    const row = allInteractions.find(r => r.id === id);
    if (!row) return;

    const fullResult = row.full_result_json ? JSON.parse(row.full_result_json) : null;

    const modal = document.getElementById('detail-modal');
    const body = document.getElementById('modal-body');

    let scoresHtml = '';
    if (fullResult && fullResult.scores) {
        const dims = ['clarity', 'token_efficiency', 'goal_alignment', 'structure', 'vagueness_index'];
        scoresHtml = `<div class="modal-scores">${dims.map(d => {
            const s = fullResult.scores[d];
            const color = getScoreColor(s.score);
            return `<div class="modal-score-item">
                <span class="score-val" style="color:${color}">${s.score}</span>
                <span class="score-name">${formatDimension(d)}</span>
            </div>`;
        }).join('')}</div>`;
    }

    let mistakesHtml = '';
    if (fullResult && fullResult.mistakes && fullResult.mistakes.length > 0) {
        mistakesHtml = `
            <div class="modal-prompt-section">
                <div class="modal-prompt-label">Mistakes (${fullResult.mistakes.length})</div>
                ${fullResult.mistakes.map(m => `
                    <div style="padding:8px 12px;background:var(--bg-input);border-radius:var(--radius-sm);margin-bottom:8px;border-left:3px solid var(--accent-red);">
                        <div style="font-size:11px;font-weight:600;color:var(--accent-red);text-transform:uppercase;">${formatMistakeType(m.type)}</div>
                        ${m.text ? `<div style="font-family:var(--font-mono);font-size:12px;margin:4px 0;">"${escapeHtml(m.text)}"</div>` : ''}
                        <div style="font-size:12px;color:var(--accent-green);">💡 ${escapeHtml(m.suggestion)}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    body.innerHTML = `
        <div style="margin-bottom:16px;">
            <span class="score-badge ${row.overall_score >= 85 ? 'excellent' : row.overall_score >= 65 ? 'good' : row.overall_score >= 40 ? 'fair' : 'poor'}" style="font-size:16px;padding:6px 16px;">
                Overall: ${row.overall_score}
            </span>
            <span style="margin-left:12px;color:var(--text-muted);font-size:13px;">
                ${formatTime(row.timestamp)} · ${row.source_agent ? '🤖 ' + row.source_agent : '👤 Human'}
                ${row.project_id ? ' · 📁 ' + row.project_id : ''}
            </span>
        </div>

        ${scoresHtml}

        <div class="modal-prompt-section">
            <div class="modal-prompt-label">Original Prompt (${row.original_tokens} tokens)</div>
            <div class="modal-prompt-text">${escapeHtml(row.original_prompt)}</div>
        </div>

        ${row.rewritten_prompt ? `
        <div class="modal-prompt-section">
            <div class="modal-prompt-label">Optimized Rewrite (${row.rewritten_tokens} tokens · ${row.token_savings_percent}% saved)</div>
            <div class="modal-prompt-text" style="border-color:var(--accent-green);">${escapeHtml(row.rewritten_prompt)}</div>
        </div>` : ''}

        ${mistakesHtml}
    `;

    modal.classList.remove('hidden');
}

function closeModal(event) {
    if (event.target === event.currentTarget) {
        document.getElementById('detail-modal').classList.add('hidden');
    }
}

function closeDetail() {
    document.getElementById('detail-modal').classList.add('hidden');
}

// ── Helpers ───────────────────────────────────────────────────

function formatTime(ts) {
    if (!ts) return '—';
    try {
        const d = new Date(ts);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
            ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch { return ts; }
}

function formatMistakeType(type) {
    return (type || 'unknown').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatDimension(dim) {
    return dim.replace(/_/g, ' ');
}

function getScoreColor(score) {
    if (score >= 85) return '#10b981';
    if (score >= 65) return '#3b82f6';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
