SELECT
  c.c_customer_id,
  c.c_first_name,
  c.c_last_name,
  SUM(cs.cs_ext_sales_price) AS catalog_sales_total
FROM catalog_sales cs
JOIN customer c
  ON cs.cs_bill_customer_sk = c.c_customer_sk
JOIN date_dim d
  ON cs.cs_sold_date_sk = d.d_date_sk
WHERE d.d_year = 2001
GROUP BY c.c_customer_id, c.c_first_name, c.c_last_name
ORDER BY catalog_sales_total DESC
LIMIT 100;
