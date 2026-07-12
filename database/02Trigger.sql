USE floraflowdb;

-- Trigger 1: Decrease plant quantity after a sale
DELIMITER $$
CREATE TRIGGER afterSaleDetailInsert
AFTER INSERT ON SaleDetails
FOR EACH ROW
BEGIN
    IF NEW.plantId IS NOT NULL THEN
        UPDATE Plants
        SET quantity = quantity - NEW.quantity
        WHERE plantId = NEW.plantId;
    END IF;
END$$
DELIMITER ;

-- Trigger 2: Increase plant quantity after a purchase
DELIMITER $$
CREATE TRIGGER afterPurchasePlantDetailInsert
AFTER INSERT ON PurchasePlantDetails
FOR EACH ROW
BEGIN
    UPDATE Plants
    SET quantity = quantity + NEW.quantity
    WHERE plantId = NEW.plantId;
END$$
DELIMITER ;

-- Trigger 3: Increase accessory quantity after a purchase
DELIMITER $$
CREATE TRIGGER afterPurchaseAccessoryDetailInsert
AFTER INSERT ON PurchaseAccessoryDetails
FOR EACH ROW
BEGIN
    UPDATE Accessories
    SET quantity = quantity + NEW.quantity
    WHERE accessoryId = NEW.accessoryId;
END$$
DELIMITER ;