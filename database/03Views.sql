USE floraflowdb;

-- View 1: Low stock plants and accessories combined
CREATE VIEW lowStockView AS

    SELECT 
        'plant' AS itemType,
        plantId AS itemId,
        plantName AS itemName,
        quantity
    FROM Plants
    WHERE quantity < 5

    UNION ALL

    SELECT 
        'accessory' AS itemType,
        accessoryId AS itemId,
        accessoryName AS itemName,
        quantity
    FROM Accessories
    WHERE quantity < 5;
    
    SHOW FULL TABLES WHERE Table_type = 'VIEW';