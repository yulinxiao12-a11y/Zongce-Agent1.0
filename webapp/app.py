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
from models import db, User, CatalogItem, UserItem, Submission, UploadedFile, RegulationDoc
from ai_engine import analyze_files, ai_suggest_item_fields
from competitions_data import COMPETITIONS
from activities_data import load_activities, add_activity, update_activity, delete_activity

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
        items = UserItem.query.filter_by(user_id=current_user.id).order_by(
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
        subs = Submission.query.filter_by(user_id=current_user.id).order_by(
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
        ai_confidence = data.get('ai_confidence', 0)
        ai_decision = data.get('ai_decision', 'medium')
        ai_reason = data.get('ai_reason', '')

        ci = CatalogItem.query.get(catalog_item_id)
        if not ci:
            return jsonify({'error': '综测项目不存在'}), 404

        # ---- 查重：已通过/审核中的项目不允许重复提交 ----
        existing_item = UserItem.query.filter_by(
            user_id=current_user.id, catalog_item_id=catalog_item_id
        ).first()
        if existing_item:
            return jsonify({'error': f'该项目「{ci.title}」已在你的星轨加分中（+{existing_item.score}分），不能重复提交', 'code': 'duplicate'}), 409

        existing_sub = Submission.query.filter(
            Submission.user_id == current_user.id,
            Submission.catalog_item_id == catalog_item_id,
            Submission.status.in_(['pending', 'auto_approved']),
        ).first()
        if existing_sub:
            status_label = '审核中' if existing_sub.status == 'pending' else '已AI自动通过'
            return jsonify({'error': f'该项目「{ci.title}」已有提交记录（{status_label}），请等待审核结果', 'code': 'duplicate'}), 409
        # --------------------------------------------------------

        title = ci.title
        description = ci.description

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
        required_proofs = get_required_proofs({'subcategory': ci.subcategory})
        submitted_proof_types = set(f.proof_type for f in proof_files if f.proof_type)
        required_types = set(p['type'] for p in required_proofs)
        missing_proofs = required_types - submitted_proof_types

        proof_filenames = [f.original_filename for f in proof_files]
        proof_filepath = proof_files[0].file_path

        # Determine status based on proof completeness AND AI confidence
        proofs_complete = len(missing_proofs) == 0
        if proofs_complete and ai_decision == 'high':
            status = 'auto_approved'
        elif not proofs_complete:
            status = 'pending'
            ai_reason = (ai_reason + f' [缺失材料: {", ".join(missing_proofs)}]').strip()
        else:
            status = 'pending'

        submission = Submission(
            user_id=current_user.id,
            catalog_item_id=catalog_item_id,
            title=title,
            description=description,
            proof_filename=', '.join(proof_filenames[:3]),
            proof_filepath=proof_filepath,
            completion_date=completion_date,
            status=status,
            ai_confidence=ai_confidence,
            ai_decision=ai_decision,
            ai_reason=ai_reason,
            ai_matched_items=json.dumps({
                'required_proofs': [p['type'] for p in required_proofs],
                'submitted_proofs': list(submitted_proof_types),
                'missing_proofs': list(missing_proofs),
                'proofs_complete': proofs_complete,
            }),
        )
        db.session.add(submission)
        db.session.commit()

        # Link files to submission
        for uf in proof_files:
            uf.submission_id = submission.id
        db.session.commit()

        # Auto-approve: create UserItem
        if status == 'auto_approved':
            ui = UserItem(
                user_id=current_user.id,
                catalog_item_id=catalog_item_id,
                score=ci.score,
                completion_date=completion_date,
                source='upload',
                submission_id=submission.id,
            )
            db.session.add(ui)
            db.session.commit()

        return jsonify({
            'success': True,
            'submission_id': submission.id,
            'status': status,
            'auto_added': status == 'auto_approved',
            'proofs_complete': proofs_complete,
            'missing_proofs': list(missing_proofs),
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
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Submission.query
    if status_filter:
        query = query.filter_by(status=status_filter)

    pagination = query.order_by(
        db.case({'pending': 0, 'auto_approved': 1, 'approved': 2, 'rejected': 3},
                value=Submission.status),
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
            'ai_confidence': round(s.ai_confidence, 1),
            'ai_decision': s.ai_decision,
            'ai_reason': s.ai_reason,
            'review_remarks': s.review_remarks,
            'score': ci.score if ci else 0,
            'level': ci.level if ci else '',
            'category': ci.category if ci else '',
            'required_proofs': proof_info.get('required_proofs', []),
            'submitted_proofs': proof_info.get('submitted_proofs', []),
            'missing_proofs': proof_info.get('missing_proofs', []),
            'proofs_complete': proof_info.get('proofs_complete', False),
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

        # Create UserItem
        score = data.get('score', 0)
        catalog_id = sub.catalog_item_id
        if catalog_id:
            ci = CatalogItem.query.get(catalog_id)
            if ci:
                score = ci.score

        ui = UserItem(
            user_id=sub.user_id,
            catalog_item_id=catalog_id,
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

    elif action == 'reassign':
        new_catalog_id = data.get('catalog_item_id', '')
        ci = CatalogItem.query.get(new_catalog_id)
        if ci:
            sub.catalog_item_id = new_catalog_id
            sub.title = ci.title
            sub.description = ci.description

    db.session.commit()
    return jsonify({'success': True, 'status': sub.status})


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
        'dimension': s.category if hasattr(s, 'category') else (ci.category if ci else 'academic'),
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
    return item


@app.route('/api/material-templates')
@login_required
def api_material_templates():
    dimension_weights = {'moral': 0.2, 'academic': 0.65, 'sports': 0.15}
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
            {'key': key, 'label': value['name'], 'base': value['base'], 'cap': value['extra_max'], 'weight': dimension_weights.get(key, 0)}
            for key, value in CAT_INFO.items()
        ],
        'notes': ['AI初审不等于最终入账，人工审核通过后才写入综测得分。'],
    })


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
        Submission.status.in_(['pending', 'auto_approved']),
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
    status = 'auto_approved' if not missing and ai_decision == 'high' else 'pending'

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
        }, ensure_ascii=False),
    )
    db.session.add(submission)
    db.session.commit()

    for uf in proof_files:
        uf.submission_id = submission.id
    db.session.commit()

    if status == 'auto_approved':
        db.session.add(UserItem(
            user_id=current_user.id,
            catalog_item_id=ci.id,
            score=ci.score,
            source='upload',
            submission_id=submission.id,
        ))
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
        sub.status = 'pending'
        sub.reviewer_id = current_user.id
        sub.review_remarks = data.get('comment', '请补充材料后复核')
        sub.reviewed_at = datetime.utcnow()
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
    return jsonify({
        'opportunity_count': opportunity_count,
        'application_count': Submission.query.count(),
        'pending_count': Submission.query.filter_by(status='pending').count(),
        'approved_score': round(float(approved_score), 1),
        'total_students': User.query.filter_by(role='student', is_active=True).count(),
        'pending_reviews': Submission.query.filter_by(status='pending').count(),
        'approved_today': Submission.query.filter(
            Submission.status.in_(['approved', 'auto_approved']),
            Submission.reviewed_at >= date.today()
        ).count(),
        'total_submissions': Submission.query.count(),
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
