
🔧 Prerequisites

Before you run HashShield, make sure the following software is installed and configured on your system:

XAMPP (for Apache and MySQL)
Python 3.x (with required dependencies)
Flask (Python web framework)


--------------------------------------------------------------


🚀 Installation & Setup


1. Install XAMPP

Download and install XAMPP from https://www.apachefriends.org/index.html.

Once installed:

Launch XAMPP Control Panel
Start both Apache and MySQL

2. Set Up the MySQL Database

Before running the application:

Open phpMyAdmin via http://localhost/phpmyadmin

Import the provided SQL file:
Locate the file: file_monitoring (2).sql
Click on your database, then go to the Import tab
Upload and import file_monitoring (2).sql



--------------------------------------------------------------


3. Configure Your Environment
Make sure the app.py file contains the correct database credentials, such as:

pip install flask flask-mysqldb watchdog

--------------------------------------------------------------

4. Run the Application

Launch the Flask app:

python app.py
The application should be accessible via http://localhost:5000

🔐 Logging In
When prompted to log in, ensure you enter a valid and working email address, as this may be used for alerts or notifications.

