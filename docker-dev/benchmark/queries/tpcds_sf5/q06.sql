SELECT
  w.w_warehouse_name,
  SUM(inv.inv_quantity_on_hand) AS total_inventory,
  COUNT(DISTINCT inv.inv_item_sk) AS sku_count
FROM inventory inv
JOIN warehouse w
  ON inv.inv_warehouse_sk = w.w_warehouse_sk
JOIN date_dim d
  ON inv.inv_date_sk = d.d_date_sk
WHERE d.d_year = 2001
GROUP BY w.w_warehouse_name
ORDER BY total_inventory DESC, sku_count DESC;
