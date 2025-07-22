# GradeNet

GradeNet is a web-based grade management system for the College of Computer Studies. It provides role-based dashboards and tools for Deans, Faculty, and Students to manage users, subjects, and grades efficiently.

## Features
- **Role-based Access:** Dashboards and permissions for Dean, Faculty, and Student users.
- **Faculty & Student Management:** Add, edit, archive, and list faculty and students. Bulk import students via CSV.
- **Subject Management:** Add, edit, assign, and view subjects. Faculty loading for subject assignments.
- **Grading System:** Define grading categories, enter and update grades, and calculate grade equivalents.
- **Student Portal:** Students can view their enrolled subjects and grades.
- **Authentication & Security:** Secure login, session management, and CSRF protection.

## Tech Stack
- Python 3
- Flask (with Flask-WTF, Flask-Login)
- MySQL
- WTForms
- Jinja2 Templates

## Installation
1. Clone the repository:
   ```sh
   git clone <repo-url>
   cd gradenet
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Configure your database credentials in `config.py` or set the following environment variables:
   - `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`, `SECRET_KEY`
4. Run the application:
   ```sh
   python app.py
   ```
5. Access the app at [http://localhost:5000](http://localhost:5000)

## Folder Structure
- `app.py` - Main Flask application
- `config.py` - Configuration settings
- `models.py` - Data models
- `forms.py` - WTForms definitions
- `routes/` - Blueprints for Dean, Faculty, Student, Subject, and Auth routes
- `templates/` - Jinja2 HTML templates
- `static/` - Static files (images, CSS, JS)

## License
MIT License