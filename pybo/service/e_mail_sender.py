from flask import Flask, request, jsonify, send_from_directory
import smtplib
import os



class EMailSender:
    # ✅ 이메일 설정 (Gmail/Naver 지원)
    EMAIL_SERVICE = "hiworks_ssl"  # "gmail" 또는 "naver" 선택
    EMAIL_SENDER = "davidjung@icetech.co.kr"  # 발신자 이메일 주소
    EMAIL_PASSWORD = "promise2015@"  # 앱 비밀번호 또는 SMTP 비밀번호

    # ✅ SMTP 설정 (사용할 이메일 서비스에 맞게 수정)
    SMTP_CONFIG = {
        "gmail": {
            "server": "smtp.gmail.com",
            "port": 587,  # TLS (STARTTLS)
            "use_ssl": False
        },
        "naver": {
            "server": "smtp.naver.com",
            "port": 587,  # TLS (STARTTLS)
            "use_ssl": False
        },
        "hiworks_ssl": {
            "server": "smtps.hiworks.com",
            "port": 465,  # SSL
            "use_ssl": True
        }
    }

    SMTP_SERVER = SMTP_CONFIG[EMAIL_SERVICE]["server"]
    SMTP_PORT = SMTP_CONFIG[EMAIL_SERVICE]["port"]
    USE_SSL = SMTP_CONFIG[EMAIL_SERVICE]["use_ssl"]