
[app]

title = Treino Pro Max Online
package.name = treinopromaxonline
package.domain = org.luiztreino
source.dir = .
source.include_exts = py,json,png,jpg,kv,txt
source.include_patterns = assets/*
version = 5.0.0

requirements = python3,kivy==2.3.0

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 34
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
