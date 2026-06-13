from app import app, db
from models import User

def check_all_users():
    with app.app_context():
        users = User.query.all()

        print("=" * 70)
        print(f"{'ID':<5} {'用户名':<15} {'真实姓名':<15} {'角色':<10} {'状态':<10}")
        print("=" * 70)

        for user in users:
            print(f"{user.id:<5} {user.username:<15} {user.real_name:<15} {user.role:<10} {user.status:<10}")

        print("=" * 70)
        print(f"总用户数: {len(users)}")

        # 查找所有 real_name 为"系统管理员"的用户
        admins = User.query.filter_by(real_name='系统管理员').all()
        if len(admins) > 1:
            print("\n⚠️  警告：发现多个用户名为'系统管理员'的用户！")
            for admin in admins:
                print(f"  ID: {admin.id}, 用户名: {admin.username}, 角色: {admin.role}")

if __name__ == '__main__':
    check_all_users()
