# ReceiptBuddy HR Service

Employee management, attendance tracking, leave management, and shift scheduling.

## Responsibilities

- Employee profiles (CRUD, departments, roles)
- Attendance with geolocation clock-in/out
- Leave requests with approval workflow & balance tracking
- Shift template generation and employee assignment

## API Endpoints

### Employees
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/employees` | Admin | Create employee |
| GET | `/api/employees` | User | List employees (filter: `?department=`, `?active_only=`) |
| GET | `/api/employees/{id}` | User | Get employee details |
| PUT | `/api/employees/{id}` | Admin | Update employee |
| DELETE | `/api/employees/{id}` | Admin | Delete employee |

### Attendance
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/attendance/clock-in` | Clock in (with optional geolocation) |
| POST | `/api/attendance/clock-out` | Clock out (auto-calculates hours) |
| GET | `/api/attendance/today` | Today's attendance records |
| GET | `/api/attendance/history` | Attendance history |
| GET | `/api/attendance/stats` | Attendance statistics |
| GET | `/api/attendance` | Filtered attendance list |

### Leave
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/leave/requests` | User | Submit leave request |
| GET | `/api/leave/requests` | User | List requests (filter: `?status=`) |
| PUT | `/api/leave/requests/{id}/review` | Manager | Approve/reject request |
| GET | `/api/leave/balances` | User | Get leave balance |

### Shifts
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/shift-templates` | Admin | Create shift template |
| GET | `/api/shift-templates` | User | List templates |
| POST | `/api/shifts/generate` | Admin | Generate shifts from templates |
| GET | `/api/shifts` | User | List shifts |
| GET | `/api/shifts/calendar` | User | Calendar view with assignments |
| POST | `/api/shifts/{id}/assign` | Admin | Assign employee to shift |

## Tech Stack

- **Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL
- **Cache**: Redis

## Quick Start

```bash
docker build -t receiptbuddy-hr .

docker run -p 8003:8003 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/receiptbuddy \
  -e SECRET_KEY=your-secret \
  receiptbuddy-hr
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing secret (shared across services) |

## Dependencies

- `receiptbuddy-common` — shared library
- PostgreSQL 16+, Redis 7+
