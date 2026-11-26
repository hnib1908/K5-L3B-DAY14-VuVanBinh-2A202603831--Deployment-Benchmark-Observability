# Benchmark & Observability Report — Day 14

- **Họ tên** — Vu Van Binh (2A202603831)
- **Ngày chạy** — 26/11/2026, giờ Việt Nam
- **Môi trường** — Ubuntu trên WSL2 và Docker Desktop. Ubuntu thấy 16 CPU logic và 7,6 GiB RAM. Các phép đo develop dùng Python 3.11.18 và các dependency trong `requirements.txt`. Các lần đo production dùng Docker Compose qua Nginx.

## 1. SLO của agent

| SLI | SLO | Lý do |
| --- | --- | --- |
| Độ trễ p95 của `/ask` | ≤ 500 ms | Giữ 95% yêu cầu trong ngân sách nửa giây khi đánh giá ở tải mục tiêu. |
| Tỷ lệ lỗi của `/ask` | ≤ 2% | Cho phép một số lỗi tạm thời trong mô phỏng, đồng thời giới hạn tỷ lệ người dùng phải thử lại. |
| Accuracy trên golden dataset | ≥ 80% ở lần đánh giá ban đầu, 100% sau khi sửa KB | Dùng ngưỡng 80% để so sánh v1 và v2. Sau khi sửa đủ 23 mẫu, giữ cả 23 mẫu làm điều kiện qua gate. |

Ngưỡng latency và lỗi lấy từ [load test](06-lab-complete/benchmark-observability/develop/load_test.py). Gate chất lượng dùng [trình đánh giá](06-lab-complete/benchmark-observability/develop/eval/run_eval.py) và bộ golden dataset của lab.

## 2. Benchmark hiệu năng

### 2.1 Concurrency và độ trễ của v2

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Tỷ lệ lỗi | SLO | JSON |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1 | 4,78 | 190,3 | 218,3 | 1.660,0 | 0,67% | PASS | [c1](reports/load_v2_c1.json) |
| 10 | 36,23 | 186,0 | 221,3 | 1.689,1 | 1,33% | PASS | [c10](reports/load_v2_c10.json) |
| 50 | 102,11 | 206,3 | 321,4 | 1.698,4 | 1,00% | PASS | [c50](reports/load_v2_c50.json) |
| 100 | 43,66 | 668,5 | 4.300,6 | 4.907,0 | 2,00% | FAIL | [c100](reports/load_v2_c100.json) |

Mỗi lần chạy gửi 300 request lên một tiến trình agent v2. RPS tăng đến concurrency 50 rồi giảm còn 43,66 ở 100, trong khi p95 vượt ngưỡng 500 ms. Mẫu này phù hợp với việc request phải đợi tài nguyên khi concurrency tăng. Máy cũng tải image Docker trong giai đoạn benchmark develop, nên phép đo riêng này chưa xác định được tài nguyên nào bị bão hòa.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | Trung bình (ms) | p95 (ms) | p99 (ms) | JSON |
| --- | ---: | ---: | ---: | --- |
| 0 | 193,5 | 223,5 | 230,2 | [slow 0](reports/load_v2_slow_0.json) |
| 0,03 | 226,9 | 224,2 | 1.691,1 | [slow 0,03](reports/load_v2_slow_0.03.json) |
| 0,10 | 328,3 | 1.686,7 | 1.713,9 | [slow 0,10](reports/load_v2_slow_0.1.json) |

Ở tỷ lệ chậm 3%, p99 đã tăng lên 1,69 giây, còn p95 chỉ tăng 0,7 ms. Khi tỷ lệ chậm lên 10%, p95 cũng vượt 1,68 giây. Giá trị trung bình ở lần chạy đó vẫn dưới 500 ms, nên một SLO chỉ theo trung bình sẽ bỏ sót đuôi chậm. Các lần chạy dùng fault injection ngẫu nhiên và được thực hiện trước khi thêm histogram chiều dài câu hỏi và sửa KB.

## 3. Benchmark chất lượng

| Chỉ số | [v1](reports/eval_v1.json) | [v2](reports/eval_v2.json) | [v2 sau khi sửa KB](reports/eval_v2_fixed.json) |
| --- | ---: | ---: | ---: |
| Accuracy | 4,35% (1/23) | 91,30% (21/23) | 100% (23/23) |
| Token trung bình mỗi câu | 57,8 | 109,0 | 114,4 |
| p95 (ms) | 191,8 | 209,5 | 221,8 |
| Tổng chi phí mô phỏng (USD) | 0,000414 | 0,000760 | 0,000797 |
| Chi phí mỗi câu đúng (USD) | 0,00041415 | 0,00003619 | 0,00003465 |
| Quality gate | FAIL ở 80% | PASS ở 80% | PASS ở 100% |

