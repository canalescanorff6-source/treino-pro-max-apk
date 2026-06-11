# O que a v4 adicionou em relação à v3

1. Remoção da tela de pagamento para uso pessoal.
2. Nova tela de nuvem pessoal com API URL, token e backup.
3. Backend FastAPI opcional para sincronizar backups.
4. Upload real de backup para backend pessoal.
5. Download real de backup da nuvem para arquivo local.
6. Tela de mídia dos exercícios para imagem/GIF/vídeo/link.
7. Pasta assets/media para colocar vídeos e GIFs próprios.
8. Dashboard premium com cards, gráfico e análise automática.
9. Tela de saúde/relógio para passos, sono, batimento e calorias.
10. Exportação CSV dos dados de saúde.
11. Serviço Android de lembretes em segundo plano melhorado.
12. Permissões e buildozer atualizados para mídia e notificações.
13. Interface reorganizada sem seção de monetização.
14. Documentação de nuvem pessoal e uso sem assinatura.

## Ainda depende de configuração externa

- Nuvem real: precisa rodar o backend_personal_cloud.
- Mídia profissional: você precisa anexar seus próprios vídeos/GIFs/imagens.
- Notificações com app fechado: dependem das restrições de bateria do Android.
- Integração direta com Google Fit/Health Connect: em Python/Kivy é limitada; por isso a v4 usa registro manual e CSV.
