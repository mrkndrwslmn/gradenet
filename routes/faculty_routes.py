from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from forms import AddSubjectForm
from app import app  
from app import get_db_connection
import mysql.connector
from flask_login import login_required, current_user
from models import Subject, User  
from models import Subject  

bp = Blueprint('faculty', __name__, url_prefix='/faculty')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'Faculty':
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500

    cursor = conn.cursor()
    try:
        # Count the number of subjects the faculty is teaching
        query_subjects = "SELECT COUNT(DISTINCT subject_id) FROM faculty_subjects WHERE faculty_id = %s"
        cursor.execute(query_subjects, (current_user.user_id,))
        num_subjects = cursor.fetchone()[0]

        # Count the number of enrolled students from student_enrollment filtered by faculty_id
        query_students = """
            SELECT COUNT(DISTINCT student_id)
            FROM student_enrollment
            WHERE faculty_id = %s
        """
        cursor.execute(query_students, (current_user.user_id,))
        num_students = cursor.fetchone()[0]

        return render_template('faculty_dashboard.html', num_subjects=num_subjects, num_students=num_students)

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")  # Flash the error message
        return render_template('faculty_dashboard.html', num_subjects=0, num_students=0)  # Show 0 count
    finally:
        cursor.close()
        conn.close()

@bp.route('/subjects')
@login_required
def subjects():
    if current_user.role != 'Faculty':
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500

    cursor = conn.cursor(dictionary=True)
    try:
        # Updated query to get student_count per subject
        query = """
            SELECT s.*, COUNT(DISTINCT se.student_id) AS student_count
            FROM subjects s
            JOIN faculty_subjects fs ON s.subject_id = fs.subject_id
            LEFT JOIN student_enrollment se ON se.subject_id = s.subject_id
            WHERE fs.faculty_id = %s
            GROUP BY s.subject_id
        """
        cursor.execute(query, (current_user.user_id,))
        subjects_data = cursor.fetchall()

        subjects = []
        for data in subjects_data:
            student_count = data.pop('student_count', 0)  # remove extra key
            subj = Subject(**data)
            subj.students = [None] * student_count
            subjects.append(subj)

        return render_template('faculty_subjects.html', subjects=subjects)
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return render_template('faculty_subjects.html', subjects=[])
    finally:
        cursor.close()
        conn.close()

@bp.route('/subject/<int:subject_id>', methods=['GET'])
@login_required
def subject_info(subject_id):
    if current_user.role != 'Faculty':
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('faculty.subjects'))

    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch subject information
        subject_query = "SELECT * FROM subjects WHERE subject_id = %s"
        cursor.execute(subject_query, (subject_id,))
        subject = cursor.fetchone()

        # Fetch enrolled students
        student_query = """
            SELECT s.student_number, u.first_name, u.middle_name, u.last_name, u.user_id, s.id AS student_id
            FROM student_enrollment se
            JOIN students s ON se.student_id = s.id
            JOIN users u ON s.user_id = u.user_id
            WHERE se.subject_id = %s
        """
        cursor.execute(student_query, (subject_id,))
        enrolled_students = cursor.fetchall()

        # Fetch grading categories and assessments (needed for "Grades" tab)
        categories = fetch_grading_data(cursor, current_user.user_id, subject_id) # Refactor this!

        # Calculate student summary data using the new query
        student_summary = calculate_student_summary(cursor, current_user.user_id, subject_id, categories)
        
        # Convert final averages to equivalent grades (same logic)
        for student in student_summary:
            final_average = student['final_average'] if student['final_average'] is not None else 0

            if final_average >= 99:
                student['equivalent_grade'] = 1.00
            elif final_average >= 96:
                student['equivalent_grade'] = 1.25
            elif final_average >= 93:
                student['equivalent_grade'] = 1.50
            elif final_average >= 90:
                student['equivalent_grade'] = 1.75
            elif final_average >= 87:
                student['equivalent_grade'] = 2.00
            elif final_average >= 84:
                student['equivalent_grade'] = 2.25
            elif final_average >= 81:
                student['equivalent_grade'] = 2.50
            elif final_average >= 78:
                student['equivalent_grade'] = 2.75
            elif final_average >= 75:
                student['equivalent_grade'] = 3.00
            elif final_average >= 70:
                student['equivalent_grade'] = 4.00
            else:
                student['equivalent_grade'] = 5.0

        # Calculate category averages (needed for "Summary" tab) - REFACTOR THIS
        category_averages = calculate_category_averages(enrolled_students, categories)
        
        return render_template(
            'faculty_subject_info.html',
            subject=subject,
            enrolled_students=enrolled_students,
            grading_categories=categories,
            student_summary=student_summary,
            category_averages=category_averages,
            tab=request.args.get('tab', 'list')  # pass tab parameter to template
        )

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return redirect(url_for('faculty.subjects'))
    finally:
        cursor.close()
        conn.close()

