# Treino Pro Max v4.1

App Android em Python/Kivy para treino pessoal premium, com foco em hipertrofia, ganho de massa, modo ectomorfo, histórico, timer, gráficos, alimentação, fotos, backup, nuvem pessoal e atualização remota pelo RunSite.

## O que há de novo na v4.1

- Conteúdo remoto pelo RunSite.
- Painel admin no backend para editar JSON do app.
- Treinador inteligente.
- Avaliação pós-treino.
- Editor de treinos.
- Relatório semanal.
- Cache remoto local.
- Alertas inteligentes.

## Gerar APK

Use o arquivo `COMO_GERAR_APK_COLAB.txt`.

## Usar com RunSite

Suba o pacote `treino_cloud_runsite_v4_1_ready.zip` no RunSite. No app, entre em:

`Conteúdo remoto RunSite`

Coloque a URL do RunSite e o mesmo token configurado no servidor. Depois clique em baixar conteúdo.


PATCH BUILD PYTHON 3.10:
- requirements fixado para python3==3.10.11 e hostpython3==3.10.11.
- android.minapi alterado para 26 para evitar erro de remote_debugging/preadv no Python 3.14.


## Build zero Colab
Use `COMANDOS_COLAB_DO_ZERO.txt`. Esta versão fixa `p4a.branch = v2024.01.21`, `kivy==2.3.0`, `android.archs = arm64-v8a` e `android.minapi = 26` para evitar erros de Python 3.14 e downloads instáveis.
