RFID Warehouse Logging System
Overview

    This project is a Python-based RFID logging system designed for warehouse operations to track item IN and OUT transactions using a UHF RFID reader.

    The system enforces strict validation rules to ensure accurate and complete transaction cycles, preventing duplicate scans and invalid records.

Features

    RFID scanning via serial communication

    IN/OUT transaction enforcement (OUT → IN cycle)

    Duplicate scan prevention

    Route-based validation

    Cooldown protection against rapid re-scanning

    Session-based logging with manual save

    Google Sheets integration via Google Apps Script

Deployment

    This system was successfully deployed and used in actual warehouse operations at:

    Jentec Storage Inc. – Sto. Tomas, Batangas

Tech Stack

Python

    Tkinter (GUI)

    PySerial (RFID communication)

    Requests (API calls)

    Google Apps Script (Backend)

    Google Sheets (Database)

Hardware

UHF RFID Reader (USB / Serial)

Setup Instructions
1. Clone the repository
    git clone https://github.com/YOUR_USERNAME/rfid-logger.git
cd rfid-logger
2. Install dependencies
    pip install -r requirements.txt
3. Configure the system

    Copy the example config file:

    cp config.example.py config.py

    Edit config.py and add your own:

    Serial port

    Google Apps Script URL

4. Run the application
    python main.py

Security Note

    Sensitive configuration such as API endpoints and deployment URLs are excluded from this repository. Use your own configuration when setting up the system.

Future Improvements

    Database backend (Firebase / SQL)

    Multi-device sync optimization

    Web dashboard for monitoring

    Analytics and reporting features

Author

    Developed by Jyann Guinto as part of internship work at Jentec Storage Inc.