def fetch_grading_data(cursor, faculty_id, subject_id):
    """
    Fetches grading categories, assessments, and student grades for a given faculty and subject.
    This is used for the "Grades" tab.
    """
    cat_query = """
        SELECT category_id, category_name, percentage_weight
        FROM grading_categories
        WHERE faculty_id = %s AND subject_id = %s
    """
    cursor.execute(cat_query, (faculty_id, subject_id))
    categories = cursor.fetchall()

    for category in categories:
        assess_query = """
            SELECT assessment_id, assessment_name, total_score
            FROM assessments
            WHERE category_id = %s AND subject_id = %s
        """
        cursor.execute(assess_query, (category['category_id'], subject_id))
        category['assessments'] = cursor.fetchall()

        for assessment in category['assessments']:
            grade_query = """
                SELECT sg.student_id, sg.assessment_id, sg.score_obtained
                FROM student_grades sg
                WHERE sg.assessment_id = %s
            """
            cursor.execute(grade_query, (assessment['assessment_id'],))
            grades = cursor.fetchall()
            assessment['grades'] = grades  # Store grades directly in assessment

            grade_dict = {grade['student_id']: grade['score_obtained'] for grade in grades}
            assessment['grade_dict'] = grade_dict

            print("Grades for assessment", assessment['assessment_id'], ":", grades)

    return categories

def calculate_student_summary(cursor, faculty_id, subject_id, categories):
    """
    Calculates the student summary data with fixed query and improved debugging
    """
    if not categories:
        print("No categories found for this subject.")
        return []

    # Build the CASE WHEN statements for each category
    category_cases = []
    category_names = []
    for category in categories:
        category_id = category['category_id']
        clean_name = category['category_name'].replace(" ", "_")
        category_names.append(clean_name)
        category_cases.append(f"MAX(CASE WHEN ca.category_id = {category_id} THEN category_avg END) AS {clean_name}_AVG")

    # Combine the category cases into a single string
    category_case_str = ",\n".join(category_cases)

    # Improved SQL query with explicit JOIN conditions and better subquery structure
    student_summary_query = f"""
        SELECT
            s.id,
            s.student_number,
            u.first_name,
            u.last_name,
            s.section,
            {category_case_str},
            SUM(IFNULL(category_avg, 0)) AS final_average
        FROM (
            SELECT
                sg.student_id,
                c.category_id,
                AVG(sg.score_obtained / a.total_score * 100) AS raw_avg,
                AVG(sg.score_obtained / a.total_score * 100) * (c.percentage_weight / 100) AS category_avg
            FROM student_grades sg
            JOIN assessments a ON sg.assessment_id = a.assessment_id
            JOIN grading_categories c ON a.category_id = c.category_id
            WHERE a.faculty_id = %s AND a.subject_id = %s
            GROUP BY sg.student_id, c.category_id
        ) AS category_averages
        JOIN students s ON category_averages.student_id = s.id
        JOIN users u ON s.user_id = u.user_id
        JOIN student_enrollment se ON s.id = se.student_id AND se.subject_id = %s
        JOIN grading_categories ca ON category_averages.category_id = ca.category_id AND ca.subject_id = %s
        GROUP BY s.id, s.student_number, u.first_name, u.last_name, s.section
    """

    # Execute the modified query with additional parameters for JOINs
    cursor.execute(student_summary_query, (faculty_id, subject_id, subject_id, subject_id))
    student_summary = cursor.fetchall()
    
    return student_summary

