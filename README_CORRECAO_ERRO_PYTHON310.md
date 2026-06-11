# Treino Pro Max v4.1 Completo - Correção Python 3.10.11

Este pacote já está corrigido para o erro do GitHub Actions que puxava Python 3.14.

Correções aplicadas:

- `requirements = python3==3.10.11,hostpython3==3.10.11,kivy==2.3.0,plyer`
- `p4a.branch = v2024.01.21` dentro da seção `[app]` do `buildozer.spec`
- limpeza de `.buildozer` antes de gerar APK no GitHub Actions
- licença Android aceita automaticamente
- artifact configurado para baixar o APK ao final

## Como usar

Crie um repositório separado do Render, por exemplo:

```text
treino-pro-max-v41-apk
```

Envie para esse repositório as pastas:

```text
.github/
android_kivy_apk/
```

Depois vá em:

```text
Actions > Gerar APK v4.1 Completo Render > Run workflow
```

Quando ficar verde, baixe em **Artifacts**:

```text
treino-pro-max-v4-1-completo-render-apk
```

O APK já vem preparado para conectar em:

```text
https://treino-cloud-runsite.onrender.com
```

Token do APK:

```text
treino-pro-max-online-2026
```
