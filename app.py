from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Class, ClassFund, Achievement, Activity, ActivityRegistration, Leave, CheckInRecord, get_or_404
from utils.decorators import admin_required, teacher_or_admin_required, monitor_or_admin_required, approved_student_required
from utils.jwt_utils import generate_token, token_required, admin_token_required, teacher_or_admin_token_required, monitor_or_admin_token_required
from utils.excel_export import export_class_contact_list, export_achievements_excel, export_leave_records, export_activity_list
from utils.qr_code import generate_check_in_qr
from utils.data_cleanup import clean_old_data, get_data_statistics, schedule_cleanup
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
import uuid
import calendar


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.context_processor
def utility_processor():
    return {
        'now': datetime.now,
        'len': len
    }

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        elif current_user.role == 'monitor':
            return redirect(url_for('monitor_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter((User.username == username) | (User.phone == username)).first()

        if user and user.check_password(password):
            if user.status == 'pending':
                flash('您的账号正在审核中，请耐心等待', 'warning')
                return redirect(url_for('login'))
            elif user.status == 'rejected':
                flash('您的账号审核未通过，请联系管理员', 'error')
                return redirect(url_for('login'))
            else:
                login_user(user)

                token = generate_token(user.id)

                flash(f'欢迎回来，{user.real_name}！', 'success')
                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user.role == 'teacher':
                    return redirect(url_for('teacher_dashboard'))
                elif user.role == 'monitor':
                    return redirect(url_for('monitor_dashboard'))
                else:
                    return redirect(url_for('student_dashboard'))
        else:
            flash('用户名/手机号或密码错误', 'error')

    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter((User.username == username) | (User.phone == username)).first()

    if user and user.check_password(password):
        if user.status != 'approved':
            return jsonify({'message': '账号未通过审核'}), 403

        token = generate_token(user.id)

        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'real_name': user.real_name,
                'role': user.role,
                'role_name': user.role_name
            }
        }), 200
    else:
        return jsonify({'message': '用户名或密码错误'}), 401

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        real_name = request.form.get('real_name')
        student_id = request.form.get('student_id')
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('两次密码不一致', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(student_id=student_id).first():
            flash('学号已注册', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(phone=phone).first():
            flash('手机号已注册', 'error')
            return redirect(url_for('register'))

        user = User(
            username=username,
            real_name=real_name,
            student_id=student_id,
            phone=phone,
            email=email,
            role='student',
            status='pending'
        )
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
            flash('注册成功，请等待管理员审核', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('注册失败，请稍后重试', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录', 'success')
    return redirect(url_for('login'))

# ==================== 管理员路由 ====================

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    pending_users = User.query.filter_by(status='pending').count()
    pending_leaves = Leave.query.filter_by(status='pending').count()
    pending_achievements = Achievement.query.filter_by(status='pending').count()
    pending_monitors = User.query.filter_by(monitor_application='pending').count()
    activities = Activity.query.order_by(Activity.created_at.desc()).limit(5).all()

    total_classes = Class.query.count()
    total_students = User.query.filter_by(role='student', status='approved').count()
    total_teachers = User.query.filter_by(role='teacher', status='approved').count()
    total_achievements = Achievement.query.filter_by(status='approved').count()

    school_activities = Activity.query.filter_by(activity_type='school').count()
    class_activities = Activity.query.filter_by(activity_type='class').count()

    total_income = db.session.query(db.func.sum(ClassFund.amount)).filter_by(type='income').scalar() or 0
    total_expense = db.session.query(db.func.sum(ClassFund.amount)).filter_by(type='expense').scalar() or 0
    balance = total_income - total_expense

    today = datetime.now().date()
    today_registrations = ActivityRegistration.query.filter(
        db.func.date(ActivityRegistration.registered_at) == today
    ).count()

    # SQLite 兼容的月份查询
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1)

    this_month_leaves = Leave.query.filter(
        Leave.applied_at >= month_start,
        Leave.applied_at < month_end
    ).count()

    return render_template('admin/dashboard.html',
                           pending_users=pending_users,
                           pending_leaves=pending_leaves,
                           pending_achievements=pending_achievements,
                           pending_monitors=pending_monitors,
                           activities=activities,
                           total_classes=total_classes,
                           total_students=total_students,
                           total_teachers=total_teachers,
                           total_achievements=total_achievements,
                           school_activities=school_activities,
                           class_activities=class_activities,
                           balance=balance,
                           today_registrations=today_registrations,
                           this_month_leaves=this_month_leaves)


@app.route('/admin/classes', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_classes():
    if request.method == 'POST':
        name = request.form.get('name')
        grade = request.form.get('grade')
        teacher_id = request.form.get('teacher_id')
        description = request.form.get('description')

        new_class = Class(
            name=name,
            grade=grade,
            teacher_id=int(teacher_id) if teacher_id else None,
            description=description
        )

        db.session.add(new_class)
        db.session.commit()
        flash('班级创建成功', 'success')
        return redirect(url_for('admin_classes'))

    classes = Class.query.all()
    teachers = User.query.filter_by(role='teacher', status='approved').all()
    return render_template('admin/classes.html', classes=classes, teachers=teachers)

@app.route('/admin/class_edit/<int:class_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_class_edit(class_id):
    class_obj = get_or_404(Class, class_id)

    if request.method == 'POST':
        class_obj.name = request.form.get('name')
        class_obj.grade = request.form.get('grade')
        teacher_id = request.form.get('teacher_id')
        class_obj.teacher_id = int(teacher_id) if teacher_id else None
        class_obj.description = request.form.get('description')

        db.session.commit()
        flash('班级信息更新成功', 'success')
        return redirect(url_for('admin_classes'))

    teachers = User.query.filter_by(role='teacher', status='approved').all()
    return render_template('admin/class_edit.html', class_obj=class_obj, teachers=teachers)


# ... existing code ...
@app.route('/admin/pending_users')
@login_required
@admin_required
def pending_users():
    users = User.query.filter_by(status='pending').all()
    approved_users = User.query.filter_by(status='approved').order_by(User.created_at.desc()).all()
    classes = Class.query.all()
    return render_template('admin/pending_users.html', users=users, approved_users=approved_users, classes=classes)
# ... existing code ...

# ... existing code ...
@app.route('/admin/approve_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    user = get_or_404(User, user_id)
    action = request.form.get('action')
    class_id = request.form.get('class_id')

    if action == 'approve':
        user.status = 'approved'
        # 如果提供了班级ID，分配班级
        if class_id:
            user.class_id = int(class_id)
        flash(f'已批准用户 {user.real_name}', 'success')
    elif action == 'reject':
        user.status = 'rejected'
        flash(f'已拒绝用户 {user.real_name}', 'warning')

    db.session.commit()
    return redirect(url_for('pending_users'))


# ... existing code ...
@app.route('/admin/assign_class/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def assign_class(user_id):
    """为学生或班长分配或修改班级"""
    user = get_or_404(User, user_id)
    class_id = request.form.get('class_id')

    # 只能为学生和班长分配班级
    if user.role not in ['student', 'monitor']:
        flash('只能为学生或班长分配班级', 'error')
        return redirect(url_for('admin_users'))

    if class_id:
        # 验证班级是否存在
        class_obj = get_or_404(Class, int(class_id))
        old_class = user.student_class
        user.class_id = class_obj.id

        if old_class:
            flash(f'已将 {user.real_name} 从 {old_class.name} 调整到 {class_obj.name}', 'success')
        else:
            flash(f'已将 {user.real_name} 分配到 {class_obj.name}', 'success')
    else:
        # 移除班级分配
        user.class_id = None
        flash(f'已移除 {user.real_name} 的班级分配', 'warning')

    db.session.commit()
    return redirect(url_for('admin_users'))


@app.route('/admin/assign_teacher_class/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def assign_teacher_class(user_id):
    """为班主任分配管理的班级"""
    teacher = get_or_404(User, user_id)
    class_id = request.form.get('class_id')

    # 只能为班主任分配管理的班级
    if teacher.role != 'teacher':
        flash('只能为班主任分配管理的班级', 'error')
        return redirect(url_for('admin_users'))

    if class_id:
        # 验证班级是否存在
        class_obj = get_or_404(Class, int(class_id))

        # 检查该班级是否已有班主任
        existing_teacher = User.query.filter_by(
            id=class_obj.teacher_id
        ).first() if class_obj.teacher_id else None

        class_obj.teacher_id = teacher.id

        if existing_teacher and existing_teacher.id != teacher.id:
            flash(f'已将 {teacher.real_name} 设置为 {class_obj.name} 的班主任（原班主任：{existing_teacher.real_name}）', 'success')
        else:
            flash(f'已将 {teacher.real_name} 设置为 {class_obj.name} 的班主任', 'success')
    else:
        # 移除班主任管理的班级（需要找到该班主任管理的所有班级并清空）
        managed_classes = Class.query.filter_by(teacher_id=teacher.id).all()
        for cls in managed_classes:
            cls.teacher_id = None
        flash(f'已移除 {teacher.real_name} 管理的所有班级', 'warning')

    db.session.commit()
    return redirect(url_for('admin_users'))


@app.route('/admin/teachers', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_teachers():
    if request.method == 'POST':
        username = request.form.get('username')
        real_name = request.form.get('real_name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return redirect(url_for('admin_teachers'))

        teacher = User(
            username=username,
            real_name=real_name,
            student_id=f'T{phone[-6:]}',
            phone=phone,
            email=email,
            role='teacher',
            status='approved'
        )
        teacher.set_password(password)

        db.session.add(teacher)
        db.session.commit()
        flash('班主任添加成功', 'success')
        return redirect(url_for('admin_teachers'))

    teachers = User.query.filter_by(role='teacher').all()
    return render_template('admin/teachers.html', teachers=teachers)


@app.route('/admin/class_fund', methods=['GET', 'POST'])
@login_required
@monitor_or_admin_required
def class_fund():
    if request.method == 'POST':
        class_id = request.form.get('class_id')

        if not class_id:
            flash('请选择所属班级', 'error')
            return redirect(url_for('class_fund'))

        description = request.form.get('description')
        amount = float(request.form.get('amount'))
        fund_type = request.form.get('type')
        operator = request.form.get('operator')
        date_str = request.form.get('date')

        try:
            fund = ClassFund(
                class_id=int(class_id),
                description=description,
                amount=amount,
                type=fund_type,
                operator=operator,
                date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                created_by=current_user.id
            )

            db.session.add(fund)
            db.session.commit()
            flash('班费记录添加成功', 'success')
        except Exception as e:
            db.session.rollback()
            flash('添加班费记录失败，请稍后重试', 'error')

        return redirect(url_for('class_fund'))

    class_id = request.args.get('class_id', type=int)
    if class_id:
        funds = ClassFund.query.filter_by(class_id=class_id).order_by(ClassFund.date.desc()).all()
        total_income = db.session.query(db.func.sum(ClassFund.amount)).filter_by(class_id=class_id,
                                                                                 type='income').scalar() or 0
        total_expense = db.session.query(db.func.sum(ClassFund.amount)).filter_by(class_id=class_id,
                                                                                  type='expense').scalar() or 0
    else:
        funds = ClassFund.query.order_by(ClassFund.date.desc()).all()
        total_income = db.session.query(db.func.sum(ClassFund.amount)).filter_by(type='income').scalar() or 0
        total_expense = db.session.query(db.func.sum(ClassFund.amount)).filter_by(type='expense').scalar() or 0

    balance = total_income - total_expense
    classes = Class.query.all()

    return render_template('admin/class_fund.html',
                           funds=funds,
                           total_income=total_income,
                           total_expense=total_expense,
                           balance=balance,
                           classes=classes,
                           selected_class_id=class_id)


@app.route('/admin/fund_report')
@login_required
@monitor_or_admin_required
def fund_report():
    class_id = request.args.get('class_id', type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    query = ClassFund.query
    if class_id:
        query = query.filter_by(class_id=class_id)

    start_date = datetime(year, month, 1).date()
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)

    query = query.filter(ClassFund.date >= start_date, ClassFund.date <= end_date)
    funds = query.order_by(ClassFund.date).all()

    total_income = sum(f.amount for f in funds if f.type == 'income')
    total_expense = sum(f.amount for f in funds if f.type == 'expense')

    monthly_stats = []
    for m in range(1, 13):
        month_funds = ClassFund.query.filter(
            ClassFund.date >= datetime(year, m, 1).date(),
            ClassFund.date <= (datetime(year, m + 1, 1).date() - timedelta(days=1)) if m < 12 else datetime(year + 1, 1, 1).date() - timedelta(days=1)
        )
        if class_id:
            month_funds = month_funds.filter_by(class_id=class_id)
        month_funds = month_funds.all()

        income = sum(f.amount for f in month_funds if f.type == 'income')
        expense = sum(f.amount for f in month_funds if f.type == 'expense')
        monthly_stats.append({
            'month': m,
            'income': income,
            'expense': expense,
            'balance': income - expense
        })

    classes = Class.query.all()

    return render_template('admin/fund_report.html',
                         funds=funds,
                         total_income=total_income,
                         total_expense=total_expense,
                         monthly_stats=monthly_stats,
                         year=year,
                         month=month,
                         classes=classes,
                         selected_class_id=class_id)

# ... existing code ...
@app.route('/admin/achievements_review')
@login_required
@teacher_or_admin_required
def achievements_review():
    status_filter = request.args.get('status', 'pending')
    category_filter = request.args.get('category', '')
    class_id = request.args.get('class_id', type=int)

    query = Achievement.query.filter_by(status=status_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)
    if class_id:
        query = query.join(User, Achievement.submitter_id == User.id).filter(User.class_id == class_id)

    achievements = query.order_by(Achievement.submitted_at.desc()).all()
    classes = Class.query.all()

    return render_template('admin/achievements_review.html',
                         achievements=achievements,
                         current_status=status_filter,
                         current_category=category_filter,
                         classes=classes,
                         selected_class_id=class_id)
# ... existing code ...


@app.route('/admin/review_achievement/<int:achievement_id>', methods=['POST'])
@login_required
@teacher_or_admin_required
def review_achievement(achievement_id):
    achievement = get_or_404(Achievement, achievement_id)
    action = request.form.get('action')
    comment = request.form.get('comment')
    is_public = request.form.get('is_public') == 'on'

    achievement.status = 'approved' if action == 'approve' else 'rejected'
    achievement.review_comment = comment
    achievement.is_public = is_public
    achievement.reviewed_at = datetime.utcnow()
    achievement.reviewed_by = current_user.id

    db.session.commit()
    flash('审核完成', 'success')
    return redirect(url_for('achievements_review'))


# ... existing code ...
@app.route('/admin/leave_review')
@login_required
@teacher_or_admin_required
def leave_review():
    status_filter = request.args.get('status', 'pending')
    class_id = request.args.get('class_id', type=int)

    query = Leave.query.filter_by(status=status_filter)
    if class_id:
        query = query.join(User, Leave.student_id == User.id).filter(User.class_id == class_id)

    leaves = query.order_by(Leave.applied_at.desc()).all()
    classes = Class.query.all()

    return render_template('admin/leave_review.html',
                         leaves=leaves,
                         current_status=status_filter,
                         classes=classes,
                         selected_class_id=class_id)
# ... existing code ...


@app.route('/admin/review_leave/<int:leave_id>', methods=['POST'])
@login_required
@teacher_or_admin_required
def review_leave(leave_id):
    leave = get_or_404(Leave, leave_id)
    action = request.form.get('action')
    comment = request.form.get('comment')

    leave.status = 'approved' if action == 'approve' else 'rejected'
    leave.review_comment = comment
    leave.reviewed_at = datetime.utcnow()
    leave.reviewed_by = current_user.id

    db.session.commit()
    flash('审核完成', 'success')
    return redirect(url_for('leave_review'))


# ... existing code ...
@app.route('/admin/statistics')
@login_required
@admin_required
def statistics():
    category = request.args.get('category', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    class_id = request.args.get('class_id', type=int)

    query = Achievement.query.filter_by(status='approved')

    if category:
        query = query.filter_by(category=category)
    if start_date:
        query = query.filter(Achievement.submitted_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Achievement.submitted_at <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    if class_id:
        query = query.join(User, Achievement.submitter_id == User.id).filter(User.class_id == class_id)

    achievements = query.all()

    stats_by_category = {}
    for ach in achievements:
        if ach.category not in stats_by_category:
            stats_by_category[ach.category] = 0
        stats_by_category[ach.category] += 1

    stats_by_student = {}
    for ach in achievements:
        if ach.submitter_name not in stats_by_student:
            stats_by_student[ach.submitter_name] = 0
        stats_by_student[ach.submitter_name] += 1

    leave_query = Leave.query.filter_by(status='approved')
    if class_id:
        leave_query = leave_query.join(User, Leave.student_id == User.id).filter(User.class_id == class_id)
    leave_stats = leave_query.all()

    leave_days_by_student = {}
    for leave in leave_stats:
        days = leave.days
        if leave.student.real_name not in leave_days_by_student:
            leave_days_by_student[leave.student.real_name] = 0
        leave_days_by_student[leave.student.real_name] += days

    total_achievements = len(achievements)
    total_leave_days = sum(leave_days_by_student.values())
    classes = Class.query.all()

    return render_template('admin/statistics.html',
                         achievements=achievements,
                         stats_by_category=stats_by_category,
                         stats_by_student=stats_by_student,
                         leave_days_by_student=leave_days_by_student,
                         total_achievements=total_achievements,
                         total_leave_days=total_leave_days,
                         classes=classes,
                         selected_class_id=class_id)
# ... existing code ...



@app.route('/admin/activity_create', methods=['GET', 'POST'])
@login_required
@monitor_or_admin_required
def activity_create():
    if request.method == 'POST':
        activity_type = request.form.get('activity_type', 'class')

        if activity_type == 'class':
            if current_user.role == 'monitor':
                class_id = current_user.class_id
            else:
                class_id = request.form.get('class_id')
                if not class_id:
                    flash('请选择所属班级', 'error')
                    return redirect(url_for('activity_create'))
            class_id = int(class_id)
        else:
            class_id = None

        title = request.form.get('title')
        description = request.form.get('description')
        location = request.form.get('location')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        max_participants = request.form.get('max_participants')
        check_in_enabled = request.form.get('check_in_enabled') == 'on'

        try:
            activity = Activity(
                class_id=class_id,
                title=title,
                description=description,
                location=location,
                start_time=datetime.strptime(start_time, '%Y-%m-%dT%H:%M'),
                end_time=datetime.strptime(end_time, '%Y-%m-%dT%H:%M'),
                max_participants=int(max_participants) if max_participants else None,
                created_by=current_user.id,
                check_in_enabled=check_in_enabled,
                activity_type=activity_type
            )

            if check_in_enabled:
                activity.check_in_code = str(uuid.uuid4())[:8]

            db.session.add(activity)
            db.session.commit()

            if check_in_enabled:
                qr_path = generate_check_in_qr(activity.id, activity.check_in_code)
                flash(f'活动发布成功，签到码: {activity.check_in_code}', 'success')
            else:
                flash('活动发布成功', 'success')
        except Exception as e:
            db.session.rollback()
            flash('活动发布失败，请稍后重试', 'error')
            return redirect(url_for('activity_create'))

        return redirect(url_for('admin_activities'))

    classes = Class.query.all()
    return render_template('admin/activity_create.html', classes=classes)


@app.route('/admin/activities')
@login_required
@monitor_or_admin_required
def admin_activities():
    activity_type = request.args.get('type', '')
    class_id = request.args.get('class_id', type=int)

    query = Activity.query

    if activity_type:
        query = query.filter_by(activity_type=activity_type)

    if class_id:
        query = query.filter_by(class_id=class_id)

    activities = query.order_by(Activity.start_time.desc()).all()
    classes = Class.query.all()

    return render_template('admin/activities.html',
                         activities=activities,
                         classes=classes,
                         current_type=activity_type,
                         selected_class_id=class_id)


@app.route('/admin/activity_edit/<int:activity_id>', methods=['GET', 'POST'])
@login_required
@monitor_or_admin_required
def activity_edit(activity_id):
    activity = get_or_404(Activity, activity_id)

    if request.method == 'POST':
        activity.title = request.form.get('title')
        activity.description = request.form.get('description')
        activity.location = request.form.get('location')
        activity.start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M')
        activity.end_time = datetime.strptime(request.form.get('end_time'), '%Y-%m-%dT%H:%M')
        max_p = request.form.get('max_participants')
        activity.max_participants = int(max_p) if max_p else None

        if activity.activity_type == 'class':
            class_id = request.form.get('class_id')
            activity.class_id = int(class_id) if class_id else None

        db.session.commit()
        flash('活动更新成功', 'success')
        return redirect(url_for('admin_activities'))

    classes = Class.query.all()
    return render_template('admin/activity_edit.html', activity=activity, classes=classes)


@app.route('/admin/activity_delete/<int:activity_id>', methods=['POST'])
@login_required
@monitor_or_admin_required
def activity_delete(activity_id):
    activity = get_or_404(Activity, activity_id)
    db.session.delete(activity)
    db.session.commit()
    flash('活动已删除', 'success')
    return redirect(url_for('admin_activities'))


@app.route('/admin/activity_checkin/<int:activity_id>')
@login_required
@monitor_or_admin_required
def activity_checkin(activity_id):
    activity = get_or_404(Activity, activity_id)

    if not activity.check_in_enabled:
        flash('该活动未启用签到功能', 'warning')
        return redirect(url_for('admin_activities'))

    check_in_code = request.args.get('code')

    if check_in_code and check_in_code == activity.check_in_code:
        registration = ActivityRegistration.query.filter_by(
            activity_id=activity_id,
            student_id=current_user.id
        ).first()

        if registration:
            existing_checkin = CheckInRecord.query.filter_by(
                activity_id=activity_id,
                student_id=current_user.id
            ).first()

            if not existing_checkin:
                check_in = CheckInRecord(
                    activity_id=activity_id,
                    student_id=current_user.id,
                    check_in_time=datetime.utcnow()
                )
                db.session.add(check_in)
                registration.check_in_time = datetime.utcnow()
                db.session.commit()
                flash('签到成功', 'success')
            else:
                flash('您已经签到过了', 'warning')
        else:
            flash('您未报名此活动', 'error')
    elif check_in_code:
        flash('签到码错误', 'error')

    return redirect(url_for('activities'))


@app.route('/admin/export_contact')
@login_required
@monitor_or_admin_required
def export_contact():
    class_id = request.args.get('class_id', type=int)
    filename = export_class_contact_list(class_id)
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
    return send_from_directory(export_dir, os.path.basename(filename), as_attachment=True)

@app.route('/admin/export_achievements')
@login_required
@teacher_or_admin_required
def export_achievements():
    class_id = request.args.get('class_id', type=int)
    status = request.args.get('status', 'approved')
    filename = export_achievements_excel(class_id, status)
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
    return send_from_directory(export_dir, os.path.basename(filename), as_attachment=True)

@app.route('/admin/export_leaves')
@login_required
@teacher_or_admin_required
def export_leaves():
    class_id = request.args.get('class_id', type=int)
    status = request.args.get('status', 'approved')
    filename = export_leave_records(class_id, status)
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
    return send_from_directory(export_dir, os.path.basename(filename), as_attachment=True)

@app.route('/admin/export_activities')
@login_required
@monitor_or_admin_required
def export_activities():
    activity_type = request.args.get('type', '')
    filename = export_activity_list(activity_type if activity_type else None)
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
    return send_from_directory(export_dir, os.path.basename(filename), as_attachment=True)


# ... existing code ...
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.filter_by(status='approved').order_by(User.created_at.desc()).all()
    classes = Class.query.all()
    return render_template('admin/users.html', users=users, classes=classes)
# ... existing code ...

@app.route('/admin/monitor_applications')
@login_required
@admin_required
def monitor_applications():
    """管理员查看班长申请"""
    pending = User.query.filter_by(monitor_application='pending').all()
    approved = User.query.filter_by(monitor_application='approved').all()
    rejected = User.query.filter_by(monitor_application='rejected').all()

    return render_template('admin/monitor_applications.html',
                         pending=pending,
                         approved=approved,
                         rejected=rejected)

# ... existing code ...
@app.route('/admin/review_monitor_application/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def review_monitor_application(user_id):
    user = get_or_404(User, user_id)
    action = request.form.get('action')

    if action == 'approve':
        # 防止管理员账号被降级为班长
        if user.role == 'admin':
            flash(f'不能将管理员 {user.real_name} 设置为班长', 'error')
            return redirect(url_for('monitor_applications'))

        user.monitor_application = 'approved'
        user.role = 'monitor'
        flash(f'已批准 {user.real_name} 的班长申请', 'success')
    elif action == 'reject':
        user.monitor_application = 'rejected'
        flash(f'已拒绝 {user.real_name} 的班长申请', 'warning')

    db.session.commit()
    return redirect(url_for('monitor_applications'))
# ... existing code ...



@app.route('/admin/cleanup_data', methods=['GET', 'POST'])
@login_required
@admin_required
def cleanup_data():
    """手动触发数据清理"""
    if request.method == 'POST':
        try:
            retention_years = int(request.form.get('retention_years', 5))
            dry_run = request.form.get('dry_run') == 'on'

            if retention_years < 1 or retention_years > 10:
                flash('保留年限必须在1-10年之间', 'error')
                return redirect(url_for('cleanup_data'))

            result = clean_old_data(retention_years=retention_years, dry_run=dry_run)

            if dry_run:
                flash(f'试运行完成，预计将清理以下数据: 成果{result["achievements"]}条, 活动{result["activities"]}条, 请假{result["leaves"]}条, 班费{result["funds"]}条, 签到{result["check_ins"]}条', 'info')
            else:
                total = sum(result.values())
                flash(f'数据清理完成！共清理 {total} 条记录: 成果{result["achievements"]}条, 活动{result["activities"]}条, 请假{result["leaves"]}条, 班费{result["funds"]}条, 签到{result["check_ins"]}条', 'success')

            return redirect(url_for('admin_dashboard'))
        except ValueError:
            flash('保留年限必须是有效数字', 'error')
            return redirect(url_for('cleanup_data'))
        except Exception as e:
            flash(f'数据清理失败: {str(e)}', 'error')
            return redirect(url_for('cleanup_data'))

    # GET请求显示清理页面
    stats = get_data_statistics()
    return render_template('admin/cleanup_data.html', stats=stats)

@app.route('/admin/data_statistics')
@login_required
@admin_required
def data_statistics():
    """查看数据统计"""
    stats = get_data_statistics()
    return render_template('admin/data_statistics.html', stats=stats)

@app.route('/admin/api/cleanup_preview')
@login_required
@admin_required
def cleanup_preview():
    """API接口：预览将要清理的数据"""
    try:
        retention_years = request.args.get('retention_years', 5, type=int)
        result = clean_old_data(retention_years=retention_years, dry_run=True)

        return jsonify({
            'success': True,
            'data': result,
            'total': sum(result.values())
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ==================== 班主任路由 ====================
# ... existing code ...
@app.route('/teacher/dashboard')
@login_required
@teacher_or_admin_required
def teacher_dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))

    my_class = current_user.managed_class[0] if current_user.managed_class else None
    if not my_class:
        flash('您还未管理任何班级', 'warning')
        return redirect(url_for('login'))

    students = User.query.filter_by(class_id=my_class.id, role='student', status='approved').all()
    pending_leaves = Leave.query.join(User, Leave.student_id == User.id).filter(
        User.class_id == my_class.id,
        Leave.status == 'pending'
    ).count()
    pending_achievements = Achievement.query.join(User, Achievement.submitter_id == User.id).filter(
        User.class_id == my_class.id,
        Achievement.status == 'pending'
    ).count()

    recent_activities = Activity.query.filter(
        db.or_(
            Activity.activity_type == 'school',
            Activity.class_id == my_class.id
        )
    ).order_by(Activity.start_time.desc()).limit(5).all()

    return render_template('teacher/dashboard.html',
                         my_class=my_class,
                         students=students,
                         pending_leaves=pending_leaves,
                         pending_achievements=pending_achievements,
                         recent_activities=recent_activities)
# ... existing code ...

@app.route('/teacher/class_info')
@login_required
@teacher_or_admin_required
def teacher_class_info():
    if current_user.role == 'admin':
        return redirect(url_for('admin_classes'))

    my_class = current_user.managed_class[0] if current_user.managed_class else None
    if not my_class:
        flash('您还未管理任何班级', 'warning')
        return redirect(url_for('login'))

    students = User.query.filter_by(class_id=my_class.id, role='student').all()

    return render_template('teacher/class_info.html', my_class=my_class, students=students)
# ... existing code ...
@app.route('/teacher/update_class_info', methods=['POST'])
@login_required
@teacher_or_admin_required
def update_class_info():
    if current_user.role == 'admin':
        return redirect(url_for('admin_classes'))

    my_class = current_user.managed_class[0] if current_user.managed_class else None
    if not my_class:
        flash('您还未管理任何班级', 'warning')
        return redirect(url_for('login'))

    my_class.name = request.form.get('name')
    my_class.grade = request.form.get('grade')
    my_class.description = request.form.get('description')

    db.session.commit()
    flash('班级信息更新成功', 'success')
    return redirect(url_for('teacher_class_info'))

@app.route('/teacher/export_leaves')
@login_required
@teacher_or_admin_required
def teacher_export_leaves():
    """班主任导出请假记录"""
    if current_user.role == 'admin':
        return redirect(url_for('export_leaves'))

    my_class = current_user.managed_class[0] if current_user.managed_class else None
    if not my_class:
        flash('您还未管理任何班级', 'warning')
        return redirect(url_for('teacher_dashboard'))

    status = request.args.get('status', 'approved')
    filename = export_leave_records(my_class.id, status)
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
    return send_from_directory(export_dir, os.path.basename(filename), as_attachment=True)


@app.route('/teacher/export_activities')
@login_required
@teacher_or_admin_required
def teacher_export_activities():
    """班主任导出活动列表"""
    if current_user.role == 'admin':
        return redirect(url_for('export_activities'))

    activity_type = request.args.get('type', '')
    filename = export_activity_list(activity_type if activity_type else None)
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
    return send_from_directory(export_dir, os.path.basename(filename), as_attachment=True)


@app.route('/teacher/activity_create', methods=['GET', 'POST'])
@login_required
@teacher_or_admin_required
def teacher_activity_create():
    """班主任发布活动"""
    if current_user.role == 'admin':
        return redirect(url_for('activity_create'))

    my_class = current_user.managed_class[0] if current_user.managed_class else None
    if not my_class:
        flash('您还未管理任何班级', 'warning')
        return redirect(url_for('teacher_dashboard'))

    if request.method == 'POST':
        activity_type = request.form.get('activity_type', 'class')

        if activity_type == 'class':
            class_id = my_class.id
        else:
            class_id = None

        title = request.form.get('title')
        description = request.form.get('description')
        location = request.form.get('location')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        max_participants = request.form.get('max_participants')
        check_in_enabled = request.form.get('check_in_enabled') == 'on'

        try:
            activity = Activity(
                class_id=class_id,
                title=title,
                description=description,
                location=location,
                start_time=datetime.strptime(start_time, '%Y-%m-%dT%H:%M'),
                end_time=datetime.strptime(end_time, '%Y-%m-%dT%H:%M'),
                max_participants=int(max_participants) if max_participants else None,
                created_by=current_user.id,
                check_in_enabled=check_in_enabled,
                activity_type=activity_type
            )

            if check_in_enabled:
                activity.check_in_code = str(uuid.uuid4())[:8]

            db.session.add(activity)
            db.session.commit()

            if check_in_enabled:
                qr_path = generate_check_in_qr(activity.id, activity.check_in_code)
                flash(f'活动发布成功，签到码: {activity.check_in_code}', 'success')
            else:
                flash('活动发布成功', 'success')
        except Exception as e:
            db.session.rollback()
            flash('活动发布失败，请稍后重试', 'error')
            return redirect(url_for('teacher_activity_create'))

        return redirect(url_for('teacher_dashboard'))

    return render_template('admin/activity_create.html', classes=[my_class])


# ==================== 班长路由 ====================
# ... existing code ...
@app.route('/monitor/dashboard')
@login_required
@monitor_or_admin_required
def monitor_dashboard():
    if current_user.role in ['admin', 'teacher']:
        return redirect(url_for('admin_dashboard'))

    my_class = current_user.student_class
    if not my_class:
        flash('您还未分配班级', 'warning')
        return redirect(url_for('login'))

    classmates = User.query.filter_by(class_id=my_class.id, role='student', status='approved').count()

    class_activities = Activity.query.filter_by(class_id=my_class.id, activity_type='class').count()
    school_activities = Activity.query.filter_by(activity_type='school').count()
    my_activities = class_activities + school_activities

    recent_activities = Activity.query.filter(
        db.or_(
            Activity.activity_type == 'school',
            Activity.class_id == my_class.id
        )
    ).order_by(Activity.start_time.desc()).limit(5).all()

    class_achievements = Achievement.query.join(User, Achievement.submitter_id == User.id).filter(
        User.class_id == my_class.id,
        Achievement.status == 'approved'
    ).count()

    total_income = db.session.query(db.func.sum(ClassFund.amount)).filter_by(
        class_id=my_class.id, type='income'
    ).scalar() or 0
    total_expense = db.session.query(db.func.sum(ClassFund.amount)).filter_by(
        class_id=my_class.id, type='expense'
    ).scalar() or 0
    balance = total_income - total_expense

    recent_funds = ClassFund.query.filter_by(class_id=my_class.id).order_by(
        ClassFund.date.desc()
    ).limit(5).all()

    return render_template('monitor/dashboard.html',
                         my_class=my_class,
                         classmates=classmates,
                         my_activities=my_activities,
                         class_activities=class_activities,
                         class_achievements=class_achievements,
                         balance=balance,
                         recent_activities=recent_activities,
                         recent_funds=recent_funds)
# ... existing code ...

# ==================== 学生路由 ====================

@app.route('/student/dashboard')
@login_required
@approved_student_required
def student_dashboard():
    my_achievements = Achievement.query.filter_by(submitter_id=current_user.id).order_by(Achievement.submitted_at.desc()).limit(5).all()
    my_leaves = Leave.query.filter_by(student_id=current_user.id).order_by(Leave.applied_at.desc()).limit(5).all()

    class_id = current_user.class_id

    if class_id:
        activities = Activity.query.filter(
            db.or_(
                Activity.activity_type == 'school',
                db.and_(Activity.activity_type == 'class', Activity.class_id == class_id)
            ),
            Activity.status == 'open'
        ).order_by(Activity.start_time.asc()).limit(5).all()
    else:
        activities = Activity.query.filter(
            Activity.activity_type == 'school',
            Activity.status == 'open'
        ).order_by(Activity.start_time.asc()).limit(5).all()

    my_approved_achievements = Achievement.query.filter_by(submitter_id=current_user.id, status='approved').count()
    my_pending_leaves = Leave.query.filter_by(student_id=current_user.id, status='pending').count()

    return render_template('student/dashboard.html',
                         my_achievements=my_achievements,
                         my_leaves=my_leaves,
                         activities=activities,
                         my_approved_achievements=my_approved_achievements,
                         my_pending_leaves=my_pending_leaves)


@app.route('/student/upload_achievement', methods=['GET', 'POST'])
@login_required
@approved_student_required
def upload_achievement():
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        description = request.form.get('description')

        attachment_path = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                attachment_path = filename

        achievement = Achievement(
            title=title,
            category=category,
            description=description,
            submitter_id=current_user.id,
            submitter_name=current_user.real_name,
            attachment_path=attachment_path
        )

        db.session.add(achievement)
        db.session.commit()
        flash('成果上传成功，等待审核', 'success')
        return redirect(url_for('my_achievements'))

    return render_template('student/upload_achievement.html')

@app.route('/student/my_achievements')
@login_required
@approved_student_required
def my_achievements():
    achievements = Achievement.query.filter_by(submitter_id=current_user.id).order_by(Achievement.submitted_at.desc()).all()
    return render_template('student/my_achievements.html', achievements=achievements)

@app.route('/student/activities')
@login_required
@approved_student_required
def activities():
    activity_type = request.args.get('type', '')

    query = Activity.query.filter_by(status='open')

    if activity_type:
        query = query.filter_by(activity_type=activity_type)
    else:
        if current_user.class_id:
            query = query.filter(
                db.or_(
                    Activity.activity_type == 'school',
                    db.and_(Activity.activity_type == 'class', Activity.class_id == current_user.class_id)
                )
            )
        else:
            query = query.filter_by(activity_type='school')

    all_activities = query.order_by(Activity.start_time.asc()).all()

    return render_template('student/activities.html',
                         activities=all_activities,
                         current_type=activity_type)

@app.route('/student/register_activity/<int:activity_id>', methods=['POST'])
@login_required
@approved_student_required
def register_activity(activity_id):
    activity = get_or_404(Activity, activity_id)

    existing = ActivityRegistration.query.filter_by(activity_id=activity_id, student_id=current_user.id).first()
    if existing:
        flash('您已经报名过此活动', 'warning')
        return redirect(url_for('activities'))

    if activity.max_participants:
        count = ActivityRegistration.query.filter_by(activity_id=activity_id, status='approved').count()
        if count >= activity.max_participants:
            flash('活动人数已满', 'error')
            return redirect(url_for('activities'))

    registration = ActivityRegistration(
        activity_id=activity_id,
        student_id=current_user.id,
        status='approved'
    )

    db.session.add(registration)
    db.session.commit()
    flash('报名成功', 'success')
    return redirect(url_for('activities'))


@app.route('/student/leave_apply', methods=['GET', 'POST'])
@login_required
@approved_student_required
def leave_apply():
    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason')

        if datetime.strptime(start_date, '%Y-%m-%d').date() > datetime.strptime(end_date, '%Y-%m-%d').date():
            flash('结束日期不能早于开始日期', 'error')
            return redirect(url_for('leave_apply'))

        attachment_path = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                attachment_path = filename

        leave = Leave(
            student_id=current_user.id,
            leave_type=leave_type,
            start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
            end_date=datetime.strptime(end_date, '%Y-%m-%d').date(),
            reason=reason,
            attachment_path=attachment_path
        )

        db.session.add(leave)
        db.session.commit()
        flash('请假申请提交成功，等待审核', 'success')
        return redirect(url_for('my_leaves'))

    return render_template('student/leave_apply.html')

@app.route('/student/my_leaves')
@login_required
@approved_student_required
def my_leaves():
    leaves = Leave.query.filter_by(student_id=current_user.id).order_by(Leave.applied_at.desc()).all()
    return render_template('student/my_leaves.html', leaves=leaves)

@app.route('/student/apply_monitor', methods=['GET', 'POST'])
@login_required
@approved_student_required
def apply_monitor():
    """学生申请成为班长"""
    if current_user.role == 'monitor':
        flash('您已经是班长了', 'warning')
        return redirect(url_for('student_dashboard'))

    if current_user.monitor_application == 'pending':
        flash('您的申请正在审核中，请耐心等待', 'warning')
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        current_user.monitor_application = 'pending'
        db.session.commit()

        flash('申请已提交，请等待管理员审核', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('student/apply_monitor.html')

@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==================== API 接口 ====================

@app.route('/api/check_in', methods=['POST'])
@token_required
def api_check_in(user):
    data = request.get_json()
    activity_id = data.get('activity_id')
    check_in_code = data.get('check_in_code')

    activity = db.session.get(Activity, activity_id)
    if not activity:
        return jsonify({'message': '活动不存在'}), 404

    if not activity.check_in_enabled:
        return jsonify({'message': '该活动未启用签到'}), 400

    if check_in_code != activity.check_in_code:
        return jsonify({'message': '签到码错误'}), 400

    registration = ActivityRegistration.query.filter_by(
        activity_id=activity_id,
        student_id=user.id
    ).first()

    if not registration:
        return jsonify({'message': '您未报名此活动'}), 400

    existing = CheckInRecord.query.filter_by(
        activity_id=activity_id,
        student_id=user.id
    ).first()

    if existing:
        return jsonify({'message': '您已经签到过了'}), 400

    check_in = CheckInRecord(
        activity_id=activity_id,
        student_id=user.id,
        check_in_time=datetime.utcnow()
    )
    registration.check_in_time = datetime.utcnow()

    db.session.add(check_in)
    db.session.commit()

    return jsonify({'message': '签到成功'}), 200

@app.route('/api/data_statistics')
@admin_token_required
def api_data_statistics(admin_user):
    """API接口：获取数据统计"""
    stats = get_data_statistics()
    return jsonify({
        'success': True,
        'data': stats
    })

# ==================== 初始化数据库 ====================

def init_db():
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                real_name='系统管理员',
                student_id='ADMIN001',
                phone='13800000000',
                email='admin@class.com',
                role='admin',
                status='approved'
            )
            admin.set_password('admin123')
            db.session.add(admin)

            default_class = Class(
                name='计算机科学与技术1班',
                grade='2024级',
                description='默认班级'
            )
            db.session.add(default_class)

            db.session.commit()
            print('管理员账号创建成功: admin / admin123')
            print('默认班级创建成功')

        # 启动定时数据清理任务（每月1号凌晨2点执行）
        try:
            schedule_cleanup(app, retention_years=5)
            print('定时数据清理任务已启动')
        except Exception as e:
            print(f'定时任务启动失败: {e}')
            print('提示: 如需使用定时清理功能，请安装 APScheduler: pip install APScheduler==3.10.4')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
