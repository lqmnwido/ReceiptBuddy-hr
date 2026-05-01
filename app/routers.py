"""HR routers — employees, attendance, leave, shifts."""
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from common.database import get_db
from common.models import User, Employee, Attendance, LeaveBalance, Leave
from common.repositories import (
    EmployeeRepository, AttendanceRepository, LeaveBalanceRepository,
    LeaveRepository, ShiftTemplateRepository, ShiftRepository, ShiftAssignmentRepository,
)
from common.schemas import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    AttendanceClockIn, AttendanceClockOut, AttendanceResponse,
    LeaveRequest, LeaveUpdate, LeaveResponse, LeaveBalanceResponse,
    ShiftTemplateCreate, ShiftTemplateResponse, ShiftGenerateRequest, ShiftAssignmentResponse,
)
from common.exceptions import NotFoundException, ConflictException
from common.dependencies import get_current_user, get_admin_user, get_manager_or_admin

router = APIRouter(tags=["HR"])


# ─── EMPLOYEES ───────────────────────────────────────

@router.post("/employees", response_model=EmployeeResponse, status_code=201)
def create_employee(req: EmployeeCreate, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    repo = EmployeeRepository(db)
    return repo.create_from_schema(req)


@router.get("/employees", response_model=list[EmployeeResponse])
def list_employees(
    skip: int = 0,
    limit: int = 100,
    department: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    repo = EmployeeRepository(db)
    if department:
        return repo.get_by_department(department)
    if active_only:
        return repo.get_active(skip, limit)
    return repo.list(skip=skip, limit=limit)


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    repo = EmployeeRepository(db)
    return repo.get_or_404(employee_id)


@router.put("/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    req: EmployeeUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    repo = EmployeeRepository(db)
    return repo.update_from_schema(employee_id, req)


@router.delete("/employees/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    repo = EmployeeRepository(db)
    repo.delete(employee_id)
    return {"message": "Employee deleted"}


# ─── ATTENDANCE ──────────────────────────────────────

def _resolve_employee_id(db: Session, user_id: int) -> int:
    """Resolve employee_id from user_id. Returns the employee id or raises 404."""
    emp = db.query(Employee).filter(Employee.user_id == user_id).first()
    if not emp:
        raise NotFoundException("No employee profile linked to your account")
    return emp.id


@router.post("/attendance/clock-in", response_model=AttendanceResponse)
def clock_in(
    req: AttendanceClockIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = AttendanceRepository(db)
    now = datetime.utcnow()
    emp_id = req.employee_id if req.employee_id and req.employee_id > 0 else _resolve_employee_id(db, current_user.id)

    existing = repo.get_by_employee_and_date(emp_id, req.date)
    if existing and existing.clock_in and not existing.clock_out:
        raise ConflictException("Already clocked in today")

    record = repo.create(
        employee_id=emp_id,
        date=req.date,
        clock_in=now,
        clock_in_lat=req.lat,
        clock_in_lng=req.lng,
    )
    return record


@router.post("/attendance/clock-out", response_model=AttendanceResponse)
def clock_out(
    req: AttendanceClockOut,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = AttendanceRepository(db)
    now = datetime.utcnow()
    emp_id = req.employee_id if req.employee_id and req.employee_id > 0 else _resolve_employee_id(db, current_user.id)

    record = repo.get_by_employee_and_date(emp_id, req.date)
    if not record:
        raise NotFoundException("No clock-in record found for today")

    if record.clock_out:
        raise ConflictException("Already clocked out today")

    hours = (now - record.clock_in).total_seconds() / 3600
    repo.update(
        record.id,
        clock_out=now,
        clock_out_lat=req.lat,
        clock_out_lng=req.lng,
        hours_worked=round(hours, 2),
    )
    return repo.get_or_404(record.id)


def _format_attendance_record(r: Attendance) -> dict:
    """Format an attendance record with employee name for frontend."""
    emp = None
    if r.employee_id:
        emp = r.employee
    return {
        "id": r.id,
        "employee_id": r.employee_id,
        "employee_name": emp.name if emp else "Unknown",
        "date": r.date,
        "clock_in": r.clock_in.isoformat() if r.clock_in else None,
        "clock_out": r.clock_out.isoformat() if r.clock_out else None,
        "hours_worked": r.hours_worked,
        "is_late": r.is_late,
    }


@router.get("/attendance/today")
def attendance_today(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Get today's attendance records with employee names."""
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    repo = AttendanceRepository(db)
    records = repo.get_today_attendance(today_str)
    return [_format_attendance_record(r) for r in records]


@router.get("/attendance/history")
def attendance_history(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Get attendance history with employee names."""
    repo = AttendanceRepository(db)
    records = repo.list(order_by="date", descending=True, limit=50)
    return [_format_attendance_record(r) for r in records]


@router.get("/attendance/stats")
def attendance_stats(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Get attendance statistics."""
    all_records = db.query(Attendance).all()
    total_records = len(all_records)
    if total_records == 0:
        return {"total_records": 0, "late_percentage": 0, "total_hours": 0, "average_hours_per_day": 0}

    total_hours = sum(r.hours_worked or 0 for r in all_records)
    late_count = sum(1 for r in all_records if r.is_late)
    late_pct = round(late_count / total_records * 100, 1)

    unique_dates = len(set(r.date for r in all_records))
    avg_hours = round(total_hours / unique_dates, 1) if unique_dates > 0 else 0

    return {
        "total_records": total_records,
        "late_percentage": late_pct,
        "total_hours": round(total_hours, 1),
        "average_hours_per_day": avg_hours,
    }


@router.get("/attendance", response_model=list[AttendanceResponse])
def list_attendance(
    date_str: Optional[str] = Query(None, alias="date"),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    repo = AttendanceRepository(db)
    if date_str:
        return repo.get_today_attendance(date_str)
    if employee_id:
        return repo.get_employee_history(employee_id)
    return repo.list(order_by="date", descending=True, limit=50)


# ─── LEAVE ───────────────────────────────────────────

@router.post("/leave/requests", response_model=LeaveResponse, status_code=201)
def create_leave_request(req: LeaveRequest, db: Session = Depends(get_db), _=Depends(get_current_user)):
    repo = LeaveRepository(db)
    from datetime import datetime as dt
    start = dt.strptime(req.start_date, "%Y-%m-%d")
    end = dt.strptime(req.end_date, "%Y-%m-%d")
    days = (end - start).days + 1
    return repo.create(
        employee_id=req.employee_id,
        leave_type=req.leave_type,
        start_date=req.start_date,
        end_date=req.end_date,
        days_requested=days,
        reason=req.reason,
    )


@router.get("/leave/requests", response_model=list[LeaveResponse])
def list_leave_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    repo = LeaveRepository(db)
    if status_filter:
        return repo.list(status=status_filter)
    if employee_id:
        return repo.get_by_employee(employee_id)
    return repo.list(order_by="created_at", descending=True)


@router.put("/leave/requests/{leave_id}/review", response_model=LeaveResponse)
def review_leave_request(
    leave_id: int,
    req: LeaveUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_manager_or_admin),
):
    repo = LeaveRepository(db)
    leave = repo.get_or_404(leave_id)
    if leave.status != "pending":
        raise ConflictException("Leave request already reviewed")

    now = datetime.utcnow()
    repo.update(
        leave_id,
        status=req.status,
        approved_by=current_user.id,
        approved_at=now if req.status == "approved" else None,
        rejection_reason=req.rejection_reason,
    )

    # Update leave balance if approved
    if req.status == "approved":
        lb_repo = LeaveBalanceRepository(db)
        balance = lb_repo.get_by(
            employee_id=leave.employee_id,
            leave_type=leave.leave_type,
            year=int(leave.start_date[:4]),
        )
        if balance:
            lb_repo.update(balance.id, used_days=balance.used_days + leave.days_requested)

    return repo.get_or_404(leave_id)


@router.get("/leave/balances", response_model=list[LeaveBalanceResponse])
def get_leave_balances(
    employee_id: Optional[int] = Query(None),
    year: int = Query(datetime.utcnow().year),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = LeaveBalanceRepository(db)
    # If no employee_id provided, resolve from auth token
    if not employee_id or employee_id <= 0:
        emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
        if not emp:
            return []  # No employee profile linked
        employee_id = emp.id
    balances = repo.get_employee_balance(employee_id, year)
    result = []
    for b in balances:
        result.append({
            "leave_type": b.leave_type,
            "total_days": b.total_days,
            "used_days": b.used_days,
            "remaining": b.total_days - b.used_days,
        })
    return result


# ─── SHIFTS ──────────────────────────────────────────

@router.post("/shift-templates", response_model=ShiftTemplateResponse, status_code=201)
def create_shift_template(
    req: ShiftTemplateCreate,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    repo = ShiftTemplateRepository(db)
    return repo.create_from_schema(req)


@router.get("/shift-templates", response_model=list[ShiftTemplateResponse])
def list_shift_templates(
    day_of_week: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    repo = ShiftTemplateRepository(db)
    if day_of_week is not None:
        return repo.get_by_day(day_of_week)
    return repo.list()


@router.post("/shifts/generate")
def generate_shifts(req: ShiftGenerateRequest, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Generate shifts from templates for a date range."""
    from datetime import datetime as dt, timedelta
    template_repo = ShiftTemplateRepository(db)
    shift_repo = ShiftRepository(db)

    start = dt.strptime(req.start_date, "%Y-%m-%d")
    end = dt.strptime(req.end_date, "%Y-%m-%d")
    generated = 0

    current = start
    while current <= end:
        day_of_week = current.weekday()
        templates = template_repo.get_by_day(day_of_week)

        for tpl in templates:
            date_str = current.strftime("%Y-%m-%d")
            existing = shift_repo.get_by(date=date_str, start_time=tpl.start_time, end_time=tpl.end_time)
            if not existing:
                shift_repo.create(
                    date=date_str,
                    start_time=tpl.start_time,
                    end_time=tpl.end_time,
                    role_needed=tpl.role_needed,
                    min_staff=tpl.min_staff,
                    preferred_skills=tpl.preferred_skills,
                )
                generated += 1
        current += timedelta(days=1)

    return {"message": f"Generated {generated} shifts", "count": generated}


@router.get("/shifts")
def list_shifts(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    repo = ShiftRepository(db)
    if start_date and end_date:
        return repo.get_by_date_range(start_date, end_date)
    return repo.list(order_by="date", descending=True)


@router.get("/shifts/calendar")
def shift_calendar(
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Get shifts with employee assignments for calendar view."""
    shift_repo = ShiftRepository(db)
    assignment_repo = ShiftAssignmentRepository(db)
    shifts = shift_repo.get_by_date_range(start_date, end_date)

    calendar = []
    for s in shifts:
        assignments = assignment_repo.get_by_shift(s.id)
        assigned_employees = []
        for a in assignments:
            emp = db.query(Employee).filter(Employee.id == a.employee_id).first()
            if emp:
                assigned_employees.append({"employee_id": emp.id, "name": emp.name})
        calendar.append({
            "shift_id": s.id,
            "date": s.date,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "role_needed": s.role_needed,
            "assigned_employees": assigned_employees,
            "min_staff": s.min_staff,
        })
    return calendar


@router.post("/shifts/{shift_id}/assign")
def assign_employee_to_shift(
    shift_id: int,
    employee_id: int = Query(...),
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    repo = ShiftAssignmentRepository(db)
    existing = repo.get_by(shift_id=shift_id, employee_id=employee_id)
    if existing:
        raise ConflictException("Employee already assigned to this shift")

    assignment = repo.create(shift_id=shift_id, employee_id=employee_id)
    return {"message": "Employee assigned", "assignment_id": assignment.id}
