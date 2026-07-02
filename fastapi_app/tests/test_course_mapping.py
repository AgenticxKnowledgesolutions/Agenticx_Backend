import pytest
from app.services.certificate_service import get_course_details

def test_standard_course_mappings():
    # Test Data Analytics & BI
    details = get_course_details("Data Analytics & BI")
    assert details["domain"] == "Data Analytics & BI"
    assert "Basics of Financial Accounting" in details["topics"]

    # Test Cyber Security
    details = get_course_details("ethical hacking")
    assert details["domain"] == "Cyber Security"
    assert "Vulnerability Assessment" in details["topics"]

    # Test Data Science
    details = get_course_details("Data Science")
    assert details["domain"] == "Data Science"
    assert "Statistical Methods" in details["topics"]

    # Test AI/ML
    details = get_course_details("Deep Learning")
    assert details["domain"] == "Artificial Intelligence & Machine Learning"
    assert "Machine Learning Algorithms" in details["topics"]

    # Test Accounting
    details = get_course_details("Tally Prime")
    assert details["domain"] == "Accounting & Financial Management"
    assert "Double-Entry Bookkeeping" in details["topics"]

    # Test Python Full Stack
    details = get_course_details("python full stack")
    assert details["domain"] == "Python Full Stack Web Development"
    assert "Django/Flask Frameworks" in details["topics"]


def test_case_insensitivity_and_whitespace():
    details = get_course_details("   cYbErSeCuRiTy   ")
    assert details["domain"] == "Cyber Security"


def test_longest_alias_precedence():
    # "Data Science with AI/ML" contains "Data Science", "AI/ML", and the full "Data Science with AI/ML".
    # It must match "Data Science with AI/ML" because of length/precedence.
    details = get_course_details("Data Science with AI/ML")
    assert details["domain"] == "Data Science with AI/ML"
    assert "Advanced Data Analysis" in details["topics"]


def test_dynamic_webinar_parsing():
    # Webinar with 'on'
    details1 = get_course_details("Webinar on Blockchain Technology")
    assert details1["domain"] == "Webinar: Blockchain Technology"
    assert "Blockchain Technology" in details1["topics"]

    # Webinar with ':'
    details2 = get_course_details("Webinar: Cloud Architecture")
    assert details2["domain"] == "Webinar: Cloud Architecture"

    # Webinar with '-'
    details3 = get_course_details("Webinar - Generative AI")
    assert details3["domain"] == "Webinar: Generative AI"

    # Raw Webinar
    details4 = get_course_details("Webinar Quantum Computing")
    assert details4["domain"] == "Webinar: Quantum Computing"


def test_dynamic_workshop_parsing():
    # Workshop with 'on'
    details1 = get_course_details("Workshop on FastAPI and Docker")
    assert details1["domain"] == "Workshop: FastAPI and Docker"
    assert "FastAPI and Docker" in details1["topics"]

    # Bootcamp
    details2 = get_course_details("Bootcamp: Data Wrangling")
    assert details2["domain"] == "Workshop: Data Wrangling"


def test_dynamic_internship_parsing():
    # Internship in
    details1 = get_course_details("Internship in Flutter Development")
    assert details1["domain"] == "Internship: Flutter Development"
    assert "Flutter Development" in details1["topics"]


def test_validation_exceptions():
    # Empty/None
    with pytest.raises(ValueError) as exc:
        get_course_details("")
    assert "cannot be empty" in str(exc.value)

    # Unrecognized course fallback
    details = get_course_details("Unrecognized Special Course 101")
    assert details["domain"] == "Unrecognized Special Course 101"
    assert "Professional Development, Advanced Concepts" in details["topics"]
