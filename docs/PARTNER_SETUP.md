# Hướng dẫn Thiết lập Dự án & Làm việc Nhóm (GKE Data Platform)

Tài liệu này hướng dẫn cách kết nối và đóng góp vào hạ tầng Data Platform có sẵn, sử dụng chung không gian mạng và tài nguyên máy chủ Google Cloud (GCP) với Admin của dự án. 

Hạ tầng được quản lý hoàn toàn bằng **Terraform** với trạng thái (state) được lưu trữ tập trung trên Google Cloud Storage (GCS) để đảm bảo đồng bộ hóa giữa các thành viên.

---

## 1. Yêu cầu trước khi bắt đầu (Pre-requisites)

### Phía Admin dự án
Admin dự án cần đảm bảo bạn đã được cấp các quyền sau trong Google Cloud IAM cho email của bạn (trên project `k8s-data-platform-1879`):
- `Project Editor` (hoặc các quyền tối thiểu: `Kubernetes Engine Admin`, `Compute Admin`, `Storage Admin`).

### Phía Người thiết lập (Partner/Bạn)
Hãy cài đặt các công cụ sau lên máy cá nhân của bạn:
1. **[Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install)**: Để xác thực và kết nối đến GCP.
2. **[Terraform (>= 1.5.0)](https://developer.hashicorp.com/terraform/downloads)**: Động cơ cốt lõi (IaC) để đọc code và dịch sang hạ tầng.
3. **[Kubectl](https://kubernetes.io/docs/tasks/tools/)**: Công cụ giao tiếp với cụm Kubernetes đang chạy.

---

## 2. Các bước Setup và Kết nối

### Bước 1: Clone Repo dự án
Tải mã nguồn dự án này về máy cá nhân của bạn:
```bash
git clone <đường-dẫn-repo-github-của-dự-án>
cd k8s-data-platform
```

### Bước 2: Đăng nhập vào Google Cloud
Để Terraform có thể đọc/ghi trạng thái từ GCS Bucket và tạo cấu hình, bạn cần thực hiện lấy **chuỗi token xác thực** về máy tính bằng lệnh:

```bash
gcloud auth application-default login
```
*Lưu ý: Một tab trình duyệt sẽ mở ra, hãy chọn đúng Email đã được Admin cấp quyền.*

Sau đó, xác định Project làm việc mặc định trên terminal (thay thế ID nếu cần):
```bash
gcloud config set project k8s-data-platform-1879
```

### Bước 3: Đồng bộ Hạ tầng qua Terraform
Di chuyển vào thư mục chứa code IaC:
```bash
cd terraform
```

Khởi tạo Terraform để tự động tải các Plugin (Provider) và **kết nối với State trên đám mây**:
```bash
terraform init
```

*Nếu thành công, bạn sẽ thấy thông báo: `Successfully configured the backend "gcs"`.* 

Tạo hoặc xin Admin file biến môi trường gốc nếu bạn chưa có:
```bash
cp terraform.tfvars.example terraform.tfvars
```
*(Lưu ý: Nội dung trong file `terraform.tfvars` không được push lên Github, bạn có thể tự thiết lập các thông số cơ bản cho riêng mình theo giải thích của file ví dụ).*

### Bước 4: Kiểm tra kết nối Kubernetes
Sau khi đã Sync thành công, bạn lấy cấu hình kết nối trực tiếp đến cụm GKE trên Cloud để có thể quét log, xem tài nguyên k8s bằng lệnh sau:
```bash
gcloud container clusters get-credentials data-platform-cluster --region asia-east1 --project k8s-data-platform-1879
```
Kiểm tra lại xem đã lấy được cụm k8s về máy chưa:
```bash
kubectl get nodes
kubectl get pods -A
```

---

## 3. Quy trình làm việc nhóm hàng ngày với Terraform

Vì hai người đang tương tác vào cùng một cụm hạ tầng thực tế, hãy tuân thủ nguyên tắc:

1. **Luôn Update code trước khi làm:** 
   Chạy `git pull` để nhận code `.tf` mới nhất trước khi chỉnh sửa.
2. **Dùng Plan để soát lỗi:**
   Sau khi bạn sửa file `main.tf` hay thêm các biến môi trường, **TUYỆT ĐỐI KHÔNG APPLY NGAY**, hãy chạy:
   ```bash
   terraform plan
   ```
   Lệnh này sẽ cho bạn biết những máy chủ/ổ cứng nào chuẩn bị được Thêm, Xóa, hoặc Sửa đổi.
3. **Xin Review và Apply:**
   Nếu kết quả plan (`terraform plan`) là chính xác ý muốn của bạn, tiến hành:
   ```bash
   terraform apply
   ```
4. **Không bao giờ dùng Destroy tùy tiện**:
   Lệnh `terraform destroy` sẽ đánh sập toàn bộ Database, ổ cứng, Node và Cluster đang chạy. Xin ý kiến Admin trước khi dùng lệnh này. Đừng để bay màu dữ liệu!
