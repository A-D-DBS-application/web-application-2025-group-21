-- Enum types worden direct in kolommen gedefinieerd in MySQL
-- (MySQL ondersteunt geen CREATE TYPE)

-- Users table
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(80) NOT NULL UNIQUE,
  role ENUM('consultant', 'company', 'admin') NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Consultant profiles
CREATE TABLE consultant_profiles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  display_name_masked VARCHAR(120) NOT NULL,
  headline VARCHAR(160),
  skills_text TEXT,
  location_city VARCHAR(120),
  country VARCHAR(120),
  availability VARCHAR(120),
  rate_value DECIMAL(10,2),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_consultant_profiles_user FOREIGN KEY (user_id)
    REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_consultant_profiles_user_id ON consultant_profiles(user_id);

-- Companies
CREATE TABLE companies (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  company_name_masked VARCHAR(160) NOT NULL,
  industry VARCHAR(160),
  location_city VARCHAR(120),
  country VARCHAR(120),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_companies_user FOREIGN KEY (user_id)
    REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_companies_user_id ON companies(user_id);

-- Job posts
CREATE TABLE job_posts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  company_id INT NOT NULL,
  title VARCHAR(200) NOT NULL,
  description TEXT,
  skills_required_text TEXT,
  location_city VARCHAR(120),
  country VARCHAR(120),
  contract_type VARCHAR(80),
  anonymize BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_job_posts_company FOREIGN KEY (company_id)
    REFERENCES companies(id) ON DELETE CASCADE
);
CREATE INDEX idx_job_posts_company_id ON job_posts(company_id);

-- Unlocks
CREATE TABLE unlocks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  target_type ENUM('consultant', 'job') NOT NULL,
  target_id INT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_unlocks_user FOREIGN KEY (user_id)
    REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_unlocks_user_id ON unlocks(user_id);

-- Skills (toegevoegd omdat het in relaties wordt gebruikt)
CREATE TABLE skills (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- profile_skills (many-to-many tussen consultant_profiles en skills)
CREATE TABLE profile_skills (
  profile_id INT NOT NULL,
  skill_id INT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (profile_id, skill_id),
  CONSTRAINT fk_profile_skills_profile FOREIGN KEY (profile_id)
    REFERENCES consultant_profiles(id) ON DELETE CASCADE,
  CONSTRAINT fk_profile_skills_skill FOREIGN KEY (skill_id)
    REFERENCES skills(id) ON DELETE CASCADE
);
CREATE INDEX idx_profile_skills_profile_id ON profile_skills(profile_id);
CREATE INDEX idx_profile_skills_skill_id ON profile_skills(skill_id);

-- job_skills (many-to-many tussen job_posts en skills)
CREATE TABLE job_skills (
  job_id INT NOT NULL,
  skill_id INT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (job_id, skill_id),
  CONSTRAINT fk_job_skills_job FOREIGN KEY (job_id)
    REFERENCES job_posts(id) ON DELETE CASCADE,
  CONSTRAINT fk_job_skills_skill FOREIGN KEY (skill_id)
    REFERENCES skills(id) ON DELETE CASCADE
);
CREATE INDEX idx_job_skills_job_id ON job_skills(job_id);
CREATE INDEX idx_job_skills_skill_id ON job_skills(skill_id);
