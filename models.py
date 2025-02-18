class User:
    def __init__(self, user_id, first_name, middle_name, last_name, username, email, phone, role, date_of_birth, gender, is_active=1, student_number=None, section=None, year_level=None, semester=None, created_at=None):
        self.user_id = user_id
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.username = username  
        self.email = email
        self.phone = phone
        self.role = role
        self.date_of_birth = date_of_birth
        self.gender = gender
        self.is_active = is_active
        self.student_number = student_number
        self.section = section
        self.year_level = year_level
        self.semester = semester
        self.created_at = created_at

    def __repr__(self):
        return f"<User(user_id={self.user_id}, username='{self.username}', email='{self.email}')>"

class Subject:
    def __init__(self, subject_id, subject_code, subject_name, year_level, semester, prerequisites, created_at=None):
        self.subject_id = subject_id
        self.subject_code = subject_code
        self.subject_name = subject_name
        self.year_level = year_level
        self.semester = semester
        self.prerequisites = prerequisites
        self.created_at = created_at

    def __repr__(self):
        return f"<Subject(subject_code='{self.subject_code}')>"