def calculate_category_averages(enrolled_students, categories):
    """Calculates average score per category for each student."""
    category_averages = {}
    for student in enrolled_students:
        student_id = student['student_id']
        category_averages[student_id] = {}
        for category in categories:
            category_id = category['category_id']
            total_score = 0.0
            count = 0
            for assessment in category['assessments']:
                grades = assessment.get('grades', [])
                grade = next((g for g in grades if g['student_id'] == student_id), None)
                if grade:
                    total_score += float(grade['score_obtained']) / float(assessment['total_score']) * 100
                    count += 1
            avg = total_score / count if count > 0 else 0
            category_averages[student_id][category_id] = avg
    return category_averages

@bp.route('/subject/<int:subject_id>/add_student', methods=['POST'])
@login_required
def add_student_to_subject(subject_id):
    if current_user.role != 'Faculty':
        return "Unauthorized", 403

    student_id = request.form.get('student_id')

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))

    cursor = conn.cursor()
    try:
        # Validate the student and subject
        student_query = "SELECT 1 FROM users WHERE user_id = %s AND role = 'Student'"
        cursor.execute(student_query, (student_id,))
        if not cursor.fetchone():
            flash("Invalid student", "error")
            return redirect(url_for('faculty.subject_info', subject_id=subject_id))

        subject_query = "SELECT 1 FROM subjects WHERE subject_id = %s"
        cursor.execute(subject_query, (subject_id,))
        if not cursor.fetchone():
            flash("Invalid subject", "error")
            return redirect(url_for('faculty.subject_info', subject_id=subject_id))

        # Check if the student is already enrolled
        enrollment_query = "SELECT 1 FROM student_enrollment WHERE student_id = %s AND subject_id = %s AND faculty_id = %s"
        cursor.execute(enrollment_query, (student_id, subject_id, current_user.user_id))
        if cursor.fetchone():
            flash("Student already enrolled in this subject", "error")
            return redirect(url_for('faculty.subject_info', subject_id=subject_id))

        # Enroll the student
        enroll_query = "INSERT INTO student_enrollment (student_id, subject_id, faculty_id) VALUES (%s, %s, %s)"
        cursor.execute(enroll_query, (student_id, subject_id, current_user.user_id))
        conn.commit()

        flash("Student enrolled successfully", "success")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))
    finally:
        cursor.close()
        conn.close()

@bp.route('/subject/<int:subject_id>/remove_student/<int:student_id>', methods=['POST'])
@login_required
def remove_student_from_subject(subject_id, student_id):
    if current_user.role != 'Faculty':
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))

    cursor = conn.cursor()
    try:
        # Validate student, subject, and that the faculty assigned to this subject
        query = "DELETE FROM student_enrollment WHERE student_id = %s AND subject_id = %s AND faculty_id = %s"
        cursor.execute(query, (student_id, subject_id, current_user.user_id))
        if cursor.rowcount == 0:
            flash("Student not enrolled in this subject.", "error")
            return redirect(url_for('faculty.subject_info', subject_id=subject_id))

        conn.commit()
        flash("Student removed from subject.", "success")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))
    finally:
        cursor.close()
        conn.close()

@bp.route('/loading', methods=['GET'])
@login_required
def faculty_loading():
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('faculty_loading.html', faculties=[], subjects=[])
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id, first_name, last_name FROM users WHERE role = 'Faculty'")
        faculties = cursor.fetchall()
        return render_template('faculty_loading.html', faculties=faculties, subjects=[])
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return render_template('faculty_loading.html', faculties=[], subjects=[])
    finally:
        cursor.close()
        conn.close()

