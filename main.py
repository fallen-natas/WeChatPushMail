import os
import sys
import signal
import traceback
import platform
import logging
import asyncio
import config
import itchat
from itchat.content import *
from datetime import datetime
from multiprocessing import Process, Manager
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from requests.packages import urllib3

sender_email = config.EMAIL_ADDRESS
receiver_email = config.RECEIVER_EMAIL
password = config.EMAIL_PASSWORD
smtp_server = config.SMTP_SERVER
# 配置日志
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 创建文件处理器
local_dir = '/opt/wcpm'
file_handler = logging.FileHandler(os.path.join(local_dir, 'error.log'))
file_handler.setLevel(logging.ERROR)
file_handler.setFormatter(log_formatter)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

# 获取 root logger
logger = logging.getLogger('')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

local_dir = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
errorlog_clean = open(os.path.join(local_dir, 'error.log'), 'w').close()

ppid = os.getppid()
pid = os.getpid()

def log_error(exc_info=None):
    """记录错误到日志文件"""
    logging.error("".join(traceback.format_exception(*sys.exc_info())))

def terminate_program():
    """终止程序运行"""
    log_error()
    logging.info('程序终止运行')
    system = platform.system()
    if system == 'Linux':
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    elif system == 'Windows':
        os.system(f'taskkill /F /T /PID {pid}')
    else:
        os.kill(ppid, signal.SIGTERM)

def send_email(subject, message, from_addr, to_addr, password):
    """发送电子邮件"""
    msg = MIMEMultipart()
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))
    try:
        with smtplib.SMTP_SSL(smtp_server, 465) as server:
            server.login(from_addr, password)
            server.send_message(msg)
    except Exception as e:
        logging.error("Failed to send email: %s", str(e))

def run(func):
    """运行协程函数"""
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(func)
    finally:
        loop.close()

@itchat.msg_register(itchat.content.INCOME_MSG, isFriendChat=True, isGroupChat=True)
def process_message(msg):
    """处理接收到的消息并记录到日志与控制台."""
    if not int(msg.get('NotifyCloseContact', 0)):
        message_type = determine_message_type(msg)
        name = determine_name(msg)
        formatted_message = format_message(name, message_type)
        send_email(formatted_message,"微信消息推送",sender_email,receiver_email,password)
        if msg['Type'] == itchat.content.SHARING:
            logger.info('[未知卡片消息]: AppMsgType=%s', msg.get('Text', ''))
        elif msg['Type'] == itchat.content.UNDEFINED:
            logger.info('[未知消息类型]: MsgType=%s', msg.get('Text', ''))
        else:
            logger.info(formatted_message)

def determine_message_type(msg):
    """根据消息类型确定消息符号."""
    message_types = {
        itchat.content.TEXT: msg.get('Text', ''),
        itchat.content.FRIENDS: '好友请求',
        itchat.content.PICTURE: '[图片]',
        itchat.content.RECORDING: '[语音]',
        itchat.content.VIDEO: '[视频]',
        itchat.content.LOCATIONSHARE: '[共享实时位置]',
        itchat.content.CHATHISTORY: '[聊天记录]',
        itchat.content.TRANSFER: '[转账]',
        itchat.content.REDENVELOPE: '[红包]',
        itchat.content.EMOTICON: '[动画表情]',
        itchat.content.SPLITTHEBILL: '[群收款]',
        itchat.content.SHARING: '[卡片消息]',
        itchat.content.UNDEFINED: '[发送了一条消息]',
        itchat.content.VOIP: '[通话邀请]请及时打开微信查看',
        itchat.content.SYSTEMNOTIFICATION: '[系统通知]',
        itchat.content.ATTACHMENT: '[文件]' + (msg.get('Text', '') or ''),
        itchat.content.CARD: '[名片]' + (msg.get('Text', '') or ''),
        itchat.content.MUSICSHARE: '[音乐]' + (msg.get('Text', '') or ''),
        itchat.content.SERVICENOTIFICATION: msg.get('Text', ''),
        itchat.content.MAP: '[位置分享]' + msg.get('Text', ''),
        itchat.content.WEBSHARE: '[链接]' + msg.get('Text', ''),
        itchat.content.MINIPROGRAM: '[小程序]' + msg.get('Text', '')
    }
    return message_types.get(msg['Type'], '[未知类型]')

def determine_name(msg):
    """根据消息来源确定消息名."""
    chatroom_name = ""
    if msg['Type'] == 'GroupChat':
        # 尝试从 User 对象获取群聊名称
        chatroom = next((chat for chat in itchat.get_chatrooms() if chat['UserName'] == msg['User']['UserName']), None)
        if chatroom:
            chatroom_name = chatroom.get('NickName', '')
        else:
            chatroom_name = msg.get('ActualNickName', '')
    return f'群聊 {chatroom_name}' if chatroom_name else msg.get('Name', '')

def format_message(name, message_type):
    """格式化消息."""
    return f'{name}: {message_type}'

async def login_and_run():
    await itchat.auto_login(enableCmdQR=2, hotReload=True)
    await itchat.run()

def main():
    value = Manager().dict()
    send_email("推送程序开始运行","微信消息推送",sender_email,receiver_email,password)
    try:
        urllib3.disable_warnings()
        asyncio.run(login_and_run())
    except KeyboardInterrupt:
        logging.info('程序强制停止运行')
    except Exception:
        terminate_program()

if __name__ == '__main__':
    main()