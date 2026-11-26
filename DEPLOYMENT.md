# Triển khai agent Day 14

## URL công khai

[day14-agent trên Render](https://day14-agent-5k5n.onrender.com)

## Nền tảng và cấu hình

- Nền tảng Render, Blueprint `day14-lab`, branch `main`, commit deploy `742e817`.
- Web service `day14-agent` chạy Dockerfile trong `06-lab-complete/` và dùng `/health` làm health check.
- Key Value `day14-redis` nhận kết nối qua mạng nội bộ. Cả hai service dùng gói Free cùng region Singapore. [Blueprint](06-lab-complete/render.yaml)

| Biến môi trường | Cách đặt |
| --- | --- |
| `PORT` | Do Render cấp, Dockerfile dùng khi khởi động Uvicorn. |
| `ENVIRONMENT` | `production`. |
| `AGENT_API_KEY` | Do Render sinh cho web service. |
| `REDIS_URL` | Connection string nội bộ của `day14-redis`. |

## Kiểm tra HTTP

Chạy trong Bash. Lấy `AGENT_API_KEY` từ trang Environment của web service và nhập khi terminal hỏi. Lệnh chỉ hiện mã HTTP.

```bash
BASE='https://day14-agent-5k5n.onrender.com'
read -rsp 'Render API key: ' AGENT_API_KEY
printf '\n'
curl -sS -o /dev/null -w 'GET /health: %{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w 'GET /ready: %{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w 'POST /ask (thieu key): %{http_code}\n' \
  -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w 'POST /ask (co key): %{http_code}\n' \
  -X POST "$BASE/ask" -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
unset AGENT_API_KEY
```

| Request | HTTP quan sát được | Phản hồi |
| --- | --- | --- |
| `GET /health` | `200 OK` | `{"status":"ok"}` |
| `GET /ready` | `200 OK` | `{"ready":true}` |
| `POST /ask` thiếu API key | `401 Unauthorized` | `{"detail":"Invalid or missing API key"}` |
| `POST /ask` với API key đúng | `200 OK` | Mã HTTP từ lần kiểm tra có key trong terminal. |

## Ảnh minh chứng

- [Dashboard](screenshots/dashboard.png) hiển thị web service `Deployed` và Key Value `Available`.
- [Service đang chạy](screenshots/running.png) hiển thị trạng thái Live và URL công khai.
- [Kết quả kiểm tra HTTP](screenshots/test.png) hiển thị `200`, `200`, `401`, `200`.