@bp.route('/get_subjects', methods=['GET'])
@login_required
def get_subjects():
    if current_user.role not in ('Dean', 'Secretary'):
        return jsonify({'error': 'Unauthorized'}), 403

    year_level = request.args.get('year_level')
    semester = request.args.get('semester')

    print("Year level:", year_level)  # Debug log
    print("Semester:", semester)  # Debug log

    if not year_level or not semester:
        return jsonify({'error': 'Missing parameters'}), 400

    try:
        # Convert the parameters to integers
        year_level_int = int(year_level)
        semester_int = int(semester)
    except ValueError:
        return jsonify({'error': 'Invalid parameters'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        query = "SELECT * FROM subjects WHERE year_level = %s AND semester = %s"
        cursor.execute(query, (year_level_int, semester_int))
        subjects = cursor.fetchall()
        
        return jsonify({'subjects': subjects})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/get_sections', methods=['GET'])
@login_required
def get_sections():
    if current_user.role not in ('Dean', 'Secretary'):
        return jsonify({'error': 'Unauthorized'}), 403

    year_level = request.args.get('year_level')
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        if year_level:
            query = "SELECT DISTINCT section FROM students WHERE section LIKE %s"
            pattern = f'%-{year_level}%' 
            cursor.execute(query, (pattern,))
        else:
            query = "SELECT DISTINCT section FROM students"
            cursor.execute(query)
        
        rows = cursor.fetchall()
        sections = [row['section'] for row in rows]
        return jsonify({'sections': sections})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/archive', methods=['GET'])
@login_required
def faculty_archive():
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('faculty_archive.html', archived_faculties=[])
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE role = 'Faculty' AND is_active = 0")
        archived_faculties = cursor.fetchall()
        return render_template('faculty_archive.html', archived_faculties=archived_faculties)
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return render_template('faculty_archive.html', archived_faculties=[])
    finally:
        cursor.close()
        conn.close()

@bp.route('/insert_loading', methods=['POST'])
@login_required
def insert_loading():
    if current_user.role not in ('Dean', 'Secretary'):
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    print("Payload received:", data)  

    faculty_id = data.get('faculty_id')
    subject_ids = data.get('subjects', [])
    sections = data.get('sections', [])

    if not faculty_id or (not subject_ids and not sections):
        return jsonify({'error': 'Missing parameters'}), 400

    if not subject_ids or not sections:
        return jsonify({'error': 'Both subjects and sections are required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500
    cursor = conn.cursor()

    try:
        # 1. Insert Faculty Loading (faculty_subjects)
        faculty_records = []
        for subject_id in subject_ids:
            for section in sections:
                faculty_records.append((faculty_id, subject_id, section))

        faculty_query = "INSERT INTO faculty_subjects (faculty_id, subject_id, section) VALUES (%s, %s, %s)"
        cursor.executemany(faculty_query, faculty_records)

        # 2. Enroll Students Based on Section
        enrollment_records = []
        for subject_id in subject_ids:
            for section in sections:
                find_students_query = "SELECT id FROM students WHERE section = %s"
                cursor.execute(find_students_query, (section,))
                student_ids = [row[0] for row in cursor.fetchall()]  # Extract student user IDs

                for student_id in student_ids:
                    enrollment_records.append((student_id, subject_id, faculty_id))

        if enrollment_records:
            enrollment_query = "INSERT INTO student_enrollment (student_id, subject_id, faculty_id) VALUES (%s, %s, %s)"
            cursor.executemany(enrollment_query, enrollment_records)

        conn.commit()
        return jsonify({'message': 'Faculty loading and student enrollment saved successfully!'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/subject/<int:subject_id>/update_grades', methods=['POST'])
@login_required
def update_student_grades(subject_id):
    if current_user.role != 'Faculty':
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))

    cursor = conn.cursor()
    try:
        # Update category percentages
        for key, val in request.form.items():
            if key.startswith("category_") and key.endswith("_percentage"):
                cat_name = key.split("_")[1]
                update_cat = """
                    UPDATE grading_categories
                    SET percentage_weight = %s
                    WHERE faculty_id = %s AND subject_id = %s AND category_name = %s
                """
                cursor.execute(update_cat, (val, current_user.user_id, subject_id, cat_name))

        # Update or insert student grades
        for key, value in request.form.items():
            if key.startswith("score_"):
                parts = key.split("_")
                if len(parts) == 3:
                    user_id = parts[1]  # This is actually the user_id
                    assessment_id = parts[2]
                    
                    # Get the actual student_id from user_id
                    get_student_id = """
                        SELECT id FROM students WHERE user_id = %s
                    """
                    cursor.execute(get_student_id, (user_id,))
                    student_result = cursor.fetchone()
                    
                    if not student_result:
                        print(f"No student found with user_id {user_id}")
                        continue  # Skip this entry
                        
                    student_id = student_result[0]  # Get the actual student_id

                    # Check if grade exists
                    check_grade = """
                        SELECT grade_id FROM student_grades
                        WHERE student_id = %s AND assessment_id = %s
                    """
                    cursor.execute(check_grade, (student_id, assessment_id))
                    print("Checking grade for student", student_id, "and assessment", assessment_id)
                    row = cursor.fetchone()

                    if row:
                        # Update existing grade
                        update_grade = """
                            UPDATE student_grades
                            SET score_obtained = %s
                            WHERE grade_id = %s
                        """
                        print("Updating grade for student", student_id, "and assessment", assessment_id)
                        cursor.execute(update_grade, (value, row[0]))
                    else:
                        # Insert new grade
                        insert_grade = """
                            INSERT INTO student_grades (student_id, assessment_id, score_obtained)
                            VALUES (%s, %s, %s)
                        """
                        print("Inserting grade for student", student_id, "and assessment", assessment_id)
                        cursor.execute(insert_grade, (student_id, assessment_id, value))

        conn.commit()
        flash("Grades updated successfully!", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('faculty.subject_info', subject_id=subject_id, tab='grades'))

@bp.route('/subject/<int:subject_id>/grading', methods=['GET'])
@login_required
def subject_grading(subject_id):
    if current_user.role != 'Faculty':
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))
        
    cursor = conn.cursor(dictionary=True)
    try:
        # Step 1: Check for existing grading categories for this faculty and subject
        cat_query = """
            SELECT category_id, category_name, percentage_weight 
            FROM grading_categories 
            WHERE faculty_id = %s AND subject_id = %s
        """
        cursor.execute(cat_query, (current_user.user_id, subject_id))
        categories = cursor.fetchall()

        if not categories:
            flash("No grading categories found. Please create a new category.", "error")
            return redirect(url_for('faculty.subject_info', subject_id=subject_id))

        # Step 2: For each category, fetch its assessments
        for category in categories:
            assess_query = """
                SELECT assessment_id, assessment_name, total_score 
                FROM assessments 
                WHERE category_id = %s AND subject_id = %s
            """
            cursor.execute(assess_query, (category['category_id'], subject_id))
            category['assessments'] = cursor.fetchall()

            # Step 3: For each assessment, fetch student grades
            for assessment in category['assessments']:
                grade_query = """
                    SELECT sg.student_id, sg.assessment_id, sg.score_obtained, 
                           s.student_number, u.first_name, u.last_name
                    FROM student_grades sg
                    JOIN students s ON sg.student_id = s.id
                    JOIN users u ON s.user_id = u.user_id
                    WHERE sg.assessment_id = %s
                """
                cursor.execute(grade_query, (assessment['assessment_id'],))
                assessment['grades'] = cursor.fetchall()

        # Step 6: Render the grading template with all gathered data
        return render_template('faculty_subjects_grading.html',
                               categories=categories,
                               subject_id=subject_id)
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))
    finally:
        cursor.close()
        conn.close()

