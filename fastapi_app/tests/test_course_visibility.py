import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseUpdate
from app.services.course_service import create_course, update_course

@pytest.mark.asyncio
async def test_course_create_default_visibility():
    mock_db = AsyncMock()
    
    course_in = CourseCreate(
        title="Test Python Full Stack",
        slug="test-python-full-stack",
        description="Comprehensive Python course",
        price=Decimal("20000.00"),
        show_amount_on_website=True
    )
    
    mock_course = Course(
        id="course-1",
        title=course_in.title,
        slug=course_in.slug,
        description=course_in.description,
        price=course_in.price,
        is_ai_optimized=False,
        is_deleted=False,
        show_amount_on_website=course_in.show_amount_on_website,
        stack=[],
        curriculum=[]
    )
    
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = mock_course
    mock_db.execute.return_value = mock_result
    
    response = await create_course(mock_db, course_in)
    assert response.show_amount_on_website is True
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_course_update_visibility():
    mock_db = AsyncMock()
    
    course = Course(
        id="course-1",
        title="Test Course",
        slug="test-course",
        description="Desc",
        price=Decimal("10000.00"),
        is_ai_optimized=False,
        is_deleted=False,
        show_amount_on_website=True,
        stack=[],
        curriculum=[]
    )
    
    course_up = CourseUpdate(
        show_amount_on_website=False
    )
    
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = course
    mock_db.execute.return_value = mock_result
    
    response = await update_course(mock_db, course, course_up)
    assert response.show_amount_on_website is False
    assert course.show_amount_on_website is False
    mock_db.commit.assert_called_once()
