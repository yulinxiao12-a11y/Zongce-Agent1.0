"""
综测星轨 - Flask主应用
支持账号系统、文件上传、AI智能识别、审核流程
"""
import os
import re
import uuid
import json
import random
from datetime import datetime, date
from pathlib import Path
from functools import wraps

from flask import (Flask, render_template, jsonify, request, redirect,
                   url_for, flash, send_from_directory, session)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import (LoginManager, login_user, logout_user, login_required,
                         current_user, UserMixin)

from catalog import CATALOG, CAT_INFO, SUBCAT_NAMES, get_required_proofs
from models import db, User, CatalogItem, UserItem, Submission, UploadedFile, RegulationDoc, CourseGrade, AuditLog
from ai_engine import analyze_files, ai_suggest_item_fields
from competitions_data import COMPETITIONS
from activities_data import load_activities, add_activity, update_activity, delete_activity
from honor_data import load_honors, add_honor, update_honor, delete_honor

# ============================================================
# App Factory
# ============================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'zongce.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')), exist_ok=True)

db.init_app(app)

# ============================================================
# Auth Setup
# ============================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_login'
login_manager.login_message = '请先登录以访问该页面'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def handle_unauthorized():
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not authenticated'}), 401
    return redirect(url_for('auth_login'))


@app.before_request
def clear_student_view_for_admin_pages():
    if (
        current_user.is_authenticated
        and current_user.role == 'admin'
        and request.path.startswith('/admin')
        and session.get('view_as_student')
    ):
        session.pop('view_as_student', None)


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated


# ============================================================
# CLI: Initialize Database
# ============================================================

@app.cli.command('init-db')
def init_db_command():
    """初始化数据库：建表 + 种子数据 + 默认管理员"""
    with app.app_context():
        db.create_all()

        # Seed catalog from catalog.py
        existing_ids = {c.id for c in CatalogItem.query.all()}
        for item in CATALOG:
            if item['id'] not in existing_ids:
                ci = CatalogItem(
                    id=item['id'],
                    category=item['category'],
                    subcategory=item.get('subcategory', ''),
                    title=item['title'],
                    description=item.get('description', ''),
                    level=item.get('level', ''),
                    score=item.get('score', 0),
                    icon=item.get('icon', 'fa-star'),
                    section=item.get('section', ''),
                    note=item.get('note', ''),
                )
                db.session.add(ci)

        # Default admin account
        admin = User.query.filter_by(student_id='admin').first()
        if not admin:
            admin = User(
                student_id='admin',
                name='系统管理员',
                password_hash=generate_password_hash('000000'),
                role='admin',
                department='电子与信息学院',
            )
            db.session.add(admin)

        db.session.commit()
        print(f'Database initialized with {len(CATALOG)} catalog items.')
        print('Default admin: student_id=admin, password=000000')


