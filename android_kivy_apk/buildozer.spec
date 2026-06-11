[app]
title = Treino Pro Max v4.1
package.name = treinopromaxv41
package.domain = br.com.luisborges
source.dir = .
source.include_exts = py,png,jpg,jpeg,json,txt,csv,db,gif,mp4,webp
version = 4.1.0
requirements = python3,kivy==2.3.0,plyer
orientation = portrait
fullscreen = 0
icon.filename = assets/icon.png
presplash.filename = assets/splash.png

# Serviço opcional para lembretes em segundo plano
# # services = reminder:service_reminder.py

android.permissions = INTERNET,VIBRATE,CAMERA,POST_NOTIFICATIONS,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES
android.api = 34
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0

# Usa release estável do python-for-android para evitar Python 3.14 do master
p4a.branch = v2024.01.21
