# README: How to run your WellTrack app locally

## 1. Start the Flask Backend

- Open a terminal in your project directory.
- Run:
  ```bash
  python app.py
  ```
- The server should print "Starting server..." and listen on http://127.0.0.1:5000

## 2. Serve the Frontend (HTML/JS) with a Local Server

- In a new terminal, in the same directory, run:
  ```bash
  python serve_frontend.py
  ```
- This will serve your static files at http://127.0.0.1:8000

## 3. Open the App in Your Browser

- Go to:
  - http://127.0.0.1:8000/insights_notifications.html
  - (or any other HTML file, e.g., dashboard.html)

## 4. Troubleshooting

- If you see "Network error. Could not connect to the server to fetch insights.":
  - Make sure both servers are running (Flask on 5000, static server on 8000).
  - Make sure you are accessing the frontend via http://127.0.0.1:8000, NOT file://
  - Open browser DevTools (F12) > Network tab. Click "Refresh Insights" and check for errors.
  - The Flask terminal should print "HIT /insights_notifications" when the frontend requests insights.

- If you see CORS errors:
  - Make sure you are not using file:// URLs. Always use the static server.

- If you see database errors:
  - Make sure MySQL is running and the credentials in app.py are correct.

## 5. Stopping the Servers

- Press Ctrl+C in each terminal window to stop the servers.

---

This setup ensures your frontend and backend communicate correctly and avoids CORS/network issues.
