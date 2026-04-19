SELECT
  d.d_year,
  i.i_category,
  SUM(ss.ss_ext_sales_price) AS total_sales
FROM store_sales ss
JOIN date_dim d
  ON ss.ss_sold_date_sk = d.d_date_sk
JOIN item i
  ON ss.ss_item_sk = i.i_item_sk
WHERE d.d_year IN (1999, 2000, 2001)
GROUP BY d.d_year, i.i_category
ORDER BY d.d_year, total_sales DESC;
