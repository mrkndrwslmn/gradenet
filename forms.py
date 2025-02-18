# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()]) 
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class AddFacultyForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Add Faculty')

class AddSubjectForm(FlaskForm):
    subject_code = StringField('Subject Code', validators=[DataRequired()])
    subject_name = StringField('Subject Name', validators=[DataRequired()])
    year_level = SelectField('Year Level', choices=[('1', '1st Year'), ('2', '2nd Year'), ('3', '3rd Year'), ('4', '4th Year')], validators=[DataRequired()])
    semester = SelectField('Semester', choices=[('1', 'First Semester'), ('2', 'Second Semester')], validators=[DataRequired()])
    prerequisites = StringField('Prerequisites')
    submit = SubmitField('Add')