from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, timedelta
from io import BytesIO
from fpdf import FPDF
import calendar


app = Flask(__name__)
app.secret_key = 'floraflow2024'

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'floraflowdb',
    'cursorclass': pymysql.cursors.DictCursor
}


def getDbConnection():
    conn = pymysql.connect(**db_config)
    return conn


def hashAllPasswords():
    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT staffId, passwordHash FROM Staff")
        allStaff = cursor.fetchall()
        for staff in allStaff:
            plainPassword = staff['passwordHash']
            if not plainPassword.startswith('scrypt:') and not plainPassword.startswith('pbkdf2:'):
                hashed = generate_password_hash(plainPassword)
                cursor.execute(
                    "UPDATE Staff SET passwordHash = %s WHERE staffId = %s", (hashed, staff['staffId']))
        conn.commit()
    finally:
        conn.close()


def checkAndInsertAlerts():
    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        today = date.today()

        cursor.execute("""
            SELECT cs.*, p.plantName
            FROM CareSchedule cs
            JOIN Plants p ON cs.plantId = p.plantId
            WHERE cs.nextCheck <= %s
        """, (today,))
        schedules = cursor.fetchall()

        for s in schedules:
            days_overdue = (today - s['nextCheck']).days
            if days_overdue > 0:
                msg = f"{s['plantName']} care is overdue since {days_overdue} days (careId {s['careId']})"
            else:
                msg = f"{s['plantName']} care is due today (careId {s['careId']})"

            cursor.execute("""
                SELECT * FROM SystemAlerts 
                WHERE alertType = 'careSchedule' AND message LIKE %s AND isRead = 0
            """, (f"%careId {s['careId']}%",))
            existing = cursor.fetchone()

            if not existing:
                cursor.execute("""
                    INSERT INTO SystemAlerts (alertType, message) VALUES ('careSchedule', %s)
                """, (msg,))
        conn.commit()
    finally:
        conn.close()


def checkAndInsertLowStockAlerts():
    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lowStockView")
        items = cursor.fetchall()

        for item in items:
            msg = f"{item['itemName']} stock is critically low — only {item['quantity']} units left (itemType {item['itemType']} itemId {item['itemId']})"
            cursor.execute("""
                SELECT * FROM SystemAlerts 
                WHERE alertType = 'lowStock' AND message LIKE %s AND isRead = 0
            """, (f"%itemId {item['itemId']}%",))
            existing = cursor.fetchone()
            if not existing:
                cursor.execute("""
                    INSERT INTO SystemAlerts (alertType, message) VALUES ('lowStock', %s)
                """, (msg,))
        conn.commit()
    finally:
        conn.close()


def build_pdf(title, headers, rows):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "FloraFlow Nursery", ln=1)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, title, ln=1)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Generated: {date.today().isoformat()}", ln=1)
    pdf.ln(4)

    col_width = 190 / len(headers)
    pdf.set_font("Arial", "B", 10)
    for h in headers:
        pdf.cell(col_width, 8, h, border=1)
    pdf.ln()

    pdf.set_font("Arial", "", 10)
    for row in rows:
        for cell in row:
            pdf.cell(col_width, 8, str(cell), border=1)
        pdf.ln()

    data = pdf.output(dest='S')
    if isinstance(data, str):
        data = data.encode('latin-1')
    else:
        data = bytes(data)

    return BytesIO(data)


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = getDbConnection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM Staff WHERE username = %s AND isActive = 1", (username,))
            staff = cursor.fetchone()
        finally:
            conn.close()

        if staff and check_password_hash(staff['passwordHash'], password):
            session['staffId'] = staff['staffId']
            session['username'] = staff['username']
            session['role'] = staff['role']
            session['fullName'] = staff['fullName']

            if staff['role'] == 'admin':
                checkAndInsertAlerts()
                checkAndInsertLowStockAlerts()
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('staffDashboard'))
        else:
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        # Existing Stat Boxes
        cursor.execute("SELECT COUNT(*) AS total FROM Plants")
        totalPlants = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) AS total FROM Accessories")
        totalAccessories = cursor.fetchone()['total']

        cursor.execute(
            "SELECT COUNT(*) AS total FROM Staff WHERE isActive = 1")
        totalStaff = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) AS total FROM Sales")
        totalSales = cursor.fetchone()['total']

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']

        cursor.execute("SELECT * FROM lowStockView")
        lowStock = cursor.fetchall()

        # --- NEW: CHART DATA QUERIES ---

        # 1. Revenue Last 7 Days (Line Chart)
        cursor.execute("""
            SELECT DATE(saleDate) as saleDay, SUM(totalBill) as dailyTotal
            FROM Sales
            WHERE saleDate >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            GROUP BY DATE(saleDate)
            ORDER BY saleDay ASC
        """)
        revenueData = cursor.fetchall()

        # 2. Top 5 Plants (Horizontal Bar Chart)
        cursor.execute("""
            SELECT p.plantName, SUM(sd.quantity) as qty
            FROM SaleDetails sd
            JOIN Plants p ON sd.plantId = p.plantId
            GROUP BY p.plantId
            ORDER BY qty DESC
            LIMIT 5
        """)
        topPlantsData = cursor.fetchall()

        # 3. Sales by Category (Doughnut Chart)
        cursor.execute("""
            SELECT c.categoryName, SUM(sd.quantity) as qty
            FROM SaleDetails sd
            JOIN Plants p ON sd.plantId = p.plantId
            JOIN PlantCategories c ON p.categoryId = c.categoryId
            GROUP BY c.categoryId
        """)
        categoryData = cursor.fetchall()

    finally:
        conn.close()

    # Convert complex SQL data types (like Decimals and Dates) into simple Python types
    # so they can be safely sent to the HTML page.
    formattedRevenue = [{'saleDay': str(r['saleDay']), 'dailyTotal': float(
        r['dailyTotal'])} for r in revenueData]
    formattedTopPlants = [{'plantName': r['plantName'],
                           'qty': int(r['qty'])} for r in topPlantsData]
    formattedCategory = [{'categoryName': r['categoryName'],
                          'qty': int(r['qty'])} for r in categoryData]

    return render_template('adminDashboard.html',
                           totalPlants=totalPlants,
                           totalAccessories=totalAccessories,
                           totalStaff=totalStaff,
                           totalSales=totalSales,
                           unreadAlerts=unreadAlerts,
                           lowStock=lowStock,
                           revenueData=formattedRevenue,
                           topPlantsData=formattedTopPlants,
                           categoryData=formattedCategory
                           )


