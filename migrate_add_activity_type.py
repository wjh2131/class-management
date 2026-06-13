from app import app
from models import db
from sqlalchemy import text

def migrate():
    with app.app_context():
        try:
            print("开始数据库迁移...")

            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN monitor_application VARCHAR(20) DEFAULT 'none'"))
                conn.commit()

            print("✓ 成功添加 monitor_application 字段")
            print("✅ 迁移完成！")

        except Exception as e:
            error_msg = str(e).lower()
            if "duplicate column" in error_msg or "already exists" in error_msg:
                print("⚠️  monitor_application 字段已存在")
                print("✅ 数据库已是最新状态")
            else:
                print(f"❌ 迁移失败: {str(e)}")
                raise

if __name__ == '__main__':
    migrate()