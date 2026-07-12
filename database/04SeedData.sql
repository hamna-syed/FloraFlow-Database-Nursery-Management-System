USE floraflowdb;

-- Staff (1 admin + 3 staff, passwords will be updated later via Flask with proper hashing)
INSERT INTO Staff (fullName, username, passwordHash, role, phone, email, hireDate) VALUES
('Admin User', 'admin', 'temppass', 'admin', '03001234567', 'admin@floraflow.com', '2024-01-01'),
('Ali Hassan', 'ali', 'temppass', 'staff', '03011234567', 'ali@floraflow.com', '2024-02-01'),
('Sara Khan', 'sara', 'temppass', 'staff', '03021234567', 'sara@floraflow.com', '2024-03-01'),
('Usman Raza', 'usman', 'temppass', 'staff', '03031234567', 'usman@floraflow.com', '2024-04-01');

-- PlantCategories
INSERT INTO PlantCategories (categoryName, description) VALUES
('Indoor Plants', 'Plants suitable for indoor environments'),
('Outdoor Plants', 'Plants suitable for outdoor gardens'),
('Succulents', 'Low maintenance water storing plants'),
('Flowering Plants', 'Plants that produce flowers'),
('Trees', 'Large woody plants');

-- Plants
INSERT INTO Plants (plantName, categoryId, price, quantity, description, careInstructions) VALUES
('Money Plant', 1, 250.00, 20, 'Popular indoor plant', 'Water twice a week'),
('Peace Lily', 1, 400.00, 15, 'Air purifying indoor plant', 'Keep in shade, water weekly'),
('Rose Bush', 4, 500.00, 10, 'Classic flowering plant', 'Water daily, full sunlight'),
('Cactus', 3, 150.00, 30, 'Low maintenance succulent', 'Water once a month'),
('Mango Tree', 5, 1200.00, 5, 'Fruit bearing tree', 'Water daily, full sunlight'),
('Jasmine', 4, 350.00, 12, 'Fragrant flowering plant', 'Water every 2 days'),
('Snake Plant', 1, 300.00, 25, 'Hardy indoor plant', 'Water once a week'),
('Tulip', 4, 450.00, 8, 'Colorful flowering plant', 'Water every 2 days');

-- Accessories
INSERT INTO Accessories (accessoryName, price, quantity, description) VALUES
('Clay Pot Small', 120.00, 50, 'Small clay pot for indoor plants'),
('Clay Pot Large', 250.00, 30, 'Large clay pot for outdoor plants'),
('Fertilizer Bag', 350.00, 40, 'General purpose plant fertilizer'),
('Watering Can', 480.00, 20, 'Standard watering can'),
('Garden Gloves', 180.00, 35, 'Protective garden gloves'),
('Pruning Shears', 550.00, 15, 'Sharp pruning shears'),
('Soil Bag', 200.00, 45, 'Premium potting soil');

-- Customers
INSERT INTO Customers (fullName, phone, email, address) VALUES
('Ahmed Ali', '03101234567', 'ahmed@gmail.com', 'House 5, Street 3, Rawalpindi'),
('Fatima Malik', '03111234567', 'fatima@gmail.com', 'Flat 2, Block A, Islamabad'),
('Bilal Chaudhry', '03121234567', 'bilal@gmail.com', 'House 10, Street 7, Lahore'),
('Ayesha Noor', '03131234567', 'ayesha@gmail.com', 'House 3, Street 1, Karachi');

-- Suppliers
INSERT INTO Suppliers (supplierName, phone, email, address) VALUES
('Green World Nursery', '04212345678', 'greenworld@supplier.com', 'Main Market, Lahore'),
('Flora Imports', '04223456789', 'floraimports@supplier.com', 'Industrial Area, Karachi'),
('Plant Hub', '05113456789', 'planthub@supplier.com', 'Blue Area, Islamabad');

-- CareSchedule
INSERT INTO CareSchedule (plantId, careType, lastCheck, nextCheck, notes) VALUES
(1, 'Watering', '2025-04-28', '2025-05-01', 'Check soil moisture before watering'),
(2, 'Watering', '2025-04-28', '2025-05-01', 'Keep soil slightly moist'),
(3, 'Pruning', '2025-04-25', '2025-05-01', 'Remove dead flowers'),
(4, 'Watering', '2025-04-28', '2025-05-04', 'Do not overwater'),
(5, 'Fertilizing', '2025-04-20', '2025-05-01', 'Use organic fertilizer');