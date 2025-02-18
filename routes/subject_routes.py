from flask import Blueprint, render_template, redirect, url_for, flash, request
from forms import AddSubjectForm
from app import app  # Import the app instance
from app import get_db_connection
import mysql.connector
from flask_login import login_required, current_user
from models import Subject, User  # Import Subject and User models
from flask_paginate import Pagination, get_page_parameter

bp = Blueprint('subject', __name__, url_prefix='/subject')

@bp.route('/list')
@login_required
def list_subjects():
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    search_term = request.args.get('search', '')
    per_page = int(request.args.get('entries', 10))  # Number of entries per page
    page = request.args.get(get_page_parameter(), type=int, default=1)  # Current page number

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('subjects.html', subjects=[], pagination=None, search_term=search_term, page=page)

    cursor = conn.cursor(dictionary=True)
    try:
        # Build the base query
        query = "SELECT * FROM subjects"
        where_clause = ""
        params = []

        # Add search filter if applicable
        if search_term:
            where_clause = " WHERE subject_code LIKE %s OR subject_name LIKE %s"
            params.extend([f"%{search_term}%", f"%{search_term}%"])

        # Count the total number of subjects (before pagination)
        count_query = "SELECT COUNT(*) FROM subjects" + where_clause
        cursor.execute(count_query, params)
        total = cursor.fetchone()['COUNT(*)']
        num_pages = (total + per_page - 1) // per_page

        # Add pagination limits to the query
        query += where_clause + " LIMIT %s OFFSET %s"
        params.extend([per_page, (page - 1) * per_page])

        # Execute the main query to retrieve subjects
        cursor.execute(query, params)
        subjects_data = cursor.fetchall()

        subjects = [Subject(**data) for data in subjects_data] #mapping object

        # Create the pagination object
        pagination = Pagination(page=page, total=total, per_page=per_page, search=search_term, record_name='subjects')

        return render_template('subjects.html', subjects=subjects, pagination=pagination, search_term=search_term, page=page, num_pages=num_pages)

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return render_template('subjects.html', subjects=[], pagination=None, search_term=search_term, page=page)

    finally:
        cursor.close()
        conn.close()

@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_subject():
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    form = AddSubjectForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "error")
            return render_template('add_subject.html', form=form)

        cursor = conn.cursor()
        try:
            query = "INSERT INTO subjects (subject_code, subject_name, year_level, semester, prerequisites) VALUES (%s, %s, %s, %s, %s)"
            values = (form.subject_code.data, form.subject_name.data, form.year_level.data, form.semester.data, form.prerequisites.data)
            cursor.execute(query, values)
            conn.commit()
            flash('Subject added successfully!', 'success')
            return redirect(url_for('subject.list_subjects'))

        except mysql.connector.Error as err:
            conn.rollback()
            print(f"Database error: {err}")
            flash(f"Database error: {err}", "error")
            return render_template('add_subject.html', form=form)

        finally:
            cursor.close()
            conn.close()

    return render_template('add_subject.html', form=form)

@bp.route('/assign_faculty', methods=['GET', 'POST'])
@login_required
def assign_faculty():
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('faculty_loading.html', faculties=[], subjects=[])

    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == 'POST':
            faculty_id = request.form.get('faculty_id')
            year_level = request.form.get('year_level')
            semester = request.form.get('semester')
            subject_ids = request.form.getlist('subject_ids')

            # remove previous faculty assignments
            delete_query = "DELETE FROM faculty_subjects WHERE faculty_id = %s"
            cursor.execute(delete_query, (faculty_id,))

            # add new faculty assignments
            insert_query = "INSERT INTO faculty_subjects (faculty_id, subject_id) VALUES (%s, %s)"
            for subject_id in subject_ids:
                cursor.execute(insert_query, (faculty_id, subject_id))

            conn.commit()
            flash('Subject assigned successfully!', 'success')
            return redirect(url_for('subject.list_subjects'))

        else:
            # Retrieve faculty list
            faculty_query = "SELECT user_id, first_name, last_name FROM users WHERE role = 'Faculty'"
            cursor.execute(faculty_query)
            faculties_data = cursor.fetchall()
            faculties = [User(**data) for data in faculties_data]

            # Retrieve subject list with year_level and semester
            subject_query = "SELECT subject_id, subject_code, subject_name, year_level, semester FROM subjects"
            cursor.execute(subject_query)
            subjects_data = cursor.fetchall()
            subjects = [Subject(**data) for data in subjects_data]

            return render_template('faculty_loading.html', faculties=faculties, subjects=subjects)

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error: {err}")
        flash(f"Database error: {err}", "error")
        return render_template('faculty_loading.html', faculties=[], subjects=[])

    finally:
        cursor.close()
        conn.close()

@bp.route('/view/<int:subject_id>', methods=['GET'])
@login_required
def view_subject(subject_id):
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('subject.list_subjects'))

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM subjects WHERE subject_id = %s", (subject_id,))
        subject = cursor.fetchone()
        if not subject:
            flash("Subject not found", "error")
            return redirect(url_for('subject.list_subjects'))
        return render_template('view_subject.html', subject=subject)
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return redirect(url_for('subject.list_subjects'))
    finally:
        cursor.close()
        conn.close()

@bp.route('/edit/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def edit_subject(subject_id):
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('subject.list_subjects'))

    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == 'POST':
            subject_code = request.form.get('subject_code')
            subject_name = request.form.get('subject_name')
            year_level = request.form.get('year_level')
            semester = request.form.get('semester')
            prerequisites = request.form.get('prerequisites')
            query = """UPDATE subjects SET subject_code=%s, subject_name=%s, year_level=%s, semester=%s, prerequisites=%s WHERE subject_id=%s"""
            values = (subject_code, subject_name, year_level, semester, prerequisites, subject_id)
            cursor.execute(query, values)
            conn.commit()
            flash("Subject updated successfully", "success")
            return redirect(url_for('subject.list_subjects'))
        else:
            cursor.execute("SELECT * FROM subjects WHERE subject_id = %s", (subject_id,))
            subject = cursor.fetchone()
            if not subject:
                flash("Subject not found", "error")
                return redirect(url_for('subject.list_subjects'))
            return render_template('edit_subject.html', subject=subject)
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error: {err}", "error")
        return redirect(url_for('subject.list_subjects'))
    finally:
        cursor.close()
        conn.close()

@bp.route('/delete/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    if current_user.role not in ('Dean', 'Secretary'):
        return "Unauthorized", 403

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('subject.list_subjects'))

    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM subjects WHERE subject_id = %s", (subject_id,))
        conn.commit()
        flash("Subject deleted successfully", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error: {err}", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('subject.list_subjects'))