from enum import Enum

class ProgramType(str, Enum):
    COURSE = "Course"
    INTERNSHIP = "Internship"
    CRASH_COURSE = "Crash Course"
    WEBINAR = "Webinar"
    WORKSHOP = "Workshop"
    FACULTY_DEVELOPMENT_PROGRAMME = "Faculty Development Programme"

class PerformanceType(str, Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    AVERAGE = "Average"
    SATISFACTORY = "Satisfactory"