@app.cli.command('migrate-academic-year')
def migrate_academic_year():
    """迁移：新增 CourseGrade 表 + UserItem/Submission 加 academic_year 字段"""
    with app.app_context():
        # CourseGrade 表通过 create_all 创建
        db.create_all()

        # SQLite ALTER TABLE — 检测并新增列
        def _add_column_if_missing(table, col_name, col_def):
            try:
                db.session.execute(db.text(f'ALTER TABLE {table} ADD COLUMN {col_name} {col_def}'))
                db.session.commit()
                print(f'  + Added {col_name} to {table}')
            except Exception as e:
                db.session.rollback()
                if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                    print(f'  - {col_name} already exists in {table}, skipping')
                else:
                    print(f'  ! Failed to add {col_name} to {table}: {e}')

        _add_column_if_missing('user_items', 'academic_year', "VARCHAR(16) DEFAULT '2025-2026'")
        _add_column_if_missing('submissions', 'academic_year', "VARCHAR(16) DEFAULT '2025-2026'")

        # Set default for existing rows
        for table in ['user_items', 'submissions']:
            try:
                db.session.execute(db.text(
                    f"UPDATE {table} SET academic_year = '2025-2026' WHERE academic_year IS NULL"
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()

        # Create index
        for table in ['user_items', 'submissions']:
            try:
                db.session.execute(db.text(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_academic_year ON {table} (academic_year)"
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()

        print('Academic year migration complete.')
        print('CourseGrade table created.')
        print('Existing data defaulted to academic_year=2025-2026.')


# ============================================================
# Auth Routes
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def auth_login():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        student_id = data.get('student_id', '').strip()
        password = data.get('password', '').strip()

        if not student_id or not password:
            return jsonify({'error': '请输入学号和密码'}), 400

        # student_id can repeat; try all matches
        users = User.query.filter_by(student_id=student_id, is_active=True).all()
        for user in users:
            if check_password_hash(user.password_hash, password):
                login_user(user, remember=True)
                next_url = '/admin' if user.role == 'admin' else '/'
                return jsonify({'success': True, 'redirect': next_url, 'role': user.role})

        return jsonify({'error': '学号或密码错误'}), 401

    return render_template('login.html')


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json(silent=True) or {}
    student_id = data.get('student_id', '').strip()
    password = data.get('password', '').strip()

    if not student_id or not password:
        return jsonify({'error': '请输入学号和密码'}), 400

    users = User.query.filter_by(student_id=student_id, is_active=True).all()
    for user in users:
        if check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            return jsonify({
                'success': True,
                'redirect': '/admin' if user.role == 'admin' else '/student',
                'role': user.role,
            })

    return jsonify({'error': '学号或密码错误'}), 401


@app.route('/logout')
def auth_logout():
    logout_user()
    return redirect(url_for('auth_login'))


@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    logout_user()
    return jsonify({'success': True})


@app.route('/register', methods=['POST'])
def auth_register():
    data = request.get_json(silent=True) or {}
    student_id = data.get('student_id', '').strip()
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()

    # Validation
    if not student_id or not name or not password:
        return jsonify({'error': '所有字段均为必填'}), 400
    if not re.match(r'^\d+$', student_id):
        return jsonify({'error': '学号只能包含数字'}), 400
    if not re.match(r'^[a-zA-Z0-9]{6,}$', password):
        return jsonify({'error': '密码至少6位，可包含数字和大小写字母'}), 400

    # Check for duplicate student_id + name combo (warning only, not blocking)
    existing = User.query.filter_by(student_id=student_id, name=name).first()
    if existing:
        return jsonify({'error': '该学号和姓名已注册，请直接登录'}), 400

    user = User(
        student_id=student_id,
        name=name,
        password_hash=generate_password_hash(password),
        role='student',
        department=data.get('department', '电子与信息学院'),
        class_name=data.get('class_name', ''),
    )
    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)
    return jsonify({'success': True, 'redirect': '/'})


@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    data = request.get_json(silent=True) or {}
    student_id = data.get('student_id', '').strip()
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()

    if not student_id or not name or not password:
        return jsonify({'error': '所有字段均为必填'}), 400
    if not re.match(r'^\d+$', student_id):
        return jsonify({'error': '学号只能包含数字'}), 400
    if not re.match(r'^[a-zA-Z0-9]{6,}$', password):
        return jsonify({'error': '密码至少6位，可包含数字和大小写字母'}), 400

    existing = User.query.filter_by(student_id=student_id, name=name).first()
    if existing:
        return jsonify({'error': '该学号和姓名已注册，请直接登录'}), 400

    user = User(
        student_id=student_id,
        name=name,
        password_hash=generate_password_hash(password),
        role='student',
        department=data.get('department', '电子与信息学院'),
        class_name=data.get('class_name', ''),
    )
    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)
    return jsonify({'success': True, 'redirect': '/student', 'role': user.role})


@app.route('/api/auth/me')
def api_auth_me():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify({'data': {
        'id': current_user.id,
        'student_id': current_user.student_id,
        'name': current_user.name,
        'role': current_user.role,
        'department': current_user.department,
        'class_name': current_user.class_name,
    }})


# ============================================================
# Page Routes
# ============================================================

def _redirect_admin():
    """Redirect admin to dashboard unless viewing as student"""
    if current_user.role == 'admin' and not session.get('view_as_student'):
        return redirect(url_for('admin_dashboard'))
    return None


@app.route('/view-as-student')
@login_required
def view_as_student():
    session['view_as_student'] = True
    return redirect(url_for('page_hall'))


@app.route('/back-to-admin')
@login_required
def back_to_admin():
    session.pop('view_as_student', None)
    return redirect(url_for('admin_dashboard'))


@app.route('/')
@login_required
def page_hall():
    redir = _redirect_admin()
    if redir:
        return redir
    return render_template('index.html', catalog=CATALOG,
                           cat_info=CAT_INFO, subcat_names=SUBCAT_NAMES)


@app.route('/hall')
@login_required
def page_hall_alias():
    return redirect(url_for('page_hall'))


@app.route('/personal')
@login_required
def page_personal():
    redir = _redirect_admin()
    if redir:
        return redir
    return render_template('personal.html', cat_info=CAT_INFO)


@app.route('/upload')
@login_required
def page_upload():
    redir = _redirect_admin()
    if redir:
        return redir
    return render_template('upload.html')


@app.route('/opportunities')
@login_required
def page_opportunities():
    redir = _redirect_admin()
    if redir:
        return redir
    return render_template('opportunities.html', competitions=COMPETITIONS)


@app.route('/competitions')
@login_required
def page_competitions():
    redir = _redirect_admin()
    if redir:
        return redir
    return render_template('competitions.html')


@app.route('/api/competitions')
def api_competitions():
    """返回比赛列表，支持筛选"""
    level = request.args.get('level', '')
    keyword = request.args.get('keyword', '').strip().lower()
    result = COMPETITIONS
    if level:
        result = [c for c in result if c['mapped_level'] == level]
    if keyword:
        result = [c for c in result if keyword in c['name'].lower() or keyword in c.get('organizer', '').lower()]
    return jsonify({'competitions': result, 'total': len(result)})


@app.route('/api/activities')
def api_activities():
    """返回近期活动列表"""
    activities = load_activities()
    keyword = request.args.get('keyword', '').strip().lower()
    if keyword:
        activities = [a for a in activities if keyword in a['title'].lower() or keyword in a.get('description','').lower()]
    return jsonify({'activities': activities, 'total': len(activities)})


def _activity_dimension(activity):
    text = ''.join([
        activity.get('category', ''),
        activity.get('related_score', ''),
        activity.get('title', ''),
    ])
    if any(key in text for key in ['学业', '学科', '竞赛', '证书', '科研', '论文']):
        return 'academic', '学业'
    if any(key in text for key in ['文体', '文化', '体育', '文艺', '主持']):
        return 'arts_sports', '文体'
    return 'moral', '德育'


def _activity_roi(activity):
    score_text = activity.get('related_score', '')
    numbers = [float(item) for item in re.findall(r'\d+(?:\.\d+)?', score_text)]
    if numbers:
        return round(max(3.0, min(5.0, max(numbers) / 10)), 1)
    return 3.8


def _activity_to_opportunity(activity):
    dimension, dimension_label = _activity_dimension(activity)
    activity_id = activity.get('id') or ''
    return {
        'id': activity_id,
        'source_type': 'activity',
        'source_label': '近期活动',
        'title': activity.get('title', ''),
        'category': activity.get('category', ''),
        'dimension': dimension,
        'dimension_label': dimension_label,
        'organizer': activity.get('organizer', ''),
        'location': activity.get('location', ''),
        'start_time': activity.get('date', ''),
        'deadline': activity.get('date', ''),
        'season_months': '',
        'credit_hint': activity.get('related_score', ''),
        'rule_ref': activity.get('related_score', ''),
        'official_url': activity.get('official_url', ''),
        'registration_url': activity.get('registration_url', ''),
        'contact_email': '',
        'article_url': '',
        'group_qr_url': '',
        'description': activity.get('description', ''),
        'requirements': ['活动通知', '参与证明或结果证明'],
        'tags': [item for item in [activity.get('level'), activity.get('status')] if item],
        'attachments': [],
        'images': activity.get('images', []),
        'roi_score': _activity_roi(activity),
        'in_basket': False,
        'status': activity.get('status', ''),
        'activity_id': activity_id,
    }


def _competition_to_opportunity(comp):
    """将学科竞赛分类表中的竞赛转换为 Opportunity 对象"""
    level = comp.get('mapped_level', comp.get('level', ''))
    comp_id = comp.get('id', '')
    website = comp.get('website', '').strip()
    # 使用本地生成的封面图（640x360 > 480p）
    cover_path = f'/competition-covers/{comp_id}.png'
    return {
        'id': comp_id,
        'source_type': 'competition',
        'source_label': '学科竞赛',
        'title': comp.get('name', ''),
        'category': level,
        'dimension': 'academic',
        'dimension_label': '学业',
        'organizer': comp.get('organizer', ''),
        'location': '',
        'start_time': '',
        'deadline': '',
        'season_months': '',
        'credit_hint': '学业表现：按竞赛级别和获奖证书审核加分',
        'rule_ref': f'{level}学科竞赛，按综测细则竞赛目录核验',
        'official_url': website,
        'registration_url': '',
        'contact_email': '',
        'article_url': '',
        'group_qr_url': '',
        'description': f'{comp.get("organizer", "")}主办的{level}学科竞赛' if comp.get('organizer') else f'{level}学科竞赛',
        'requirements': ['赛事通知', '报名或参赛证明', '过程材料', '获奖证书或结项证明'],
        'tags': [level, '学科竞赛'],
        'attachments': [],
        'images': [cover_path],
        'roi_score': 4.5 if '国家级' in str(level) else 3.5,
        'in_basket': False,
        'status': '常驻赛事',
        'activity_id': comp_id,
    }


def _frontend_dimension(category):
    if category == 'sports':
        return 'arts_sports'
    if category in ('moral', 'academic', 'arts_sports'):
        return category
    return 'academic'


def _dimension_meta():
    return {
        'moral': {
            'label': CAT_INFO['moral']['name'],
            'base': CAT_INFO['moral']['base'],
            'cap': CAT_INFO['moral']['extra_max'],
            'weight': 0.20,
        },
        'academic': {
            'label': CAT_INFO['academic']['name'],
            'base': CAT_INFO['academic']['base'],
            'cap': CAT_INFO['academic']['extra_max'],
            'weight': 0.65,
        },
        'arts_sports': {
            'label': CAT_INFO['sports']['name'],
            'base': CAT_INFO['sports']['base'],
            'cap': CAT_INFO['sports']['extra_max'],
            'weight': 0.15,
        },
    }


def _default_academic_year():
    """根据当前月份推断学年。9月-12月→当年-次年，1月-8月→去年-当年"""
    from datetime import date
    now = date.today()
    if now.month >= 9:
        return f'{now.year}-{now.year + 1}'
    else:
        return f'{now.year - 1}-{now.year}'


def _student_context_user():
    requested_id = request.args.get('user_id', type=int)
    if current_user.role != 'admin':
        return current_user

    requested = User.query.get(requested_id) if requested_id else None
    if requested and requested.role == 'student':
        return requested

    return (
        User.query.filter_by(role='student', is_active=True).order_by(User.id).first()
        or current_user
    )


def _all_opportunities_for_user(user):
    return (
        [_activity_to_opportunity(item) for item in load_activities()]
        + [_competition_to_opportunity(c) for c in COMPETITIONS]
    )


def _catalog_item_to_opportunity(item):
    dimension = _frontend_dimension(item.category)
    return {
        'id': f'CAT-{item.id}',
        'source_type': 'evergreen',
        'source_label': '星轨探索',
        'title': item.title,
        'category': item.section or CAT_INFO.get(item.category, {}).get('name', '综测项目'),
        'dimension': dimension,
        'dimension_label': CAT_INFO.get(item.category, {}).get('name', dimension),
        'organizer': '综测细则目录',
        'location': '',
        'start_time': '',
        'deadline': '',
        'season_months': '',
        'credit_hint': item.description or f'{item.level}项目，预计可加 {item.score:g} 分',
        'rule_ref': item.section or item.note or '',
        'official_url': '',
        'registration_url': '',
        'contact_email': '',
        'article_url': '',
        'group_qr_url': '',
        'description': item.description or item.title,
        'requirements': [
            proof.get('label') or proof.get('type') or ''
            for proof in get_required_proofs({'subcategory': item.subcategory, 'title': item.title})
            if proof.get('label') or proof.get('type')
        ],
        'tags': [value for value in [item.level, item.section] if value],
        'attachments': [],
        'images': [],
        'roi_score': float(item.score or 0),
        'in_basket': False,
        'status': '备赛规划',
        'activity_id': f'CAT-{item.id}',
        'catalog_item_id': item.id,
    }


def _find_opportunity_for_user(user, opportunity_id):
    target = str(opportunity_id)
    if target.startswith('CAT-'):
        catalog_item = CatalogItem.query.get(target[4:])
        if catalog_item and catalog_item.is_active:
            return _catalog_item_to_opportunity(catalog_item)
    for item in _all_opportunities_for_user(user):
        if str(item.get('id')) == target:
            return item
    return None


def _basket_session_key(user_id):
    return f'plan_basket_{user_id}'


EVERGREEN_COMPETITIONS = [
    {
        'id': 'EVG-EI-001',
        'title': '全国大学生电子设计竞赛',
        'category': '学科竞赛',
        'organizer': '教育部高等教育司、工业和信息化部',
        'season_months': '通常 7-8 月',
        'description': '面向电子信息类学生的综合硬件设计竞赛，适合提前准备电路、嵌入式、传感器与系统调试能力。',
        'credit_hint': '学业表现：按竞赛级别、奖项和证明材料审核加分。',
        'rule_ref': '学业附加分：国家级/省级学科竞赛按综测细则核验。',
        'official_url': 'http://nuedc.xjtu.edu.cn/',
        'images': ['/competition-covers/nuedc.png'],
        'roi_score': 4.8,
        'keywords': ['电子', '通信', '自动化', '电气', '物联网', '嵌入式', '信息'],
    },
    {
        'id': 'EVG-EI-002',
        'title': '蓝桥杯全国软件和信息技术专业人才大赛',
        'category': '程序设计',
        'organizer': '国信蓝桥教育科技',
        'season_months': '通常 3-6 月',
        'description': '覆盖软件、电子、嵌入式等赛道，适合计算机、电子信息、物联网方向学生长期刷题备赛。',
        'credit_hint': '学业表现：按获奖级别和获奖证书审核。',
        'rule_ref': '学业附加分：学科竞赛获奖按竞赛目录和奖项等级核验。',
        'official_url': 'https://dasai.lanqiao.cn/',
        'images': ['https://assets.lanqiao.cn/lanqiaobei-fe/v8.5.3/dist/favico.png'],
        'roi_score': 4.4,
        'keywords': ['软件', '计算机', '电子', '信息', '物联网', '人工智能'],
    },
    {
        'id': 'EVG-EI-003',
        'title': '中国大学生计算机设计大赛',
        'category': '软件开发',
        'organizer': '中国教育电视台等',
        'season_months': '通常 3-8 月',
        'description': '以计算机应用设计为核心，适合做 Web、移动应用、数据可视化、AI 应用和数字媒体项目。',
        'credit_hint': '学业表现：以参赛证明、作品材料、获奖证书作为审核依据。',
        'rule_ref': '学业附加分：计算机类竞赛按国家级/省级/校级奖项核验。',
        'official_url': 'https://jsjds.blcu.edu.cn/',
        'images': ['https://jsjds.blcu.edu.cn/images/banner11.PNG'],
        'roi_score': 4.2,
        'keywords': ['计算机', '软件', '人工智能', '信息', '网络', '数据'],
    },
    {
        'id': 'EVG-EI-004',
        'title': '全国大学生信息安全竞赛',
        'category': '信息安全',
        'organizer': '信息安全类专业教学指导委员会',
        'season_months': '通常 4-8 月',
        'description': '覆盖作品赛与攻防实践，适合网络工程、信息安全、计算机和电子信息方向学生积累安全项目。',
        'credit_hint': '学业表现：按竞赛通知、参赛记录、获奖证书和综测细则审核。',
        'rule_ref': '学业附加分：信息安全竞赛按学科竞赛获奖标准核验。',
        'official_url': 'https://www.ciscn.cn/',
        'images': ['https://www.ciscn.cn/uploads/banner/2025-banner.jpg'],
        'roi_score': 4.1,
        'keywords': ['安全', '网络', '计算机', '软件', '信息'],
    },
    {
        'id': 'EVG-EI-005',
        'title': '全国大学生数学建模竞赛',
        'category': '数学建模',
        'organizer': '中国工业与应用数学学会',
        'season_months': '通常 9 月',
        'description': '三人组队完成建模、求解与论文撰写，适合电子信息、计算机、数据分析方向提前训练算法和表达。',
        'credit_hint': '学业表现：按建模竞赛级别、获奖证书和材料完整性审核。',
        'rule_ref': '学业附加分：数学建模竞赛按获奖等级核验。',
        'official_url': 'https://www.mcm.edu.cn/',
        'images': ['https://www.mcm.edu.cn/theme/mcm/image/top_cn.jpg'],
        'roi_score': 4.0,
        'keywords': ['数学', '统计', '计算机', '电子', '信息', '数据'],
    },
    {
        'id': 'EVG-EI-006',
        'title': '全国大学生物联网设计竞赛',
        'category': '物联网',
        'organizer': '全国高等学校计算机教育研究会',
        'season_months': '通常 4-9 月',
        'description': '围绕感知、通信、平台和应用完成物联网系统方案，适合电子、通信、嵌入式与软件协同项目。',
        'credit_hint': '学业表现：以作品、参赛证明和获奖证书审核。',
        'rule_ref': '学业附加分：物联网与电子信息类竞赛按细则核验。',
        'official_url': 'http://iot.sjtu.edu.cn/',
        'images': ['https://iot.sjtu.edu.cn/favicon.ico'],
        'roi_score': 4.0,
        'keywords': ['物联网', '电子', '通信', '嵌入式', '信息'],
    },
    {
        'id': 'EVG-GEN-001',
        'title': '挑战杯系列竞赛',
        'category': '创新创业',
        'organizer': '共青团中央等',
        'season_months': '大挑（学术科研·奇数年）/ 小挑（创业计划·偶数年）',
        'description': '覆盖学术科技作品和创业计划，适合把课程项目、科研训练或社会实践沉淀为可参赛成果。',
        'credit_hint': '学业表现或德育表现：按项目属性、证明材料和获奖等级审核。',
        'rule_ref': '综测加分以学院通知、竞赛目录和最终获奖证明为准。',
        'official_url': 'https://tiaozhanbei.net/',
        'images': [],
        'roi_score': 3.9,
        'keywords': ['创新', '创业', '管理', '设计'],
    },
    {
        'id': 'EVG-GEN-002',
        'title': 'RoboMaster 机甲大师高校系列赛',
        'category': '机器人',
        'organizer': '大疆创新',
        'season_months': '通常全年分阶段',
        'description': '大型机器人竞赛与工程项目，适合机械、电子、控制、视觉算法和软件协同能力训练。',
        'credit_hint': '学业表现：按赛事级别、队伍证明、获奖证书和贡献材料审核。',
        'rule_ref': '学业附加分：机器人与工程实践竞赛按奖项等级核验。',
        'official_url': 'https://www.robomaster.com/zh-CN',
        'images': ['https://rm-static.djicdn.com/documents/55708/6d77a3be8b2431741835508145145792.png'],
        'roi_score': 3.8,
        'keywords': ['机器人', '自动化', '电子', '机械', '控制', '计算机'],
    },
]


def _competition_dimension(item):
    if item['category'] in ['创新创业']:
        return 'academic', '学业'
    return 'academic', '学业'


def _recommended_evergreen_opportunities(user):
    profile = ' '.join([
        getattr(user, 'department', '') or '',
        getattr(user, 'class_name', '') or '',
        getattr(user, 'name', '') or '',
    ])
    ranked = []
    for index, item in enumerate(EVERGREEN_COMPETITIONS):
        score = sum(1 for keyword in item['keywords'] if keyword and keyword in profile)
        if score == 0 and any(key in profile for key in ['电子', '信息', '计算机', '通信', '软件']):
            score = 1 if item['id'].startswith('EVG-EI') else 0
        ranked.append((score, -index, item))
    selected = [item for score, _, item in sorted(ranked, reverse=True) if score > 0]
    if len(selected) < 6:
        selected.extend(item for _, _, item in ranked if item not in selected)
    opportunities = []
    for item in selected[:8]:
        dimension, dimension_label = _competition_dimension(item)
        opportunities.append({
            'id': item['id'],
            'source_type': 'evergreen',
            'source_label': '常驻赛事',
            'title': item['title'],
            'category': item['category'],
            'dimension': dimension,
            'dimension_label': dimension_label,
            'organizer': item['organizer'],
            'location': '',
            'start_time': '',
            'deadline': '',
            'season_months': item['season_months'],
            'credit_hint': item['credit_hint'],
            'rule_ref': item['rule_ref'],
            'official_url': item['official_url'],
            'registration_url': '',
            'contact_email': '',
            'article_url': '',
            'group_qr_url': '',
            'description': item['description'],
            'requirements': ['赛事通知', '报名或参赛证明', '过程材料', '获奖证书或结项证明'],
            'tags': ['AI专业推荐', item['category'], item['season_months']],
            'attachments': [],
            'images': item.get('images', []),
            'roi_score': item['roi_score'],
            'in_basket': False,
            'status': '常驻准备',
            'activity_id': item['id'],
        })
    return opportunities


@app.route('/api/opportunities', methods=['GET', 'POST'])
@login_required
def api_opportunities_compat():
    """Vue 学生端机会大厅兼容接口：近期活动=管理员发布的活动，学科竞赛=竞赛分类表。"""
    if request.method == 'GET':
        source_type = request.args.get('source_type', '')
        category = request.args.get('category', '')
        dimension = request.args.get('dimension', '')
        keyword = request.args.get('keyword', '').strip().lower()

        opportunities = (
            [_activity_to_opportunity(item) for item in load_activities()]
            + [_competition_to_opportunity(c) for c in COMPETITIONS]
        )
        if source_type:
            opportunities = [item for item in opportunities if item['source_type'] == source_type]
        if category:
            opportunities = [item for item in opportunities if item['category'] == category]
        if dimension:
            opportunities = [item for item in opportunities if item['dimension'] == dimension]
        if keyword:
            opportunities = [
                item for item in opportunities
                if keyword in item['title'].lower() or keyword in item.get('description', '').lower()
            ]
        return jsonify(opportunities)

    data = request.get_json(silent=True) or {}
    if not data.get('title'):
        return jsonify({'error': '活动标题不能为空'}), 400

    activity = add_activity({
        'title': data.get('title', ''),
        'category': data.get('category') or data.get('dimension_label') or '院级活动',
        'level': data.get('award_level') or data.get('level') or '院级',
        'date': data.get('deadline') or data.get('start_time') or '',
        'organizer': data.get('organizer', ''),
        'description': data.get('description', ''),
        'status': data.get('status') or '即将开始',
        'related_score': data.get('credit_hint') or data.get('rule_ref') or '',
        'images': data.get('images', []),
        'location': data.get('location', ''),
        'official_url': data.get('official_url', ''),
        'registration_url': data.get('registration_url', ''),
    })
    return jsonify(_activity_to_opportunity(activity)), 201


@app.route('/api/dashboard/summary')
@login_required
def api_dashboard_summary():
    user = _student_context_user()
    academic_year = request.args.get('academic_year', _default_academic_year())
    meta = _dimension_meta()
    totals = {key: 0.0 for key in meta}
    ledgers = []

    user_items = UserItem.query.filter_by(
        user_id=user.id, academic_year=academic_year
    ).order_by(UserItem.created_at.desc()).all()
    for item in user_items:
        catalog_item = item.catalog_item
        dimension = _frontend_dimension(catalog_item.category if catalog_item else '')
        totals[dimension] += float(item.score or 0)
        ledgers.append({
            'title': (catalog_item.title if catalog_item else item.custom_title) or '',
            'dimension': dimension,
            'score': float(item.score or 0),
            'rule_ref': (catalog_item.section if catalog_item else item.source) or '',
        })

    # ── 学业基础分 + 绩点加分：优先使用 CourseGrade 计算 ──
    gpa_info = {
        'score': user.gpa_score,
        'bonus': 0,
        'tier': '',
        'weighted_average': None,
        'academic_base': None,
        'from_courses': False,
    }
    courses = CourseGrade.query.filter_by(
        user_id=user.id, academic_year=academic_year
    ).all()

    if courses:
        total_weighted = sum(c.grade * c.credits for c in courses)
        total_credits = sum(c.credits for c in courses)
        weighted_avg = round(total_weighted / total_credits, 2) if total_credits > 0 else 0
        academic_base = round(min(80.0, weighted_avg * 0.8), 2)

        # GPA bonus: only check 必修+限选
        required = [c for c in courses if c.course_type in ('必修', '限选')]
        req_total_weighted = sum(c.grade * c.credits for c in required)
        req_total_credits = sum(c.credits for c in required)
        req_avg = round(req_total_weighted / req_total_credits, 2) if req_total_credits > 0 else 0

        bonus = 0
        tier = ''
        if req_avg >= 85 and all(c.grade >= 75 for c in required):
            bonus, tier = 5, '均分≥85且单科≥75'
        elif req_avg >= 80 and all(c.grade >= 70 for c in required):
            bonus, tier = 3, '均分≥80且单科≥70'
        elif req_avg >= 75 and all(c.grade >= 70 for c in required):
            bonus, tier = 2, '均分≥75且单科≥70'

        gpa_info = {
            'score': req_avg,
            'bonus': bonus,
            'tier': tier,
            'weighted_average': weighted_avg,
            'academic_base': academic_base,
            'from_courses': True,
            'course_count': len(courses),
        }

        # Replace academic base: use course-based computation
        # totals['academic'] tracks ONLY extra items (catalog + GPA bonus)
        # academic_base replaces the fixed base=80 in the details loop
        # Do NOT add academic_base to totals — it's the base, not an extra

        if bonus > 0:
            totals['academic'] += bonus
            ledgers.append({
                'title': f'必修限选加权均分{req_avg}（{tier}）',
                'dimension': 'academic',
                'score': bonus,
                'rule_ref': '学业成绩加分',
            })
        ledgers.append({
            'title': f'学业基本分（加权均分{weighted_avg}×0.8）',
            'dimension': 'academic',
            'score': academic_base,
            'rule_ref': '学业基础分',
            'kind': 'base',  # 标记为基础分，前端分布图排除
        })
    elif user.gpa_score is not None and user.gpa_score > 0:
        # Fallback: old single-value GPA
        avg = user.gpa_score
        if avg >= 85:
            gpa_info['bonus'] = 5
            gpa_info['tier'] = '均分≥85且单科≥75'
        elif avg >= 80:
            gpa_info['bonus'] = 3
            gpa_info['tier'] = '均分≥80且单科≥70'
        elif avg >= 75:
            gpa_info['bonus'] = 2
            gpa_info['tier'] = '均分≥75且单科≥70'
        if gpa_info['bonus'] > 0:
            totals['academic'] += gpa_info['bonus']
            ledgers.append({
                'title': f'必修课/限选课均分{avg:.1f}（{gpa_info["tier"]}）',
                'dimension': 'academic',
                'score': gpa_info['bonus'],
                'rule_ref': '学业成绩加分',
            })

    details = []
    weighted_total = 0.0
    for key, info in meta.items():
        raw_add = totals[key]
        normalized_add = min(raw_add, float(info['cap']))
        deduction = 0.0
        # 学业：使用课程数据计算的基本分替代固定80分
        if key == 'academic' and gpa_info.get('from_courses') and gpa_info.get('academic_base') is not None:
            effective_base = gpa_info['academic_base']
        else:
            effective_base = float(info['base'])
        score = max(0.0, min(100.0, effective_base + normalized_add - deduction))
        weighted = score * float(info['weight'])
        weighted_total += weighted
        details.append({
            'key': key,
            'label': info['label'],
            'base': round(effective_base, 2),
            'raw_add': round(raw_add, 2),
            'normalized_add': round(normalized_add, 2),
            'deduction': 0,
            'score': round(score, 2),
            'weight': info['weight'],
            'weighted': round(weighted, 2),
            'cap': info['cap'],
        })

    pending_statuses = ['pending', 'pending_ai', 'pending_human', 'needs_more']
    pending = Submission.query.filter(
        Submission.user_id == user.id,
        Submission.academic_year == academic_year,
        Submission.status.in_(pending_statuses),
    ).order_by(Submission.created_at.desc()).all()
    pending_score = 0.0
    for item in pending:
        if item.catalog_item_id:
            catalog_item = CatalogItem.query.get(item.catalog_item_id)
            if catalog_item:
                pending_score += float(catalog_item.score or 0)

    total = round(weighted_total, 2)
    return jsonify({
        'user': {
            'name': user.name,
            'college': user.department,
            'major': user.class_name,
        },
        'score': {
            'rule_version': '2025-07-electronic-info',
            'total': total,
            'details': details,
        },
        'academic_year': academic_year,
        'gpa_info': gpa_info,
        'scoring_rules': {
            'formula': '品德行为表现×20% + 学业表现×65% + 文体表现×15%',
            'dimensions': [
                {'key': k, 'label': v['label'], 'base': v['base'], 'cap': v['cap'], 'weight': v['weight']}
                for k, v in meta.items()
            ],
            'note': '学业基本分=加权均分×0.8(满分80)；GPA加分需同时满足必修限选均分和单科最低分条件。',
        },
        'pending_score': round(pending_score, 2),
        'goal_gap': max(0, round(90 - total, 2)),
        'ledgers': ledgers,
        'pending_applications': [_submission_to_certification(item) for item in pending],
    })


@app.route('/api/plan-basket', methods=['GET', 'POST'])
@login_required
def api_plan_basket():
    user = _student_context_user()
    key = _basket_session_key(user.id)
    basket = session.get(key, [])

    if request.method == 'GET':
        rows = []
        for item in basket:
            opportunity = _find_opportunity_for_user(user, item.get('opportunity_id'))
            if opportunity:
                rows.append({
                    'id': item.get('id'),
                    'stage': item.get('stage') or '想参加',
                    'note': item.get('note') or '',
                    'opportunity': opportunity,
                })
        return jsonify(rows)

    data = request.get_json(silent=True) or {}
    catalog_item_id = data.get('catalog_item_id')
    opportunity_id = f'CAT-{catalog_item_id}' if catalog_item_id else data.get('opportunity_id')
    opportunity = _find_opportunity_for_user(user, opportunity_id)
    if not opportunity:
        return jsonify({'error': '机会不存在'}), 404

    for item in basket:
        if str(item.get('opportunity_id')) == str(opportunity_id):
            return jsonify({
                'id': item.get('id'),
                'stage': item.get('stage') or '想参加',
                'note': item.get('note') or '',
                'opportunity': opportunity,
            })

    item = {
        'id': int(datetime.utcnow().timestamp() * 1000),
        'opportunity_id': opportunity_id,
        'stage': data.get('stage') or '想参加',
        'note': data.get('note') or '',
    }
    basket.append(item)
    session[key] = basket
    session.modified = True
    return jsonify({
        'id': item['id'],
        'stage': item['stage'],
        'note': item['note'],
        'opportunity': opportunity,
    }), 201


@app.route('/api/plan-basket/<int:item_id>', methods=['PATCH', 'DELETE'])
@login_required
def api_plan_basket_detail(item_id):
    user = _student_context_user()
    key = _basket_session_key(user.id)
    basket = session.get(key, [])
    item = next((row for row in basket if int(row.get('id', 0)) == item_id), None)
    if not item:
        return jsonify({'error': '清单条目不存在'}), 404

    if request.method == 'DELETE':
        session[key] = [row for row in basket if int(row.get('id', 0)) != item_id]
        session.modified = True
        return jsonify({'success': True})

    data = request.get_json(silent=True) or {}
    item['stage'] = data.get('stage', item.get('stage') or '想参加')
    item['note'] = data.get('note', item.get('note') or '')
    session[key] = basket
    session.modified = True
    opportunity = _find_opportunity_for_user(user, item.get('opportunity_id'))
    return jsonify({
        'id': item['id'],
        'stage': item['stage'],
        'note': item['note'],
        'opportunity': opportunity,
    })


def _honor_owner_id():
    return request.args.get('user_id') or (request.get_json(silent=True) or {}).get('user_id') or current_user.id


@app.route('/api/honor-wall', methods=['GET', 'POST'])
@login_required
def api_honor_wall():
    if request.method == 'GET':
        return jsonify(load_honors(_honor_owner_id()))

    data = request.get_json(silent=True) or {}
    if not data.get('title'):
        return jsonify({'error': '荣誉标题不能为空'}), 400
    return jsonify(add_honor(_honor_owner_id(), data)), 201


@app.route('/api/honor-wall/<int:honor_id>', methods=['PATCH', 'PUT', 'DELETE'])
@login_required
def api_honor_wall_detail(honor_id):
    if request.method == 'DELETE':
        if not delete_honor(_honor_owner_id(), honor_id):
            return jsonify({'error': '荣誉记录不存在'}), 404
        return jsonify({'success': True})

    data = request.get_json(silent=True) or {}
    item = update_honor(_honor_owner_id(), honor_id, data)
    if not item:
        return jsonify({'error': '荣誉记录不存在'}), 404
    return jsonify(item)


@app.route('/api/admin/activities', methods=['GET', 'POST'])
@admin_required
def api_admin_activities():
    if request.method == 'GET':
        return jsonify({'activities': load_activities()})
    elif request.method == 'POST':
        data = request.get_json()
        if not data.get('title'):
            return jsonify({'error': '活动标题不能为空'}), 400
        act = add_activity(data)
        return jsonify({'success': True, 'activity': act})


@app.route('/api/admin/activities/<act_id>', methods=['PUT', 'DELETE'])
@admin_required
def api_admin_activity_detail(act_id):
    if request.method == 'PUT':
        data = request.get_json()
        act = update_activity(act_id, data)
        if not act:
            return jsonify({'error': '活动不存在'}), 404
        return jsonify({'success': True, 'activity': act})
    elif request.method == 'DELETE':
        delete_activity(act_id)
        return jsonify({'success': True})


@app.route('/api/admin/activities/ai-fill', methods=['POST'])
@admin_required
def api_admin_activity_ai_fill():
    """AI智能填充活动信息"""
    data = request.get_json()
    name = data.get('name', '')
    desc = data.get('description', '')
    suggestion = ai_suggest_item_fields(name, desc)
    return jsonify(suggestion)


# ============================================================
# Admin Page Routes
# ============================================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    return redirect(url_for('admin_submissions_page'))


@app.route('/admin/submissions')
@admin_required
def admin_submissions_page():
    return render_template('admin_submissions.html')


@app.route('/admin/users')
@admin_required
def admin_users_page():
    return render_template('admin_users.html')


@app.route('/admin/items')
@admin_required
def admin_items_page():
    return render_template('admin_items.html', cat_info=CAT_INFO, subcat_names=SUBCAT_NAMES)


@app.route('/admin/activities')
@admin_required
def admin_activities_page():
    return render_template('admin_activities.html')


@app.route('/admin/regulations')
@admin_required
def admin_regulations_page():
    return render_template('admin_regulations.html')


# ============================================================
# API: Regulations
# ============================================================

@app.route('/api/admin/regulations', methods=['GET', 'POST'])
@admin_required
def api_admin_regulations():
    if request.method == 'GET':
        docs = RegulationDoc.query.order_by(RegulationDoc.uploaded_at.desc()).all()
        return jsonify({'regulations': [{
            'id': d.id, 'title': d.title, 'original_filename': d.original_filename,
            'file_type': d.file_type, 'file_size': d.file_size,
            'is_current': d.is_current,
            'extracted_items_count': len(json.loads(d.extracted_items or '[]')),
            'uploaded_at': d.uploaded_at.strftime('%Y-%m-%d %H:%M'),
        } for d in docs]})
    # POST: upload new regulation file
    if 'file' not in request.files:
        return jsonify({'error': '请选择文件'}), 400
    f = request.files['file']
    if not f or not f.filename:
        return jsonify({'error': '请选择文件'}), 400
    ext = f.filename.rsplit('.', 1)[1].lower() if '.' in f.filename else ''
    if ext not in ('pdf', 'docx', 'doc', 'txt', 'jpg', 'jpeg', 'png'):
        return jsonify({'error': '不支持的文件格式，请上传 PDF/DOCX/TXT/图片'}), 400

    sfn = f"{uuid.uuid4().hex}.{ext}"
    reg_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'regulations')
    os.makedirs(reg_dir, exist_ok=True)
    fp = os.path.join(reg_dir, sfn)
    f.save(fp)

    title = request.form.get('title', '').strip() or f.filename

    # 提取文字
    from ai_engine import extract_text_from_file
    extracted = extract_text_from_file(fp, ext)

    doc = RegulationDoc(
        title=title, original_filename=f.filename, stored_filename=sfn,
        file_path=os.path.join('regulations', sfn), file_type=ext,
        file_size=os.path.getsize(fp), extracted_text=extracted,
        is_current=RegulationDoc.query.count() == 0,
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify({'success': True, 'id': doc.id, 'extracted_text': extracted[:500]})


@app.route('/api/admin/regulations/<int:doc_id>', methods=['GET', 'DELETE'])
@admin_required
def api_admin_regulation_detail(doc_id):
    doc = RegulationDoc.query.get_or_404(doc_id)
    if request.method == 'GET':
        items = json.loads(doc.extracted_items or '[]')
        return jsonify({
            'id': doc.id, 'title': doc.title, 'original_filename': doc.original_filename,
            'file_type': doc.file_type, 'extracted_text': doc.extracted_text,
            'extracted_items': items, 'is_current': doc.is_current,
            'file_path': doc.file_path, 'uploaded_at': doc.uploaded_at.strftime('%Y-%m-%d %H:%M'),
        })
    # DELETE
    fp = os.path.join(app.config['UPLOAD_FOLDER'], doc.file_path)
    if os.path.exists(fp):
        os.remove(fp)
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/regulations/<int:doc_id>/extract', methods=['POST'])
@admin_required
def api_admin_regulation_extract(doc_id):
    """AI 提取细则中的综测项目"""
    doc = RegulationDoc.query.get_or_404(doc_id)
    text = doc.extracted_text
    if not text.strip():
        return jsonify({'error': '未能从文件中提取文字，请确认文件包含可识别文本'}), 400

    # 先用规则提取，再用 Claude 增强
    from ai_engine import extract_regulation_items, extract_regulation_items_llm
    items = extract_regulation_items(text)
    llm_items = extract_regulation_items_llm(text)

    # 合并：Claude 结果优先（去重）
    existing_titles = {it['title'] for it in items}
    for ci in llm_items:
        if ci['title'] not in existing_titles:
            items.append(ci)
            existing_titles.add(ci['title'])

    doc.extracted_items = json.dumps(items, ensure_ascii=False)
    db.session.commit()
    return jsonify({'success': True, 'items': items, 'total': len(items)})


@app.route('/api/admin/regulations/<int:doc_id>/apply', methods=['POST'])
@admin_required
def api_admin_regulation_apply(doc_id):
    """将提取的项目批量添加到综测目录"""
    doc = RegulationDoc.query.get_or_404(doc_id)
    data = request.get_json()
    items_to_apply = data.get('items', [])

    added = 0
    for it in items_to_apply:
        # 生成新 ID
        cat_prefix = {'moral': 'M', 'academic': 'A', 'sports': 'S'}.get(it.get('category', ''), 'X')
        existing = CatalogItem.query.order_by(CatalogItem.id.desc()).first()
        last_num = int(existing.id[1:]) if existing and existing.id[1:].isdigit() else 0
        new_id = f"{cat_prefix}{last_num + 1 + added:03d}"

        if not CatalogItem.query.get(new_id):
            db.session.add(CatalogItem(
                id=new_id,
                category=it.get('category', 'academic'),
                subcategory=it.get('subcategory', ''),
                title=it.get('title', ''),
                description=it.get('description', ''),
                level=it.get('level', '校级'),
                score=it.get('score', 1),
                icon=it.get('icon', 'fa-star'),
                section=it.get('section', ''),
                note=it.get('note', ''),
            ))
            added += 1

    doc.is_current = True
    # 取消其他文件的 is_current
    RegulationDoc.query.filter(RegulationDoc.id != doc_id).update({'is_current': False})
    db.session.commit()
    return jsonify({'success': True, 'added': added})


@app.route('/api/admin/regulations/<int:doc_id>/file')
@admin_required
def api_admin_regulation_file(doc_id):
    """查看/下载细则文件"""
    doc = RegulationDoc.query.get_or_404(doc_id)
    directory = os.path.join(app.config['UPLOAD_FOLDER'], 'regulations')
    return send_from_directory(directory, doc.stored_filename,
                               download_name=doc.original_filename)


@app.route('/api/admin/regulations/current')
@admin_required
def api_admin_regulation_current():
    """获取当前生效的细则"""
    doc = RegulationDoc.query.filter_by(is_current=True).first()
    if not doc:
        return jsonify({'error': '暂无细则文件'}), 404
    return jsonify({
        'id': doc.id, 'title': doc.title,
        'original_filename': doc.original_filename,
        'uploaded_at': doc.uploaded_at.strftime('%Y-%m-%d %H:%M'),
        'file_path': f'/api/admin/regulations/{doc.id}/file',
    })


# ============================================================
# API: Academic Years
# ============================================================

@app.route('/api/academic-years')
@login_required
def api_academic_years():
    """返回用户所有有数据的学年 + 系统默认的学年列表"""
    user = _student_context_user()
    years_set = set()

    # 从 course_grades 收集学年
    from models import CourseGrade
    cg_years = db.session.query(CourseGrade.academic_year).filter(
        CourseGrade.user_id == user.id
    ).distinct().all()
    for (y,) in cg_years:
        if y:
            years_set.add(y)

    # 从 user_items 收集学年
    ui_years = db.session.query(UserItem.academic_year).filter(
        UserItem.user_id == user.id
    ).distinct().all()
    for (y,) in ui_years:
        if y:
            years_set.add(y)

    # 从 submissions 收集学年
    sub_years = db.session.query(Submission.academic_year).filter(
        Submission.user_id == user.id
    ).distinct().all()
    for (y,) in sub_years:
        if y:
            years_set.add(y)

    # 生成默认学年列表（当前+前3年）
    current = _default_academic_year()
    cy = int(current.split('-')[0])
    default_years = [f'{cy - i}-{cy - i + 1}' for i in range(4)]
    all_years = sorted(set(default_years) | years_set, reverse=True)

    return jsonify({
        'years': all_years,
        'current': current,
    })


# ============================================================
# API: Course Grades (学业成绩)
# ============================================================

@app.route('/api/course-grades', methods=['GET', 'POST'])
@login_required
def api_course_grades():
    from models import CourseGrade
    user = _student_context_user()
    academic_year = request.args.get('academic_year', _default_academic_year()) \
        if request.method == 'GET' else None

    if request.method == 'GET':
        courses = CourseGrade.query.filter_by(
            user_id=user.id, academic_year=academic_year
        ).order_by(CourseGrade.course_type.asc(), CourseGrade.course_name.asc()).all()

        course_list = [{
            'id': c.id,
            'course_name': c.course_name,
            'grade': c.grade,
            'credits': c.credits,
            'course_type': c.course_type,
            'ocr_source': c.ocr_source,
        } for c in courses]

        # 计算
        comp = _compute_course_summary(courses)

        return jsonify({
            'academic_year': academic_year,
            'courses': course_list,
            'course_count': len(courses),
            **comp,
        })

    # POST: Replace all courses for a given academic_year
    data = request.get_json()
    academic_year = data.get('academic_year', _default_academic_year())
    course_list = data.get('courses', [])

    if not course_list:
        return jsonify({'error': '课程列表不能为空'}), 400

    # Validate courses
    valid_types = ('必修', '限选', '任选', '公选')
    for i, c in enumerate(course_list):
        if not c.get('course_name', '').strip():
            return jsonify({'error': f'第{i+1}门课程名称为空'}), 400
        grade = c.get('grade')
        credits = c.get('credits')
        if grade is None or not (0 <= float(grade) <= 100):
            return jsonify({'error': f'课程"{c.get("course_name")}"成绩必须在0-100之间'}), 400
        if credits is None or not (0 < float(credits) <= 15):
            return jsonify({'error': f'课程"{c.get("course_name")}"学分必须在0.5-15之间'}), 400
        if c.get('course_type', '必修') not in valid_types:
            return jsonify({'error': f'课程"{c.get("course_name")}"类型无效'}), 400

    # Delete existing courses for this user+year
    CourseGrade.query.filter_by(
        user_id=user.id, academic_year=academic_year
    ).delete()

    # Insert new courses
    for c in course_list:
        course = CourseGrade(
            user_id=user.id,
            academic_year=academic_year,
            course_name=c['course_name'].strip(),
            grade=float(c['grade']),
            credits=float(c['credits']),
            course_type=c.get('course_type', '必修'),
            ocr_source=c.get('ocr_source', False),
        )
        db.session.add(course)
    db.session.commit()

    # Return computation
    courses = CourseGrade.query.filter_by(
        user_id=user.id, academic_year=academic_year
    ).all()
    comp = _compute_course_summary(courses)

    return jsonify({
        'success': True,
        'academic_year': academic_year,
        'course_count': len(courses),
        **comp,
    })


@app.route('/api/course-grades/ocr', methods=['POST'])
@login_required
def api_course_grades_ocr():
    """OCR识别成绩单：接受已上传的 file_ids，返回识别出的课程列表（不保存）"""
    from models import CourseGrade
    from ai_engine import extract_text_from_file, extract_courses_from_ocr_text

    data = request.get_json()
    file_ids = data.get('uploaded_file_ids', [])
    if not file_ids:
        return jsonify({'error': '请先上传文件'}), 400

    files = UploadedFile.query.filter(
        UploadedFile.id.in_(file_ids),
        UploadedFile.user_id == current_user.id,
    ).all()

    if not files:
        return jsonify({'error': '文件不存在'}), 404

    results = []
    for f in files:
        try:
            # 使用已有的 OCR 函数提取文字
            ocr_text = extract_text_from_file(f.file_path, f.file_type)
            # 从 OCR 文字中提取课程
            courses = extract_courses_from_ocr_text(ocr_text or '')

            results.append({
                'file_id': f.id,
                'file_name': f.original_filename,
                'extracted_text_preview': (ocr_text or '')[:500],
                'courses': courses,
            })
        except Exception as e:
            results.append({
                'file_id': f.id,
                'file_name': f.original_filename,
                'error': str(e),
                'courses': [],
            })

    return jsonify({'results': results})


def _compute_course_summary(courses):
    """根据课程列表计算加权均分、学业基本分、GPA加分"""
    if not courses:
        return {
            'weighted_average': None,
            'academic_base_score': None,
            'gpa_bonus': 0,
            'gpa_tier': '',
            'required_courses_avg': None,
            'required_min_grade': None,
            'all_required_pass': False,
        }

    total_weighted = sum(c.grade * c.credits for c in courses)
    total_credits = sum(c.credits for c in courses)
    weighted_avg = round(total_weighted / total_credits, 2) if total_credits > 0 else 0
    academic_base = round(min(80.0, weighted_avg * 0.8), 2)

    required = [c for c in courses if c.course_type in ('必修', '限选')]
    if required:
        req_weighted = sum(c.grade * c.credits for c in required)
        req_credits = sum(c.credits for c in required)
        req_avg = round(req_weighted / req_credits, 2) if req_credits > 0 else 0
        req_min = round(min(c.grade for c in required), 1)
    else:
        req_avg = None
        req_min = None

    bonus = 0
    tier = ''
    if required:
        if req_avg >= 85 and all(c.grade >= 75 for c in required):
            bonus, tier = 5, '均分≥85且单科≥75'
        elif req_avg >= 80 and all(c.grade >= 70 for c in required):
            bonus, tier = 3, '均分≥80且单科≥70'
        elif req_avg >= 75 and all(c.grade >= 70 for c in required):
            bonus, tier = 2, '均分≥75且单科≥70'

    return {
        'weighted_average': weighted_avg,
        'academic_base_score': academic_base,
        'gpa_bonus': bonus,
        'gpa_tier': tier,
        'required_courses_avg': req_avg,
        'required_min_grade': req_min,
        'all_required_pass': required and all(c.grade >= 70 for c in required) if required else False,
    }


# ============================================================
# API: Catalog
# ============================================================

@app.route('/api/catalog')
def api_catalog():
    category = request.args.get('category', '')
    level = request.args.get('level', '')
    subcategory = request.args.get('subcategory', '')
    section = request.args.get('section', '')
    keyword = request.args.get('keyword', '').strip().lower()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 300, type=int)

    query = CatalogItem.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    if level:
        query = query.filter_by(level=level)
    if subcategory:
        query = query.filter_by(subcategory=subcategory)
    if section:
        query = query.filter_by(section=section)
    if keyword:
        query = query.filter(
            db.or_(
                CatalogItem.title.contains(keyword),
                CatalogItem.description.contains(keyword),
                CatalogItem.section.contains(keyword),
            )
        )

    pagination = query.order_by(
        db.case({'国家级': 5, '省级': 4, '校级': 3, '院级': 2, '班级': 1},
                value=CatalogItem.level).desc(),
        CatalogItem.score.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    items = []
    for item in pagination.items:
        items.append({
            'id': item.id,
            'category': item.category,
            'category_name': CAT_INFO.get(item.category, {}).get('name', ''),
            'subcategory': item.subcategory,
            'subcategory_name': SUBCAT_NAMES.get(item.subcategory, item.subcategory),
            'title': item.title,
            'description': item.description,
            'level': item.level,
            'score': item.score,
            'icon': item.icon,
            'section': item.section,
            'note': item.note,
            'required_proofs': get_required_proofs({
                'subcategory': item.subcategory,
            }),
        })

    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'filters': {
            'categories': [{'key': k, 'name': v['name']} for k, v in CAT_INFO.items()],
            'levels': ['国家级', '省级', '校级', '院级', '班级'],
            'subcategories': [{'key': k, 'name': v} for k, v in SUBCAT_NAMES.items()],
            'sections': sorted(set(
                i.section for i in CatalogItem.query.filter_by(is_active=True).all()
                if i.section
            )),
        }
    })


