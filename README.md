# Stock Portfolio and Watchlist Manager

A **Flask-based web application** that helps users manage their stock portfolios and watchlists. This app provides insights on stock performance, trends, and actionable recommendations based on key metrics.

## Features

- **Portfolio Analysis**:
  - Tracks portfolio performance.
  - Calculates percentage difference from the 150-day moving average.
  - Provides recommendations (e.g., Buy, Sell, Stay Away).

- **Watchlist Management**:
  - Monitors stocks for upward trends.
  - Suggests actions like "Get Ready," "Buy," or "Next Time."
  - Tracks recent close prices and moving averages.

- **User-Friendly Interface**:
  - Add or edit stock portfolios and watchlists.
  - Save personalized user data for future sessions.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/your-repo-name.git
   cd your-repo-name
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # For Linux/Mac
   venv\Scripts\activate     # For Windows
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up the application:
   - Ensure `user_data.json` exists in the root directory.
   - Update the `app.secret_key` in `app.py`.

5. Run the app:
   ```bash
   python app.py
   ```

6. Open the app in your browser:
   ```
   http://127.0.0.1:5000
   ```

## Usage

### Home Page
- Enter stock tickers and watchlist tickers (comma-separated).
- Click **Submit** to view the analysis.

### Results Page
- Analyze portfolio and watchlist performance.
- View actionable insights and stock trends.

### User Management
- Add new users via the **New User** page.
- Edit existing user preferences.

## Folder Structure

```
├── app.py                 # Main application file
├── templates/             # HTML templates
│   ├── index.html         # Home page
│   ├── results.html       # Results page
│   ├── new_user.html      # New user form
├── static/                # Static assets (CSS, JS)
├── user_data.json         # User data file
├── stock_utils.py         # Stock data utilities
├── user_data_utils.py     # User data management
└── requirements.txt       # Project dependencies
```

## Dependencies

- Flask
- Pandas
- Any additional dependencies in `requirements.txt`

## Example

![Screenshot](https://ibb.co/VSzzHVZ/image.png)
![Screenshot](https://i.ibb.co/Fx0BFjb/image.png)

## Notes

- Replace `'your_secret_key_here'` in `app.py` with a secure key for production.
- Debugging information is logged for specific problematic tickers (`UNH`, `TXN`, `TEL`).

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## Disclaimer

This software is for educational purposes only. USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR TRADING RESULTS. Do not risk money which you are afraid to lose. There might be bugs in the code - this software DOES NOT come with ANY warranty.

---

Developed with ❤️ using Flask.
