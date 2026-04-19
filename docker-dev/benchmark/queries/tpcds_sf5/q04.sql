SELECT
  i.i_brand_id,
  i.i_brand,
  SUM(ws.ws_ext_sales_price) AS web_sales_total,
  SUM(wr.wr_return_amt) AS web_return_total
FROM web_sales ws
LEFT JOIN web_returns wr
  ON ws.ws_order_number = wr.wr_order_number
 AND ws.ws_item_sk = wr.wr_item_sk
JOIN item i
  ON ws.ws_item_sk = i.i_item_sk
JOIN date_dim d
  ON ws.ws_sold_date_sk = d.d_date_sk
WHERE d.d_year = 2001
GROUP BY i.i_brand_id, i.i_brand
ORDER BY web_sales_total DESC
LIMIT 50;
