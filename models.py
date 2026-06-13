from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Class(db.Model):
    __tablename__ = 'classes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(20), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)

    teacher = db.relationship('User', backref='managed_class', foreign_keys=[teacher_id])
    students = db.relationship('User', backref='student_class', lazy=True, foreign_keys='User.class_id')
    activities = db.relationship('Activity', backref='activity_class', lazy=True)
    funds = db.relationship('ClassFund', backref='fund_class', lazy=True)

    def get_student_count(self):
        return User.query.filter_by(class_id=self.id, role='student', status='approved').count()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    real_name = db.Column(db.String(80), nullable=False)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='student')
    status = db.Column(db.String(20), default='pending')
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    monitor_application = db.Column(db.String(20), default='none')

    leaves = db.relationship('Leave', backref='student', lazy=True, foreign_keys='Leave.student_id')
    reviewed_leaves = db.relationship('Leave', backref='reviewer', lazy=True, foreign_keys='Leave.reviewed_by')
    achievements = db.relationship('Achievement', backref='submitter', lazy=True, foreign_keys='Achievement.submitter_id')
    reviewed_achievements = db.relationship('Achievement', backref='reviewer', lazy=True, foreign_keys='Achievement.reviewed_by')
    activity_registrations = db.relationship('ActivityRegistration', backref='student', lazy=True)
    created_activities = db.relationship('Activity', backref='creator', lazy=True, foreign_keys='Activity.created_by')
    check_in_records = db.relationship('CheckInRecord', backref='student', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def role_name(self):
        roles = {
            'admin': '管理员',
            'teacher': '班主任',
            'monitor': '班长',
            'student': '学生'
        }
        return roles.get(self.role, '学生')

    @property
    def monitor_application_name(self):
        statuses = {
            'none': '未申请',
            'pending': '待审核',
            'approved': '已通过',
            'rejected': '已拒绝'
        }
        return statuses.get(self.monitor_application, '未知')


class ClassFund(db.Model):
    __tablename__ = 'class_funds'

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    operator = db.Column(db.String(80), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


class Achievement(db.Model):
    __tablename__ = 'achievements'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    submitter_name = db.Column(db.String(80), nullable=False)
    attachment_path = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')
    review_comment = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_public = db.Column(db.Boolean, default=False)

    @property
    def category_name(self):
        categories = {
            'academic': '学术类',
            'sports': '体育类',
            'art': '艺术类',
            'competition': '竞赛类',
            'other': '其他'
        }
        return categories.get(self.category, '其他')

    @property
    def status_name(self):
        statuses = {'pending': '待审核', 'approved': '已通过', 'rejected': '已拒绝'}
        return statuses.get(self.status, '未知')


class Activity(db.Model):
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    max_participants = db.Column(db.Integer)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='open')
    check_in_enabled = db.Column(db.Boolean, default=False)
    check_in_code = db.Column(db.String(100), nullable=True)
    activity_type = db.Column(db.String(20), default='class')

    registrations = db.relationship('ActivityRegistration', backref='activity', lazy=True)
    check_in_records = db.relationship('CheckInRecord', backref='activity', lazy=True)

    @property
    def status_name(self):
        statuses = {'open': '报名中', 'closed': '已结束', 'cancelled': '已取消'}
        return statuses.get(self.status, '未知')

    @property
    def activity_type_name(self):
        types = {
            'school': '校级活动',
            'class': '班级活动'
        }
        return types.get(self.activity_type, '未知')

    @property
    def registered_count(self):
        return ActivityRegistration.query.filter_by(activity_id=self.id, status='approved').count()



class ActivityRegistration(db.Model):
    __tablename__ = 'activity_registrations'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    check_in_time = db.Column(db.DateTime, nullable=True)


class CheckInRecord(db.Model):
    __tablename__ = 'check_in_records'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_valid = db.Column(db.Boolean, default=True)


class Leave(db.Model):
    __tablename__ = 'leaves'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    attachment_path = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')
    review_comment = db.Column(db.Text)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def status_name(self):
        statuses = {'pending': '待审核', 'approved': '已通过', 'rejected': '已拒绝'}
        return statuses.get(self.status, '未知')


def get_or_404(model, ident):
    """兼容 SQLAlchemy 2.0 的 get_or_404"""
    from flask import abort
    obj = db.session.get(model, ident)
    if obj is None:
        abort(404)
    return obj


def query_get(model, ident):
    """兼容 SQLAlchemy 2.0 的 get"""
    return db.session.get(model, ident)

