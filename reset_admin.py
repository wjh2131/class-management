from app import app, db
from models import User, Class

def reset_admin():
    with app.app_context():
        # 删除旧的 admin
        old_admin = User.query.filter_by(username='admin').first()
        if old_admin:
            db.session.delete(old_admin)
            db.session.commit()
            print("已删除旧的 admin 账号")

        # 创建新的 admin
        admin = User(
            username='admin',
            real_name='系统管理员',
            student_id='ADMIN001',
            phone='13800000000',
            email='admin@class.com',
            role='admin',
            status='approved',
            monitor_application='none'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

        print("✅ 新的 admin 账号已创建")
        print("用户名: admin")
        print("密码: admin123")

if __name__ == '__main__':
    reset_admin()
