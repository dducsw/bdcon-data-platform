SELECT
  s.s_store_name,
  SUM(sr.sr_return_amt) AS returned_amount,
  SUM(ss.ss_net_paid) AS net_paid
FROM store_returns sr
JOIN store_sales ss
  ON sr.sr_item_sk = ss.ss_item_sk
 AND sr.sr_ticket_number = ss.ss_ticket_number
JOIN store s
  ON sr.sr_store_sk = s.s_store_sk
JOIN date_dim d
  ON sr.sr_returned_date_sk = d.d_date_sk
WHERE d.d_moy = 11
  AND d.d_year = 2000
GROUP BY s.s_store_name
ORDER BY returned_amount DESC, net_paid DESC;
