SELECT
  ca.ca_state,
  hd.hd_buy_potential,
  COUNT(*) AS order_count,
  SUM(cs.cs_ext_sales_price) AS total_revenue
FROM catalog_sales cs
JOIN customer c
  ON cs.cs_bill_customer_sk = c.c_customer_sk
JOIN customer_address ca
  ON c.c_current_addr_sk = ca.ca_address_sk
JOIN household_demographics hd
  ON c.c_current_hdemo_sk = hd.hd_demo_sk
JOIN date_dim d
  ON cs.cs_sold_date_sk = d.d_date_sk
WHERE d.d_qoy = 1
  AND d.d_year = 2002
GROUP BY ca.ca_state, hd.hd_buy_potential
ORDER BY total_revenue DESC, order_count DESC;
