# FloraFlow - Nursery Management System
<div align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" alt="HTML5">
  <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" alt="CSS">
</div>
## Aim & Objective
FloraFlow is a fully normalized, web-based relational database management system designed to bridge the gap between traditional nursery operations and modern technology. The objective of this project is to eliminate the financial losses and poor plant health associated with manual, paper-based tracking by automating inventory management, point-of-sale (POS) transactions, and daily staff management and plant care schedules so plant health is never compromised.

## Scope
This system acts as a complete operational hub for a local plant nursery. It handles secure staff authentication, role-based access control, real-time inventory deductions, dynamic reporting, and task delegation. The database logic is highly strict, heavily utilizing SQL triggers, views, and ACID-compliant transactions to guarantee data integrity across all operations. 

## Dependencies & Tech Stack
This project uses a lightweight, beginner-friendly architecture:
*   **Backend:** Python 3.x, Flask (Routing and session control)
*   **Frontend:** HTML5, CSS, Bootstrap, Jinja2 (Dynamic templating)
*   **Database:** MySQL (Managed via XAMPP)
*   **Connector:** PyMySQL (For Python-to-Database connectivity)

## Core Functions
*   **Role-Based Access Control (RBAC):** Distinct dashboards for Administrators (financials, inventory control) and Staff Members (POS, tasks).
*   **ACID-Compliant POS:** A secure checkout system that utilizes `commit()` and `rollback()` transaction states to prevent partial cart saves and ghost orders during multi-item checkouts.
*   **Automated Inventory (Triggers):** SQL Triggers (`afterSale`, `afterPurchase`) automatically increment or decrement stock in real-time, while a `BEFORE` trigger acts as a constraint to prevent overselling.
*   **Plant Care Alerts:** A dynamic scheduling system that queries the database against the current system date to alert staff of overdue watering, pruning, or fertilizing tasks.
*   **Dynamic Views:** SQL Views (`lowStock`) simplify complex reporting and enhance security by strictly filtering underlying physical table data.

## Database Architecture
The database has been rigorously normalized to the **Third Normal Form (3NF)** to eliminate insert, update, and delete anomalies. Complex relationships, such as the Many-to-Many mapping between Sales and Plants, are cleanly resolved using junction tables (`SaleDetails`) to ensure strict atomic values.

## How to Run the Project Locally
1. Clone this repository to your local machine.
2. Ensure **XAMPP** is installed and start the **MySQL** and **Apache** modules.
3. Open MySQL Workbench or phpMyAdmin and import the `database.sql` schema file.
4. Open your terminal in the project directory and install dependencies: `pip install flask pymysql`
5. Run the application: `python app.py`
6. Open your web browser and navigate to: `http://127.0.0.1:5000`