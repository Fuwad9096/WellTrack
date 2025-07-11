document.addEventListener('DOMContentLoaded', function () {
    const currentMoodElem = document.getElementById('currentMood');
    const moodStreakElem = document.getElementById('moodStreak');
    const pointsEarnedElem = document.getElementById('pointsEarned');
    const recentActivitiesList = document.getElementById('recentActivitiesList');
    const logoutButton = document.getElementById('logoutButton');

    let moodTrendChartInstance = null;
    let moodDistributionChartInstance = null;

    function renderMoodTrendChart(labels, data) {
        const ctx = document.getElementById('moodChart').getContext('2d');
        if (moodTrendChartInstance) moodTrendChartInstance.destroy();
        moodTrendChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Mood Score (1=Bad, 5=Great)',
                    data: data,
                    borderColor: '#4F46E5',
                    backgroundColor: 'rgba(79, 70, 229, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 5,
                        ticks: {
                            stepSize: 1,
                            callback: function (value) {
                                const moodMap = { 1: 'Bad', 2: 'Neutral', 3: 'OK', 4: 'Good', 5: 'Great' };
                                return moodMap[value] || value;
                            }
                        }
                    }
                }
            }
        });
    }

    function renderMoodDistributionChart(moodCounts) {
        const ctx = document.getElementById('moodDistributionChart').getContext('2d');
        if (moodDistributionChartInstance) moodDistributionChartInstance.destroy();
        const labels = ['Very Bad', 'Bad', 'Neutral', 'Good', 'Great'];
        const data = labels.map((_, i) => moodCounts[i + 1] || 0);
        moodDistributionChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: [
                        '#EF4444', '#F97316', '#EAB308', '#22C55E', '#3B82F6'
                    ],
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right' },
                    title: { display: false }
                }
            }
        });
    }

    // Fetch dashboard data
    async function fetchDashboardData() {
        const userEmail = localStorage.getItem('user_email');
        if (!userEmail) {
            window.location.href = 'login.html';
            return;
        }
        try {
            const response = await fetch(`http://127.0.0.1:5000/dashboard_data?user_email=${userEmail}`);
            const result = await response.json();
            if (result.success) {
                const data = result.data;
                if (currentMoodElem) currentMoodElem.textContent = data.current_mood || '-';
                if (moodStreakElem) moodStreakElem.textContent = data.streak || '0';
                if (pointsEarnedElem) pointsEarnedElem.textContent = data.points_earned || '0';
                if (recentActivitiesList) {
                    recentActivitiesList.innerHTML = '';
                    (data.recent_activities || []).forEach(act => {
                        const li = document.createElement('li');
                        li.className = 'mb-2';
                        li.innerHTML = `<span class="font-semibold">${act.type}:</span> ${act.detail} <span class="text-xs text-gray-500">${act.time}</span>`;
                        if (act.notes) li.innerHTML += `<br><span class='text-xs text-gray-400'>Notes: ${act.notes}</span>`;
                        recentActivitiesList.appendChild(li);
                    });
                }
                renderMoodTrendChart(data.mood_trend_labels, data.mood_trend_data);
                // Optionally, fetch and render mood distribution chart if endpoint/data available
            } else {
                if (currentMoodElem) currentMoodElem.textContent = '-';
                if (moodStreakElem) moodStreakElem.textContent = '0';
                if (pointsEarnedElem) pointsEarnedElem.textContent = '0';
                if (recentActivitiesList) recentActivitiesList.innerHTML = '<li>No recent activities.</li>';
            }
        } catch (e) {
            if (currentMoodElem) currentMoodElem.textContent = '-';
            if (moodStreakElem) moodStreakElem.textContent = '0';
            if (pointsEarnedElem) pointsEarnedElem.textContent = '0';
            if (recentActivitiesList) recentActivitiesList.innerHTML = '<li>Error loading data.</li>';
        }
    }

    // Fetch and render Mood Distribution chart
    async function fetchMoodDistribution() {
        const userEmail = localStorage.getItem('user_email');
        if (!userEmail) return;
        try {
            const response = await fetch(`http://127.0.0.1:5000/mood_history?user_email=${userEmail}`);
            const result = await response.json();
            if (result.success && result.data.length > 0) {
                // Count moods (assuming mood_score is 1-5)
                const moodCounts = {};
                result.data.forEach(entry => {
                    moodCounts[entry.mood_score] = (moodCounts[entry.mood_score] || 0) + 1;
                });
                renderMoodDistributionChart(moodCounts);
            } else {
                renderMoodDistributionChart({});
            }
        } catch (e) {
            renderMoodDistributionChart({});
        }
    }

    // Logout logic
    if (logoutButton) {
        logoutButton.addEventListener('click', function() {
            localStorage.removeItem('user_email');
            window.location.href = 'login.html';
        });
    }

    // Initial load
    fetchDashboardData();
    fetchMoodDistribution();
});
