import qrcode
import os
from datetime import datetime
from flask import current_app
import base64
from io import BytesIO


def generate_check_in_qr(activity_id, check_in_code, save_to_file=True):
    """
    生成活动签到二维码

    Args:
        activity_id: 活动ID
        check_in_code: 签到码
        save_to_file: 是否保存到文件，如果为False则返回base64编码

    Returns:
        str: 二维码图片路径或base64字符串
    """
    # 构建二维码数据
    qr_data = f"{activity_id}:{check_in_code}"

    # 创建二维码对象
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 高容错率
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    # 生成图片
    img = qr.make_image(fill_color="black", back_color="white")

    if save_to_file:
        # 保存到文件
        upload_folder = current_app.config['UPLOAD_FOLDER']
        qr_folder = os.path.join(upload_folder, 'qr_codes')
        os.makedirs(qr_folder, exist_ok=True)

        filename = f"qr_{activity_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(qr_folder, filename)

        img.save(filepath)

        # 返回相对路径
        return f"qr_codes/{filename}"
    else:
        # 返回base64编码（用于API响应）
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"


def generate_qr_with_info(activity_title, activity_id, check_in_code, location, start_time):
    """
    生成包含详细信息的签到二维码（带文字说明）

    Args:
        activity_title: 活动标题
        activity_id: 活动ID
        check_in_code: 签到码
        location: 活动地点
        start_time: 活动开始时间

    Returns:
        str: 二维码图片路径
    """
    from PIL import Image, ImageDraw, ImageFont

    # 生成基础二维码
    qr_path = generate_check_in_qr(activity_id, check_in_code)

    # 如果需要添加文字信息，可以在这里扩展
    # 目前返回基础二维码路径
    return qr_path


def verify_check_in_code(input_code, activity_check_in_code):
    """
    验证签到码是否正确

    Args:
        input_code: 用户输入的签到码
        activity_check_in_code: 活动的正确签到码

    Returns:
        bool: 是否匹配
    """
    return input_code.strip() == activity_check_in_code.strip()


def parse_qr_data(qr_data):
    """
    解析二维码数据

    Args:
        qr_data: 二维码中的数据字符串，格式为 "activity_id:check_in_code"

    Returns:
        tuple: (activity_id, check_in_code) 或 None
    """
    try:
        parts = qr_data.split(':')
        if len(parts) == 2:
            activity_id = int(parts[0])
            check_in_code = parts[1]
            return activity_id, check_in_code
    except (ValueError, AttributeError):
        pass

    return None