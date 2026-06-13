from app import app, db
from models import User

def check_admin():
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()

        if not admin:
            print("❌ 未找到 admin 用户")
            return

        print("=" * 50)
        print("Admin 用户信息:")
        print("=" * 50)
        print(f"用户名: {admin.username}")
        print(f"真实姓名: {admin.real_name}")
        print(f"角色代码: {admin.role}")
        print(f"角色名称: {admin.role_name}")
        print(f"状态: {admin.status}")
        print(f"学号: {admin.student_id}")
        print(f"手机号: {admin.phone}")
        print(f"邮箱: {admin.email}")
        print("=" * 50)

        if admin.role != 'admin':
            print("\n⚠️  警告：admin 用户的角色不是 'admin'！")
            fix = input("是否修复为管理员角色？(yes/no): ")
            if fix.lower() == 'yes':
                admin.role = 'admin'
                db.session.commit()
                print("✅ 已修复为管理员角色")
        else:
            print("\n✅ admin 用户角色正确")

if __name__ == '__main__':
    check_admin()
