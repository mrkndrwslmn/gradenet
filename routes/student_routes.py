from flask import Blueprint, render_template, flash, redirect, url_for, request
from app import app  # Import the app instance
from app import get_db_connection
import mysql.connector
from flask_login import login_required, current_user
from models import Subject  # Import Subject model
from werkzeug.security import generate_password_hash

bp = Blueprint('student', __name__, url_prefix='/student')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'Student':
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('student_dashboard.html', subject_data=[])

    cursor = conn.cursor(dictionary=True)
    try:
        # First get the student's ID from the students table
        student_id_query = "SELECT id FROM students WHERE user_id = %s"
        cursor.execute(student_id_query, (current_user.user_id,))
        student_result = cursor.fetchone()
        
        if not student_result:
            flash("Student record not found", "error")
            return render_template('student_dashboard.html', subject_data=[])
            
        student_id = student_result['id']

        # Step 1: Get all subjects the student is enrolled in
        enrollment_query = """
            SELECT s.subject_id, s.subject_code, s.subject_name
            FROM student_enrollment se
            JOIN subjects s ON se.subject_id = s.subject_id
            WHERE se.student_id = %s
        """
        cursor.execute(enrollment_query, (student_id,))
        subjects = cursor.fetchall()

        # Step 2: For each subject, fetch categories and compute averages
        subject_data = []
        for subj in subjects:
            cat_query = """
                SELECT c.category_id, c.category_name, c.percentage_weight
                FROM grading_categories c
                WHERE c.subject_id = %s
            """
            cursor.execute(cat_query, (subj['subject_id'],))
            categories = cursor.fetchall()

            # Calculate category averages
            final_grade_accumulator = 0
            for cat in categories:
                print("Categories: ", cat['category_id'], subj['subject_id'], student_id)
                assess_query = """
                    SELECT a.assessment_id, 
                           a.assessment_name, 
                           a.total_score,
                           sg.score_obtained
                    FROM assessments a
                    LEFT JOIN student_grades sg 
                        ON a.assessment_id = sg.assessment_id
                    WHERE a.category_id = %s 
                        AND a.subject_id = %s
                        AND sg.student_id = %s
                """
                cursor.execute(assess_query, (cat['category_id'], subj['subject_id'], student_id))
                assessments = cursor.fetchall()

                print("Query values: ", cat['category_id'], subj['subject_id'], student_id)
                
                # Average for this category
                if assessments:
                    total_percentage = 0
                    for assess in assessments:
                        if assess['score_obtained'] is not None:
                            total_percentage += (assess['score_obtained'] / assess['total_score']) * 100
                    cat_avg = (total_percentage / len(assessments)) if len(assessments) > 0 else 0
                else:
                    cat_avg = 0

                # Weighted contribution
                final_grade_accumulator += (cat_avg * (cat['percentage_weight'] / 100))

            subj['final_grade'] = round(final_grade_accumulator, 2)
            subject_data.append(subj)

        return render_template('student_dashboard.html', subject_data=subject_data)

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return render_template('student_dashboard.html', subject_data=[])

    finally:
        cursor.close()
        conn.close()

@bp.route('/grades')
@login_required
def grades():
    if current_user.role != 'Student':
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('student_grades.html', subjects_data=[])

    cursor = conn.cursor(dictionary=True)
    try:
        # First get the student's ID from the students table
        student_id_query = "SELECT id FROM students WHERE user_id = %s"
        cursor.execute(student_id_query, (current_user.user_id,))
        student_result = cursor.fetchone()
        
        if not student_result:
            flash("Student record not found", "error")
            return render_template('student_grades.html', subjects_data=[])
            
        student_id = student_result['id']

        # Get enrolled subjects using student_id
        subj_query = """
            SELECT s.subject_id, s.subject_code, s.subject_name
            FROM student_enrollment se
            JOIN subjects s ON se.subject_id = s.subject_id
            WHERE se.student_id = %s
        """
        cursor.execute(subj_query, (student_id,))
        subjects = cursor.fetchall()

        subjects_data = []
        for s in subjects:
            # Fetch categories for this subject
            cat_query = """
                SELECT category_id, category_name, percentage_weight
                FROM grading_categories
                WHERE subject_id = %s
            """
            cursor.execute(cat_query, (s['subject_id'],))
            categories = cursor.fetchall()

            # Initialize placeholders
            cat_list = []
            total_final = 0.0

            # For each category, compute average
            for c in categories:
                assess_query = """
                    SELECT a.assessment_name, a.total_score, sg.score_obtained
                    FROM assessments a
                    LEFT JOIN student_grades sg 
                        ON a.assessment_id = sg.assessment_id AND sg.student_id = %s                        
                    WHERE a.category_id = %s
                      AND a.subject_id = %s
                """
                print("Query: ", assess_query, student_id, c['category_id'], s['subject_id'])
                cursor.execute(assess_query, (student_id, c['category_id'], s['subject_id']))
                assessments = cursor.fetchall()

                # Compute category average
                total_pct = 0.0
                for assess in assessments:
                    if assess['score_obtained'] is not None:
                        total_pct += (assess['score_obtained'] / assess['total_score']) * 100
                cat_avg = (total_pct / len(assessments)) if assessments else 0

                # Weighted contribution to final
                weighted = cat_avg * (c['percentage_weight'] / 100.0)
                total_final += weighted

                c['assessments'] = assessments
                c['category_average'] = round(cat_avg, 2)
                cat_list.append(c)

            # Determine grade equivalent
            grade_equiv = None
            if total_final >= 99:
                grade_equiv = 1.00
            elif total_final >= 96:
                grade_equiv = 1.25
            elif total_final >= 93:
                grade_equiv = 1.50
            elif total_final >= 90:
                grade_equiv = 1.75
            elif total_final >= 87:
                grade_equiv = 2.00
            elif total_final >= 84:
                grade_equiv = 2.25
            elif total_final >= 81:
                grade_equiv = 2.50
            elif total_final >= 78:
                grade_equiv = 2.75
            elif total_final >= 75:
                grade_equiv = 3.00
            elif total_final >= 70:
                grade_equiv = 4.0
            else:
                grade_equiv = 5.0

            subjects_data.append({
                'subject_code': s['subject_code'],
                'subject_name': s['subject_name'],
                'categories': cat_list,
                'total_average': round(total_final, 2),
                'grade_equivalent': grade_equiv
            })

        return render_template('student_grades.html', subjects_data=subjects_data)

    except mysql.connector.Error as err:
        print("Database error:", err)
        flash(f"Database error: {err}", "error")
        return render_template('student_grades.html', subjects_data=[])
    finally:
        cursor.close()
        conn.close()

