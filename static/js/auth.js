/**
 * PTVault Authentication Handler
 * Handles login and setup forms
 */

// Wait for both DOM and API module to be ready
function waitForAPI() {
    return new Promise((resolve) => {
        if (window.API) {
            resolve();
        } else {
            const checkAPI = setInterval(() => {
                if (window.API) {
                    clearInterval(checkAPI);
                    resolve();
                }
            }, 50);
        }
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    await waitForAPI();

    const isLoginPage = document.getElementById('loginForm');
    const isSetupPage = document.getElementById('setupForm');

    if (isLoginPage) {
        initLoginForm();
    } else if (isSetupPage) {
        initSetupForm();
    }
});

/**
 * Initialize login form
 */
function initLoginForm() {
    const form = document.getElementById('loginForm');
    const errorMessage = document.getElementById('errorMessage');
    const submitBtn = form.querySelector('button[type="submit"]');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        errorMessage.style.display = 'none';
        errorMessage.textContent = '';

        const identity = document.getElementById('loginIdentity').value.trim();
        const password = document.getElementById('password').value;

        if (!identity || !password) {
            showError('Please enter your email/username and password');
            return;
        }

        submitBtn.disabled = true;
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline';

        try {
            await API.auth.login(identity, password);
            window.location.href = '/dashboard';
        } catch (error) {
            showError(error.message || 'Login failed. Please check your credentials.');
            submitBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoading.style.display = 'none';
            document.getElementById('password').value = '';
            document.getElementById('loginIdentity').focus();
        }
    });

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
    }
}

/**
 * Initialize setup form
 */
function initSetupForm() {
    const form = document.getElementById('setupForm');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    const submitBtn = form.querySelector('button[type="submit"]');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');

    // Check if encryption is available and show the option
    checkEncryptionAvailability();

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        errorMessage.style.display = 'none';
        errorMessage.textContent = '';
        successMessage.style.display = 'none';
        successMessage.textContent = '';

        const fullName = document.getElementById('fullName').value.trim();
        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        const encryptionCheckbox = document.getElementById('enableEncryption');
        const enableEncryption = encryptionCheckbox ? encryptionCheckbox.checked : false;

        if (!email || !password || !confirmPassword) {
            showError('Please fill in all required fields');
            return;
        }

        if (password.length < 8) {
            showError('Password must be at least 8 characters long');
            return;
        }

        if (password !== confirmPassword) {
            showError('Passwords do not match');
            return;
        }

        submitBtn.disabled = true;
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline';

        try {
            await API.auth.setup({ email, password, full_name: fullName || undefined, enable_encryption: enableEncryption });

            showSuccess('Setup complete! Redirecting to dashboard...');

            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1500);
        } catch (error) {
            showError(error.message || 'Setup failed. Please try again.');
            submitBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoading.style.display = 'none';
            document.getElementById('password').value = '';
            document.getElementById('confirmPassword').value = '';
            document.getElementById('password').focus();
        }
    });

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
    }

    function showSuccess(message) {
        successMessage.textContent = message;
        successMessage.style.display = 'block';
    }
}

/**
 * Check if SQLCipher encryption is available and show/hide the encryption option.
 */
async function checkEncryptionAvailability() {
    const encryptionOption = document.getElementById('encryptionOption');
    if (!encryptionOption) return;

    try {
        const response = await fetch('/api/admin/encryption/available');
        if (response.ok) {
            const data = await response.json();
            if (data.available) {
                encryptionOption.style.display = 'block';
            }
        }
    } catch {
        // Encryption status endpoint may not be accessible before setup
        // (no auth required for this check during setup)
    }
}