@app.route('/api/catalog/<item_id>/proofs')
def api_catalog_item_proofs(item_id):
    """获取指定综测项目需要的证明材料清单"""
    ci = CatalogItem.query.get(item_id)
    if not ci:
        return jsonify({'error': '项目不存在'}), 404
    proofs = get_required_proofs({
        'subcategory': ci.subcategory,
        'title': ci.title,
    })
    return jsonify({
        'item_id': item_id,
        'title': ci.title,
        'category': ci.category,
        'category_name': CAT_INFO.get(ci.category, {}).get('name', ''),
        'level': ci.level,
        'score': ci.score,
        'required_proofs': proofs,
    })


# ============================================================
# API: User Items (个人已完成库)
# ============================================================

@app.route('/api/user-items', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_user_items():
    if request.method == 'GET':
        academic_year = request.args.get('academic_year', _default_academic_year())
        items = UserItem.query.filter_by(
            user_id=current_user.id, academic_year=academic_year
        ).order_by(
            UserItem.created_at.desc()
        ).all()
        result = []
        for ui in items:
            item_data = {
                'id': ui.id,
                'catalog_item_id': ui.catalog_item_id,
                'title': ui.custom_title or '',
                'score': ui.score,
                'category': '',
                'category_name': '',
                'level': '',
                'section': '',
                'completion_date': ui.completion_date.strftime('%Y-%m-%d') if ui.completion_date else '',
                'source': ui.source,
                'submission_id': ui.submission_id,
                'created_at': ui.created_at.strftime('%Y-%m-%d %H:%M'),
            }
            if ui.catalog_item_id:
                ci = CatalogItem.query.get(ui.catalog_item_id)
                if ci:
                    item_data['title'] = ci.title
                    item_data['category'] = ci.category
                    item_data['category_name'] = CAT_INFO.get(ci.category, {}).get('name', '')
                    item_data['level'] = ci.level
                    item_data['section'] = ci.section
                    item_data['description'] = ci.description
                    item_data['icon'] = ci.icon
            result.append(item_data)

        return jsonify({'items': result, 'total': len(result)})

    elif request.method == 'POST':
        data = request.get_json()
        catalog_id = data.get('catalog_item_id', '')
        completion_date_str = data.get('completion_date', '')

        ci = CatalogItem.query.get(catalog_id)
        if not ci:
            return jsonify({'error': '项目不存在'}), 404

        completion_date = None
        if completion_date_str:
            try:
                completion_date = datetime.strptime(completion_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        ui = UserItem(
            user_id=current_user.id,
            catalog_item_id=catalog_id,
            score=ci.score,
            completion_date=completion_date,
            academic_year=data.get('academic_year', _default_academic_year()),
            source=data.get('source', 'manual'),
        )
        db.session.add(ui)
        db.session.commit()

        return jsonify({'success': True, 'id': ui.id})

    elif request.method == 'DELETE':
        # Clear all user items
        UserItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return jsonify({'success': True})


@app.route('/api/user-items/<int:item_id>', methods=['DELETE'])
@login_required
def api_delete_user_item(item_id):
    ui = UserItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not ui:
        return jsonify({'error': '项目不存在'}), 404
    db.session.delete(ui)
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# API: Calculate Scores
# ============================================================

@app.route('/api/calculate', methods=['POST'])
@login_required
def api_calculate():
    user_items = UserItem.query.filter_by(user_id=current_user.id).all()

    moral_extra_raw = 0
    academic_extra_raw = 0
    sports_extra_raw = 0
    details = []

    for ui in user_items:
        cat = ''
        title = ui.custom_title or ''
        description = ''
        level = ''
        section = ''
        icon = 'fa-star'

        if ui.catalog_item_id:
            ci = CatalogItem.query.get(ui.catalog_item_id)
            if ci:
                cat = ci.category
                title = ci.title
                description = ci.description
                level = ci.level
                section = ci.section
                icon = ci.icon

        if cat == 'moral':
            moral_extra_raw += ui.score
        elif cat == 'academic':
            academic_extra_raw += ui.score
        else:
            sports_extra_raw += ui.score

        details.append({
            'id': ui.catalog_item_id or str(ui.id),
            'user_item_id': ui.id,
            'title': title,
            'description': description,
            'category': cat,
            'category_name': CAT_INFO.get(cat, {}).get('name', ''),
            'level': level,
            'section': section,
            'score': ui.score,
            'icon': icon,
            'subcategory_name': '',
            'completion_date': ui.completion_date.strftime('%Y-%m-%d') if ui.completion_date else '',
        })

    # 按综测细则上限封顶：品德30、学业20、文体40
    moral_extra = min(moral_extra_raw, CAT_INFO['moral']['extra_max'])
    academic_extra = min(academic_extra_raw, CAT_INFO['academic']['extra_max'])
    sports_extra = min(sports_extra_raw, CAT_INFO['sports']['extra_max'])

    moral_score = min(100, CAT_INFO['moral']['base'] + moral_extra)
    academic_score = min(100, CAT_INFO['academic']['base'] + academic_extra)
    sports_score = min(100, CAT_INFO['sports']['base'] + sports_extra)

    # 综测总分 = 品德×20% + 学业×65% + 文体×15%
    total = round(moral_score * 0.20 + academic_score * 0.65 + sports_score * 0.15, 1)

    # AI Suggestions - identify gaps by comparing against catalog
    suggestions = []
    completed_cat_ids = {
        ui.catalog_item_id for ui in user_items if ui.catalog_item_id
    }

    if moral_extra < 8:
        suggestions.append({
            'type': 'tip',
            'text': f'品德附加分偏低（当前+{moral_extra}分）。建议：担任学生干部（最高12分）、参加志愿活动或争取荣誉称号。'
        })
    if academic_extra < 5:
        suggestions.append({
            'type': 'tip',
            'text': f'学业附加分有提升空间（当前+{academic_extra}分）。建议：参加科技竞赛（最高40分）、考取英语四六级或发表论文。'
        })
    if sports_extra < 8:
        suggestions.append({
            'type': 'tip',
            'text': f'文体附加分不足（当前+{sports_extra}分）。建议：参加校/院运动会、文艺演出或社团竞赛。'
        })
    if total >= 85:
        suggestions.append({
            'type': 'praise',
            'text': f'综合成绩{total}分，表现优秀！继续保持全方面发展态势。'
        })
    elif total >= 75:
        suggestions.append({
            'type': 'info',
            'text': f'综合成绩{total}分，良好。重点关注附加分较低的板块，有针对性地参与活动。'
        })
    else:
        suggestions.append({
            'type': 'tip',
            'text': f'综合成绩{total}分，还有提升空间。建议从多个板块同时发力。'
        })

    suggestions.append({
        'type': 'info',
        'text': '近期可关注：大学生创新创业项目申报（省级+14分、国家级+20分）；英语四六级考试（四级+8、六级+10）；互联网+/挑战杯竞赛（最高+40分）。'
    })

    return jsonify({
        'moral_score': round(moral_score, 1),
        'academic_score': round(academic_score, 1),
        'sports_score': round(sports_score, 1),
        'total_score': total,
        'moral_extra': round(moral_extra, 1),
        'academic_extra': round(academic_extra, 1),
        'sports_extra': round(sports_extra, 1),
        'selected_count': len(user_items),
        'details': details,
        'suggestions': suggestions,
    })


# ============================================================
# API: File Upload
# ============================================================

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'pdf', 'doc', 'docx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload_files():
    if 'files' not in request.files:
        return jsonify({'error': '请选择文件'}), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': '请选择文件'}), 400

    proof_type = request.form.get('proof_type', '').strip()
    catalog_item_id = request.form.get('catalog_item_id', '').strip()

    # User upload directory
    user_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)

    uploaded = []
    for f in files:
        if not f or not f.filename:
            continue
        if not allowed_file(f.filename):
            continue

        raw_filename = os.path.basename((f.filename or '').replace('\\', '/')).strip()
        safe_filename = secure_filename(raw_filename)
        original_filename = raw_filename or safe_filename or 'upload'
        ext_source = safe_filename or original_filename
        ext = ext_source.rsplit('.', 1)[1].lower() if '.' in ext_source else ''
        if not ext and '.' in original_filename:
            ext = original_filename.rsplit('.', 1)[1].lower()
        if not ext:
            ext = 'bin'
        stored_filename = f"{uuid.uuid4().hex}.{ext}"

        file_path = os.path.join(user_dir, stored_filename)
        f.save(file_path)

        file_size = os.path.getsize(file_path)

        uf = UploadedFile(
            user_id=current_user.id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=f'{current_user.id}/{stored_filename}',
            file_type=ext,
            file_size=file_size,
            proof_type=proof_type if proof_type else None,
        )
        db.session.add(uf)
        db.session.commit()

        uploaded.append({
            'id': uf.id,
            'original_filename': original_filename,
            'filename': original_filename,
            'stored_filename': stored_filename,
            'file_path': uf.file_path,
            'view_url': f'/api/uploads/{uf.file_path}',
            'file_type': ext,
            'file_size': file_size,
            'uploaded_at': uf.uploaded_at.strftime('%Y-%m-%d %H:%M'),
        })

    return jsonify({'files': uploaded, 'total': len(uploaded)})


@app.route('/api/uploads/<path:filepath>')
@login_required
def api_serve_file(filepath):
    """Serve uploaded files with permission check"""
    # Extract user_id from path: {user_id}/{filename}
    parts = filepath.replace('\\', '/').split('/')
    if len(parts) < 2:
        return jsonify({'error': 'Invalid path'}), 400

    owner_id = parts[0]
    if current_user.role != 'admin' and str(current_user.id) != owner_id:
        return jsonify({'error': '无权访问'}), 403

    directory = os.path.join(app.config['UPLOAD_FOLDER'], owner_id)
    filename = '/'.join(parts[1:])
    return send_from_directory(directory, filename)


@app.route('/uploads/<path:filepath>')
@login_required
def serve_public_upload(filepath):
    """Serve demo/public uploaded assets such as honor wall seed images."""
    safe_path = filepath.replace('\\', '/').lstrip('/')
    directory = os.path.join(app.config['UPLOAD_FOLDER'], os.path.dirname(safe_path))
    filename = os.path.basename(safe_path)
    return send_from_directory(directory, filename)


# ============================================================
# API: AI Analyze (Enhanced - using ai_engine.py)
# ============================================================

@app.route('/api/analyze', methods=['POST'])
@login_required
def api_analyze():
    data = request.get_json()
    uploaded_file_ids = data.get('uploaded_file_ids', [])
    extra_keyword = data.get('keyword', '').strip()

    # Get uploaded files from DB
    uploaded_files = []
    for uf_id in uploaded_file_ids:
        uf = UploadedFile.query.filter_by(id=uf_id, user_id=current_user.id).first()
        if uf:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], uf.file_path)
            uploaded_files.append({
                'id': uf.id,
                'original_filename': uf.original_filename,
                'file_path': full_path,
                'file_type': uf.file_type,
            })

    if not uploaded_files:
        return jsonify({'error': '未找到已上传的文件'}), 400

    # Get catalog items
    catalog_items = []
    for ci in CatalogItem.query.filter_by(is_active=True).all():
        catalog_items.append({
            'id': ci.id,
            'category': ci.category,
            'category_name': CAT_INFO.get(ci.category, {}).get('name', ''),
            'subcategory': ci.subcategory,
            'title': ci.title,
            'description': ci.description,
            'level': ci.level,
            'score': ci.score,
            'icon': ci.icon,
            'section': ci.section,
            'note': ci.note,
        })

    # Run AI analysis (传递学生信息用于置信度评估)
    results = analyze_files(uploaded_files, catalog_items, extra_keyword,
                           student_name=current_user.name or '',
                           student_id=current_user.student_id or '')

    # Format response
    formatted = []
    for r in results:
        formatted.append({
            'file_id': r['file_id'],
            'filename': r['filename'],
            'extracted_text': r['extracted_text'],
            'has_text_content': r['has_text_content'],
            'ai_enhanced': r.get('ai_enhanced', False),
            'matches': [{
                'id': m['id'],
                'title': m['title'],
                'description': m.get('description', ''),
                'category': m['category'],
                'category_name': m.get('category_name', ''),
                'level': m.get('level', ''),
                'score': m.get('score_val', 0),
                'icon': m.get('icon', 'fa-star'),
                'section': m.get('section', ''),
                'note': m.get('note', ''),
                'confidence': m['confidence'],
                'confidence_detail': m.get('confidence_detail', ''),
                'risk_level': m.get('risk_level', 'low'),
                'decision': m.get('decision', 'medium'),
                'reason': m.get('reason', ''),
                'audit': m.get('audit', {}),
            } for m in r['matches']],
        })

    return jsonify({'results': formatted})


