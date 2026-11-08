/* Finding editor page (moved out of finding_editor.html: the CSP allows no inline script, L-21). */
// Initialize EasyMDE instances
const findingMDE = new EasyMDE({
    element: document.getElementById('findingContent'),
    autoDownloadFontAwesome: false,  // vendored in static/vendor; never fetch from a CDN
    placeholder: 'Describe the vulnerability, impact, and proof of concept...',
    spellChecker: false,
    autosave: { enabled: false },
    minHeight: '280px',
    toolbar: [
        'bold', 'italic', 'heading', '|',
        'quote', 'code', 'unordered-list', 'ordered-list', '|',
        'link', '|',
        'preview', 'side-by-side', 'fullscreen'
    ],
    // EasyMDE's own bundled marked does not sanitize (H-9)
    previewRender: plainText => renderMarkdown(plainText)
});

const remediationMDE = new EasyMDE({
    element: document.getElementById('remediationContent'),
    autoDownloadFontAwesome: false,  // vendored in static/vendor; never fetch from a CDN
    placeholder: 'Describe recommended fixes and mitigations...',
    spellChecker: false,
    autosave: { enabled: false },
    minHeight: '280px',
    toolbar: [
        'bold', 'italic', 'heading', '|',
        'quote', 'code', 'unordered-list', 'ordered-list', '|',
        'link', '|',
        'preview', 'side-by-side', 'fullscreen'
    ],
    // EasyMDE's own bundled marked does not sanitize (H-9)
    previewRender: plainText => renderMarkdown(plainText)
});

// Clipboard image paste for both editors
[findingMDE, remediationMDE].forEach(function(mde) {
    attachClipboardImagePaste(mde, {
        engagementId: function () {
            return window.AppState && window.AppState.activeEngagement
                ? window.AppState.activeEngagement.id
                : null;
        },
        hostId: function () { return null; }, // findings don't carry a host context
        onError: function (msg) {
            if (window.showToast) window.showToast(msg, 'error');
            else console.warn(msg);
        },
    });
});

// Get parameters from URL
const urlParams = new URLSearchParams(window.location.search);
const hostIp = urlParams.get('host_ip') || '';
const hostHostname = urlParams.get('host_hostname') || '';
const returnHost = urlParams.get('return_host');
const returnTab = urlParams.get('return_tab');
const editFindingId = urlParams.get('finding_id');

let isEditMode = !!editFindingId;
let editEngagementId = null;

if (isEditMode) {
    document.getElementById('pageTitle').textContent = 'Edit Finding';
    document.getElementById('saveBtn').textContent = 'Update Finding';
    document.title = 'Edit Finding - PTVault';
    waitForAPI().then(() => loadFindingForEdit(parseInt(editFindingId)));
} else {
    if (hostIp) document.getElementById('findingIpAddress').value = hostIp;
    if (hostHostname) document.getElementById('findingHostname').value = hostHostname;
}

// Initialize theme
document.addEventListener('DOMContentLoaded', function() {
    ThemeManager.init();
});

function waitForAPI() {
    return new Promise(resolve => {
        if (window.API) return resolve();
        const check = setInterval(() => {
            if (window.API) { clearInterval(check); resolve(); }
        }, 50);
    });
}

async function loadFindingForEdit(findingId) {
    try {
        const activeData = await API.engagements.getActive();
        editEngagementId = activeData.id || activeData.active_engagement_id || null;
        if (!editEngagementId) {
            alert('No active engagement.');
            window.location.href = '/dashboard';
            return;
        }

        const findings = await API.engagements.getFindings(editEngagementId);
        const finding = findings.find(f => f.id === findingId);
        if (!finding) {
            alert('Finding not found.');
            window.location.href = getDashboardReturnUrl();
            return;
        }

        document.getElementById('findingTitle').value = finding.title || '';
        document.getElementById('findingIpAddress').value = finding.ip_address || '';
        document.getElementById('findingHostname').value = finding.hostname || '';
        document.getElementById('findingCriticality').value = finding.criticality || 'medium';
        document.getElementById('findingCvss').value = finding.cvss_score !== null && finding.cvss_score !== undefined ? finding.cvss_score : '';
        document.getElementById('findingIncludeReport').checked = finding.include_in_report;

        findingMDE.value(finding.finding_content || '');
        remediationMDE.value(finding.remediation_content || '');
    } catch (error) {
        console.error('Failed to load finding:', error);
        alert('Failed to load finding for editing.');
        window.location.href = getDashboardReturnUrl();
    }
}

function getDashboardReturnUrl() {
    const params = new URLSearchParams();
    if (returnHost) params.set('host', returnHost);
    if (returnTab) params.set('tab', returnTab);
    const qs = params.toString();
    return '/dashboard' + (qs ? '?' + qs : '');
}

async function saveFinding() {
    const title = document.getElementById('findingTitle').value.trim();
    if (!title) {
        alert('Title is required');
        return;
    }

    const findingData = {
        title,
        ip_address: document.getElementById('findingIpAddress').value.trim() || null,
        hostname: document.getElementById('findingHostname').value.trim() || null,
        criticality: document.getElementById('findingCriticality').value,
        cvss_score: document.getElementById('findingCvss').value ? parseFloat(document.getElementById('findingCvss').value) : null,
        finding_content: findingMDE.value() || null,
        remediation_content: remediationMDE.value() || null,
        include_in_report: document.getElementById('findingIncludeReport').checked
    };

    try {
        if (isEditMode) {
            const engId = editEngagementId || (await API.engagements.getActive()).id;
            await API.engagements.updateFinding(engId, parseInt(editFindingId), findingData);
        } else {
            const activeData = await API.engagements.getActive();
            const activeEngagementId = activeData.id || activeData.active_engagement_id || null;
            if (!activeEngagementId) {
                alert('No active engagement. Please select an engagement first.');
                window.location.href = '/dashboard';
                return;
            }
            await API.engagements.createFinding(activeEngagementId, findingData);
        }

        window.location.href = getDashboardReturnUrl();
    } catch (error) {
        console.error('Failed to save finding:', error);
        alert('Failed to save finding: ' + (error.message || 'Please try again.'));
    }
}

function cancelFinding() {
    const hasContent = document.getElementById('findingTitle').value.trim() || findingMDE.value().trim();
    if (!isEditMode && hasContent && !confirm('Discard this finding?')) return;
    if (isEditMode && !confirm('Discard changes?')) return;
    window.location.href = getDashboardReturnUrl();
}
