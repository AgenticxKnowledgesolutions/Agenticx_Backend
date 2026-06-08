-- ============================================================
-- AgenticX FastAPI — Initial Schema Migration
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- Alembic version tracking
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- ============================================================
-- ENUM TYPES
-- ============================================================

DO $$ BEGIN
    CREATE TYPE userrole AS ENUM ('admin', 'trainer', 'student');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE reviewsource AS ENUM ('google', 'internal');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE activitytype AS ENUM ('webinar', 'bootcamp', 'workshop', 'seminar');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE coursemode AS ENUM ('online', 'offline', 'hybrid');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE coursedifficulty AS ENUM ('beginner', 'intermediate', 'advanced');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id           VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email        VARCHAR(255) NOT NULL UNIQUE,
    username     VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    role         userrole NOT NULL DEFAULT 'admin',
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_users_email    ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);

-- ============================================================
-- REVIEWS
-- ============================================================

CREATE TABLE IF NOT EXISTS reviews (
    id          VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name        VARCHAR(255) NOT NULL,
    rating      INTEGER NOT NULL,
    review      TEXT NOT NULL,
    role        VARCHAR(255),
    image_url   VARCHAR(500),
    source      reviewsource NOT NULL DEFAULT 'internal',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- ACTIVITIES
-- ============================================================

CREATE TABLE IF NOT EXISTS activities (
    id               VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    title            VARCHAR(255) NOT NULL,
    description      TEXT,
    image_url        VARCHAR(500),
    duration         VARCHAR(100) NOT NULL,
    price            NUMERIC(10, 2),
    is_free          BOOLEAN NOT NULL DEFAULT FALSE,
    activity_type    activitytype NOT NULL DEFAULT 'webinar',
    start_date       TIMESTAMPTZ,
    end_date         TIMESTAMPTZ,
    registration_url VARCHAR(500),
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- COURSES (parent)
-- ============================================================

CREATE TABLE IF NOT EXISTS courses (
    id              VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    title           VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) NOT NULL UNIQUE,
    description     TEXT NOT NULL,
    badge           VARCHAR(100),
    price           NUMERIC(10, 2) NOT NULL DEFAULT 0,
    duration        VARCHAR(100),
    format          VARCHAR(100),
    projects        VARCHAR(100),
    career_support  VARCHAR(100),
    cover_image_url VARCHAR(500),
    next_cohort     VARCHAR(100),
    mode            coursemode NOT NULL DEFAULT 'hybrid',
    difficulty      coursedifficulty NOT NULL DEFAULT 'intermediate',
    is_ai_optimized BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_courses_slug ON courses(slug);

-- ============================================================
-- TECH STACKS (child of courses)
-- ============================================================

CREATE TABLE IF NOT EXISTS tech_stacks (
    id        VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    course_id VARCHAR NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    name      VARCHAR(100) NOT NULL,
    icon_url  VARCHAR(500),
    "order"   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_tech_stacks_course_id ON tech_stacks(course_id);

-- ============================================================
-- CURRICULUM MONTHS (child of courses)
-- ============================================================

CREATE TABLE IF NOT EXISTS curriculum_months (
    id            VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    course_id     VARCHAR NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    tab_title     VARCHAR(255) NOT NULL,
    section_title VARCHAR(255) NOT NULL,
    "order"       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_curriculum_months_course_id ON curriculum_months(course_id);

-- ============================================================
-- CURRICULUM MODULES (child of curriculum_months)
-- ============================================================

CREATE TABLE IF NOT EXISTS curriculum_modules (
    id          VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    month_id    VARCHAR NOT NULL REFERENCES curriculum_months(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    "order"     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_curriculum_modules_month_id ON curriculum_modules(month_id);

-- ============================================================
-- LEADS
-- ============================================================

CREATE TABLE IF NOT EXISTS leads (
    id                VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name              VARCHAR(255) NOT NULL,
    email             VARCHAR(255) NOT NULL,
    phone             VARCHAR(20),
    message           TEXT,
    interested_course VARCHAR(255),
    source_page       VARCHAR(255),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_leads_email ON leads(email);

-- ============================================================
-- Mark migration as applied
-- ============================================================

INSERT INTO alembic_version (version_num) VALUES ('001_initial_schema')
ON CONFLICT DO NOTHING;

-- ============================================================
-- SEED: Initial admin user (agenticx / agenticx@gmail.com)
-- Password hash = bcrypt of "1234"
-- ============================================================

INSERT INTO users (id, email, username, hashed_password, role, is_active)
VALUES (
    gen_random_uuid()::text,
    'agenticx@gmail.com',
    'agenticx',
    '$2b$12$ieXsr3OHOg59CZbDT8sf5eodciq2/E2DW4ZC7j3L0rI102Pi4TPWq',
    'admin',
    TRUE
)
ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- COMPANY SETTINGS
-- ============================================================

CREATE TABLE IF NOT EXISTS company_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    company_name VARCHAR(255) NOT NULL,
    company_tagline VARCHAR(255),
    company_description TEXT,
    primary_phone VARCHAR(50),
    secondary_phone VARCHAR(50),
    primary_email VARCHAR(255),
    secondary_email VARCHAR(255),
    website_url VARCHAR(255),
    address_line_1 VARCHAR(255),
    address_line_2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    google_maps_url TEXT,
    placement_assistance_percentage INTEGER DEFAULT 100,
    college_partners_count INTEGER DEFAULT 20,
    graduates_trained_count INTEGER DEFAULT 250,
    students_trained_count INTEGER DEFAULT 100,
    core_services_count INTEGER DEFAULT 5,
    linkedin_url VARCHAR(255),
    instagram_url VARCHAR(255),
    facebook_url VARCHAR(255),
    youtube_url VARCHAR(255),
    whatsapp_number VARCHAR(50),
    hero_title VARCHAR(255),
    hero_description TEXT,
    hero_primary_cta_text VARCHAR(100),
    hero_secondary_cta_text VARCHAR(100),
    meta_title VARCHAR(255),
    meta_description TEXT,
    meta_keywords VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT company_settings_singleton CHECK (id = 1)
);

INSERT INTO company_settings (
    id,
    company_name,
    company_tagline,
    company_description,
    primary_phone,
    secondary_phone,
    primary_email,
    secondary_email,
    website_url,
    address_line_1,
    address_line_2,
    city,
    state,
    country,
    postal_code,
    google_maps_url,
    placement_assistance_percentage,
    college_partners_count,
    graduates_trained_count,
    students_trained_count,
    core_services_count,
    linkedin_url,
    instagram_url,
    facebook_url,
    youtube_url,
    whatsapp_number,
    hero_title,
    hero_description,
    hero_primary_cta_text,
    hero_secondary_cta_text,
    meta_title,
    meta_description,
    meta_keywords
) VALUES (
    1,
    'AgenticX Knowledge Solutions',
    'Bridging Education and Industry',
    'Transforming fresh graduates into industry-ready professionals through effective career coaching and comprehensive graduate training.',
    '+91 9496552094',
    '+91 9496852094',
    'anju.muraleedharan@agenticx.co.in',
    'agenticxknowledgesolutions@gmail.com',
    'https://agenticx.co.in',
    '3rd Floor, Raj Plaza',
    'Town Limit',
    'Kollam',
    'Kerala',
    'India',
    '691001',
    'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d246.36208069536437!2d76.61254242851638!3d8.898800762722871!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x3b05fd109874a36b%3A0x26d35fe01fea3245!2sAgenticX%20Knowledge%20Solutions%20LLP!5e0!3m2!1sen!2sin!4v1779083931591!5m2!1sen!2sin',
    100,
    20,
    250,
    100,
    5,
    'https://linkedin.com/company/agenticx',
    'https://instagram.com/agenticx',
    'https://facebook.com/agenticx',
    'https://youtube.com/agenticx',
    '+919496552094',
    'Decode Data. Develop Systems. Drive Business.',
    'Transforming fresh graduates into industry-ready professionals through effective career coaching and comprehensive graduate training.',
    'Explore Courses',
    'Book Free Demo',
    'AgenticX | AI-Optimized Graduate Training & Placements',
    'Bridging the gap between education and industry through HTD (Hire-Train-Deploy) models and custom curriculum.',
    'AI, Machine Learning, Data Science, MERN stack, Python, HTD, Placements'
) ON CONFLICT (id) DO NOTHING;

-- Phase 2 Dashboard Operations additions
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS next_followup_date TIMESTAMP WITH TIME ZONE;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_notes TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'Website';

