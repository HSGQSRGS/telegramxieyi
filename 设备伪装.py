"""设备伪装模块 - 协议工具箱
作者: Lion
生成模拟设备型号、系统版本、应用版本、内置白名单 ID、举报原因映射等
"""
import random
import requests
from 配置 import 作者名称

品牌池 = ['Dell', 'HP', 'Lenovo', 'Asus', 'Acer', 'MSI', 'Microsoft', 'Apple', 'Huawei', 'Samsung']
型号池 = ['XPS', 'Inspiron', 'Latitude', 'Precision', 'EliteBook', 'ProBook', 'ThinkPad', 'IdeaPad',
        'ROG', 'TUF', 'Swift', 'Nitro', 'Surface', 'MacBook', 'MateBook', 'Galaxy Book']
后缀池 = ['', ' 15', ' 13', ' 14', ' 16', ' Pro', ' Air', ' Ultra', ' Gaming', ' 2-in-1']
年份池 = ['2022', '2023', '2024', 'Gen 3', 'Gen 4', 'Gen 5']
Windows版本 = [
    'Windows 10 Pro', 'Windows 11 Pro', 'Windows 10 Enterprise', 'Windows 11 Enterprise',
    'Windows 10 Home', 'Windows 11 Home', 'Windows 10 Education', 'Windows 11 Education'
]
桌面应用版本 = [
    '4.10.2 x64', '4.11.0 x64', '4.12.1 x64', '4.13.0 x64',
    '5.0.1 x64', '5.1.0 x64', '5.2.0 x64'
]
安卓版本 = ['Android 11', 'Android 12', 'Android 13', 'Android 14', 'Android 15']
安卓型号 = [
    'Samsung Galaxy S21', 'Samsung Galaxy S22', 'Samsung Galaxy S23',
    'Xiaomi 12', 'Xiaomi 13', 'Xiaomi 14',
    'OnePlus 9', 'OnePlus 10', 'OnePlus 11',
    'Google Pixel 6', 'Google Pixel 7', 'Google Pixel 8',
    'OPPO Find X5', 'OPPO Find X6',
    'vivo X80', 'vivo X90'
]
安卓应用版本 = [
    '10.6.0 (45678)', '10.7.0 (46890)', '10.8.0 (47890)',
    '11.0.0 (50001)', '11.1.0 (51234)', '11.2.0 (52468)'
]
TG官方ID = 777000
白名单ID = [777000, 42777, 333000, 4244000]
白名单用户名 = ["spambot", "premiumbot", "wallet", "notoscam",
               "gdprbot", "stickers", "botfather"]
预设表情 = ["👍", "❤️", "🔥", "🥰", "👏", "🎉", "💯", "😍", "🤩", "😘",
           "👎", "💩", "🤡", "💔", "😡", "🤬", "😤", "🙄", "😒", "🖕"]
举报原因映射 = {
    'spam': '垃圾广告',
    'violence': '暴力内容',
    'pornography': '色情内容',
    'child_abuse': '虐待儿童',
    'copyright': '侵犯版权',
    'fake': '假冒身份',
    'illegal_drugs': '非法毒品',
    'personal_details': '泄露隐私',
    'other': '其他原因',
    'geo': '地理位置',
}
隐私选项 = [
    'phone_number', 'add_by_phone', 'last_seen', 'profile_photo',
    'forwards', 'phone_call', 'group_invite'
]

def 生成桌面环境():
    brand = random.choice(品牌池)
    series = random.choice(型号池)
    suffix = random.choice(后缀池)
    year = random.choice(年份池)
    device_model = f"{brand} {series}{suffix} {year}".strip()
    system_version = random.choice(Windows版本)
    app_version = random.choice(桌面应用版本)
    return {
        'device_model': device_model,
        'system_version': system_version,
        'app_version': app_version,
        'system_lang_code': 'en-US',
        'lang_code': 'en',
        'lang_pack': 'tdesktop'
    }

def 生成安卓环境():
    device_model = random.choice(安卓型号)
    system_version = random.choice(安卓版本)
    app_version = random.choice(安卓应用版本)
    return {
        'device_model': device_model,
        'system_version': system_version,
        'app_version': app_version,
        'system_lang_code': 'en',
        'lang_code': 'en',
        'lang_pack': 'android'
    }

def 生成环境(设备类型='desktop'):
    if 设备类型 == 'android':
        return 生成安卓环境()
    return 生成桌面环境()

def 生成魔法型号():
    设备类型列表 = ['Desktop', 'SMARTPHONE', 'Pad']
    前缀池 = ['K', 'Z', 'A', 'T', 'U', 'P', 'M', 'S', 'Q']
    型号数字池 = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
               '20', '30', '40', '50', '60', '70', '80', '90', '100']
    后缀型号池 = ['i', 'E', 'Pro', 'ProMax']
    版本池 = ['5G', '4G']
    设备类型 = random.choice(设备类型列表)
    prefix = random.choice(前缀池)
    model = random.choice(型号数字池)
    suffix = random.choice(后缀型号池)
    version = random.choice(版本池)
    return f'{作者名称}Magic {设备类型} {prefix}{model}{suffix} {version}'

def 获取IP信息():
    try:
        resp = requests.get('https://ping0.cc/geo', timeout=5)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None