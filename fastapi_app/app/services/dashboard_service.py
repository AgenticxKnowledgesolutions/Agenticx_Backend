from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

from app.models.lead import Lead
from app.models.course import Course
from app.models.review import Review
from app.models.activity import Activity


async def get_dashboard_summary(db: AsyncSession) -> Dict[str, Any]:
    ist_tz = ZoneInfo("Asia/Kolkata")
    now = datetime.now(ist_tz)
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=ist_tz)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=ist_tz)
    start_of_month = datetime(now.year, now.month, 1, tzinfo=ist_tz)

    # 1. Totals (excluding soft deleted leads, courses, reviews, activities)
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

    # Follow-ups counts
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

    # Duplicate lead groups warning alerts
    dup_query = select(Lead.email, Lead.interested_course).where(Lead.is_deleted == False).group_by(Lead.email, Lead.interested_course).having(func.count(Lead.id) > 1)
    dup_by_email = (await db.execute(dup_query)).all()
    
    dup_phone_query = select(Lead.phone, Lead.interested_course).where(Lead.is_deleted == False, Lead.phone != None).group_by(Lead.phone, Lead.interested_course).having(func.count(Lead.id) > 1)
    dup_by_phone = (await db.execute(dup_phone_query)).all()
    
    potential_duplicates_count = len(dup_by_email) + len(dup_by_phone)

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

    # 2. Lead Funnel (Cumulative)
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

    # 3. Course Performance
    leads_data_result = await db.execute(select(Lead.interested_course, Lead.status).where(Lead.is_deleted == False))
    leads_rows = leads_data_result.all()
    
    course_stats = {}
    for course, status in leads_rows:
        course_name = course or "General Inquiry"
        if course_name not in course_stats:
            course_stats[course_name] = {"lead_count": 0, "enrollment_count": 0}
        course_stats[course_name]["lead_count"] += 1
        if status and status.lower() in ["enrolled", "converted"]:
            course_stats[course_name]["enrollment_count"] += 1
            
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

    # 4. Lead Sources
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

    # 5. Recent Leads (latest 10)
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

    # 6. Recent Enrollments (latest 10 enrolled/converted)
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

    # 7. Upcoming Activities (soonest 5, excluding deleted)
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

    # 8. Today's Followups list
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

    # 9. Operational Alerts
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

    # Chart monthly leads
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    six_months_ago = now - timedelta(days=180)
    dates_result = await db.execute(
        select(Lead.created_at).where(Lead.created_at >= six_months_ago, Lead.is_deleted == False)
    )
    dates = [row[0] for row in dates_result.all()]
    
    trend_dict = {}
    ordered_months = []
    for i in range(5, -1, -1):
        m_date = now - timedelta(days=i * 30)
        m_label = f"{month_names[m_date.month - 1]}"
        trend_dict[m_label] = 0
        ordered_months.append(m_label)
        
    for dt in dates:
        if dt:
            dt_label = month_names[dt.month - 1]
            if dt_label in trend_dict:
                trend_dict[dt_label] += 1
    monthly_leads = [{"month": label, "count": trend_dict[label]} for label in ordered_months]

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
