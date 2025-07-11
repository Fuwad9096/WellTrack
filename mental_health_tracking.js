// Mood tracking logic for WellTrack

document.addEventListener('DOMContentLoaded', function() {
    const moodForm = document.getElementById('mood-form');
    const moodMessage = document.getElementById('mood-message');
    const moodHistoryList = document.getElementById('mood-history-list');

    // Submit mood log
    if (moodForm) {
        moodForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const userEmail = localStorage.getItem('user_email');
            const moodScore = document.getElementById('mood-score').value;
            const notes = document.getElementById('mood-notes').value;
            if (!userEmail || !moodScore) {
                showMoodMessage('Mood score is required.', 'error');
                return;
            }
            try {
                const response = await fetch('http://127.0.0.1:5000/mood_log', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_email: userEmail, mood_score: moodScore, notes })
                });
                const result = await response.json();
                if (response.ok && result.success) {
                    showMoodMessage('Mood logged!', 'success');
                    fetchMoodHistory();
                    moodForm.reset();
                } else {
                    showMoodMessage(result.message || 'Failed to log mood.', 'error');
                }
            } catch (e) {
                showMoodMessage('Network error. Try again.', 'error');
            }
        });
    }
    function showMoodMessage(msg, type) {
        if (!moodMessage) return;
        moodMessage.textContent = msg;
        moodMessage.className = 'message-box' + (type ? ' active ' + type : '');
    }

    // Fetch and display mood history
    async function fetchMoodHistory() {
        const userEmail = localStorage.getItem('user_email');
        if (!userEmail) {
            moodHistoryList.innerHTML = '<li>Please log in to view your mood history.</li>';
            return;
        }
        try {
            const response = await fetch(`http://127.0.0.1:5000/mood_history?user_email=${userEmail}`);
            const result = await response.json();
            moodHistoryList.innerHTML = '';
            if (result.success && result.data.length > 0) {
                result.data.forEach(entry => {
                    const li = document.createElement('li');
                    li.innerHTML = `<span class='font-semibold'>${entry.mood_score}</span> <span class='text-xs text-gray-500'>${entry.timestamp}</span>${entry.notes ? `<br><span class='text-xs text-gray-400'>Notes: ${entry.notes}</span>` : ''}`;
                    moodHistoryList.appendChild(li);
                });
            } else {
                moodHistoryList.innerHTML = '<li>No mood history found.</li>';
            }
        } catch (e) {
            moodHistoryList.innerHTML = '<li>Error loading mood history.</li>';
        }
    }

    // Initial load
    fetchMoodHistory();
});
