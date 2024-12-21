Gil-Stocks2
A Flask-based web application for managing and analyzing stock portfolios and watchlists.

Overview
Gil-Stocks2 allows users to input stock tickers, view portfolio performance, and analyze potential stock purchases. The application fetches stock data, performs calculations, and displays results in a user-friendly interface.

Features
User Authentication: Users can create and manage their accounts.

Portfolio Management: Input stock tickers and view portfolio performance.

Watchlist Analysis: Analyze potential stock purchases based on trends and averages.

Data Persistence: Save user preferences and data for future sessions.

Setup
Prerequisites
Python 3.x

Flask

Pandas

Installation
Clone the repository:

bash
git clone https://github.com/yourusername/Gil-Stocks2.git
cd Gil-Stocks2
Install dependencies:

bash
pip install -r requirements.txt
Run the application:

bash
python app.py
Access the application:

Open your web browser and navigate to http://localhost:5000.

Usage
Home Page
The home page allows you to input stock tickers and watchlist items. Enter your user ID and stock tickers, and then submit the form to view results.

Results Page
The results page displays your portfolio performance and watchlist analysis. It includes:

Current Price: The latest stock price.

Average Price: The rolling average price over the specified period.

Percentage Difference: The percentage difference between the current and average prices.

Action: Suggested actions based on stock performance.

Trend Status: Analysis of stock trends.

New User Page
Create a new user account by entering a user ID and optional default tickers and watchlist items.

Project Structure
plaintext
Gil-Stocks2/
├── app.py
├── templates/
│   ├── index.html
│   ├── results.html
│   └── new_user.html
├── static/
├── requirements.txt
└── README.md