@app.route('/staffDashboard')
def staffDashboard():
    if 'staffId' not in session or session['role'] != 'staff':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        staff_id = session['staffId']
        today = date.today()

        # 1. Check if the user has marked attendance today
        cursor.execute("""
            SELECT status FROM Attendance 
            WHERE staffId = %s AND attendanceDate = %s
        """, (staff_id, today))
        attendance = cursor.fetchone()
        att_status = attendance['status'] if attendance else None

        # 2. Get active tasks for this specific staff member
        cursor.execute("""
            SELECT * FROM StaffTasks 
            WHERE staffId = %s AND status != 'done'
            ORDER BY dueDate ASC, assignedDate DESC
        """, (staff_id,))
        active_tasks = cursor.fetchall()

        # 3. Get care schedules that are due today or overdue
        cursor.execute("""
            SELECT cs.*, p.plantName 
            FROM CareSchedule cs
            JOIN Plants p ON cs.plantId = p.plantId
            WHERE cs.nextCheck <= %s
            ORDER BY cs.nextCheck ASC
        """, (today,))
        care_tasks = cursor.fetchall()

    finally:
        conn.close()

    # We added unreadAlerts=0 here to fix the base.html error!
    return render_template('staffDashboard.html',
                           att_status=att_status,
                           active_tasks=active_tasks,
                           care_tasks=care_tasks,
                           today=today,
                           unreadAlerts=0)


# ─── Plants ─────────────────────────────────────────────────────────────────


@app.route('/plants')
def plants():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, c.categoryName 
            FROM Plants p 
            JOIN PlantCategories c ON p.categoryId = c.categoryId
            ORDER BY p.plantId
        """)
        allPlants = cursor.fetchall()

        cursor.execute("SELECT * FROM PlantCategories ORDER BY categoryName")
        categories = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('plants.html', allPlants=allPlants, categories=categories, unreadAlerts=unreadAlerts)


@app.route('/addPlant', methods=['POST'])
def addPlant():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    plantName = request.form['plantName']
    categoryId = request.form['categoryId']
    price = request.form['price']
    quantity = request.form['quantity']
    description = request.form['description']
    careInstructions = request.form['careInstructions']

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Plants (plantName, categoryId, price, quantity, description, careInstructions)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (plantName, categoryId, price, quantity, description, careInstructions))
        conn.commit()
        flash('Plant added successfully', 'success')
    finally:
        conn.close()

    return redirect(url_for('plants'))


@app.route('/editPlant/<int:plantId>', methods=['GET', 'POST'])
def editPlant(plantId):
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        if request.method == 'POST':
            plantName = request.form['plantName']
            categoryId = request.form['categoryId']
            price = request.form['price']
            quantity = request.form['quantity']
            description = request.form['description']
            careInstructions = request.form['careInstructions']

            cursor.execute("""
                UPDATE Plants SET plantName=%s, categoryId=%s, price=%s, 
                quantity=%s, description=%s, careInstructions=%s
                WHERE plantId=%s
            """, (plantName, categoryId, price, quantity, description, careInstructions, plantId))
            conn.commit()
            flash('Plant updated successfully', 'success')
            return redirect(url_for('plants'))

        cursor.execute("SELECT * FROM Plants WHERE plantId = %s", (plantId,))
        plant = cursor.fetchone()

        cursor.execute("SELECT * FROM PlantCategories ORDER BY categoryName")
        categories = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('editPlant.html', plant=plant, categories=categories, unreadAlerts=unreadAlerts)


@app.route('/deletePlant/<int:plantId>')
def deletePlant(plantId):
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Plants WHERE plantId = %s", (plantId,))
        conn.commit()
        flash('Plant deleted successfully', 'success')
    finally:
        conn.close()

    return redirect(url_for('plants'))

# ─── Accessories ─────────────────────────────────────────────────────────────


@app.route('/accessories')
def accessories():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Accessories ORDER BY accessoryId")
        allAccessories = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('accessories.html', allAccessories=allAccessories, unreadAlerts=unreadAlerts)


@app.route('/addAccessory', methods=['POST'])
def addAccessory():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    accessoryName = request.form['accessoryName']
    price = request.form['price']
    quantity = request.form['quantity']
    description = request.form['description']

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Accessories (accessoryName, price, quantity, description)
            VALUES (%s, %s, %s, %s)
        """, (accessoryName, price, quantity, description))
        conn.commit()
        flash('Accessory added successfully', 'success')
    finally:
        conn.close()

    return redirect(url_for('accessories'))


@app.route('/editAccessory/<int:accessoryId>', methods=['GET', 'POST'])
def editAccessory(accessoryId):
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        if request.method == 'POST':
            accessoryName = request.form['accessoryName']
            price = request.form['price']
            quantity = request.form['quantity']
            description = request.form['description']

            cursor.execute("""
                UPDATE Accessories SET accessoryName=%s, price=%s, quantity=%s, description=%s
                WHERE accessoryId=%s
            """, (accessoryName, price, quantity, description, accessoryId))
            conn.commit()
            flash('Accessory updated successfully', 'success')
            return redirect(url_for('accessories'))

        cursor.execute(
            "SELECT * FROM Accessories WHERE accessoryId = %s", (accessoryId,))
        accessory = cursor.fetchone()

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('editAccessory.html', accessory=accessory, unreadAlerts=unreadAlerts)


