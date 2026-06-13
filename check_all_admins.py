from app import app, db
from models import User

def check_all_admins():
    with app.app_context():
        # 查找所有包含 admin 的用户
        users = User.query.filter(
            (User.username.like('%admin%')) |
            (User.phone == '13800000000') |
            (User.student_id == 'ADMIN001')
        ).all()

        print("=" * 60)
        print("所有可能的管理员账号:")
        print("=" * 60)
        for user in users:
            print(f"用户名: {user.username}")
            print(f"  真实姓名: {user.real_name}")
            print(f"  角色: {user.role} ({user.role_name})")
            print(f"  手机号: {user.phone}")
            print(f"  学号: {user.student_id}")
            print(f"  状态: {user.status}")
            print(f"  班长申请: {user.monitor_application}")
            print("-" * 60)

if __name__ == '__main__':
    check_all_admins()
