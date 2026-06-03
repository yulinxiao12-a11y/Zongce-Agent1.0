"""
综测系统 - 数据模型
User / CatalogItem / UserItem / Submission / UploadedFile
"""
from datetime import datetime, date
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), default='student')
    department = db.Column(db.String(128), default='电子与信息学院')
    class_name = db.Column(db.String(64), default='')
    gpa_score = db.Column(db.Float, nullable=True)  # 学生填写的学年必修课/限选课均分
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    submissions = db.relationship('Submission', backref='student', lazy='dynamic',
                                   foreign_keys='Submission.user_id')
    user_items = db.relationship('UserItem', backref='owner', lazy='dynamic')
    uploaded_files = db.relationship('UploadedFile', backref='owner', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.student_id} {self.name}>'


class CatalogItem(db.Model):
    __tablename__ = 'catalog_items'

    id = db.Column(db.String(8), primary_key=True)
    category = db.Column(db.String(16), nullable=False, index=True)
    subcategory = db.Column(db.String(32), default='')
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, default='')
    level = db.Column(db.String(16), index=True)
    score = db.Column(db.Float, default=0)
    icon = db.Column(db.String(32), default='fa-star')
    section = db.Column(db.String(64), default='')
    note = db.Column(db.Text, default='')
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<CatalogItem {self.id} {self.title}>'


class UserItem(db.Model):
    __tablename__ = 'user_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    catalog_item_id = db.Column(db.String(8), db.ForeignKey('catalog_items.id'), nullable=True)
    custom_title = db.Column(db.String(256), nullable=True)
    custom_score = db.Column(db.Float, nullable=True)
    score = db.Column(db.Float, nullable=False, default=0)
    source = db.Column(db.String(16), default='manual')
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=True)
    completion_date = db.Column(db.Date, nullable=True)
    academic_year = db.Column(db.String(16), default='2025-2026', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    catalog_item = db.relationship('CatalogItem', lazy='joined')

    def __repr__(self):
        return f'<UserItem {self.id} user={self.user_id} score={self.score}>'


class Submission(db.Model):
    __tablename__ = 'submissions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    catalog_item_id = db.Column(db.String(8), db.ForeignKey('catalog_items.id'), nullable=True)
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, default='')
    proof_filename = db.Column(db.String(256), nullable=True)
    proof_filepath = db.Column(db.String(512), nullable=True)
    completion_date = db.Column(db.Date, nullable=True)
    academic_year = db.Column(db.String(16), default='2025-2026', index=True)
    status = db.Column(db.String(16), default='pending', index=True)
    ai_confidence = db.Column(db.Float, default=0)
    ai_decision = db.Column(db.String(16), nullable=True)
    ai_reason = db.Column(db.Text, default='')
    ai_matched_items = db.Column(db.Text, default='[]')
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    review_remarks = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    reviewer = db.relationship('User', foreign_keys=[reviewer_id])

    def __repr__(self):
        return f'<Submission {self.id} status={self.status}>'


class UploadedFile(db.Model):
    __tablename__ = 'uploaded_files'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=True, index=True)
    proof_type = db.Column(db.String(64), nullable=True)
    original_filename = db.Column(db.String(256), nullable=False)
    stored_filename = db.Column(db.String(256), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(16), nullable=False)
    file_size = db.Column(db.Integer, default=0)
    ai_verified = db.Column(db.Boolean, default=False)
    ai_verification_note = db.Column(db.Text, default='')
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    submission = db.relationship('Submission', backref='files')

    def __repr__(self):
        return f'<UploadedFile {self.id} {self.original_filename}>'


class AuditLog(db.Model):
    """双重属性审计日志 — 记录AI模型版本+置信度+管理员操作
    按照《综测材料AI审核机制设计》"Dual-Attribution Logs"要求实现"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False, index=True)
    action_type = db.Column(db.String(32), nullable=False)  # approve|reject|needs_more|override|auto_approve
    # AI 端属性
    ai_model_version = db.Column(db.String(64), default='ai-engine-v3')
    ai_confidence = db.Column(db.Float, default=0)
    ai_decision = db.Column(db.String(16), nullable=True)
    ai_score_suggested = db.Column(db.Float, nullable=True)
    # 管理端属性
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    admin_ip = db.Column(db.String(64), nullable=True)
    admin_score_set = db.Column(db.Float, nullable=True)
    admin_decision = db.Column(db.String(16), nullable=True)
    # 偏差存证 (Override Evidence)
    override_reason = db.Column(db.String(256), nullable=True)
    override_detail = db.Column(db.Text, nullable=True)
    # 审计元数据
    remarks = db.Column(db.Text, default='')
    user_agent = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    submission = db.relationship('Submission', backref=db.backref('audit_logs', lazy='dynamic'))
    admin = db.relationship('User', foreign_keys=[admin_id])

    def __repr__(self):
        return f'<AuditLog {self.id} {self.action_type} sub={self.submission_id}>'


class CourseGrade(db.Model):
    """学生学业成绩（按学年存储，支持加权均分和GPA加分计算）"""
    __tablename__ = 'course_grades'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    academic_year = db.Column(db.String(16), nullable=False, index=True)
    course_name = db.Column(db.String(128), nullable=False)
    grade = db.Column(db.Float, nullable=False)
    credits = db.Column(db.Float, nullable=False)
    course_type = db.Column(db.String(16), nullable=False, default='必修')
    ocr_source = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('course_grades', lazy='dynamic'))

    def __repr__(self):
        return f'<CourseGrade {self.course_name} {self.grade} {self.credits}学分>'


class RegulationDoc(db.Model):
    """综测细则文件"""
    __tablename__ = 'regulation_docs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(256), nullable=False)
    original_filename = db.Column(db.String(256), nullable=False)
    stored_filename = db.Column(db.String(256), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(16), nullable=False)
    file_size = db.Column(db.Integer, default=0)
    extracted_text = db.Column(db.Text, default='')
    extracted_items = db.Column(db.Text, default='[]')
    is_current = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<RegulationDoc {self.id} {self.title}>'