| Mẫu v2 sai ban đầu | Từ khóa thiếu | Cách sửa |
| --- | --- | --- |
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung mục JWT mô tả token có chữ ký, trường hết hạn và kiểm tra ở API Gateway. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung mục HPA mô tả các tín hiệu có thể dùng để tự tăng giảm replica. |

V2 dùng gần gấp đôi token và p95 cao hơn 17,7 ms so với v1. Tổng chi phí mô phỏng tăng, còn chi phí mỗi câu đúng giảm hơn 11 lần nhờ số câu đạt tăng từ 1 lên 21. Hai mục KB giúp v2 trả lời đủ bộ test với mức tăng 5,4 token trung bình mỗi câu so với v2 ban đầu. [KB của agent develop](06-lab-complete/benchmark-observability/develop/utils/mock_llm.py)

Khi chạy v1 với ngưỡng 85% và dùng v2 làm baseline, runner ghi 20 regression và trả exit code `1`. V2 sau sửa đạt gate 100% và có 0 regression so với v2 ban đầu. Trong CI, có thể chạy bộ đánh giá trên mỗi pull request, dùng bản đã duyệt trên `main` làm baseline và yêu cầu job thành công trước khi merge. CP7 cũng đã xác nhận `/metrics` trả chuỗi `counter`, `gauge`, `histogram` và `agent_question_length_chars_count 23.0` sau lượt eval cố định. [Histogram trong agent develop](06-lab-complete/benchmark-observability/develop/app.py)

## 4. Observability stack

### 4.1 Dashboard lúc có tải

Locust chạy 30 users, tăng 5 users mỗi giây. Lúc chụp, Golden Signals hiển thị khoảng 18,4 request/giây, 1,28% lỗi, p95 296,59 ms và 6 request đang xử lý. Prometheus đo trung bình 239,24 ms trong cùng cửa sổ một phút. p95 cao hơn trung bình 57,34 ms, còn đường p99 trên biểu đồ nằm trên 1,5 giây vì một phần nhỏ request chậm. [Dashboard Grafana](screenshots/grafana-dashboard.png)

- Ở cuối biểu đồ **Requests/s theo instance**, hai replica còn chạy nhận lần lượt 9,32 và 9,24 request/giây trong cửa sổ 30 giây. Lưu lượng được chia gần đều. Đường thứ ba ở phần đầu biểu đồ là replica của lượt benchmark scaling trước đó.
- Prometheus đo 1.359,87 input token/giây và 722,65 output token/giây. Input tính cả câu hỏi và ngữ cảnh đưa vào mock LLM. [Mock LLM](06-lab-complete/benchmark-observability/production/utils/mock_llm.py)
- `GET /metrics` qua Nginx ở cổng `8080` trả `404`. Prometheus đọc trực tiếp `/metrics` của từng replica trong mạng nội bộ. [Nginx](06-lab-complete/benchmark-observability/production/nginx/nginx.conf) · [Prometheus](06-lab-complete/benchmark-observability/production/prometheus/prometheus.yml)

### 4.2 Thí nghiệm cảnh báo

`promtool test rules` trả `SUCCESS`. Giữ nguyên tải 30 users và cập nhật đồng thời hai biến fault injection khi tạo lại agent. Thời gian trong bảng được đo từ lúc bắt đầu cập nhật Compose đến lần đầu API Prometheus báo `firing`.

| Thử nghiệm | Thay đổi | Điều kiện cảnh báo | Đến lúc firing | Giá trị lúc firing | Panel |
| --- | --- | --- | ---: | ---: | --- |
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` vượt 5% trong 1 phút | 93,2 s | 20,17% lỗi | Error rate |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` vượt 1 giây trong 2 phút | 147,3 s | p95 1,89 s | Latency p95 |

Hai cảnh báo cùng ở trạng thái **FIRING** trong nhóm `agent-slo`. Ảnh cũng ghi lại cảnh báo chi phí đã kích hoạt trong lượt tải trước đó. [Trang Alerts của Prometheus](screenshots/prometheus-alert-firing.png)

Với thí nghiệm E, giảm xuống v1 có thể làm nội dung trả lời sai dù request vẫn trả `200` và latency nằm trong ngưỡng. Tôi sẽ chạy golden eval trước deploy, so với baseline và chặn phiên bản làm accuracy giảm. Sau deploy, có thể chạy các câu hỏi mẫu định kỳ để cảnh báo accuracy giảm theo phiên bản. [Kết quả eval v1](reports/eval_v1.json) · [Alert rules](06-lab-complete/benchmark-observability/production/prometheus/alert_rules.yml)

