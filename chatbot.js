document.addEventListener('DOMContentLoaded', function () {
    const chatbotIcon = document.getElementById('chatbotIcon');
    const chatbotWindow = document.getElementById('chatbotWindow');
    const closeChatbot = document.getElementById('closeChatbot');
    const chatbotMessages = document.getElementById('chatbotMessages');
    const userInput = document.getElementById('userInput');
    const sendMessage = document.getElementById('sendMessage');

    function displayMessage(message, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender}-message`;
        msgDiv.textContent = message;
        chatbotMessages.appendChild(msgDiv);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    }

    function removeTypingIndicator() {
        const typing = chatbotMessages.querySelector('.typing-indicator');
        if (typing) typing.remove();
    }

    async function sendUserMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        displayMessage(message, 'user');
        userInput.value = '';

        const typing = document.createElement('div');
        typing.className = 'message bot-message typing-indicator';
        typing.textContent = 'Typing...';
        chatbotMessages.appendChild(typing);

        try {
            const response = await fetch('http://127.0.0.1:5000/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message })
            });

            const data = await response.json();
            removeTypingIndicator();

            if (response.ok) {
                displayMessage(data.reply, 'bot');
            } else {
                displayMessage('Oops! Error: ' + (data.reply || 'Unknown error'), 'bot');
            }

        } catch (error) {
            removeTypingIndicator();
            displayMessage('Oops! Something went wrong: ' + error.message, 'bot');
        }
    }

    sendMessage.addEventListener('click', sendUserMessage);
    userInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendUserMessage();
        }
    });

    chatbotIcon?.addEventListener('click', () => {
        chatbotWindow.style.display = 'flex';
        chatbotWindow.offsetHeight;
        chatbotWindow.classList.add('active');
        chatbotIcon.style.display = 'none';
    });

    closeChatbot?.addEventListener('click', () => {
        chatbotWindow.classList.remove('active');
        setTimeout(() => {
            chatbotWindow.style.display = 'none';
            chatbotIcon.style.display = 'flex';
        }, 300);
    });
});
