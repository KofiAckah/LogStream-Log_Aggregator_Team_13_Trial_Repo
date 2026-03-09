# PR Summary

## What Changed
- Added environment-specific Spring Boot configs for dev, prod, and test.
- Restored the Maven `pom.xml` with required dependencies and Java 21.
- Introduced shared response DTOs, including `PaginatedResponse` and updates to `ErrorResponse`.
- Removed compiled `target/classes` artifacts (per change summary).

## Why
- Standardize environment configuration, fix build setup, and centralize API response shapes for pagination/error handling.

## Testing
- Not run.

## Files Referenced
- `git-changes-summary.md`
- `backend/src/main/java/com/logstream/common/response/PaginatedResponse.java`
- `backend/src/main/java/com/logstream/common/response/ErrorResponse.java`
- `backend/src/main/resources/application-dev.yml`
- `backend/src/main/resources/application-prod.yml`
- `backend/src/main/resources/application-test.yml`
- `backend/src/main/resources/application.yml`
- `backend/pom.xml`

