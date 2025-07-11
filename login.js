document.addEventListener('DOMContentLoaded', function() {
            const loginForm = document.getElementById('login-form');
            const loginMessage = document.getElementById('login-message');

            if (!loginForm) return;

            loginForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const email = document.getElementById('login-email').value.trim();
                const password = document.getElementById('login-password').value;
                if (!email || !password) {
                    showMessage('Email and password are required.', 'error');
                    return;
                }
                try {
                    const response = await fetch('http://127.0.0.1:5000/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password })
                    });
                    let result = { message: 'Unknown error.' };
                    try {
                        result = await response.json();
                    } catch (err) {
                        showMessage('Invalid server response.', 'error');
                        return;
                    }
                    if (response.ok && result.success) {
                        showMessage(result.message || 'Login successful!', 'success');
                        localStorage.setItem('user_email', email);
                        setTimeout(() => {
                            window.location.href = 'dashboard.html';
                        }, 1500);
                    } else {
                        showMessage(result.message || 'Login failed.', 'error');
                    }
                } catch (error) {
                    showMessage('Network error. Could not connect to the server.', 'error');
                }
            });

            function showMessage(msg, type) {
                if (!loginMessage) return;
                loginMessage.textContent = msg;
                loginMessage.className = 'message-box' + (type ? ' active ' + type : '');
            }
        });