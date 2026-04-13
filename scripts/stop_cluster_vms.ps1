$ErrorActionPreference = "Continue"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   🛑 SHUTDOWN ALL VMs (MAXIMUM SAVINGS) 🛑   " -ForegroundColor Red
Write-Host "=============================================" -ForegroundColor Cyan

# 1. Thu hồi toàn bộ K8s Pods về 0 để dọn dẹp nhẹ nhàng trước
Write-Host "`n[1/3] Đang thu hồi các ứng dụng..." -ForegroundColor Magenta
kubectl scale deployment,statefulset --all -n data-platform --replicas=0
kubectl scale kafkanodepool --all -n data-platform --replicas=0

# Xoá cả system namespace nếu muốn dọn sạch nhất có thể
kubectl scale deployment,statefulset --all -n monitoring --replicas=0
kubectl scale deployment,statefulset --all -n external-secrets --replicas=0
kubectl scale deployment,statefulset --all -n ingress-nginx --replicas=0

Start-Sleep -Seconds 10

# 2. Xoá bảo vệ số lượng Node tối thiểu
Write-Host "`n[2/3] Gỡ bỏ giới hạn số lượng VM tối thiểu cho Infra-pool..." -ForegroundColor Magenta
gcloud container clusters update data-platform-cluster --zone asia-southeast1-a --node-pool infra-pool --enable-autoscaling --min-nodes 0 --max-nodes 1 --quiet

# 3. Ra lệnh bóp gáy tắt toàn bộ VM ngay lập tức
Write-Host "`n[3/3] Đang gửi lệnh ép toàn bộ máy chủ (VMs) về 0... (Sẽ mất khoảng 1-2 phút)" -ForegroundColor Magenta
gcloud container clusters resize data-platform-cluster --node-pool compute-pool --num-nodes 0 --zone asia-southeast1-a --quiet
gcloud container clusters resize data-platform-cluster --node-pool query-pool   --num-nodes 0 --zone asia-southeast1-a --quiet
gcloud container clusters resize data-platform-cluster --node-pool infra-pool   --num-nodes 0 --zone asia-southeast1-a --quiet

Write-Host "`n🎉 ĐÃ TẮT SẠCH VM! Hiện tại hệ thống không còn bất kỳ một máy chủ nào chạy tốn tiền của bạn nữa." -ForegroundColor Green
Write-Host "   (Ngày mai khi cần dùng lại, bạn mở \`main.tf\` và chạy lại \`terraform apply\` để hệ thống khôi phục 1 Node cho Infra-pool)." -ForegroundColor Yellow