@app.route('/deleteAccessory/<int:accessoryId>')
def deleteAccessory(accessoryId):
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM Accessories WHERE accessoryId = %s", (accessoryId,))
        conn.commit()
        flash('Accessory deleted successfully', 'success')
    finally:
        conn.close()

    return redirect(url_for('accessories'))

# ─── POS ─────────────────────────────────────────────────────────────────────


@app.route('/pos')
def pos():
    if 'staffId' not in session:
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM Plants WHERE quantity > 0 ORDER BY plantName")
        allPlants = cursor.fetchall()

        cursor.execute(
            "SELECT * FROM Accessories WHERE quantity > 0 ORDER BY accessoryName")
        allAccessories = cursor.fetchall()

        cursor.execute("SELECT * FROM Customers ORDER BY fullName")
        allCustomers = cursor.fetchall()

        unreadAlerts = 0
        if session['role'] == 'admin':
            cursor.execute(
                "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
            unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('pos.html',
                           allPlants=allPlants,
                           allAccessories=allAccessories,
                           llCustomers=allCustomers,
                           unreadAlerts=unreadAlerts
                           )


@app.route('/completeSale', methods=['POST'])
def completeSale():
    if 'staffId' not in session:
        return redirect(url_for('login'))

    customerName = request.form.get('customerName', '').strip()
    customerPhone = request.form.get('customerPhone', '').strip()
    paymentMethod = request.form.get('paymentMethod', 'cash')
    itemTypes = request.form.getlist('itemType[]')
    itemIds = request.form.getlist('itemId[]')
    itemQuantities = request.form.getlist('itemQuantity[]')
    itemPrices = request.form.getlist('itemPrice[]')

    if customerName and (not customerPhone.isdigit() or len(customerPhone) != 11):
        flash('Phone number must be exactly 11 digits', 'danger')
        return redirect(url_for('pos'))

    if not itemIds:
        flash('Please add at least one item to the cart', 'danger')
        return redirect(url_for('pos'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        conn.begin()

        customerId = None
        if customerName:
            cursor.execute(
                "SELECT customerId FROM Customers WHERE phone = %s", (customerPhone,))
            existing = cursor.fetchone()
            if existing:
                customerId = existing['customerId']
            else:
                cursor.execute("""
                    INSERT INTO Customers (fullName, phone) VALUES (%s, %s)
                """, (customerName, customerPhone))
                customerId = cursor.lastrowid

        totalBill = sum(
            float(itemPrices[i]) * int(itemQuantities[i]) for i in range(len(itemIds)))

        cursor.execute("""
            INSERT INTO Sales (customerId, staffId, totalBill, paymentMethod)
            VALUES (%s, %s, %s, %s)
        """, (customerId, session['staffId'], totalBill, paymentMethod))
        saleId = cursor.lastrowid

        for i in range(len(itemIds)):
            itemType = itemTypes[i]
            itemId = int(itemIds[i])
            qty = int(itemQuantities[i])
            price = float(itemPrices[i])
            subtotal = qty * price

            if itemType == 'plant':
                cursor.execute(
                    "SELECT quantity FROM Plants WHERE plantId = %s", (itemId,))
                stock = cursor.fetchone()
                if not stock or stock['quantity'] < qty:
                    conn.rollback()
                    flash(
                        f'Insufficient stock for plant ID {itemId}', 'danger')
                    return redirect(url_for('pos'))
                cursor.execute("""
                    INSERT INTO SaleDetails (saleId, plantId, accessoryId, quantity, unitPrice, subtotal)
                    VALUES (%s, %s, NULL, %s, %s, %s)
                """, (saleId, itemId, qty, price, subtotal))

            elif itemType == 'accessory':
                cursor.execute(
                    "SELECT quantity FROM Accessories WHERE accessoryId = %s", (itemId,))
                stock = cursor.fetchone()
                if not stock or stock['quantity'] < qty:
                    conn.rollback()
                    flash(
                        f'Insufficient stock for accessory ID {itemId}', 'danger')
                    return redirect(url_for('pos'))
                cursor.execute("""
                    INSERT INTO SaleDetails (saleId, plantId, accessoryId, quantity, unitPrice, subtotal)
                    VALUES (%s, NULL, %s, %s, %s, %s)
                """, (saleId, itemId, qty, price, subtotal))

        conn.commit()
        flash(
            f'Sale completed successfully! Total: Rs. {totalBill:.2f}', 'success')
        return redirect(url_for('saleSuccess', saleId=saleId))

    except Exception as e:
        conn.rollback()
        flash(f'Sale failed: {str(e)}', 'danger')
        return redirect(url_for('pos'))

    finally:
        conn.close()


@app.route('/saleSuccess/<int:saleId>')
def saleSuccess(saleId):
    if 'staffId' not in session:
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.fullName AS customerName, c.phone AS customerPhone,
            st.fullName AS staffName
            FROM Sales s
            LEFT JOIN Customers c ON s.customerId = c.customerId
            JOIN Staff st ON s.staffId = st.staffId
            WHERE s.saleId = %s
        """, (saleId,))
        sale = cursor.fetchone()

        cursor.execute("""
            SELECT sd.*, 
            p.plantName, a.accessoryName
            FROM SaleDetails sd
            LEFT JOIN Plants p ON sd.plantId = p.plantId
            LEFT JOIN Accessories a ON sd.accessoryId = a.accessoryId
            WHERE sd.saleId = %s
        """, (saleId,))
        saleItems = cursor.fetchall()

        unreadAlerts = 0
        if session['role'] == 'admin':
            cursor.execute(
                "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
            unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('saleSuccess.html', sale=sale, saleItems=saleItems, unreadAlerts=unreadAlerts)


@app.route('/salesHistory')
def salesHistory():
    if 'staffId' not in session:
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.saleId, s.saleDate, s.totalBill, s.paymentMethod,
            c.fullName AS customerName, c.phone AS customerPhone,
            st.fullName AS staffName
            FROM Sales s
            LEFT JOIN Customers c ON s.customerId = c.customerId
            JOIN Staff st ON s.staffId = st.staffId
            ORDER BY s.saleDate DESC
        """)
        allSales = cursor.fetchall()

        unreadAlerts = 0
        if session['role'] == 'admin':
            cursor.execute(
                "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
            unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('salesHistory.html', allSales=allSales, unreadAlerts=unreadAlerts)


@app.route('/saleDetail/<int:saleId>')
def saleDetail(saleId):
    if 'staffId' not in session:
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.fullName AS customerName, c.phone AS customerPhone,
            st.fullName AS staffName
            FROM Sales s
            LEFT JOIN Customers c ON s.customerId = c.customerId
            JOIN Staff st ON s.staffId = st.staffId
            WHERE s.saleId = %s
        """, (saleId,))
        sale = cursor.fetchone()

        cursor.execute("""
            SELECT sd.*, p.plantName, a.accessoryName
            FROM SaleDetails sd
            LEFT JOIN Plants p ON sd.plantId = p.plantId
            LEFT JOIN Accessories a ON sd.accessoryId = a.accessoryId
            WHERE sd.saleId = %s
        """, (saleId,))
        saleItems = cursor.fetchall()

        unreadAlerts = 0
        if session['role'] == 'admin':
            cursor.execute(
                "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
            unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('saleDetail.html', sale=sale, saleItems=saleItems, unreadAlerts=unreadAlerts)

# ─── Procurement ─────────────────────────────────────────────────────────────


@app.route('/procurement')
def procurement():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.purchaseId, p.purchaseDate, p.totalCost,
                   s.supplierName, st.fullName AS staffName
            FROM Purchases p
            JOIN Suppliers s ON p.supplierId = s.supplierId
            JOIN Staff st ON p.staffId = st.staffId
            ORDER BY p.purchaseDate DESC
        """)
        allPurchases = cursor.fetchall()

        cursor.execute("SELECT * FROM Suppliers ORDER BY supplierName")
        allSuppliers = cursor.fetchall()

        cursor.execute(
            "SELECT plantId, plantName, price FROM Plants ORDER BY plantName")
        allPlants = cursor.fetchall()

        cursor.execute(
            "SELECT accessoryId, accessoryName, price FROM Accessories ORDER BY accessoryName")
        allAccessories = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('procurement.html',
                           allPurchases=allPurchases,
                           allSuppliers=allSuppliers,
                           allPlants=allPlants,
                           allAccessories=allAccessories,
                           unreadAlerts=unreadAlerts)


@app.route('/addPurchase', methods=['POST'])
def addPurchase():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    supplierId = request.form.get('supplierId', '').strip()
    itemTypes = request.form.getlist('itemType[]')
    itemIds = request.form.getlist('itemId[]')
    quantities = request.form.getlist('itemQuantity[]')
    unitCosts = request.form.getlist('unitCost[]')

    if not supplierId or not supplierId.isdigit():
        flash('Please select a supplier.', 'danger')
        return redirect(url_for('procurement'))

    if not itemIds:
        flash('Please add at least one item to the purchase.', 'danger')
        return redirect(url_for('procurement'))

    try:
        parsedItems = []
        for i in range(len(itemIds)):
            qty = int(quantities[i])
            cost = float(unitCosts[i])
            if qty <= 0:
                raise ValueError('Quantity must be a positive integer.')
            if cost <= 0:
                raise ValueError('Unit cost must be a positive value.')
            parsedItems.append({
                'type': itemTypes[i],
                'id':   int(itemIds[i]),
                'qty':  qty,
                'cost': cost,
                'sub':  round(qty * cost, 2)
            })
    except (ValueError, IndexError) as e:
        flash(f'Invalid input: {e}', 'danger')
        return redirect(url_for('procurement'))

    totalCost = round(sum(item['sub'] for item in parsedItems), 2)

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        conn.begin()

        cursor.execute("""
            INSERT INTO Purchases (supplierId, staffId, totalCost)
            VALUES (%s, %s, %s)
        """, (supplierId, session['staffId'], totalCost))
        purchaseId = cursor.lastrowid

        for item in parsedItems:
            if item['type'] == 'plant':
                cursor.execute("""
                    INSERT INTO PurchasePlantDetails
                        (purchaseId, plantId, quantity, unitCost, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                """, (purchaseId, item['id'], item['qty'], item['cost'], item['sub']))
            elif item['type'] == 'accessory':
                cursor.execute("""
                    INSERT INTO PurchaseAccessoryDetails
                        (purchaseId, accessoryId, quantity, unitCost, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                """, (purchaseId, item['id'], item['qty'], item['cost'], item['sub']))

        conn.commit()
        flash(
            f'Purchase recorded successfully! Total: Rs. {totalCost:,.2f}', 'success')
        return redirect(url_for('purchaseDetail', purchaseId=purchaseId))

    except Exception as e:
        conn.rollback()
        flash(f'Purchase failed: {str(e)}', 'danger')
        return redirect(url_for('procurement'))

    finally:
        conn.close()


@app.route('/purchaseDetail/<int:purchaseId>')
def purchaseDetail(purchaseId):
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, s.supplierName, s.phone AS supplierPhone,
                   st.fullName AS staffName
            FROM Purchases p
            JOIN Suppliers s ON p.supplierId = s.supplierId
            JOIN Staff st    ON p.staffId    = st.staffId
            WHERE p.purchaseId = %s
        """, (purchaseId,))
        purchase = cursor.fetchone()

        if not purchase:
            flash('Purchase not found.', 'danger')
            return redirect(url_for('procurement'))

        cursor.execute("""
            SELECT ppd.quantity, ppd.unitCost, ppd.subtotal,
                   pl.plantName AS itemName, 'plant' AS itemType
            FROM PurchasePlantDetails ppd
            JOIN Plants pl ON ppd.plantId = pl.plantId
            WHERE ppd.purchaseId = %s
        """, (purchaseId,))
        plantItems = cursor.fetchall()

        cursor.execute("""
            SELECT pad.quantity, pad.unitCost, pad.subtotal,
                   ac.accessoryName AS itemName, 'accessory' AS itemType
            FROM PurchaseAccessoryDetails pad
            JOIN Accessories ac ON pad.accessoryId = ac.accessoryId
            WHERE pad.purchaseId = %s
        """, (purchaseId,))
        accessoryItems = cursor.fetchall()

        purchaseItems = list(plantItems) + list(accessoryItems)

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('purchaseDetail.html',
                           purchase=purchase,
                           purchaseItems=purchaseItems,
                           unreadAlerts=unreadAlerts)


# ─── Staff Management ────────────────────────────────────────────────────────


@app.route('/staff')
def staff():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT staffId, fullName, username, role, designation, salary,
                   phone, email, hireDate, isActive
            FROM Staff
            ORDER BY isActive DESC, staffId
        """)
        allStaff = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('staff.html',
                           allStaff=allStaff,
                           unreadAlerts=unreadAlerts,
                           currentStaffId=session['staffId'])


@app.route('/addStaff', methods=['POST'])
def addStaff():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    fullName = request.form['fullName'].strip()
    username = request.form['username'].strip()
    password = request.form['password']
    role = request.form['role']
    designation = request.form.get('designation', '').strip()
    salary = request.form.get('salary') or None
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    hireDate = request.form['hireDate']

    if not fullName or not username or not password or not hireDate:
        flash('Full name, username, password and hire date are required.', 'danger')
        return redirect(url_for('staff'))

    if len(password) < 4:
        flash('Password must be at least 4 characters long.', 'danger')
        return redirect(url_for('staff'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT staffId FROM Staff WHERE username = %s", (username,))
        if cursor.fetchone():
            flash('Username already exists. Please choose another.', 'danger')
            return redirect(url_for('staff'))

        hashed = generate_password_hash(password)

        cursor.execute("""
            INSERT INTO Staff (fullName, username, passwordHash, role,
                               designation, salary, phone, email, hireDate, isActive)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
        """, (fullName, username, hashed, role, designation, salary,
              phone, email, hireDate))
        conn.commit()
        flash(f'Staff member "{fullName}" added successfully.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Failed to add staff: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('staff'))


@app.route('/editStaff/<int:staffId>', methods=['GET', 'POST'])
def editStaff(staffId):
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        if request.method == 'POST':
            fullName = request.form['fullName'].strip()
            role = request.form['role']
            designation = request.form.get('designation', '').strip()
            salary = request.form.get('salary') or None
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip()
            hireDate = request.form['hireDate']

            if staffId == session['staffId'] and role != 'admin':
                flash('You cannot demote your own admin account.', 'danger')
                return redirect(url_for('editStaff', staffId=staffId))

            cursor.execute("""
                UPDATE Staff
                SET fullName=%s, role=%s, designation=%s, salary=%s,
                    phone=%s, email=%s, hireDate=%s
                WHERE staffId=%s
            """, (fullName, role, designation, salary, phone, email,
                  hireDate, staffId))
            conn.commit()
            flash('Staff details updated successfully.', 'success')
            return redirect(url_for('staff'))

        cursor.execute("SELECT * FROM Staff WHERE staffId = %s", (staffId,))
        staffMember = cursor.fetchone()

        if not staffMember:
            flash('Staff member not found.', 'danger')
            return redirect(url_for('staff'))

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('editStaff.html',
                           staffMember=staffMember,
                           unreadAlerts=unreadAlerts,
                           currentStaffId=session['staffId'])


@app.route('/toggleStaff/<int:staffId>')
def toggleStaff(staffId):
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if staffId == session['staffId']:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('staff'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT isActive, fullName FROM Staff WHERE staffId = %s", (staffId,))
        row = cursor.fetchone()

        if not row:
            flash('Staff member not found.', 'danger')
            return redirect(url_for('staff'))

        newStatus = 0 if row['isActive'] == 1 else 1
        cursor.execute(
            "UPDATE Staff SET isActive = %s WHERE staffId = %s", (newStatus, staffId))
        conn.commit()

        action = 'activated' if newStatus == 1 else 'deactivated'
        flash(f'{row["fullName"]} has been {action}.', 'success')
    finally:
        conn.close()

    return redirect(url_for('staff'))


@app.route('/resetPassword/<int:staffId>', methods=['POST'])
def resetPassword(staffId):
    # Security check: Only admins can perform this action
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        # Hash the temporary default password
        new_hashed_password = generate_password_hash('staff1234')

        # Update the specific staff member's password
        cursor.execute("""
            UPDATE Staff 
            SET passwordHash = %s 
            WHERE staffId = %s
        """, (new_hashed_password, staffId))

        conn.commit()

        # We need to fetch the staff name just to make the flash message look nice!
        cursor.execute(
            "SELECT fullName FROM Staff WHERE staffId = %s", (staffId,))
        staff = cursor.fetchone()

        flash(
            f'Password for {staff["fullName"]} successfully reset to: staff1234', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'Error resetting password: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('staff'))

# ─── Attendance ──────────────────────────────────────────────────────────────


@app.route('/attendance', methods=['GET'])
def attendance():
    if 'staffId' not in session:
        return redirect(url_for('login'))

    role = session['role']
    today = date.today()

    fromDate = request.args.get('fromDate', '').strip()
    toDate = request.args.get('toDate', '').strip()
    filterStaffId = request.args.get('filterStaffId', '').strip()

    if not fromDate:
        fromDate = (today - timedelta(days=30)).isoformat()
    if not toDate:
        toDate = today.isoformat()

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM Attendance
            WHERE staffId = %s AND attendanceDate = %s
        """, (session['staffId'], today))
        myTodayRecord = cursor.fetchone()

        if role == 'admin':
            cursor.execute("""
                SELECT staffId, fullName, role, designation
                FROM Staff WHERE isActive = 1
                ORDER BY role DESC, fullName
            """)
            allStaff = cursor.fetchall()

            cursor.execute("""
                SELECT staffId, status FROM Attendance
                WHERE attendanceDate = %s
            """, (today,))
            todayMap = {row['staffId']: row['status']
                        for row in cursor.fetchall()}

            historyQuery = """
                SELECT a.attendanceId, a.attendanceDate, a.status,
                       s.fullName, s.role
                FROM Attendance a
                JOIN Staff s ON a.staffId = s.staffId
                WHERE a.attendanceDate BETWEEN %s AND %s
            """
            params = [fromDate, toDate]

            if filterStaffId and filterStaffId.isdigit():
                historyQuery += " AND a.staffId = %s"
                params.append(filterStaffId)

            historyQuery += " ORDER BY a.attendanceDate DESC, s.fullName"
            cursor.execute(historyQuery, tuple(params))
            history = cursor.fetchall()

            cursor.execute(
                "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
            unreadAlerts = cursor.fetchone()['total']

        else:
            allStaff = []
            todayMap = {}
            cursor.execute("""
                SELECT a.attendanceId, a.attendanceDate, a.status
                FROM Attendance a
                WHERE a.staffId = %s AND a.attendanceDate BETWEEN %s AND %s
                ORDER BY a.attendanceDate DESC
            """, (session['staffId'], fromDate, toDate))
            history = cursor.fetchall()
            unreadAlerts = 0

    finally:
        conn.close()

    return render_template('attendance.html',
                           role=role,
                           today=today,
                           myTodayRecord=myTodayRecord,
                           allStaff=allStaff,
                           todayMap=todayMap,
                           history=history,
                           fromDate=fromDate,
                           toDate=toDate,
                           filterStaffId=filterStaffId,
                           unreadAlerts=unreadAlerts)


@app.route('/markAttendance', methods=['POST'])
def markAttendance():
    if 'staffId' not in session:
        return redirect(url_for('login'))

    today = date.today()
    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT attendanceId FROM Attendance
            WHERE staffId = %s AND attendanceDate = %s
        """, (session['staffId'], today))
        existing = cursor.fetchone()

        if existing:
            flash('You have already marked your attendance today.', 'warning')
        else:
            cursor.execute("""
                INSERT INTO Attendance (staffId, attendanceDate, status)
                VALUES (%s, %s, 'present')
            """, (session['staffId'], today))
            conn.commit()
            flash('Your attendance has been marked as Present.', 'success')
    finally:
        conn.close()

    return redirect(url_for('attendance'))


@app.route('/bulkMarkAttendance', methods=['POST'])
def bulkMarkAttendance():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    today = date.today()
    staffIds = request.form.getlist('staffId[]')
    statuses = request.form.getlist('status[]')

    if not staffIds:
        flash('No staff data submitted.', 'danger')
        return redirect(url_for('attendance'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        conn.begin()

        marked = 0
        for sid, status in zip(staffIds, statuses):
            if not status:
                continue

            cursor.execute("""
                INSERT INTO Attendance (staffId, attendanceDate, status)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE status = VALUES(status)
            """, (sid, today, status))
            marked += 1

        conn.commit()
        flash(
            f'Attendance recorded/updated for {marked} staff member(s).', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Failed to mark attendance: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('attendance'))


@app.route('/editAttendance/<int:attendanceId>', methods=['POST'])
def editAttendance(attendanceId):
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    newStatus = request.form.get('status', '').strip()
    if newStatus not in ('present', 'absent', 'late'):
        flash('Invalid status.', 'danger')
        return redirect(url_for('attendance'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Attendance SET status = %s WHERE attendanceId = %s
        """, (newStatus, attendanceId))
        conn.commit()
        flash('Attendance record updated.', 'success')
    finally:
        conn.close()

    return redirect(url_for('attendance'))

# ─── Tasks ───────────────────────────────────────────────────────────────────


@app.route('/tasks')
def tasks():
    if 'staffId' not in session:
        return redirect(url_for('login'))

    role = session['role']
    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        if role == 'admin':
            cursor.execute("""
                SELECT t.*, s.fullName
                FROM StaffTasks t
                JOIN Staff s ON t.staffId = s.staffId
                ORDER BY t.assignedDate DESC, t.taskId DESC
            """)
            allTasks = cursor.fetchall()

            cursor.execute(
                "SELECT staffId, fullName FROM Staff WHERE isActive = 1 ORDER BY fullName")
            allStaff = cursor.fetchall()

            cursor.execute(
                "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
            unreadAlerts = cursor.fetchone()['total']
        else:
            cursor.execute("""
                SELECT t.*, s.fullName
                FROM StaffTasks t
                JOIN Staff s ON t.staffId = s.staffId
                WHERE t.staffId = %s
                ORDER BY t.assignedDate DESC, t.taskId DESC
            """, (session['staffId'],))
            allTasks = cursor.fetchall()
            allStaff = []
            unreadAlerts = 0

    finally:
        conn.close()

    return render_template('tasks.html',
                           allTasks=allTasks,
                           allStaff=allStaff,
                           role=role,
                           unreadAlerts=unreadAlerts)


@app.route('/addTask', methods=['POST'])
def addTask():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    staffId = request.form.get('staffId')
    taskTitle = request.form.get('taskTitle', '').strip()
    taskDescription = request.form.get('taskDescription', '').strip()
    dueDate = request.form.get('dueDate') or None

    if not staffId or not taskTitle:
        flash('Please select staff and enter task name.', 'danger')
        return redirect(url_for('tasks'))

    # Step 2: Generate the missing values
    assignedDate = date.today()
    status = 'Pending'

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        # Step 3: Update query to include all fields defined in the schema
        cursor.execute("""
            INSERT INTO StaffTasks (staffId, taskTitle, taskDescription, assignedDate, dueDate, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (staffId, taskTitle, taskDescription, assignedDate, dueDate, status))

        conn.commit()
        flash('Task added successfully.', 'success')

    except Exception as e:
        # Step 4: Add error handling
        conn.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')

    finally:
        conn.close()

    return redirect(url_for('tasks'))


@app.route('/updateTaskStatus/<int:taskId>', methods=['POST'])
def updateTaskStatus(taskId):
    if 'staffId' not in session:
        return redirect(url_for('login'))

    newStatus = request.form.get('status')

    if newStatus not in ('pending', 'inProgress', 'done'):
        flash('Invalid status.', 'danger')
        return redirect(url_for('tasks'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        if session['role'] == 'admin':
            cursor.execute("UPDATE StaffTasks SET status = %s WHERE taskId = %s",
                           (newStatus, taskId))
        else:
            cursor.execute("""
                UPDATE StaffTasks SET status = %s
                WHERE taskId = %s AND staffId = %s
            """, (newStatus, taskId, session['staffId']))

        conn.commit()
        flash('Task status updated.', 'success')
    finally:
        conn.close()

    return redirect(url_for('tasks'))


@app.route('/deleteTask/<int:taskId>')
def deleteTask(taskId):
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM StaffTasks WHERE taskId = %s", (taskId,))
        conn.commit()
        flash('Task deleted.', 'success')
    finally:
        conn.close()

    return redirect(url_for('tasks'))

# ─── Care Schedule ───────────────────────────────────────────────────────────


@app.route('/careSchedule')
def careSchedule():
    if 'staffId' not in session:
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT cs.*, p.plantName
            FROM CareSchedule cs
            JOIN Plants p ON cs.plantId = p.plantId
            ORDER BY cs.nextCheck ASC
        """)
        schedules = cursor.fetchall()

        cursor.execute(
            "SELECT plantId, plantName FROM Plants ORDER BY plantName")
        allPlants = cursor.fetchall()

        unreadAlerts = 0
        if session['role'] == 'admin':
            cursor.execute(
                "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
            unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('careSchedule.html',
                           schedules=schedules,
                           allPlants=allPlants,
                           today=date.today(),
                           unreadAlerts=unreadAlerts,
                           role=session['role'])


@app.route('/addCareSchedule', methods=['POST'])
def addCareSchedule():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    plantId = request.form.get('plantId')
    careType = request.form.get('careType', '').strip()
    nextCheck = request.form.get('nextCheck')
    notes = request.form.get('notes', '').strip()

    if not plantId or not careType or not nextCheck:
        flash('Please fill all required fields.', 'danger')
        return redirect(url_for('careSchedule'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO CareSchedule (plantId, careType, nextCheck, notes)
            VALUES (%s, %s, %s, %s)
        """, (plantId, careType, nextCheck, notes))
        conn.commit()
        flash('Care schedule added.', 'success')
    finally:
        conn.close()

    return redirect(url_for('careSchedule'))


@app.route('/markCareDone/<int:careId>')
def markCareDone(careId):
    if 'staffId' not in session:
        return redirect(url_for('login'))

    today = date.today()
    nextDate = today + timedelta(days=3)

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE CareSchedule
            SET lastCheck = %s, nextCheck = %s
            WHERE careId = %s
        """, (today, nextDate, careId))
        conn.commit()
        flash('Care task marked as done. Next check set +3 days.', 'success')
    finally:
        conn.close()

    return redirect(url_for('careSchedule'))

# ─── Alerts ──────────────────────────────────────────────────────────────────


@app.route('/alerts')
def alerts():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM SystemAlerts ORDER BY isRead ASC, createdAt DESC")
        allAlerts = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']
    finally:
        conn.close()

    return render_template('alerts.html', allAlerts=allAlerts, unreadAlerts=unreadAlerts)


@app.route('/markAlertRead/<int:alertId>')
def markAlertRead(alertId):
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE SystemAlerts SET isRead = 1 WHERE alertId = %s", (alertId,))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('alerts'))


@app.route('/markAllAlertsRead')
def markAllAlertsRead():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE SystemAlerts SET isRead = 1 WHERE isRead = 0")
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('alerts'))

# ─── Reports ─────────────────────────────────────────────────────────────────


@app.route('/reports')
def reports():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    today = date.today()

    salesFrom = request.args.get(
        'salesFrom', (today - timedelta(days=30)).isoformat())
    salesTo = request.args.get('salesTo', today.isoformat())

    topFrom = request.args.get(
        'topFrom', (today - timedelta(days=30)).isoformat())
    topTo = request.args.get('topTo', today.isoformat())

    attMonth = request.args.get('attMonth', today.strftime('%Y-%m'))
    y, m = map(int, attMonth.split('-'))
    startDate = date(y, m, 1)
    lastDay = calendar.monthrange(y, m)[1]
    endDate = date(y, m, lastDay)

    conn = getDbConnection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT st.fullName, SUM(s.totalBill) AS total
            FROM Sales s
            JOIN Staff st ON s.staffId = st.staffId
            WHERE s.saleDate BETWEEN %s AND %s
            GROUP BY s.staffId
            ORDER BY total DESC
        """, (salesFrom, salesTo))
        salesByStaff = cursor.fetchall()

        totalSales = sum(row['total']
                         for row in salesByStaff) if salesByStaff else 0
        topStaff = salesByStaff[0]['fullName'] if salesByStaff else '—'

        cursor.execute("""
            SELECT p.plantName, SUM(sd.quantity) AS qty
            FROM SaleDetails sd
            JOIN Sales s ON sd.saleId = s.saleId
            JOIN Plants p ON sd.plantId = p.plantId
            WHERE sd.plantId IS NOT NULL
              AND s.saleDate BETWEEN %s AND %s
            GROUP BY sd.plantId
            ORDER BY qty DESC
        """, (topFrom, topTo))
        topPlants = cursor.fetchall()

        cursor.execute("SELECT * FROM lowStockView")
        lowStock = cursor.fetchall()

        cursor.execute("""
            SELECT s.fullName,
                   SUM(a.status='present') AS presentCount,
                   SUM(a.status='absent') AS absentCount,
                   SUM(a.status='late') AS lateCount
            FROM Attendance a
            JOIN Staff s ON a.staffId = s.staffId
            WHERE a.attendanceDate BETWEEN %s AND %s
            GROUP BY a.staffId
            ORDER BY s.fullName
        """, (startDate, endDate))
        attendanceSummary = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) AS total FROM SystemAlerts WHERE isRead = 0")
        unreadAlerts = cursor.fetchone()['total']

    finally:
        conn.close()

    return render_template('reports.html',
                           salesByStaff=salesByStaff,
                           totalSales=totalSales,
                           topStaff=topStaff,
                           salesFrom=salesFrom,
                           salesTo=salesTo,
                           topPlants=topPlants,
                           topFrom=topFrom,
                           topTo=topTo,
                           lowStock=lowStock,
                           attendanceSummary=attendanceSummary,
                           attMonth=attMonth,
                           unreadAlerts=unreadAlerts)


@app.route('/reports/sales/pdf')
def salesReportPdf():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    salesFrom = request.args.get('salesFrom')
    salesTo = request.args.get('salesTo')

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT st.fullName, SUM(s.totalBill) AS total
            FROM Sales s
            JOIN Staff st ON s.staffId = st.staffId
            WHERE s.saleDate BETWEEN %s AND %s
            GROUP BY s.staffId
            ORDER BY total DESC
        """, (salesFrom, salesTo))
        rows = cursor.fetchall()
    finally:
        conn.close()

    pdf = build_pdf("Sales Report", ["Staff", "Total Sales"],
                    [[r['fullName'], f"Rs. {r['total']:.2f}"] for r in rows])
    return Response(pdf.getvalue(), mimetype='application/pdf',
                    headers={"Content-Disposition": "attachment;filename=sales_report.pdf"})


@app.route('/reports/topSelling/pdf')
def topSellingPdf():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    topFrom = request.args.get('topFrom')
    topTo = request.args.get('topTo')

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.plantName, SUM(sd.quantity) AS qty
            FROM SaleDetails sd
            JOIN Sales s ON sd.saleId = s.saleId
            JOIN Plants p ON sd.plantId = p.plantId
            WHERE sd.plantId IS NOT NULL
            AND s.saleDate BETWEEN %s AND %s
            GROUP BY sd.plantId
            ORDER BY qty DESC
        """, (topFrom, topTo))
        rows = cursor.fetchall()
    finally:
        conn.close()

    pdf = build_pdf("Top Selling Plants", ["Plant", "Quantity"],
                    [[r['plantName'], r['qty']] for r in rows])
    return Response(pdf.getvalue(), mimetype='application/pdf',
                    headers={"Content-Disposition": "attachment;filename=top_selling_plants.pdf"})


@app.route('/reports/lowStock/pdf')
def lowStockPdf():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lowStockView")
        rows = cursor.fetchall()
    finally:
        conn.close()

    pdf = build_pdf("Low Stock Report", ["Type", "Name", "Qty"],
                    [[r['itemType'], r['itemName'], r['quantity']] for r in rows])
    return Response(pdf.getvalue(), mimetype='application/pdf',
                    headers={"Content-Disposition": "attachment;filename=low_stock_report.pdf"})


@app.route('/reports/attendance/pdf')
def attendancePdf():
    if 'staffId' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    attMonth = request.args.get('attMonth')
    y, m = map(int, attMonth.split('-'))
    startDate = date(y, m, 1)
    lastDay = calendar.monthrange(y, m)[1]
    endDate = date(y, m, lastDay)

    conn = getDbConnection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.fullName,
                SUM(a.status='present') AS presentCount,
                SUM(a.status='absent') AS absentCount,
                SUM(a.status='late') AS lateCount
            FROM Attendance a
            JOIN Staff s ON a.staffId = s.staffId
            WHERE a.attendanceDate BETWEEN %s AND %s
            GROUP BY a.staffId
            ORDER BY s.fullName
        """, (startDate, endDate))
        rows = cursor.fetchall()
    finally:
        conn.close()

    pdf = build_pdf("Attendance Report", ["Staff", "Present", "Absent", "Late"],
                    [[r['fullName'], r['presentCount'], r['absentCount'], r['lateCount']] for r in rows])
    return Response(pdf.getvalue(), mimetype='application/pdf',
                    headers={"Content-Disposition": "attachment;filename=attendance_report.pdf"})


if __name__ == '__main__':
    hashAllPasswords()
    app.run(debug=True)
