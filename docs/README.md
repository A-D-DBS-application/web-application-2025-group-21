# IConsult MVP
IConsult is a smart matchmaking platform designed to connect freelance consultants with companies. Consultants can create a profile, upload their CV, list their skills, and browse relevant job posts. The application utilizes an intelligent matching algorithm, based on skills, search relevance, recency, and popularity, to ensure the best fit. Conversely, companies can use the same system to find the ideal consultant. To ensure privacy and quality connections, contact information remains hidden until a user chooses to unlock a profile, allowing collaboration to begin.

## UI prototype link
https://www.figma.com/make/xumkoQNSaaOEKy52ykyEZP/User-Account-Management?node-id=0-1&t=4C3WZtTAkpU5eSxI-1 

## Kanban board link
https://miro.com/app/board/uXjVJz_l5cU=/?share_link_id=471385065574

## Feedback sessions
### Meeting 1 
https://ugentbe-my.sharepoint.com/personal/lennerdc_declerck_ugent_be/_layouts/15/stream.aspx?id=%2Fpersonal%2Flennerdc%5Fdeclerck%5Fugent%5Fbe%2FDocuments%2FOpnamen%2FIConsult%2D20251113%5F165941%2DMeeting%20Recording%2Emp4&referrer=StreamWebApp%2EWeb&referrerScenario=AddressBarCopied%2Eview%2Ea3aa3ba2%2D55fc%2D49a8%2D9acc%2D95e076f93d63
### Meeting 2
https://ugentbe-my.sharepoint.com/personal/lennerdc_declerck_ugent_be/_layouts/15/stream.aspx?id=%2Fpersonal%2Flennerdc%5Fdeclerck%5Fugent%5Fbe%2FDocuments%2FOpnamen%2FIConsult%2D20251204%5F181647%2DMeeting%20Recording%2Emp4&referrer=StreamWebApp%2EWeb&referrerScenario=AddressBarCopied%2Eview%2E82a7315c%2Dd9f9%2D43dc%2Dba51%2D3ff034ed658a

## Supabase
https://supabase.com/dashboard/project/yezkgrihchdjhiypfykc

## ERD model
https://dbdiagram.io/d/693aebc1e877c630747c59ac

## Database backup 
Due to network restrictions when connecting to Supabase with pg_dump,a direct SQL dump was not possible. The database backup is therefore provided as CSV exports per table.
Location:/database_backup/
Each CSV file represents the full contents of a database table and can be re-imported into PostgreSQL or Supabase.

## Demo
c:\Users\birth\OneDrive\Documenten\3e jaar\SEM1\Algoritmen en datastructuren\Demo project.mp4

# Installation & Running the App (Local)

### Prerequisites
- Python 3.x  
- pip  
- PostgreSQL or Supabase Postgres  
- .env file with:
  DATABASE_URL
  SUPABASE_URL
  SUPABASE_KEY
  SUPABASE_BUCKET_NAME
  MAPBOX_TOKEN

---

## Installation Steps (All in One)

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd <your-repo-folder>

# 2. Create & activate virtual environment
python -m venv venv
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file (manually in the root folder)--> ask our group members the correct passwords and url's
# Content example:
# DATABASE_URL=your_database_url
# SUPABASE_URL=your_supabase_url
# SUPABASE_KEY=your_supabase_key
# SUPABASE_BUCKET_NAME=iconsult-assets
# MAPBOX_TOKEN=your_mapbox_token

# 5. Initialize the database
python create_tables.py

# 6. Run the application
flask run
# or:
python app.py

# 7. Open the application in your browser
# http://localhost:5000
```

## Basic Usage
### Consultants
1. Register / log in as consultant
2. Complete your profile (headline, location, experience, skills)
3. Upload your CV and profile picture
4. Browse job posts
5. Unlock job contact details to start a collaboration

### Companies
1. Register / log in as company
2. Complete your company profile (name, location, industries)
3. Create job posts with required skills and contract type
4. Browse available consultants
5. Unlock consultant contact details and start collaborations