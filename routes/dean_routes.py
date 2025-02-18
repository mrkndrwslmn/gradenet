from flask import Blueprint, render_template, redirect, url_for, request, flash
from forms import AddFacultyForm
from flask_login import login_required, current_user
from models import User
from app import app  # Import the app instance
from app import app, get_db_connection 
import mysql.connector
from werkzeug.security import generate_password_hash
import csv

bp = Blueprint('dean', __name__, url_prefix='/dean')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'Faculty'")
        num_faculty = cursor.fetchone()[0]  # Get the count from the result

        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'Student'")
        num_students = cursor.fetchone()[0]

        return render_template('dashboard.html', num_faculty=num_faculty, num_students=num_students)
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return render_template('dashboard.html', num_faculty="Error", num_students="Error") #Return to previous screen and show error
    finally:
        cursor.close()
        conn.close()

@bp.route('/faculty_list')
@login_required
def faculty_list():
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    search_term = request.args.get('search', '')
    entries_per_page = request.args.get('entries', '10')
    entries_per_page = int(entries_per_page) if entries_per_page.isdigit() else 10
    page = int(request.args.get('page', 1))

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('faculty_list.html', faculties=[], pagination=None, search_term=search_term)

    cursor = conn.cursor(dictionary=True)
    try:
        # Build the base query
        query = """SELECT user_id, first_name, middle_name, last_name, email, phone, role, date_of_birth, gender FROM users WHERE role = 'Faculty' AND is_active = 1"""
        params = []
        where_clause = ""

        # Add search filter if applicable
        if search_term:
            where_clause = " AND (first_name LIKE %s OR last_name LIKE %s OR email LIKE %s)"
            params.extend([f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"])
        
        # Get total count for pagination
        count_query = "SELECT COUNT(*) FROM users WHERE role = 'Faculty'" + where_clause
        cursor.execute(count_query, tuple(params))
        total_records = cursor.fetchone()['COUNT(*)']
        num_pages = (total_records + entries_per_page - 1) // entries_per_page

        # Add limit and offset
        query += where_clause + " LIMIT %s OFFSET %s"
        params.extend([entries_per_page, (page - 1) * entries_per_page])

        # Execute the query to retrieve faculties
        cursor.execute(query, tuple(params))
        faculties_data = cursor.fetchall()

        # Update the mapping for faculties in the faculty_list route:
        faculties = [User(
            data.get('user_id'),
            data.get('first_name'),
            data.get('middle_name'),
            data.get('last_name'),
            "",                           # default for username
            data.get('email'),
            data.get('phone'),
            data.get('role'),
            data.get('date_of_birth'),
            data.get('gender'),
            None                          # default for created_at
        ) for data in faculties_data]

        return render_template('faculty_list.html', faculties=faculties, num_pages=num_pages, page=page, search_term=search_term, total_records=total_records, entries_per_page=entries_per_page)
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return render_template('faculty_list.html', faculties=[], search_term=search_term, entries_per_page=entries_per_page, page=page, num_pages=0)
    finally:
        cursor.close()
        conn.close()

@bp.route('/add_faculty', methods=['GET', 'POST'])
@login_required
def add_faculty():
    if request.method == 'POST':
        # Retrieve form fields (password is not provided by form)
        first_name = request.form.get('first_name')
        middle_name = request.form.get('middle_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        gender = request.form.get('gender')

        # Validate required fields (adjust as needed)
        if not all([first_name, last_name, email, phone, gender]):
            flash("Missing required fields", "error")
            return render_template('add_faculty.html')
        
        # Generate username: first letter of first name + last name (all lowercase)
        username = f"{first_name[0].lower()}{last_name.lower()}"

        # Set default password as '123456' and hash it
        default_pwd = "123456"
        hashed_password = generate_password_hash(default_pwd)

        # Insert into database
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "error")
            return render_template('add_faculty.html')
        cursor = conn.cursor()
        try:
            # Insert into users table with gender included
            user_query = """
                INSERT INTO users (first_name, middle_name, last_name, username, email, phone, password, role, gender)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            user_values = (first_name, middle_name, last_name, username, email, phone, hashed_password, 'Faculty', gender)
            cursor.execute(user_query, user_values)
            
            conn.commit()
            flash("Faculty added successfully", "success")
            return redirect(url_for('dean.faculty_list'))
        except Exception as e:
            conn.rollback()
            flash(f"Database error: {e}", "error")
            return render_template('add_faculty.html')
        finally:
            cursor.close()
            conn.close()
    else:
        return render_template('add_faculty.html')

@bp.route('/faculty/archive/<int:faculty_id>', methods=['POST'])
@login_required
def archive_faculty(faculty_id):
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500

    cursor = conn.cursor()
    print("Archiving faculty with ID:", faculty_id)
    try:
        conn.start_transaction()
        # Update user's is_active status
        query = "UPDATE users SET is_active = 0 WHERE user_id = %s"
        cursor.execute(query, (faculty_id,))
        # Check if any rows were affected
        if cursor.rowcount == 0:
            flash("Faculty not found.", "error")
            return redirect(url_for('dean.faculty_list'))
        conn.commit()
        flash('Faculty archived successfully!', 'success')
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('dean.faculty_list'))

@bp.route('/faculty/unarchive/<int:faculty_id>', methods=['POST'])
@login_required
def unarchive_faculty(faculty_id):
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500

    cursor = conn.cursor()
    try:
        conn.start_transaction()
        # Update user's is_active status
        query = "UPDATE users SET is_active = 1 WHERE user_id = %s"
        cursor.execute(query, (faculty_id,))
        # Check if any rows were affected
        if cursor.rowcount == 0:
            flash("Faculty not found.", "error")
            return redirect(url_for('dean.faculty_list'))
        conn.commit()
        flash('Faculty unarchived successfully!', 'success')
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('dean.faculty_list'))

@bp.route('/students', methods=['GET', 'POST'])
@login_required
def students():
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    search_term = request.args.get('search', '')
    entries_per_page = request.args.get('entries', '10')
    entries_per_page = int(entries_per_page) if entries_per_page.isdigit() else 10
    page = int(request.args.get('page', 1))
    section_filter = request.args.get('sectionToggle', 'all')

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('students.html', students=[], distinct_sections=[], num_pages=0, page=1, search_term="")

    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch distinct sections from the students table
        cursor.execute("SELECT DISTINCT section FROM students")
        sections_data = cursor.fetchall()
        distinct_sections = [row['section'] for row in sections_data if row.get('section')]

        # Updated query to also select year_level and semester
        query = """SELECT u.user_id, u.first_name, u.middle_name, u.last_name, u.email, u.phone, 
                          u.role, u.username, u.date_of_birth, u.gender, 
                          s.student_number, s.section, s.year_level, s.semester 
                   FROM users u 
                   JOIN students s ON u.user_id = s.user_id 
                   WHERE u.role = 'Student'"""
        params = []
        where_clause = ""
        # Apply section filter on the students table
        if section_filter != 'all' and section_filter:
            where_clause += " AND s.section = %s"
            params.append(section_filter)
        # Apply search filter on users and students fields
        if search_term:
            if where_clause:
                where_clause += " AND (u.first_name LIKE %s OR u.last_name LIKE %s OR u.email LIKE %s OR s.student_number LIKE %s)"
            else:
                where_clause = " AND (u.first_name LIKE %s OR u.last_name LIKE %s OR u.email LIKE %s OR s.student_number LIKE %s)"
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
        
        # Get total count for pagination
        count_query = "SELECT COUNT(*) FROM users u JOIN students s ON u.user_id = s.user_id WHERE u.role = 'Student'" + where_clause
        cursor.execute(count_query, tuple(params))
        total_records = cursor.fetchone()['COUNT(*)']
        num_pages = (total_records + entries_per_page - 1) // entries_per_page

        # Append LIMIT and OFFSET
        query += where_clause + " LIMIT %s OFFSET %s"
        params.extend([entries_per_page, (page - 1) * entries_per_page])
        cursor.execute(query, tuple(params))
        students_data = cursor.fetchall()

        # Map to User objects (student_number is passed in)
        students = [User(**data) for data in students_data]
        if not students:
            print("No student records found.")
        else:
            print("Mapped students:", students)
        return render_template('students.html', students=students, distinct_sections=distinct_sections, num_pages=num_pages, page=page, search_term=search_term, total_records=total_records, entries_per_page=entries_per_page, section_filter=section_filter)
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return render_template('students.html', students=[], distinct_sections=[], num_pages=0, page=1, search_term="")
    finally:
        cursor.close()
        conn.close()

@bp.route('/students/import', methods=['POST'])
@login_required
def import_students():
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    print("Request files:", request.files)  # Debug: log full files dictionary
    
    if 'studentFile' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('dean.students'))
    
    file = request.files['studentFile']
    print("Uploaded file name:", file.filename)  # Debug: log file name
    
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('dean.students'))

    if not file.filename.endswith('.csv'):
        flash('Invalid file type. Only CSV files are allowed.', 'error')
        return redirect(url_for('dean.students'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('dean.students'))
    
    cursor = conn.cursor()  # Define cursor immediately

    try:
        raw_data = file.stream.read()
        print("Raw data length:", len(raw_data))  # Debug: log data length
        if not raw_data:
            print("No data read from file")  # Debug print

        csv_data = csv.reader(raw_data.decode("utf-8").splitlines())
        header = next(csv_data)  # Skip header row
        print("CSV header:", header)  # Debug print

        for row in csv_data:
            print("Processing row:", row)  

            if len(row) < 9:
                flash(f"Row has insufficient columns: {row}", 'error')
                continue
            student_number, first_name, middle_name, last_name, email, _, section, year_level, semester = row
            username = f"{first_name.lower()}{last_name.lower()}".replace(" ", "")

            # Basic validation (add more as needed)
            if not all([student_number, first_name, last_name, email, section, year_level, semester]):
                print("Invalid data in row:", row)  # Debug print
                flash(f"Invalid data: {row}", 'error')
                continue

            student_number = student_number.replace('-', '')  # Remove existing dashes
            if len(student_number) >= 8:
                student_number = f"{student_number[:4]}-{student_number[4:]}"
            elif len(student_number) < 8:
                flash(f"Invalid student number format.  Needs at least 8 digits: {student_number}", "error")
                continue # Skip to the next row in the csv
            else:
                flash(f"Invalid student number format.  Needs at least 8 digits: {student_number}", "error")
                continue # Skip to the next row in the csv

            # Set fixed password and hash it
            password = "123456"
            hashed_password = generate_password_hash(password)

            try:
                cursor.execute("SAVEPOINT sp")
                query = """INSERT INTO users (first_name, middle_name, last_name, email, password, role, username, phone, date_of_birth, gender) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                values = (first_name, middle_name, last_name, email, hashed_password, 'Student', username, "", "", "")
                cursor.execute(query, values)
                user_id = cursor.lastrowid

                query2 = "INSERT INTO students (user_id, student_number, section, year_level, semester) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query2, (user_id, student_number, section, year_level, semester))
            except mysql.connector.Error as err:
                if (err.errno == 1062):
                    cursor.execute("ROLLBACK TO sp")
                    continue
                else:
                    raise
        conn.commit()
        flash('Students imported successfully!', 'success')
    except Exception as e:
        conn.rollback()
        print("Error during CSV import:", e)  # Debug print
        flash(f"Error during import: {e}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('dean.students'))

# Add the edit_faculty route
@bp.route('/faculty/edit/<int:faculty_id>', methods=['GET', 'POST'])
@login_required
def edit_faculty(faculty_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('dean.faculty_list'))
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE user_id = %s AND role = 'Faculty'", (faculty_id,))
        faculty = cursor.fetchone()
        if not faculty:
            flash("Faculty not found", "error")
            return redirect(url_for('dean.faculty_list'))
        if request.method == 'POST':
            first_name = request.form.get('first_name')
            middle_name = request.form.get('middle_name')
            last_name = request.form.get('last_name')
            username = request.form.get('username')
            email = request.form.get('email')
            phone = request.form.get('phone')
            role = request.form.get('role')
            date_of_birth = request.form.get('date_of_birth')
            gender = request.form.get('gender')
            update_query = """
                UPDATE users
                SET first_name = %s,
                    middle_name = %s,
                    last_name = %s,
                    username = %s,
                    email = %s,
                    phone = %s,
                    role = %s,
                    date_of_birth = %s,
                    gender = %s
                WHERE user_id = %s
            """
            cursor.execute(update_query, (first_name, middle_name, last_name, username, email, phone, role, date_of_birth, gender, faculty_id))
            conn.commit()
            flash("Faculty updated successfully", "success")
            return redirect(url_for('dean.faculty_list'))
        return render_template('edit_faculty.html', faculty=faculty)
    except mysql.connector.Error as err:
        print(f"Error updating faculty: {err}")  # <-- Print the error details
        conn.rollback()
        flash(f"Database error: {err}", "error")
        return redirect(url_for('dean.faculty_list'))
    finally:
        cursor.close()
        conn.close()