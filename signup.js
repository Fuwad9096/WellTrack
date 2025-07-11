document.addEventListener('DOMContentLoaded', function() {
    const signupForm = document.getElementById('signup-form');
    const signupMessage = document.getElementById('signup-message');
    const signupSubmitBtn = document.getElementById('signup-submit-btn');

    if (!signupForm) return;

    signupForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Terms & Conditions checkbox
        const termsCheckbox = document.getElementById('terms');
        if (termsCheckbox && !termsCheckbox.checked) {
            showMessage('You must agree to the Terms & Conditions.', 'error');
            return;
        }

        signupSubmitBtn.disabled = true;
        signupSubmitBtn.textContent = 'Signing Up...';
        showMessage('', '');

        const email = document.getElementById('signup-email').value.trim();
        const password = document.getElementById('signup-password').value;

        if (!email || !password) {
            showMessage('Email and password are required.', 'error');
            resetButton();
            return;
        }

        try {
            const response = await fetch('http://127.0.0.1:5000/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            let result = { message: 'Unknown error.' };
            try {
                result = await response.json();
            } catch (err) {
                showMessage('Invalid server response.', 'error');
                resetButton();
                return;
            }

            if (response.ok && result.success) {
                showMessage(result.message || 'Signup successful!', 'success');
                signupForm.reset();
                setTimeout(() => {
                    window.location.href = 'login.html';
                }, 2000);
            } else {
                showMessage(result.message || 'Signup failed.', 'error');
            }
        } catch (error) {
            showMessage('Network error. Could not connect to the server.', 'error');
        }
        resetButton();
    });

    function showMessage(msg, type) {
        if (!signupMessage) return;
        signupMessage.textContent = msg;
        signupMessage.className = 'message-box' + (type ? ' active ' + type : '');
    }

    function resetButton() {
        signupSubmitBtn.disabled = false;
        signupSubmitBtn.textContent = 'Create Account';
    }
});