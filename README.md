# RFID Warehouse Automation System

## Overview

This project is a Python-based RFID Automation system designed for warehouse operations to track item IN and OUT transactions using a UHF RFID reader.

The system enforces strict validation rules to ensure accurate and complete transaction cycles, preventing duplicate scans and invalid records.

## Features

* RFID scanning via serial communication
* IN/OUT transaction enforcement (OUT → IN cycle)
* Duplicate scan prevention
* Route-based validation
* Cooldown protection against rapid re-scanning
* Session-based logging with manual save
* Google Sheets integration via Google Apps Script

## Deployment

This system was successfully deployed and used in actual warehouse operations at:

Jentec Storage Inc. – Sto. Tomas, Batangas

## Tech Stack

* Python
* Tkinter (GUI)
* PySerial (RFID communication)
* Requests (API calls)
* Google Apps Script (Backend)
* Google Sheets (Database)

## Hardware

* UHF RFID Reader (USB / Serial)

## Installation

### 1. Clone the repository

```
git clone https://github.com/YOUR_USERNAME/RFID-Logger.git
cd RFID-Logger
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Configure the system

Copy the example configuration file:

```
cp config.example.py config.py
```

Edit `config.py` and configure the following:

* Serial port
* Google Apps Script URL

### 4. Run the application

```
python main.py
```

## Configuration

The `config.py` file contains environment-specific and sensitive information such as API endpoints and device configuration.

This file is excluded from version control. Use `config.example.py` as a reference when setting up the project.

## Future Improvements

* Migration to a dedicated database (e.g., Firebase or SQL)
* Multi-device synchronization improvements
* Web-based monitoring dashboard
* Analytics and reporting features

## Author

Jyann Guinto
Developed as part of internship work at Jentec Storage Inc.
