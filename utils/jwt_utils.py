import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from models import User, db


def generate_token(user_id):
    """
    生成JWT令牌

    Args:
        user_id: 用户ID

    Returns:
        str: JWT token字符串
    """
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
        'iat': datetime.utcnow(),
        'type': 'access'
    }
    token = jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')
    return token


def verify_token(token):
    """
    验证JWT令牌

    Args:
        token: JWT token字符串

    Returns:
        User对象或None
    """
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])

        if payload.get('type') != 'access':
            return None

        user = db.session.get(User, payload['user_id'])
        return user
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    """
    JWT令牌验证装饰器

    使用方式:
        @app.route('/api/protected')
        @token_required
        def protected_route(user):
            # user参数是已验证的用户对象
            pass
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 从Authorization header中获取token
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        # 也支持从查询参数获取（用于二维码签到等场景）
        if not token:
            token = request.args.get('token')

        if not token:
            return jsonify({'message': '缺少认证令牌', 'code': 401}), 401

        user = verify_token(token)
        if not user:
            return jsonify({'message': '令牌无效或已过期', 'code': 401}), 401

        if user.status != 'approved':
            return jsonify({'message': '账号未通过审核', 'code': 403}), 403

        # 将用户对象传递给被装饰的函数
        return f(user, *args, **kwargs)
    return decorated


def admin_token_required(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    @token_required
    def decorated(user, *args, **kwargs):
        if user.role != 'admin':
            return jsonify({'message': '需要管理员权限', 'code': 403}), 403
        return f(user, *args, **kwargs)
    return decorated


def teacher_or_admin_token_required(f):
    """班主任或管理员权限验证装饰器"""
    @wraps(f)
    @token_required
    def decorated(user, *args, **kwargs):
        if user.role not in ['admin', 'teacher']:
            return jsonify({'message': '需要班主任或管理员权限', 'code': 403}), 403
        return f(user, *args, **kwargs)
    return decorated


def monitor_or_admin_token_required(f):
    """班长或管理员权限验证装饰器"""
    @wraps(f)
    @token_required
    def decorated(user, *args, **kwargs):
        if user.role not in ['admin', 'monitor']:
            return jsonify({'message': '需要班长或管理员权限', 'code': 403}), 403
        return f(user, *args, **kwargs)
    return decorated
