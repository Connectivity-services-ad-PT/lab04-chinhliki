# Docker Readiness Checklist

## Dockerfile

- [x] Có base image hợp lý.
- [x] Có `WORKDIR`.
- [x] Có copy dependency trước source để tận dụng cache.
- [x] Có `EXPOSE`.
- [x] Có `CMD` hoặc `ENTRYPOINT`.
- [x] Có `HEALTHCHECK`.
- [x] Có user non-root.
- [x] Không chứa secret thật.

## Runtime

- [x] Container chạy được.
- [x] Port map đúng.
- [x] `/health` trả `200`.
- [x] Log khởi động rõ ràng.
- [x] Cấu hình qua ENV.

## Testing

- [x] Chạy lại Postman Collection từ Lab 03.
- [x] Newman report sinh ra trong `reports/`.
- [x] Functional test pass.
- [x] Auth test pass trên local/container.
- [x] Negative test pass trên local/container.
- [x] Boundary test pass hoặc có giải thích hợp đồng.

## Evidence

- [x] Có ảnh/log `docker build`.
- [x] Có ảnh/log `docker run`.
- [x] Có ảnh/log `curl /health`.
- [x] Có Newman HTML/XML report.
- [x] Có tag image đúng quy ước.
