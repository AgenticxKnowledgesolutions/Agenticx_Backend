import time
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

from app.models.lead import Lead
from app.models.course import Course
from app.models.review import Review
from app.models.activity import Activity
from app.models.candidate_application import CandidateApplication

logger = logging.getLogger("app.dashboard_service")

async def get_dashboard_summary(db: AsyncSession) -> Dict[str, Any]:
    overall_start = time.perf_counter()
    logger.info("Starting dashboard summary aggregation...")

    ist_tz = ZoneInfo("Asia/Kolkata")
    now = datetime.now(ist_tz)
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=ist_tz)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=ist_tz)
    start_of_month = datetime(now.year, now.month, 1, tzinfo=ist_tz)

    # 1. Totals / KPI Cards Section
    kpi_start = time.perf_counter()
    
    total_leads = (await db.execute(select(func.count(Lead.id)).where(Lead.is_deleted == False))).scalar() or 0
    total_courses = (await db.execute(select(func.count(Course.id)).where(Course.is_deleted == False))).scalar() or 0
    total_reviews = (await db.execute(select(func.count(Review.id)).where(Review.is_deleted == False))).scalar() or 0
    total_activities = (await db.execute(select(func.count(Activity.id)).where(Activity.is_deleted == False))).scalar() or 0

    new_leads_this_month = (
        await db.execute(select(func.count(Lead.id)).where(Lead.created_at >= start_of_month, Lead.is_deleted == False))
    ).scalar() or 0

    converted_leads = (
        await db.execute(
            select(func.count(Lead.id)).where(Lead.status.ilike("converted"), Lead.is_deleted == False)
        )
    ).scalar() or 0
    enrolled_leads = (
        await db.execute(
            select(func.count(Lead.id)).where(Lead.status.ilike("enrolled"), Lead.is_deleted == False)
        )
    ).scalar() or 0
    
    total_converted = converted_leads + enrolled_leads
    conversion_rate = int((total_converted / total_leads) * 100) if total_leads > 0 else 0

    # Follow-ups counts (optimized - single round trip if we want, but these count queries are fast with index)
    overdue_query = select(func.count(Lead.id)).where(
        Lead.next_followup_date < today_start,
        Lead.status.notin_(["Converted", "Enrolled", "converted", "enrolled"]),
        Lead.is_deleted == False
    )
    overdue_count = (await db.execute(overdue_query)).scalar() or 0

    today_followups_query = select(func.count(Lead.id)).where(
        Lead.next_followup_date >= today_start,
        Lead.next_followup_date <= today_end,
        Lead.status.notin_(["Converted", "Enrolled", "converted", "enrolled"]),
        Lead.is_deleted == False
    )
    today_followups_count = (await db.execute(today_followups_query)).scalar() or 0

    pending_followups_query = select(func.count(Lead.id)).where(
        Lead.next_followup_date > today_end,
        Lead.status.notin_(["Converted", "Enrolled", "converted", "enrolled"]),
        Lead.is_deleted == False
    )
    pending_followups_count = (await db.execute(pending_followups_query)).scalar() or 0

    # Duplicate lead counts (Optimized using GROUP BY instead of fetching full table scans)
    dup_query = select(Lead.email).where(Lead.is_deleted == False, Lead.email != None, Lead.email != "").group_by(Lead.email).having(func.count(Lead.id) > 1)
    dup_by_email_res = await db.execute(dup_query)
    dup_by_email_count = len(dup_by_email_res.all())
    
    dup_phone_query = select(Lead.phone).where(Lead.is_deleted == False, Lead.phone != None, Lead.phone != "").group_by(Lead.phone).having(func.count(Lead.id) > 1)
    dup_by_phone_res = await db.execute(dup_phone_query)
    dup_by_phone_count = len(dup_by_phone_res.all())
    
    potential_duplicates_count = dup_by_email_count + dup_by_phone_count

    totals = {
        "total_leads": total_leads,
        "new_leads_this_month": new_leads_this_month,
        "conversion_rate": conversion_rate,
        "total_courses": total_courses,
        "total_activities": total_activities,
        "total_reviews": total_reviews,
        "leads_requiring_followup": {
            "pending": pending_followups_count,
            "overdue": overdue_count,
            "today": today_followups_count
        },
        "potential_duplicates_count": potential_duplicates_count
    }
    kpi_end = time.perf_counter()
    logger.info(f"PERF: KPI cards section took {kpi_end - kpi_start:.4f} seconds")

    # 2. Lead Funnel (Cumulative)
    funnel_start = time.perf_counter()
    contacted_statuses = ["contacted", "demo booked", "enrolled", "converted", "ignored"]
    demo_statuses = ["demo booked", "enrolled", "converted"]
    enrolled_statuses = ["enrolled", "converted"]

    contacted_count = (
        await db.execute(
            select(func.count(Lead.id)).where(Lead.status.in_(contacted_statuses), Lead.is_deleted == False)
        )
    ).scalar() or 0

    demo_count = (
        await db.execute(
            select(func.count(Lead.id)).where(Lead.status.in_(demo_statuses), Lead.is_deleted == False)
        )
    ).scalar() or 0

    enrolled_count = (
        await db.execute(
            select(func.count(Lead.id)).where(Lead.status.in_(enrolled_statuses), Lead.is_deleted == False)
        )
    ).scalar() or 0

    lead_funnel = {
        "total_leads": total_leads,
        "contacted": contacted_count,
        "demo_booked": demo_count,
        "enrolled": enrolled_count
    }
    funnel_end = time.perf_counter()
    logger.info(f"PERF: Lead funnel section took {funnel_end - funnel_start:.4f} seconds")

    # 3. Course Performance (Aggregated in DB to prevent N+1 and massive memory loading)
    course_start = time.perf_counter()
    course_query = select(
        Lead.interested_course,
        Lead.status,
        func.count(Lead.id)
    ).where(Lead.is_deleted == False).group_by(Lead.interested_course, Lead.status)
    
    course_res = await db.execute(course_query)
    course_rows = course_res.all()
    
    course_stats = {}
    for course, status, count in course_rows:
        course_name = course or "General Inquiry"
        if course_name not in course_stats:
            course_stats[course_name] = {"lead_count": 0, "enrollment_count": 0}
        course_stats[course_name]["lead_count"] += count
        if status and status.lower() in ["enrolled", "converted"]:
            course_stats[course_name]["enrollment_count"] += count
            
    course_performance = []
    for c_name, stats in course_stats.items():
        lc = stats["lead_count"]
        ec = stats["enrollment_count"]
        cr = int((ec / lc) * 100) if lc > 0 else 0
        course_performance.append({
            "course_name": c_name,
            "lead_count": lc,
            "enrollment_count": ec,
            "conversion_rate": cr
        })
    course_performance.sort(key=lambda x: x["lead_count"], reverse=True)
    course_end = time.perf_counter()
    logger.info(f"PERF: Course performance took {course_end - course_start:.4f} seconds")

    # 4. Lead Sources
    source_start = time.perf_counter()
    source_result = await db.execute(
        select(Lead.source, func.count(Lead.id)).where(Lead.is_deleted == False).group_by(Lead.source)
    )
    lead_sources = [
        {"source": row[0] or "Website", "count": row[1]}
        for row in source_result.all()
    ]
    lead_sources.sort(key=lambda x: x["count"], reverse=True)

    # Priority Breakdown
    priority_result = await db.execute(
        select(Lead.priority, func.count(Lead.id)).where(Lead.is_deleted == False).group_by(Lead.priority)
    )
    priority_breakdown = {row[0] or "Cold": row[1] for row in priority_result.all()}
    for p in ["Hot", "Warm", "Cold"]:
        if p not in priority_breakdown:
            priority_breakdown[p] = 0
    source_end = time.perf_counter()
    logger.info(f"PERF: Lead sources and priority breakdown took {source_end - source_start:.4f} seconds")

    # 5. Recent Leads (latest 10)
    recent_start = time.perf_counter()
    leads_result = await db.execute(
        select(Lead).where(Lead.is_deleted == False).order_by(Lead.created_at.desc()).limit(10)
    )
    recent_leads = []
    for lead in leads_result.scalars().all():
        recent_leads.append({
            "id": lead.id,
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "interested_course": lead.interested_course,
            "status": lead.status,
            "priority": lead.priority,
            "assigned_to": lead.assigned_to,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
            "next_followup_date": lead.next_followup_date.isoformat() if lead.next_followup_date else None,
            "followup_notes": lead.followup_notes,
            "source": lead.source or "Website"
        })
    recent_end = time.perf_counter()
    logger.info(f"PERF: Recent leads query took {recent_end - recent_start:.4f} seconds")

    # 6. Recent Enrollments (latest 10 enrolled/converted)
    enr_start = time.perf_counter()
    enrollments_result = await db.execute(
        select(Lead)
        .where(Lead.status.in_(["Enrolled", "Converted", "enrolled", "converted"]), Lead.is_deleted == False)
        .order_by(Lead.created_at.desc())
        .limit(10)
    )
    recent_enrollments = []
    for enr in enrollments_result.scalars().all():
        recent_enrollments.append({
            "id": enr.id,
            "name": enr.name,
            "course": enr.interested_course or "General Inquiry",
            "enrollment_date": enr.created_at.isoformat() if enr.created_at else None
        })
    enr_end = time.perf_counter()
    logger.info(f"PERF: Recent enrollments query took {enr_end - enr_start:.4f} seconds")

    # 7. Upcoming Activities (soonest 5, excluding deleted)
    act_start = time.perf_counter()
    activities_result = await db.execute(
        select(Activity)
        .where(Activity.is_active == True, Activity.start_date >= today_start, Activity.is_deleted == False)
        .order_by(Activity.start_date.asc())
        .limit(5)
    )
    upcoming_activities = []
    for act in activities_result.scalars().all():
        upcoming_activities.append({
            "id": act.id,
            "title": act.title,
            "date": act.start_date.isoformat() if act.start_date else None,
            "seats": "50 Seats",
            "status": "Upcoming" if act.start_date > now else "Active"
        })
    act_end = time.perf_counter()
    logger.info(f"PERF: Upcoming activities query took {act_end - act_start:.4f} seconds")

    # 8. Today's Followups list
    followup_start = time.perf_counter()
    today_followups_list = await db.execute(
        select(Lead)
        .where(
            Lead.next_followup_date >= today_start,
            Lead.next_followup_date <= today_end,
            Lead.status.notin_(["Converted", "Enrolled", "converted", "enrolled"]),
            Lead.is_deleted == False
        )
        .order_by(Lead.next_followup_date.asc())
    )
    followups = []
    for f in today_followups_list.scalars().all():
        due_time = f.next_followup_date.isoformat() if f.next_followup_date else ""
        followups.append({
            "id": f.id,
            "name": f.name,
            "course": f.interested_course or "General Inquiry",
            "phone": f.phone or "N/A",
            "due_time": due_time,
            "priority": f.priority
        })
    followup_end = time.perf_counter()
    logger.info(f"PERF: Today follow-ups list took {followup_end - followup_start:.4f} seconds")

    # 9. Candidate Application Metrics (CAF statistics)
    candidate_start = time.perf_counter()
    total_candidates = (await db.execute(select(func.count(CandidateApplication.id)))).scalar() or 0
    
    # Candidates by status
    candidate_status_res = await db.execute(
        select(CandidateApplication.application_status, func.count(CandidateApplication.id))
        .group_by(CandidateApplication.application_status)
    )
    candidates_by_status = {row[0]: row[1] for row in candidate_status_res.all()}
    
    # Candidates by document status
    candidate_doc_res = await db.execute(
        select(CandidateApplication.document_status, func.count(CandidateApplication.id))
        .group_by(CandidateApplication.document_status)
    )
    candidates_by_doc_status = {row[0]: row[1] for row in candidate_doc_res.all()}
    
    candidate_metrics = {
        "total_candidates": total_candidates,
        "by_status": candidates_by_status,
        "by_document_status": candidates_by_doc_status
    }
    # Add to totals dict
    totals["total_candidates"] = total_candidates
    totals["candidate_metrics"] = candidate_metrics
    candidate_end = time.perf_counter()
    logger.info(f"PERF: Candidate metrics took {candidate_end - candidate_start:.4f} seconds")

    # 10. Operational Alerts
    alert_start = time.perf_counter()
    alerts = []
    # leads pending > 7 days
    seven_days_ago = now - timedelta(days=7)
    pending_7d_count = (
        await db.execute(
            select(func.count(Lead.id)).where(
                Lead.status.ilike("pending"),
                Lead.created_at <= seven_days_ago,
                Lead.is_deleted == False
            )
        )
    ).scalar() or 0
    if pending_7d_count > 0:
        alerts.append(f"{pending_7d_count} leads pending > 7 days")

    # activities starting this week (excluding deleted)
    end_of_week = today_start + timedelta(days=7)
    activities_week_count = (
        await db.execute(
            select(func.count(Activity.id)).where(
                Activity.is_active == True,
                Activity.start_date >= today_start,
                Activity.start_date <= end_of_week,
                Activity.is_deleted == False
            )
        )
    ).scalar() or 0
    if activities_week_count > 0:
        alerts.append(f"{activities_week_count} activities starting this week")

    if overdue_count > 0:
        alerts.append(f"{overdue_count} follow-ups overdue")

    if potential_duplicates_count > 0:
        alerts.append(f"{potential_duplicates_count} potential duplicates found")

    if not alerts:
        alerts.append("No critical operational alerts today.")
    alert_end = time.perf_counter()
    logger.info(f"PERF: Operational alerts check took {alert_end - alert_start:.4f} seconds")

    # 11. Chart monthly leads (Optimized GROUP BY on DB)
    chart_start = time.perf_counter()
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    six_months_ago = now - timedelta(days=180)
    
    monthly_query = select(
        func.extract('month', Lead.created_at).label('month_num'),
        func.count(Lead.id).label('count')
    ).where(
        Lead.created_at >= six_months_ago,
        Lead.is_deleted == False
    ).group_by(func.extract('month', Lead.created_at))
    
    monthly_res = await db.execute(monthly_query)
    monthly_counts = {int(row[0]): row[1] for row in monthly_res.all() if row[0] is not None}
    
    trend_dict = {}
    ordered_months = []
    for i in range(5, -1, -1):
        m_date = now - timedelta(days=i * 30)
        m_label = f"{month_names[m_date.month - 1]}"
        trend_dict[m_label] = monthly_counts.get(m_date.month, 0)
        ordered_months.append(m_label)
        
    monthly_leads = [{"month": label, "count": trend_dict[label]} for label in ordered_months]
    chart_end = time.perf_counter()
    logger.info(f"PERF: Monthly chart data query took {chart_end - chart_start:.4f} seconds")

    overall_end = time.perf_counter()
    overall_time = overall_end - overall_start
    logger.info(f"PERF: OVERALL dashboard summary aggregation took {overall_time:.4f} seconds")
    print(f"\n>>> [DASHBOARD PERF LOG] Total time: {overall_time:.4f}s | KPIs: {kpi_end-kpi_start:.4f}s | Funnel: {funnel_end-funnel_start:.4f}s | CoursePerf: {course_end-course_start:.4f}s | Sources: {source_end-source_start:.4f}s | Recent: {recent_end-recent_start:.4f}s | Enrollments: {enr_end-enr_start:.4f}s | Activities: {act_end-act_start:.4f}s | Followups: {followup_end-followup_start:.4f}s | CandidateMetrics: {candidate_end-candidate_start:.4f}s | Alerts: {alert_end-alert_start:.4f}s | Chart: {chart_end-chart_start:.4f}s\n", flush=True)

    return {
        "totals": totals,
        "lead_funnel": lead_funnel,
        "course_performance": course_performance,
        "lead_sources": lead_sources,
        "priority_breakdown": priority_breakdown,
        "recent_leads": recent_leads,
        "recent_enrollments": recent_enrollments,
        "upcoming_activities": upcoming_activities,
        "followups": followups,
        "alerts": alerts,
        "monthly_leads": monthly_leads
    }