### 4.3 Debug bằng trace

**Trace chậm** — `abcb8997c48280338559ca60dccc862b`. Tổng thời gian 1.721,36 ms. Span `chat mock-llm-small` mất 1.698,79 ms, chiếm 98,69% thời lượng. Đây là trace khớp với mẫu có `llm_ms` lớn nhất trong các log agent thu được lúc thí nghiệm. [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png)

```json
{"ts":"2026-11-26T16:54:33.774494+00:00","level":"INFO","service":"observable-agent","instance":"d1595375a94f","event":"llm_call","trace_id":"abcb8997c48280338559ca60dccc862b","span_id":"f61d79cb8619ec3e","request_id":"629a23333260","model":"mock-llm-small","agent_version":"v2","input_tokens":95,"output_tokens":55,"cost_usd":0.000047,"llm_ms":1698.6}
```

**Trace lỗi** — `3412a1653cb084aca9a067ff92326d27`. Endpoint trả HTTP `503`. Span `chat mock-llm-small` ghi event `exception` với loại `utils.mock_llm.LLMError` và thông báo `Upstream LLM error: 503 Service Unavailable (mock)`. Dòng log `llm_error` mang cùng `trace_id`. [Trace lỗi trong Jaeger](screenshots/jaeger-error-trace.png)

```json
{"ts":"2026-11-26T16:56:10.045804+00:00","level":"INFO","service":"observable-agent","instance":"bf406f81b11b","event":"llm_error","trace_id":"3412a1653cb084aca9a067ff92326d27","span_id":"a1e291e8e0795f29","request_id":"3ffd0e20a656","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling

Mỗi lượt dùng Locust headless với 100 users, tốc độ tăng 10 users/giây trong 2 phút qua Nginx. Agent v2 trong stack observability dùng KB production của lab, `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`. Mỗi replica có 1 worker, được cấp tối đa 0,5 CPU và 256 MB bộ nhớ. Tôi dùng `docker compose run --no-deps` cho Locust để Compose giữ số replica đã đặt trước lượt đo. Kiểm tra số agent đang chạy ở cuối mỗi lượt. [Compose](06-lab-complete/benchmark-observability/production/docker-compose.yml) · [Kịch bản Locust](06-lab-complete/benchmark-observability/production/locust/locustfile.py)

| Replica | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures | Tỷ lệ lỗi | CSV |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 59,72 | 200 | 340 | 1.700 | 70 / 7.118 | 0,98% | [scale 1](benchmark-results/scale_1_stats.csv) |
| 3 | 59,71 | 190 | 230 | 1.700 | 74 / 7.055 | 1,05% | [scale 3](benchmark-results/scale_3_stats.csv) |

Bảng dùng dòng `POST /ask` trong mỗi CSV. Tăng từ 1 lên 3 replica làm p95 giảm 110 ms (32,4%) ở lượt đo này. RPS gần như giữ nguyên với cùng số người dùng và thời gian nghỉ sau mỗi lần gọi; số liệu chưa đo công suất tối đa của mỗi cấu hình. p99 vẫn khoảng 1,7 giây vì mỗi request chậm tiếp tục mất thời gian trong mock LLM, kể cả khi phân tải qua nhiều replica. Tỷ lệ lỗi quanh 1% phù hợp với cấu hình lỗi mô phỏng. Báo cáo cuối của cả hai lượt ghi lỗi HTTP `503`.

## 6. Kết luận

1. Cần xem percentile theo tỷ lệ request chậm. Trong lượt fault 3%, p99 đã tăng rõ rệt trong khi p95 gần như giữ nguyên. Ở 10%, cả p95 và p99 đều phản ánh đuôi chậm.
2. Chất lượng cần được kiểm thử độc lập với độ trễ và lỗi HTTP. Eval v1 đạt 1/23 và v2 sau sửa đạt 23/23. Chênh lệch lớn đó chỉ xuất hiện khi chấm nội dung câu trả lời.
3. Scale có thể giảm thời gian chờ ở một mức tải. Khi trace cho thấy thời gian tập trung ở LLM, thêm replica vẫn để lại độ trễ của chính bước đó. Cần theo dõi p95, p99 và span LLM cùng lúc để chọn cách tối ưu.

Khi triển khai thực tế, tôi sẽ thêm metric độ trễ chờ ở hàng đợi, phân tách theo route. Nếu p95 thời gian chờ tăng trong lúc p95 của LLM ổn định, có thể kiểm tra giới hạn concurrency và tải từng replica. Tôi sẽ dùng ngưỡng dựa trên ngân sách độ trễ của dịch vụ để cảnh báo sớm trước khi tổng p95 vi phạm SLO.