@bp.route('/subject/<int:subject_id>/add_category', methods=['POST'])
@login_required
def add_grading_category(subject_id):
    if current_user.role != 'Faculty':
        return "Unauthorized", 403

    category_name = request.form.get('category_name')
    percentage_weight = request.form.get('percentage_weight')
    if not category_name or not percentage_weight:
        flash("Missing category name or percentage", "error")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))
    cursor = conn.cursor()
    try:
        insert_query = """
            INSERT INTO grading_categories (faculty_id, subject_id, category_name, percentage_weight)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(insert_query, (current_user.user_id, subject_id, category_name, percentage_weight))
        conn.commit()
        flash("Grade category added successfully!", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('faculty.subject_info', subject_id=subject_id, tab='grades'))

@bp.route('/subject/<int:subject_id>/add_assessment', methods=['POST'])
@login_required
def add_assessment(subject_id):
    if current_user.role != 'Faculty':
        return "Unauthorized", 403
    
    category_id = request.form.get('category_id')
    assessment_name = request.form.get('assessment_name')
    total_score = request.form.get('total_score')
    
    print("Add Assessment - Received:", category_id, assessment_name, total_score)
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('faculty.subject_info', subject_id=subject_id))

    cursor = conn.cursor()
    try:
        # Modified query to include faculty_id for the foreign key constraint.
        insert_query = """
            INSERT INTO assessments (faculty_id, category_id, subject_id, assessment_name, total_score)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (current_user.user_id, category_id, subject_id, assessment_name, total_score))
        conn.commit()
        flash("Assessment added successfully!", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        print("Database error:", err)
        flash(f"Database error: {err}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('faculty.subject_info', subject_id=subject_id, tab='grades'))