@bp.route('/add_student', methods=['GET', 'POST'])
@login_required
def add_student():
    # Default message and style
    message = ""
    category = "info"

    if request.method == 'POST':
        student_number = request.form.get('student_number')
        first_name = request.form.get('first_name')
        middle_name = request.form.get('middle_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        section = request.form.get('section')
        password = request.form.get('password')
        gender = request.form.get('gender') # Added
        phone = request.form.get('phone') #Added
        date_of_birth = request.form.get('date_of_birth') #Added
        year_level = int(request.form.get('year_level')) # Added
        semester = int(request.form.get('semester')) # Added

        if not all([student_number, first_name, last_name, email, section, password, gender, phone, date_of_birth, year_level, semester]):
            message = "Missing required fields"
            category = "error"
            return render_template('add_student.html', message=message, category=category)

        # Generate username
        username = f"{first_name.lower()}{last_name.lower()}".replace(" ", "")
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        if not conn:
            message = "Database connection error"
            category = "error"
            return render_template('add_student.html', message=message, category=category, generated_username=username)

        cursor = conn.cursor()
        try:
            # Insert into users table
            query = "INSERT INTO users (first_name, middle_name, last_name, email, password, role, username, phone, date_of_birth, gender) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            values = (first_name, middle_name, last_name, email, hashed_password, 'Student', username, phone, date_of_birth, gender)
            cursor.execute(query, values)
            user_id = cursor.lastrowid

            # Insert into students table
            query2 = "INSERT INTO students (user_id, student_number, section, year_level, semester) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(query2, (user_id, student_number, section, year_level, semester))

            conn.commit()

            # Success message
            message = "Student added successfully"
            category = "success"
            flash(message, category)

            return redirect(url_for('dean.students'))
        except mysql.connector.Error as err:
            conn.rollback()
            message = f"Database error: {err}"
            category = "error"
            flash(message, category)
            return render_template('add_student.html', message=message, category=category)
        finally:
            cursor.close()
            conn.close()
    else:
        username = ""
        conn = get_db_connection()
        return render_template('add_student.html', generated_username=username)

    print(category)
    return render_template('add_student.html', message=message, category=category)

# New endpoint to view a student's details
@bp.route('/view/<int:student_id>', methods=['GET'])
@login_required
def view_student(student_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('dean.students'))
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT u.*, s.student_number, s.section, s.year_level, s.semester FROM users u JOIN students s ON u.user_id = s.user_id WHERE u.user_id = %s", (student_id,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found", "error")
            return redirect(url_for('dean.students'))
        return render_template('view_student.html', student=student)
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return redirect(url_for('dean.students'))
    finally:
        cursor.close()
        conn.close()

# New endpoint to edit a student's details
@bp.route('/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('dean.students'))
    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == 'POST':
            student_number = request.form.get('student_number')
            first_name = request.form.get('first_name')
            middle_name = request.form.get('middle_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            section = request.form.get('section')
            gender = request.form.get('gender')
            phone = request.form.get('phone')
            date_of_birth = request.form.get('date_of_birth')
            year_level = request.form.get('year_level')
            semester = request.form.get('semester')
            query = """UPDATE users SET first_name=%s, middle_name=%s, last_name=%s, email=%s, phone=%s, date_of_birth=%s, gender=%s WHERE user_id=%s"""
            values = (first_name, middle_name, last_name, email, phone, date_of_birth, gender, student_id)
            cursor.execute(query, values)
            query2 = """UPDATE students SET student_number=%s, section=%s, year_level=%s, semester=%s WHERE user_id=%s"""
            values2 = (student_number, section, year_level, semester, student_id)
            cursor.execute(query2, values2)
            conn.commit()
            flash("Student updated successfully", "success")
            return redirect(url_for('dean.students'))
        else:
            cursor.execute("SELECT u.*, s.student_number, s.section, s.year_level, s.semester FROM users u JOIN students s ON u.user_id = s.user_id WHERE u.user_id = %s", (student_id,))
            student = cursor.fetchone()
            if not student:
                flash("Student not found", "error")
                return redirect(url_for('dean.students'))
            return render_template('edit_student.html', student=student)
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error: {err}", "error")
        return redirect(url_for('dean.students'))
    finally:
        cursor.close()
        conn.close()

# New endpoint to delete a student
@bp.route('/delete/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('dean.students'))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM students WHERE user_id = %s", (student_id,))
        cursor.execute("DELETE FROM users WHERE user_id = %s", (student_id,))
        conn.commit()
        flash("Student deleted successfully", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error: {err}", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('dean.students'))