from datetime import datetime, timedelta
from models import db, Achievement, Activity, Leave, ClassFund, CheckInRecord, ActivityRegistration
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_old_data(retention_years=5, dry_run=False):
    """
    清理超过存储期限的旧数据

    Args:
        retention_years: 数据保留年限，默认5年
        dry_run: 如果为True，只统计不删除

    Returns:
        dict: 包含各表删除数量的字典
    """
    cutoff_date = datetime.utcnow() - timedelta(days=retention_years * 365)

    logger.info(f"开始清理 {cutoff_date} 之前的数据...")

    deleted = {
        'achievements': 0,
        'activities': 0,
        'activity_registrations': 0,
        'leaves': 0,
        'funds': 0,
        'check_ins': 0
    }

    try:
        # 1. 清理旧成果记录
        old_achievements = Achievement.query.filter(Achievement.submitted_at < cutoff_date).all()
        deleted['achievements'] = len(old_achievements)
        logger.info(f"找到 {deleted['achievements']} 条过期成果记录")

        if not dry_run:
            for item in old_achievements:
                db.session.delete(item)

        # 2. 清理旧活动报名记录（先清理关联记录）
        old_registrations = ActivityRegistration.query.join(Activity).filter(
            Activity.created_at < cutoff_date
        ).all()
        deleted['activity_registrations'] = len(old_registrations)
        logger.info(f"找到 {deleted['activity_registrations']} 条过期活动报名记录")

        if not dry_run:
            for item in old_registrations:
                db.session.delete(item)

        # 3. 清理旧活动签到记录
        old_checkins = CheckInRecord.query.join(Activity).filter(
            Activity.created_at < cutoff_date
        ).all()
        deleted['check_ins'] = len(old_checkins)
        logger.info(f"找到 {deleted['check_ins']} 条过期签到记录")

        if not dry_run:
            for item in old_checkins:
                db.session.delete(item)

        # 4. 清理旧活动
        old_activities = Activity.query.filter(Activity.created_at < cutoff_date).all()
        deleted['activities'] = len(old_activities)
        logger.info(f"找到 {deleted['activities']} 条过期活动记录")

        if not dry_run:
            for item in old_activities:
                db.session.delete(item)

        # 5. 清理旧请假记录
        old_leaves = Leave.query.filter(Leave.applied_at < cutoff_date).all()
        deleted['leaves'] = len(old_leaves)
        logger.info(f"找到 {deleted['leaves']} 条过期请假记录")

        if not dry_run:
            for item in old_leaves:
                db.session.delete(item)

        # 6. 清理旧班费记录
        old_funds = ClassFund.query.filter(ClassFund.created_at < cutoff_date).all()
        deleted['funds'] = len(old_funds)
        logger.info(f"找到 {deleted['funds']} 条过期班费记录")

        if not dry_run:
            for item in old_funds:
                db.session.delete(item)

        # 提交事务
        if not dry_run:
            db.session.commit()
            logger.info("数据清理完成并已提交")
        else:
            logger.info("试运行模式，未执行删除操作")

        # 记录总清理数量
        total_deleted = sum(deleted.values())
        logger.info(f"总计清理 {total_deleted} 条记录")

        return deleted

    except Exception as e:
        db.session.rollback()
        logger.error(f"数据清理失败: {str(e)}")
        raise e


def get_data_statistics():
    """
    获取当前数据统计信息

    Returns:
        dict: 各表的数据统计
    """
    from models import User, Class

    stats = {
        'users': {
            'total': User.query.count(),
            'approved': User.query.filter_by(status='approved').count(),
            'pending': User.query.filter_by(status='pending').count()
        },
        'classes': Class.query.count(),
        'achievements': {
            'total': Achievement.query.count(),
            'approved': Achievement.query.filter_by(status='approved').count(),
            'pending': Achievement.query.filter_by(status='pending').count()
        },
        'activities': Activity.query.count(),
        'leaves': {
            'total': Leave.query.count(),
            'approved': Leave.query.filter_by(status='approved').count(),
            'pending': Leave.query.filter_by(status='pending').count()
        },
        'class_funds': ClassFund.query.count(),
        'check_in_records': CheckInRecord.query.count()
    }

    return stats


def schedule_cleanup(app, retention_years=5):
    """
    设置定时清理任务（需要在生产环境中配合APScheduler使用）

    Args:
        app: Flask应用实例
        retention_years: 数据保留年限
    """
    logger.info(f"数据清理任务已配置，保留期限: {retention_years}年")
    logger.info("提示: 在生产环境中建议使用cron job或APScheduler定期执行clean_old_data()")

    # 示例：每月1号凌晨2点执行清理
    # 需要在requirements.txt中添加: APScheduler==3.10.4
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=lambda: clean_old_data(retention_years),
            trigger=CronTrigger(day=1, hour=2, minute=0),
            id='data_cleanup',
            name='清理过期数据',
            replace_existing=True
        )
        scheduler.start()

        logger.info("定时清理任务已启动")

        # 在应用关闭时停止调度器
        import atexit
        atexit.register(lambda: scheduler.shutdown())

    except ImportError:
        logger.warning("APScheduler未安装，定时任务未启动")
        logger.warning("请手动定期执行clean_old_data()函数或使用系统cron")