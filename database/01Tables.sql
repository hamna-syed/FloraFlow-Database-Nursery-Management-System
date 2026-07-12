USE floraflowdb;

CREATE TABLE Staff (
    staffId INT AUTO_INCREMENT,
    fullName VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    passwordHash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'staff') NOT NULL DEFAULT 'staff',
    phone VARCHAR(20),
    email VARCHAR(100),
    hireDate DATE NOT NULL,
    isActive TINYINT(1) NOT NULL DEFAULT 1,
    CONSTRAINT pkStaffId PRIMARY KEY (staffId)
);
CREATE TABLE PlantCategories (
    categoryId INT AUTO_INCREMENT,
    categoryName VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    PRIMARY KEY (categoryId)
);

CREATE TABLE Plants (
    plantId INT AUTO_INCREMENT,
    plantName VARCHAR(100) NOT NULL,
    categoryId INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    description TEXT,
    careInstructions TEXT,
    PRIMARY KEY (plantId),
    CONSTRAINT fkPlantCategory FOREIGN KEY (categoryId) REFERENCES PlantCategories(categoryId)
);

CREATE TABLE Accessories (
    accessoryId INT AUTO_INCREMENT,
    accessoryName VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    description TEXT,
    PRIMARY KEY (accessoryId)
);

CREATE TABLE Customers (
    customerId INT AUTO_INCREMENT,
    fullName VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    address TEXT,
    PRIMARY KEY (customerId)
);

CREATE TABLE Sales (
    saleId INT AUTO_INCREMENT,
    customerId INT,
    staffId INT NOT NULL,
    saleDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    totalBill DECIMAL(10,2) NOT NULL DEFAULT 0,
    paymentMethod ENUM('cash', 'card') NOT NULL DEFAULT 'cash',
    PRIMARY KEY (saleId),
    CONSTRAINT fkSaleCustomer FOREIGN KEY (customerId) REFERENCES Customers(customerId),
    CONSTRAINT fkSaleStaff FOREIGN KEY (staffId) REFERENCES Staff(staffId)
);

CREATE TABLE SaleDetails (
    saleDetailId INT AUTO_INCREMENT,
    saleId INT NOT NULL,
    plantId INT,
    accessoryId INT,
    quantity INT NOT NULL,
    unitPrice DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (saleDetailId),
    CONSTRAINT fkSaleDetailSale FOREIGN KEY (saleId) REFERENCES Sales(saleId),
    CONSTRAINT fkSaleDetailPlant FOREIGN KEY (plantId) REFERENCES Plants(plantId),
    CONSTRAINT fkSaleDetailAccessory FOREIGN KEY (accessoryId) REFERENCES Accessories(accessoryId)
);

CREATE TABLE Suppliers (
    supplierId INT AUTO_INCREMENT,
    supplierName VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    address TEXT,
    PRIMARY KEY (supplierId)
);

CREATE TABLE Purchases (
    purchaseId INT AUTO_INCREMENT,
    supplierId INT NOT NULL,
    staffId INT NOT NULL,
    purchaseDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    totalCost DECIMAL(10,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (purchaseId),
    CONSTRAINT fkPurchaseSupplier FOREIGN KEY (supplierId) REFERENCES Suppliers(supplierId),
    CONSTRAINT fkPurchaseStaff FOREIGN KEY (staffId) REFERENCES Staff(staffId)
);

CREATE TABLE PurchasePlantDetails (
    purchasePlantDetailId INT AUTO_INCREMENT,
    purchaseId INT NOT NULL,
    plantId INT NOT NULL,
    quantity INT NOT NULL,
    unitCost DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (purchasePlantDetailId),
    CONSTRAINT fkPurchasePlantDetailPurchase FOREIGN KEY (purchaseId) REFERENCES Purchases(purchaseId),
    CONSTRAINT fkPurchasePlantDetailPlant FOREIGN KEY (plantId) REFERENCES Plants(plantId)
);

CREATE TABLE PurchaseAccessoryDetails (
    purchaseAccessoryDetailId INT AUTO_INCREMENT,
    purchaseId INT NOT NULL,
    accessoryId INT NOT NULL,
    quantity INT NOT NULL,
    unitCost DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (purchaseAccessoryDetailId),
    CONSTRAINT fkPurchaseAccessoryDetailPurchase FOREIGN KEY (purchaseId) REFERENCES Purchases(purchaseId),
    CONSTRAINT fkPurchaseAccessoryDetailAccessory FOREIGN KEY (accessoryId) REFERENCES Accessories(accessoryId)
);

CREATE TABLE CareSchedule (
    careId INT AUTO_INCREMENT,
    plantId INT NOT NULL,
    careType VARCHAR(100) NOT NULL,
    lastCheck DATE,
    nextCheck DATE NOT NULL,
    notes TEXT,
    PRIMARY KEY (careId),
    CONSTRAINT fkCareSchedulePlant FOREIGN KEY (plantId) REFERENCES Plants(plantId)
);

CREATE TABLE StaffTasks (
    taskId INT AUTO_INCREMENT,
    staffId INT NOT NULL,
    taskDescription TEXT NOT NULL,
    assignedDate DATE NOT NULL DEFAULT (CURRENT_DATE),
    dueDate DATE,
    status ENUM('pending', 'inProgress', 'done') NOT NULL DEFAULT 'pending',
    PRIMARY KEY (taskId),
    CONSTRAINT fkStaffTaskStaff FOREIGN KEY (staffId) REFERENCES Staff(staffId)
);

CREATE TABLE Attendance (
    attendanceId INT AUTO_INCREMENT,
    staffId INT NOT NULL,
    attendanceDate DATE NOT NULL DEFAULT (CURRENT_DATE),
    status ENUM('present', 'absent', 'late') NOT NULL DEFAULT 'present',
    PRIMARY KEY (attendanceId),
    CONSTRAINT fkAttendanceStaff FOREIGN KEY (staffId) REFERENCES Staff(staffId)
);

CREATE TABLE SystemAlerts (
    alertId INT AUTO_INCREMENT,
    alertType VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    createdAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    isRead TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY (alertId)
);
SHOW TABLES;