# ============================================================
# API: Submissions (Review System)
# ============================================================

@app.route('/api/submissions', methods=['GET', 'POST'])
@login_required
def api_submissions():
    if request.method == 'GET':
        academic_year = request.args.get('academic_year', _default_academic_year())
        subs = Submission.query.filter_by(
            user_id=current_user.id, academic_year=academic_year
        ).order_by(
            Submission.created_at.desc()
        ).all()
        result = []
        for s in subs:
            # Get linked files
            linked_files = []
            for uf in s.files:
                linked_files.append({
                    'id': uf.id,
                    'filename': uf.original_filename,
                    'proof_type': uf.proof_type or '',
                    'file_type': uf.file_type,
                    'uploaded_at': uf.uploaded_at.strftime('%Y-%m-%d %H:%M'),
                })

            result.append({
                'id': s.id,
                'catalog_item_id': s.catalog_item_id,
                'title': s.title,
                'description': s.description,
                'proof_filename': s.proof_filename,
                'completion_date': s.completion_date.strftime('%Y-%m-%d') if s.completion_date else '',
                'academic_year': s.academic_year,
                'status': s.status,
                'ai_confidence': round(s.ai_confidence, 1),
                'ai_decision': s.ai_decision,
                'ai_reason': s.ai_reason,
                'review_remarks': s.review_remarks,
                'created_at': s.created_at.strftime('%Y-%m-%d %H:%M'),
                'reviewed_at': s.reviewed_at.strftime('%Y-%m-%d %H:%M') if s.reviewed_at else '',
                'files': linked_files,
            })
        return jsonify({'submissions': result})

    elif request.method == 'POST':
        data = request.get_json()
        catalog_item_id = data.get('catalog_item_id', '')
        uploaded_file_ids = data.get('uploaded_file_ids', [])
        if not uploaded_file_ids and data.get('uploaded_file_id'):
            uploaded_file_ids = [data['uploaded_file_id']]
        completion_date_str = data.get('completion_date', '')
        academic_year = data.get('academic_year', _default_academic_year())
        ai_confidence = data.get('ai_confidence', 0)
        ai_decision = data.get('ai_decision', 'medium')
        ai_reason = data.get('ai_reason', '')
        ai_audit = data.get('ai_audit') or {}
        manual_title = (data.get('manual_title') or data.get('title') or '').strip()
        manual_category = (data.get('manual_category') or data.get('category') or 'academic').strip()
        manual_level = (data.get('manual_level') or data.get('level') or '').strip()
        manual_description = (data.get('manual_description') or data.get('description') or '').strip()
        try:
            manual_score = float(data.get('manual_score') or data.get('score') or 0)
        except (TypeError, ValueError):
            manual_score = 0

        ci = CatalogItem.query.get(catalog_item_id) if catalog_item_id else None
        if catalog_item_id and not ci:
            return jsonify({'error': '综测项目不存在'}), 404
        if not ci and not manual_title:
            return jsonify({'error': '请填写加分项目名称'}), 400

        # ---- 查重：已通过/审核中的项目不允许重复提交 ----
        if ci:
            existing_item = UserItem.query.filter_by(
                user_id=current_user.id, catalog_item_id=catalog_item_id
            ).first()
            if existing_item:
                return jsonify({'error': f'该项目「{ci.title}」已在你的星轨加分中（+{existing_item.score}分），不能重复提交', 'code': 'duplicate'}), 409

            existing_sub = Submission.query.filter(
                Submission.user_id == current_user.id,
                Submission.catalog_item_id == catalog_item_id,
                Submission.status.in_(['pending', 'needs_more', 'auto_approved']),
            ).first()
            if existing_sub:
                status_label = '审核中' if existing_sub.status in ('pending', 'needs_more') else '已AI自动通过'
                return jsonify({'error': f'该项目「{ci.title}」已有提交记录（{status_label}），请等待审核结果', 'code': 'duplicate'}), 409
        # --------------------------------------------------------

        title = ci.title if ci else manual_title
        description = ci.description if ci else manual_description

        completion_date = None
        if completion_date_str:
            try:
                completion_date = datetime.strptime(completion_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Get uploaded files
        proof_files = UploadedFile.query.filter(
            UploadedFile.id.in_(uploaded_file_ids),
            UploadedFile.user_id == current_user.id
        ).all()

        if not proof_files:
            return jsonify({'error': '请先上传证明文件'}), 400

        # Check required proofs completeness
        required_proofs = get_required_proofs({'subcategory': ci.subcategory}) if ci else []
        submitted_proof_types = set(f.proof_type for f in proof_files if f.proof_type)
        required_types = set(p['type'] for p in required_proofs)
        missing_proofs = required_types - submitted_proof_types

        proof_filenames = [f.original_filename for f in proof_files]
        proof_filepath = proof_files[0].file_path

        # Determine status based on proof completeness AND AI confidence.
        # AI only provides an initial recommendation; new submissions never auto-post score.
        proofs_complete = len(missing_proofs) == 0
        status = 'pending'
        if not proofs_complete:
            status = 'needs_more'
            ai_reason = (ai_reason + f' [缺失材料: {", ".join(missing_proofs)}]').strip()
        if ai_audit.get('missing_fields') or ai_audit.get('status') in ('NEED_SUPPLEMENT', 'HIGH_RISK'):
            status = 'needs_more'

        audit_payload = {
            'required_proofs': [p['type'] for p in required_proofs],
            'submitted_proofs': list(submitted_proof_types),
            'missing_proofs': list(missing_proofs),
            'proofs_complete': proofs_complete,
            'audit': ai_audit,
            'matched_regulation': ai_audit.get('matched_regulation', {}),
            'extracted_features': ai_audit.get('extracted_features', {}),
            'risk_assessment': ai_audit.get('risk_assessment', {}),
            'missing_fields': ai_audit.get('missing_fields', []),
            'audit_chain': ai_audit.get('audit_chain', []),
            'manual_submission': not bool(ci),
            'manual_category': manual_category if not ci else '',
            'manual_level': manual_level if not ci else '',
            'manual_score': manual_score if not ci else None,
            'manual_description': manual_description if not ci else '',
        }

        submission = Submission(
            user_id=current_user.id,
            catalog_item_id=catalog_item_id,
            title=title,
            description=description,
            proof_filename=', '.join(proof_filenames[:3]),
            proof_filepath=proof_filepath,
            completion_date=completion_date,
            academic_year=academic_year,
            status=status,
            ai_confidence=ai_confidence,
            ai_decision=ai_decision,
            ai_reason=ai_reason,
            ai_matched_items=json.dumps(audit_payload, ensure_ascii=False),
        )
        db.session.add(submission)
        db.session.commit()

        # Link files to submission
        for uf in proof_files:
            uf.submission_id = submission.id
        db.session.commit()

        return jsonify({
            'success': True,
            'submission_id': submission.id,
            'status': status,
            'auto_added': False,
            'proofs_complete': proofs_complete,
            'missing_proofs': list(missing_proofs),
            'audit': ai_audit,
        })


# ============================================================
# API: View Submission Files (Student)
# ============================================================

@app.route('/api/submissions/<int:sub_id>/files')
@login_required
def api_submission_files(sub_id):
    """学生查看自己提交的证明材料"""
    sub = Submission.query.get_or_404(sub_id)
    if current_user.role != 'admin' and sub.user_id != current_user.id:
        return jsonify({'error': '无权访问'}), 403
    files = []
    for uf in sub.files:
        files.append({
            'id': uf.id, 'filename': uf.original_filename,
            'proof_type': uf.proof_type or '',
            'file_type': uf.file_type, 'file_size': uf.file_size,
            'uploaded_at': uf.uploaded_at.strftime('%Y-%m-%d %H:%M'),
            'view_url': f'/api/uploads/{uf.file_path}',
        })
    return jsonify({'submission_id': sub.id, 'title': sub.title, 'files': files})


# ============================================================
# API: Admin Submissions (Review Queue)
# ============================================================

@app.route('/api/admin/submissions', methods=['GET'])
@admin_required
def api_admin_submissions():
    status_filter = request.args.get('status', '')
    queue_filter = request.args.get('queue', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Submission.query
    if queue_filter == 'high_confidence':
        query = query.filter(Submission.status.in_(['pending', 'needs_more']), Submission.ai_confidence >= 90)
    elif queue_filter in ('pending', 'pending_human'):
        query = query.filter_by(status='pending')
    elif queue_filter == 'needs_more':
        query = query.filter_by(status='needs_more')
    elif queue_filter == 'risk':
        query = query.filter(Submission.status.in_(['pending', 'needs_more']), Submission.ai_confidence < 60)
    elif queue_filter == 'approved':
        query = query.filter(Submission.status.in_(['approved', 'auto_approved']))
    elif queue_filter == 'rejected':
        query = query.filter_by(status='rejected')
    elif status_filter:
        query = query.filter_by(status=status_filter)

    pagination = query.order_by(
        db.case({'needs_more': 0, 'pending': 1, 'auto_approved': 2, 'approved': 3, 'rejected': 4},
                value=Submission.status),
        Submission.ai_confidence.asc(),
        Submission.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    items = []
    for s in pagination.items:
        student = User.query.get(s.user_id)
        ci = CatalogItem.query.get(s.catalog_item_id) if s.catalog_item_id else None

        # Parse proof info
        proof_info = {}
        try:
            proof_info = json.loads(s.ai_matched_items) if s.ai_matched_items else {}
        except Exception:
            pass

        # Get linked files
        linked_files = []
        for uf in s.files:
            linked_files.append({
                'id': uf.id,
                'filename': uf.original_filename,
                'proof_type': uf.proof_type or '',
                'file_type': uf.file_type,
                'file_path': uf.file_path,
                'uploaded_at': uf.uploaded_at.strftime('%Y-%m-%d %H:%M'),
            })

        # ── HITL 智能路由队列计算 ──
        # 绿色(≥95%): AI可自动通过  |  黄色(<95%): 需人工复核  |  红色: 高危欺诈
        ai_conf = round(s.ai_confidence, 1)
        risk_tags = proof_info.get('risk_assessment', {}).get('risk_tags', [])
        audit_status = proof_info.get('audit', {}).get('status', '')
        if 'TAMPER_SUSPECTED' in risk_tags or audit_status == 'HIGH_RISK' or ai_conf < 40:
            routing_queue = 'fraud_alert'
            routing_label = '🔴 高危欺诈'
        elif ai_conf >= 95:
            routing_queue = 'auto_approve'
            routing_label = '🟢 建议通过'
        else:
            routing_queue = 'human_review'
            routing_label = '🟡 需人工复核'

        items.append({
            'id': s.id,
            'student_id': student.student_id if student else '',
            'student_name': student.name if student else '',
            'catalog_item_id': s.catalog_item_id,
            'title': s.title,
            'description': s.description,
            'proof_filename': s.proof_filename,
            'completion_date': s.completion_date.strftime('%Y-%m-%d') if s.completion_date else '',
            'status': s.status,
            'ai_confidence': ai_conf,
            'ai_decision': s.ai_decision,
            'ai_reason': s.ai_reason,
            'routing_queue': routing_queue,
            'routing_label': routing_label,
            'review_remarks': s.review_remarks,
            'score': ci.score if ci else proof_info.get('manual_score', 0),
            'level': ci.level if ci else proof_info.get('manual_level', ''),
            'category': ci.category if ci else proof_info.get('manual_category', ''),
            'required_proofs': proof_info.get('required_proofs', []),
            'submitted_proofs': proof_info.get('submitted_proofs', []),
            'missing_proofs': proof_info.get('missing_proofs', []),
            'proofs_complete': proof_info.get('proofs_complete', False),
            'audit': proof_info.get('audit', {}),
            'matched_regulation': proof_info.get('matched_regulation', {}),
            'extracted_features': proof_info.get('extracted_features', {}),
            'risk_assessment': proof_info.get('risk_assessment', {}),
            'missing_fields': proof_info.get('missing_fields', []),
            'audit_chain': proof_info.get('audit_chain', []),
            'files': linked_files,
            'created_at': s.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    return jsonify({
        'submissions': items,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })


@app.route('/api/admin/submissions/<int:sub_id>', methods=['PUT'])
@admin_required
def api_review_submission(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    data = request.get_json()
    action = data.get('action', '')

    if action == 'approve':
        sub.status = 'approved'
        sub.reviewer_id = current_user.id
        sub.review_remarks = data.get('remarks', '')
        sub.reviewed_at = datetime.utcnow()

        # ── 强制偏差存证: 管理员覆盖AI判定时需提供原因 ──
        try:
            proof_info = json.loads(sub.ai_matched_items) if sub.ai_matched_items else {}
        except Exception:
            proof_info = {}
        ai_suggested = proof_info.get('audit', {}).get('matched_regulation', {}).get('score_calculated', 0)
        admin_score = data.get('score', 0)

        override_reason = data.get('override_reason', '')
        if admin_score and ai_suggested and abs(admin_score - ai_suggested) > 0.5:
            if not override_reason:
                return jsonify({
                    'error': '检测到覆盖AI判定，请提供修改原因',
                    'code': 'override_reason_required',
                    'ai_suggested': ai_suggested,
                }), 400
            # 记录偏差存证
            sub.review_remarks = (
                f'[人工覆盖] AI建议{ai_suggested}分→管理员设定{admin_score}分。'
                f'原因: {override_reason}。备注: {data.get("remarks", "")}'
            )

        # Create UserItem
        score = admin_score or 0
        catalog_id = sub.catalog_item_id
        custom_title = None
        custom_score = None
        if catalog_id:
            ci = CatalogItem.query.get(catalog_id)
            if ci:
                score = ci.score
        else:
            score = admin_score or proof_info.get('manual_score', score)
            custom_score = score
            custom_title = sub.title

        if not UserItem.query.filter_by(user_id=sub.user_id, submission_id=sub.id).first():
            ui = UserItem(
                user_id=sub.user_id,
                catalog_item_id=catalog_id,
                custom_title=custom_title,
                custom_score=custom_score,
                score=score,
                completion_date=sub.completion_date,
                source='upload',
                submission_id=sub.id,
            )
            db.session.add(ui)

    elif action == 'reject':
        sub.status = 'rejected'
        sub.reviewer_id = current_user.id
        sub.review_remarks = data.get('remarks', '材料不全或不符合要求')
        sub.reviewed_at = datetime.utcnow()

    elif action == 'needs_more':
        sub.status = 'needs_more'
        sub.reviewer_id = current_user.id
        sub.review_remarks = data.get('remarks', '请补充材料后复核')
        sub.reviewed_at = datetime.utcnow()

    elif action == 'return':
        sub.status = 'needs_more'
        sub.reviewer_id = current_user.id
        sub.review_remarks = data.get('remarks', '重新打回，需补充材料后复核')
        sub.reviewed_at = datetime.utcnow()
        for item in UserItem.query.filter_by(user_id=sub.user_id, submission_id=sub.id).all():
            db.session.delete(item)

    elif action == 'reassign':
        new_catalog_id = data.get('catalog_item_id', '')
        ci = CatalogItem.query.get(new_catalog_id)
        if ci:
            sub.catalog_item_id = new_catalog_id
            sub.title = ci.title
            sub.description = ci.description

    # ── 双重审计日志 — 记录AI+管理员双端属性 ──
    ai_matched = {}
    try:
        ai_matched = json.loads(sub.ai_matched_items) if sub.ai_matched_items else {}
    except Exception:
        pass
    ai_suggested_score = ai_matched.get('audit', {}).get('matched_regulation', {}).get('score_calculated', 0)
    admin_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '')
    user_agent = request.headers.get('User-Agent', '')[:512]

    audit = AuditLog(
        submission_id=sub.id,
        action_type=action,
        ai_model_version='ai-engine-v3',
        ai_confidence=sub.ai_confidence or 0,
        ai_decision=sub.ai_decision or '',
        ai_score_suggested=ai_suggested_score,
        admin_id=current_user.id,
        admin_ip=admin_ip,
        admin_score_set=data.get('score'),
        admin_decision=action,
        override_reason=data.get('override_reason', ''),
        override_detail=data.get('remarks', ''),
        remarks=data.get('remarks', ''),
        user_agent=user_agent,
    )
    db.session.add(audit)

    db.session.commit()
    return jsonify({'success': True, 'status': sub.status})


@app.route('/api/admin/submissions/batch-approve', methods=['POST'])
@admin_required
def api_batch_approve():
    """批量批准高置信度(≥95%)申请 — 直通式处理(STP)"""
    data = request.get_json()
    sub_ids = data.get('ids', [])
    if not sub_ids:
        return jsonify({'error': '请选择要批准的申请'}), 400

    approved_count = 0
    skipped_count = 0
    errors = []

    for sub_id in sub_ids:
        sub = Submission.query.get(sub_id)
        if not sub:
            errors.append(f'#{sub_id}: 不存在')
            skipped_count += 1
            continue
        if sub.status not in ('pending', 'needs_more', 'pending_ai', 'pending_human'):
            errors.append(f'#{sub_id}: 状态为{sub.status}，不可批量操作')
            skipped_count += 1
            continue

        # 批量通过仅限高置信度申请
        if sub.ai_confidence and sub.ai_confidence < 95:
            errors.append(f'#{sub_id}: 置信度{sub.ai_confidence}%<95%，需人工复核')
            skipped_count += 1
            continue

        try:
            sub.status = 'approved'
            sub.reviewer_id = current_user.id
            sub.review_remarks = f'[批量STP] AI置信度{sub.ai_confidence}%，自动通过'
            sub.reviewed_at = datetime.utcnow()

            score = 0
            if sub.catalog_item_id:
                ci = CatalogItem.query.get(sub.catalog_item_id)
                if ci:
                    score = ci.score

            if not UserItem.query.filter_by(user_id=sub.user_id, submission_id=sub.id).first():
                ui = UserItem(
                    user_id=sub.user_id,
                    catalog_item_id=sub.catalog_item_id,
                    score=score,
                    completion_date=sub.completion_date,
                    source='upload',
                    submission_id=sub.id,
                )
                db.session.add(ui)
            # ── 审计日志：批量STP ──
            admin_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '')
            audit = AuditLog(
                submission_id=sub.id,
                action_type='auto_approve',
                ai_model_version='ai-engine-v3',
                ai_confidence=sub.ai_confidence or 0,
                ai_decision=sub.ai_decision or '',
                admin_id=current_user.id,
                admin_ip=admin_ip,
                admin_decision='approve',
                remarks=f'[批量STP] AI置信度{sub.ai_confidence}%≥95%，自动通过',
                user_agent=request.headers.get('User-Agent', '')[:512],
            )
            db.session.add(audit)
            approved_count += 1
        except Exception as e:
            errors.append(f'#{sub_id}: {str(e)}')
            skipped_count += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'approved': approved_count,
        'skipped': skipped_count,
        'errors': errors,
    })


# ============================================================
# API: Vue compatibility for certification review workflow
# ============================================================

def _submission_to_certification(s, admin_view=False):
    student = User.query.get(s.user_id)
    ci = CatalogItem.query.get(s.catalog_item_id) if s.catalog_item_id else None
    try:
        proof_info = json.loads(s.ai_matched_items) if s.ai_matched_items else {}
    except Exception:
        proof_info = {}

    if s.status == 'pending':
        status = 'pending_human'
    elif s.status == 'auto_approved':
        status = 'approved'
    else:
        status = s.status

    files = []
    for uf in s.files:
        files.append({
            'id': uf.id,
            'name': uf.original_filename,
            'filename': uf.original_filename,
            'proof_type': uf.proof_type or '',
            'file_type': uf.file_type,
            'url': f'/api/uploads/{uf.file_path}',
            'view_url': f'/api/uploads/{uf.file_path}',
        })

    missing = proof_info.get('missing_proofs', [])
    risk_tags = []
    if s.ai_confidence >= 85:
        risk_tags.append('AI高置信')
    elif s.ai_confidence < 60:
        risk_tags.append('低置信需复核')
    else:
        risk_tags.append('待人工确认')
    if missing:
        risk_tags.append('材料待补齐')

    item = {
        'id': s.id,
        'user_id': s.user_id,
        'catalog_item_id': s.catalog_item_id,
        'title': s.title,
        'dimension': _frontend_dimension(ci.category if ci else 'academic'),
        'award_level': ci.level if ci else '',
        'material_manifest': {
            proof_type: proof_type in proof_info.get('submitted_proofs', [])
            for proof_type in proof_info.get('required_proofs', [])
        },
        'files': files,
        'ai_review': {
            'recognized_text': s.ai_reason,
            'missing_materials': missing,
            'rule_ref': ci.section if ci else '',
            'recommendation': s.ai_reason or ('AI建议通过，等待人工复核。' if s.ai_confidence >= 85 else '建议人工复核材料。'),
            'matched_regulation': proof_info.get('matched_regulation', {}),
            'extracted_features': proof_info.get('extracted_features', {}),
            'risk_assessment': proof_info.get('risk_assessment', {}),
            'missing_fields': proof_info.get('missing_fields', []),
            'audit_chain': proof_info.get('audit_chain', []),
        },
        'ai_confidence': round((s.ai_confidence or 0) / 100, 3),
        'risk_tags': risk_tags,
        'suggested_score': ci.score if ci else 0,
        'status': status,
        'admin_comment': s.review_remarks or '',
        'student_name': student.name if student else '',
        'student_id': student.student_id if student else '',
        'opportunity_title': ci.title if ci else '',
        'created_at': s.created_at.strftime('%Y-%m-%d %H:%M'),
    }
    if admin_view:
        item['required_proofs'] = proof_info.get('required_proofs', [])
        item['submitted_proofs'] = proof_info.get('submitted_proofs', [])
        item['missing_fields'] = proof_info.get('missing_fields', [])
        item['audit_chain'] = proof_info.get('audit_chain', [])
    return item


@app.route('/api/material-templates')
@login_required
def api_material_templates():
    dimension_weights = {'moral': 0.2, 'academic': 0.65, 'arts_sports': 0.15}
    current_doc = RegulationDoc.query.filter_by(is_current=True).order_by(
        RegulationDoc.uploaded_at.desc()
    ).first()
    strict_materials = []
    seen = set()
    for ci in CatalogItem.query.filter_by(is_active=True).all():
        for proof in get_required_proofs({'subcategory': ci.subcategory}):
            name = proof.get('name') or proof.get('type')
            if name and name not in seen:
                seen.add(name)
                strict_materials.append(name)
    return jsonify({
        'rule_version': current_doc.title if current_doc else '2025年7月电信学院综测细则',
        'active_rule_document': {
            'id': current_doc.id,
            'name': current_doc.title,
            'version': current_doc.title,
            'file_url': f'/api/admin/regulations/{current_doc.id}/file',
            'notes': '',
            'is_active': 1,
            'uploaded_at': current_doc.uploaded_at.strftime('%Y-%m-%d %H:%M'),
        } if current_doc else None,
        'strict_materials': strict_materials[:12] or ['获奖证书', '参赛证明', '官方来源证明'],
        'dimensions': [
            {'key': _frontend_dimension(key), 'label': value['name'], 'base': value['base'], 'cap': value['extra_max'], 'weight': dimension_weights.get(_frontend_dimension(key), 0)}
            for key, value in CAT_INFO.items()
        ],
        'notes': ['AI初审不等于最终入账，人工审核通过后才写入综测得分。'],
    })


@app.route('/api/rule-documents')
@login_required
def api_rule_documents():
    docs = RegulationDoc.query.order_by(
        RegulationDoc.is_current.desc(),
        RegulationDoc.uploaded_at.desc(),
    ).all()
    return jsonify([{
        'id': doc.id,
        'name': doc.title,
        'version': doc.title,
        'file_url': f'/api/admin/regulations/{doc.id}/file',
        'notes': '',
        'is_active': 1 if doc.is_current else 0,
        'uploaded_at': doc.uploaded_at.strftime('%Y-%m-%d %H:%M'),
    } for doc in docs])


@app.route('/api/certifications', methods=['GET', 'POST'])
@login_required
def api_certifications_compat():
    if request.method == 'GET':
        subs = Submission.query.filter_by(user_id=current_user.id).order_by(
            Submission.created_at.desc()
        ).all()
        return jsonify([_submission_to_certification(s) for s in subs])

    data = request.get_json() or {}
    uploaded_file_ids = data.get('uploaded_file_ids') or []
    if not uploaded_file_ids:
        uploaded_file_ids = [f.get('id') for f in data.get('files', []) if f.get('id')]

    catalog_item_id = data.get('catalog_item_id') or data.get('catalog_id') or ''
    if not catalog_item_id:
        return jsonify({'error': '请先通过AI识别或手动选择一个综测项目'}), 400
    if not uploaded_file_ids:
        return jsonify({'error': '请先上传证明材料'}), 400

    ci = CatalogItem.query.get(catalog_item_id)
    if not ci:
        return jsonify({'error': '综测项目不存在'}), 404

    proof_files = UploadedFile.query.filter(
        UploadedFile.id.in_(uploaded_file_ids),
        UploadedFile.user_id == current_user.id
    ).all()
    if not proof_files:
        return jsonify({'error': '请先上传证明材料'}), 400

    existing_item = UserItem.query.filter_by(
        user_id=current_user.id, catalog_item_id=catalog_item_id
    ).first()
    if existing_item:
        return jsonify({'error': f'项目「{ci.title}」已在你的星轨加分中，不能重复提交', 'code': 'duplicate'}), 409

    existing_sub = Submission.query.filter(
        Submission.user_id == current_user.id,
        Submission.catalog_item_id == catalog_item_id,
        Submission.status.in_(['pending', 'needs_more', 'auto_approved']),
    ).first()
    if existing_sub:
        return jsonify({'error': f'项目「{ci.title}」已有待审核记录，请等待审核结果', 'code': 'duplicate'}), 409

    required_proofs = get_required_proofs({'subcategory': ci.subcategory})
    submitted_types = set(f.proof_type for f in proof_files if f.proof_type)
    missing = [p['type'] for p in required_proofs if p['type'] not in submitted_types]
    ai_confidence = float(data.get('ai_confidence') or 0)
    if ai_confidence <= 1:
        ai_confidence *= 100
    ai_decision = data.get('ai_decision') or ('high' if ai_confidence >= 85 else 'medium')
    ai_audit = data.get('ai_audit') or {}
    status = 'needs_more' if missing or ai_audit.get('missing_fields') else 'pending'

    submission = Submission(
        user_id=current_user.id,
        catalog_item_id=ci.id,
        title=ci.title,
        description=ci.description,
        proof_filename=', '.join(f.original_filename for f in proof_files[:3]),
        proof_filepath=proof_files[0].file_path,
        status=status,
        ai_confidence=ai_confidence,
        ai_decision=ai_decision,
        ai_reason=data.get('ai_reason') or data.get('award_level') or '',
        ai_matched_items=json.dumps({
            'required_proofs': [p['type'] for p in required_proofs],
            'submitted_proofs': list(submitted_types),
            'missing_proofs': missing,
            'proofs_complete': len(missing) == 0,
            'audit': ai_audit,
            'matched_regulation': ai_audit.get('matched_regulation', {}),
            'extracted_features': ai_audit.get('extracted_features', {}),
            'risk_assessment': ai_audit.get('risk_assessment', {}),
            'missing_fields': ai_audit.get('missing_fields', []),
            'audit_chain': ai_audit.get('audit_chain', []),
        }, ensure_ascii=False),
    )
    db.session.add(submission)
    db.session.commit()

    for uf in proof_files:
        uf.submission_id = submission.id
    db.session.commit()

    return jsonify(_submission_to_certification(submission))


@app.route('/api/admin/certifications')
@admin_required
def api_admin_certifications_compat():
    queue = request.args.get('queue', '')
    query = Submission.query
    if queue in ('pending', 'pending_human'):
        query = query.filter_by(status='pending')
    elif queue in ('approved', 'auto_approved', 'rejected'):
        if queue == 'approved':
            query = query.filter(Submission.status.in_(['approved', 'auto_approved']))
        else:
            query = query.filter_by(status=queue)
    elif queue == 'needs_more':
        query = query.filter(Submission.status == 'pending', Submission.ai_confidence < 70)

    rows = query.order_by(Submission.created_at.desc()).limit(200).all()
    return jsonify([_submission_to_certification(s, admin_view=True) for s in rows])


@app.route('/api/admin/certifications/<int:sub_id>/decision', methods=['POST'])
@admin_required
def api_admin_certification_decision_compat(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    data = request.get_json() or {}
    decision = data.get('decision', '')

    if decision == 'approved':
        sub.status = 'approved'
        sub.reviewer_id = current_user.id
        sub.review_remarks = data.get('comment', '')
        sub.reviewed_at = datetime.utcnow()
        if not UserItem.query.filter_by(user_id=sub.user_id, submission_id=sub.id).first():
            ci = CatalogItem.query.get(sub.catalog_item_id)
            db.session.add(UserItem(
                user_id=sub.user_id,
                catalog_item_id=sub.catalog_item_id,
                score=ci.score if ci else data.get('score', 0),
                completion_date=sub.completion_date,
                source='upload',
                submission_id=sub.id,
            ))
    elif decision == 'rejected':
        sub.status = 'rejected'
        sub.reviewer_id = current_user.id
        sub.review_remarks = data.get('comment', '材料不符合要求')
        sub.reviewed_at = datetime.utcnow()
    elif decision == 'needs_more':
        sub.status = 'needs_more'
        sub.reviewer_id = current_user.id
        sub.review_remarks = data.get('comment', '请补充材料后复核')
        sub.reviewed_at = datetime.utcnow()
    elif decision == 'return':
        sub.status = 'needs_more'
        sub.reviewer_id = current_user.id
        sub.review_remarks = data.get('comment', '重新打回，需补充材料后复核')
        sub.reviewed_at = datetime.utcnow()
        for item in UserItem.query.filter_by(user_id=sub.user_id, submission_id=sub.id).all():
            db.session.delete(item)
    else:
        return jsonify({'error': 'Unknown decision'}), 400

    db.session.commit()
    return jsonify(_submission_to_certification(sub, admin_view=True))


# ============================================================
# API: Admin Stats
# ============================================================

@app.route('/api/admin/stats')
@admin_required
def api_admin_stats():
    approved_score = db.session.query(
        db.func.coalesce(db.func.sum(UserItem.score), 0)
    ).scalar() or 0
    try:
        opportunity_count = len(load_activities())
    except Exception:
        opportunity_count = 0

    # ── HITL 智能路由统计 ──
    pending_reviews = Submission.query.filter(
        Submission.status.in_(['pending', 'needs_more', 'pending_ai', 'pending_human'])
    ).all()
    auto_approve_count = sum(1 for s in pending_reviews if s.ai_confidence and s.ai_confidence >= 95)
    human_review_count = sum(1 for s in pending_reviews if s.ai_confidence and 40 <= s.ai_confidence < 95)
    fraud_alert_count = sum(1 for s in pending_reviews if s.ai_confidence and s.ai_confidence < 40)

    return jsonify({
        'opportunity_count': opportunity_count,
        'application_count': Submission.query.count(),
        'pending_count': len(pending_reviews),
        'approved_score': round(float(approved_score), 1),
        'total_students': User.query.filter_by(role='student', is_active=True).count(),
        'pending_reviews': len(pending_reviews),
        'approved_today': Submission.query.filter(
            Submission.status.in_(['approved', 'auto_approved']),
            Submission.reviewed_at >= date.today()
        ).count(),
        'total_submissions': Submission.query.count(),
        # HITL routing queue counts
        'routing': {
            'auto_approve': auto_approve_count,
            'human_review': human_review_count,
            'fraud_alert': fraud_alert_count,
        },
    })


# ============================================================
# API: Admin User Management
# ============================================================

@app.route('/api/admin/users', methods=['GET', 'POST'])
@admin_required
def api_admin_users():
    if request.method == 'GET':
        keyword = request.args.get('keyword', '').strip()
        query = User.query.filter_by(role='student', is_active=True)
        if keyword:
            query = query.filter(
                db.or_(
                    User.student_id.contains(keyword),
                    User.name.contains(keyword),
                    User.department.contains(keyword),
                )
            )

        users = query.order_by(User.created_at.desc()).all()
        result = []
        for u in users:
            item_count = UserItem.query.filter_by(user_id=u.id).count()
            submission_count = Submission.query.filter_by(user_id=u.id).count()
            result.append({
                'id': u.id,
                'student_id': u.student_id,
                'name': u.name,
                'department': u.department,
                'class_name': u.class_name,
                'item_count': item_count,
                'submission_count': submission_count,
                'created_at': u.created_at.strftime('%Y-%m-%d %H:%M'),
            })
        return jsonify({'users': result})

    elif request.method == 'POST':
        data = request.get_json()
        student_id = data.get('student_id', '').strip()
        name = data.get('name', '').strip()
        password = data.get('password', '000000').strip()

        if not student_id or not name:
            return jsonify({'error': '学号和姓名不能为空'}), 400
        if not re.match(r'^\d+$', student_id):
            return jsonify({'error': '学号只能包含数字'}), 400
        if len(password) < 6:
            return jsonify({'error': '密码至少6位'}), 400

        user = User(
            student_id=student_id,
            name=name,
            password_hash=generate_password_hash(password),
            role='student',
            department=data.get('department', '电子与信息学院'),
            class_name=data.get('class_name', ''),
        )
        db.session.add(user)
        db.session.commit()

        return jsonify({'success': True, 'id': user.id})


@app.route('/api/admin/users/<int:user_id>', methods=['PUT', 'DELETE'])
@admin_required
def api_admin_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        return jsonify({'error': '不能修改管理员账号'}), 403

    if request.method == 'PUT':
        data = request.get_json()
        if data.get('name'):
            user.name = data['name']
        if data.get('department'):
            user.department = data['department']
        if data.get('class_name') is not None:
            user.class_name = data['class_name']
        db.session.commit()
        return jsonify({'success': True})

    elif request.method == 'DELETE':
        user.is_active = False
        db.session.commit()
        return jsonify({'success': True})


@app.route('/api/admin/users/<int:user_id>/items')
@admin_required
def api_admin_user_items(user_id):
    """查看指定用户的综测项目"""
    user = User.query.get_or_404(user_id)
    items = UserItem.query.filter_by(user_id=user_id).order_by(UserItem.created_at.desc()).all()
    result = []
    for ui in items:
        d = {'id': ui.id, 'catalog_item_id': ui.catalog_item_id,
             'title': ui.custom_title or '', 'score': ui.score,
             'source': ui.source, 'submission_id': ui.submission_id,
             'completion_date': ui.completion_date.strftime('%Y-%m-%d') if ui.completion_date else '',
             'created_at': ui.created_at.strftime('%Y-%m-%d %H:%M')}
        if ui.catalog_item_id:
            ci = CatalogItem.query.get(ui.catalog_item_id)
            if ci:
                d['title'] = ci.title; d['category'] = ci.category
                d['category_name'] = CAT_INFO.get(ci.category, {}).get('name', '')
                d['level'] = ci.level; d['section'] = ci.section
        result.append(d)
    return jsonify({'user': {'id': user.id, 'student_id': user.student_id, 'name': user.name},
                    'items': result, 'total': len(result)})


@app.route('/api/admin/users/<int:user_id>/items/<int:item_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_user_item(user_id, item_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        return jsonify({'error': '不能修改管理员账号'}), 403
    item = UserItem.query.filter_by(id=item_id, user_id=user_id).first()
    if not item:
        return jsonify({'error': '项目不存在'}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def api_admin_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    new_password = data.get('password', '').strip()

    if len(new_password) < 6:
        return jsonify({'error': '密码至少6位'}), 400

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# API: Admin Catalog Item Management
# ============================================================

@app.route('/api/admin/items', methods=['POST'])
@admin_required
def api_admin_create_item():
    data = request.get_json()
    new_id = data.get('id', '').strip()
    if not new_id:
        return jsonify({'error': '项目ID不能为空'}), 400

    existing = CatalogItem.query.get(new_id)
    if existing:
        return jsonify({'error': '项目ID已存在'}), 400

    ci = CatalogItem(
        id=new_id,
        category=data.get('category', 'academic'),
        subcategory=data.get('subcategory', ''),
        title=data.get('title', ''),
        description=data.get('description', ''),
        level=data.get('level', '校级'),
        score=data.get('score', 1),
        icon=data.get('icon', 'fa-star'),
        section=data.get('section', ''),
        note=data.get('note', ''),
    )
    db.session.add(ci)
    db.session.commit()
    return jsonify({'success': True, 'id': ci.id})


@app.route('/api/admin/items/<item_id>', methods=['PUT', 'DELETE'])
@admin_required
def api_admin_item_detail(item_id):
    ci = CatalogItem.query.get_or_404(item_id)

    if request.method == 'PUT':
        data = request.get_json()
        for field in ['category', 'subcategory', 'title', 'description', 'level',
                       'section', 'note', 'icon']:
            if field in data:
                setattr(ci, field, data[field])
        if 'score' in data:
            ci.score = float(data['score'])
        db.session.commit()
        return jsonify({'success': True})

    elif request.method == 'DELETE':
        ci.is_active = False
        db.session.commit()
        return jsonify({'success': True})


@app.route('/api/admin/items/ai-fill', methods=['POST'])
@admin_required
def api_admin_ai_fill():
    """AI智能填充新项目字段"""
    data = request.get_json()
    activity_name = data.get('name', '')
    activity_description = data.get('description', '')
    suggestion = ai_suggest_item_fields(activity_name, activity_description)
    return jsonify(suggestion)


# ============================================================
# API: Profile
# ============================================================

@app.route('/api/profile', methods=['PUT'])
@login_required
def api_update_profile():
    data = request.get_json()
    if data.get('name'):
        current_user.name = data['name']
    if data.get('department'):
        current_user.department = data['department']
    if data.get('class_name') is not None:
        current_user.class_name = data['class_name']
    if 'gpa_score' in data:
        val = data['gpa_score']
        current_user.gpa_score = float(val) if val else None
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# Error Handlers
# ============================================================

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('base.html'), 404


@app.errorhandler(403)
def forbidden(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify({'error': '无权访问'}), 403


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
