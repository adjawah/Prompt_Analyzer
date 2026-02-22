/**
 * Prompt Analyzer — Frontend Logic
 */

const API_BASE = window.location.origin;

let currentAnalysisId = null;
let currentResult = null;

// ── Character count ───────────────────────────────────────────

const promptInput = document.getElementById('prompt-input');
const charCount = document.getElementById('char-count');

promptInput.addEventListener('input', () => {
    const len = promptInput.value.length;
    charCount.textContent = `${len.toLocaleString()} characters`;
});

// ── Analyze ───────────────────────────────────────────────────

async function analyzePrompt() {
    const prompt = promptInput.value.trim();
    if (!prompt) {
        showToast('Please enter a prompt to analyze', 'warning');
        return;
    }

    const context = document.getElementById('context-input').value.trim() || null;
    const projectId = document.getElementById('project-input').value.trim() || null;

    const btn = document.getElementById('analyze-btn');
    btn.disabled = true;

    hideResults();
    hideError();
    showLoading();

    try {
        const response = await fetch(`${API_BASE}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt,
                context,
                project_id: projectId,
            }),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${response.status}`);
        }

        const result = await response.json();
        currentResult = result;
        currentAnalysisId = result.analysis_id;

        hideLoading();
        renderResults(result);

    } catch (error) {
        hideLoading();
        showError(error.message);
    } finally {
        btn.disabled = false;
    }
}

// ── Render Results ────────────────────────────────────────────

function renderResults(result) {
    const section = document.getElementById('results-section');
    section.classList.remove('hidden');

    // Overall score
    const score = result.overall_score;
    const scoreCard = document.getElementById('overall-score-card');
    const scoreRing = document.getElementById('score-ring');
    const scoreValue = document.getElementById('overall-score');
    const scoreLabel = document.getElementById('overall-label');

    // Remove old class
    scoreCard.className = 'overall-score-card';
    if (score >= 85) {
        scoreCard.classList.add('score-excellent');
        scoreLabel.textContent = 'Excellent — This prompt is well-crafted';
    } else if (score >= 65) {
        scoreCard.classList.add('score-good');
        scoreLabel.textContent = 'Good — Minor improvements possible';
    } else if (score >= 40) {
        scoreCard.classList.add('score-fair');
        scoreLabel.textContent = 'Fair — Several issues to address';
    } else {
        scoreCard.classList.add('score-poor');
        scoreLabel.textContent = 'Poor — Major improvements needed';
    }

    // Animate ring
    const circumference = 2 * Math.PI * 52; // r=52
    const offset = circumference - (score / 100) * circumference;
    scoreRing.style.strokeDashoffset = offset;

    // Animate number
    animateNumber(scoreValue, score);

    // Dimension scores
    const dimensions = ['clarity', 'token_efficiency', 'goal_alignment', 'structure', 'vagueness_index'];
    dimensions.forEach(dim => {
        const data = result.scores[dim];
        const numEl = document.querySelector(`[data-dimension="${dim}"]`);
        const reasoningEl = document.getElementById(`reasoning-${dim}`);

        animateNumber(numEl, data.score);
        reasoningEl.textContent = data.reasoning;

        // Color the score
        const card = document.getElementById(`score-${dim}`);
        card.style.borderColor = getScoreColor(data.score);
        numEl.style.color = getScoreColor(data.score);
    });

    // Mistakes
    const mistakesList = document.getElementById('mistakes-list');
    const mistakeCount = document.getElementById('mistake-count');
    const mistakes = result.mistakes || [];

    mistakeCount.textContent = `${mistakes.length} issue${mistakes.length !== 1 ? 's' : ''}`;
    mistakeCount.className = mistakes.length === 0 ? 'badge badge-success' : 'badge badge-error';

    if (mistakes.length === 0) {
        mistakesList.innerHTML = `
            <div style="text-align:center; padding:20px; color:var(--accent-green);">
                <span class="material-symbols-outlined" style="font-size:32px;">check_circle</span>
                <p style="margin-top:8px;">No issues found — great prompt!</p>
            </div>
        `;
    } else {
        mistakesList.innerHTML = mistakes.map(m => `
            <div class="mistake-item">
                <div class="mistake-icon">
                    <span class="material-symbols-outlined">${getMistakeIcon(m.type)}</span>
                </div>
                <div class="mistake-content">
                    <div class="mistake-type">${formatMistakeType(m.type)}</div>
                    ${m.text ? `<div class="mistake-text">"${escapeHtml(m.text)}"</div>` : ''}
                    <div class="mistake-suggestion">${escapeHtml(m.suggestion)}</div>
                </div>
            </div>
        `).join('');
    }

    // Rewrite comparison
    document.getElementById('original-text').textContent = result.original_prompt;
    document.getElementById('rewritten-text').textContent = result.rewritten_prompt;

    const tc = result.token_comparison;
    document.getElementById('original-tokens').textContent = `${tc.original_tokens} tokens`;
    document.getElementById('rewritten-tokens').textContent = `${tc.rewritten_tokens} tokens`;
    document.getElementById('savings-text').textContent = `${tc.savings_percent}% saved`;

    // Scroll to results
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Rewrite Choice ────────────────────────────────────────────

async function useRewrite() {
    if (!currentResult) return;

    // Paste rewritten prompt into the input textarea
    promptInput.value = currentResult.rewritten_prompt;
    charCount.textContent = `${promptInput.value.length.toLocaleString()} characters`;

    // Also copy to clipboard
    try {
        await navigator.clipboard.writeText(currentResult.rewritten_prompt);
        showToast('Rewritten prompt pasted into input & copied to clipboard!', 'success');
    } catch {
        showToast('Rewritten prompt pasted into input!', 'success');
    }

    // Scroll back to prompt input
    promptInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
    promptInput.focus();

    if (currentAnalysisId) {
        fetch(`${API_BASE}/rewrite-choice`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ analysis_id: currentAnalysisId, used_rewrite: true }),
        }).catch(() => { });
    }
}

async function keepOriginal() {
    if (!currentResult) return;

    try {
        await navigator.clipboard.writeText(currentResult.original_prompt);
        showToast('Original prompt copied to clipboard!', 'success');
    } catch {
        showToast('Could not copy to clipboard', 'warning');
    }

    if (currentAnalysisId) {
        fetch(`${API_BASE}/rewrite-choice`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ analysis_id: currentAnalysisId, used_rewrite: false }),
        }).catch(() => { });
    }
}

// ── Helpers ───────────────────────────────────────────────────

function animateNumber(el, target) {
    let current = 0;
    const duration = 1200;
    const stepTime = 16;
    const steps = duration / stepTime;
    const increment = target / steps;

    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        el.textContent = Math.round(current);
    }, stepTime);
}

function getScoreColor(score) {
    if (score >= 85) return 'var(--accent-green)';
    if (score >= 65) return 'var(--accent-blue)';
    if (score >= 40) return 'var(--accent-amber)';
    return 'var(--accent-red)';
}

function getMistakeIcon(type) {
    const icons = {
        vague_instruction: 'blur_on',
        missing_context: 'help_outline',
        redundancy: 'content_copy',
        contradiction: 'sync_problem',
        poor_formatting: 'format_align_left',
        missing_output_format: 'output',
        unclear_scope: 'unfold_more',
        overly_complex: 'device_hub',
    };
    return icons[type] || 'warning';
}

function formatMistakeType(type) {
    return type.replace(/_/g, ' ');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showLoading() {
    document.getElementById('loading-section').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading-section').classList.add('hidden');
}

function hideResults() {
    document.getElementById('results-section').classList.add('hidden');
}

function showError(message) {
    document.getElementById('error-message').textContent = message;
    document.getElementById('error-section').classList.remove('hidden');
}

function hideError() {
    document.getElementById('error-section').classList.add('hidden');
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const icon = document.getElementById('toast-icon');
    const msg = document.getElementById('toast-message');

    icon.textContent = type === 'success' ? 'check_circle' : 'warning';
    icon.style.color = type === 'success' ? 'var(--accent-green)' : 'var(--accent-amber)';
    msg.textContent = message;

    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 3000);
}

// Allow Ctrl+Enter to submit
promptInput.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        analyzePrompt();
    }
});
