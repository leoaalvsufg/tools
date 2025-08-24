# 📧 Sistema de Email com IA - Grupo Alves

## 🎯 **Funcionalidades Implementadas**

### ✅ **1. Composição de Email com IA**
- **Geração automática** de emails usando LLM
- **Análise de contexto** para emails profissionais
- **Edição manual** antes do envio
- **Suporte a HTML** e texto simples

### ✅ **2. Envio de Emails**
- **Integração SMTP** com servidor Grupo Alves
- **Autenticação segura** com TLS
- **Confirmação de envio** em tempo real
- **Histórico de emails enviados**

### ✅ **3. Monitoramento de Emails**
- **Verificação automática** a cada 30 segundos
- **Notificações em tempo real** via WebSocket
- **Histórico de emails recebidos**
- **Dashboard com estatísticas**

### ✅ **4. Interface Completa**
- **Painel de controle** intuitivo
- **Notificações visuais** para novos emails
- **Estatísticas em tempo real**
- **Integração com chat IA**

## 🔧 **Configuração do Servidor**

### **Dados Configurados:**
```
Servidor: grupoalves.net
Email: atende@grupoalves.net
Senha: 123Leo456@7
SMTP: smtp.uni5.net:587 (TLS)
IMAP: imap.uni5.net:143 (TLS)
```

### **Portas Utilizadas:**
- **8000**: Aplicação principal (HTTP + WebSocket)
- **4000**: n8n (admin/admin123)
- **587**: SMTP (saída de emails)
- **143**: IMAP (recebimento de emails)

## 🚀 **Como Usar**

### **1. Iniciar o Sistema:**
```bash
cd n8napp
docker-compose up --build -d
```

### **2. Acessar Interfaces:**
- **Chat com IA**: http://localhost:8000
- **Sistema de Email**: http://localhost:8000/email
- **Configurações**: http://localhost:8000/config
- **n8n**: http://localhost:4000

### **3. Compor Email com IA:**
1. Acesse http://localhost:8000/email
2. Clique em "Compor Email"
3. Descreva o email desejado (ex: "Escreva um email de agradecimento para um cliente")
4. Clique em "Gerar Email com IA"
5. Revise e edite se necessário
6. Adicione o destinatário
7. Clique em "Enviar Email"

### **4. Monitorar Emails:**
- **Caixa de Entrada**: Emails recebidos automaticamente
- **Enviados**: Histórico de emails enviados
- **Dashboard**: Estatísticas e atividade recente
- **Notificações**: Alertas em tempo real

## 📊 **Recursos Avançados**

### **Dashboard de Monitoramento:**
- Total de emails enviados/recebidos
- Emails gerados por IA
- Atividade do dia
- Status da conexão

### **Notificações em Tempo Real:**
- Novos emails recebidos
- Confirmação de envio
- Alertas de erro
- Status da conexão

### **Integração com IA:**
- Geração automática de conteúdo
- Análise de contexto
- Sugestões de assunto
- Formatação profissional

## 🔒 **Segurança**

### **Configurações de Segurança:**
- **TLS/SSL** para SMTP e IMAP
- **Autenticação** com credenciais seguras
- **Validação** de emails
- **Sanitização** de conteúdo

### **Dados Protegidos:**
- Senhas não expostas no frontend
- Conexões criptografadas
- Validação de entrada
- Logs de auditoria

## 🛠️ **Troubleshooting**

### **Problemas Comuns:**

1. **Erro de Conexão SMTP/IMAP:**
   - Verificar credenciais
   - Confirmar configurações do servidor
   - Testar conectividade de rede

2. **Emails não sendo enviados:**
   - Verificar configurações SMTP
   - Confirmar autenticação
   - Verificar logs do container

3. **Notificações não funcionando:**
   - Verificar conexão WebSocket
   - Recarregar a página
   - Verificar console do navegador

### **Comandos de Debug:**
```bash
# Ver logs da aplicação
docker-compose logs -f chat-app

# Verificar status dos containers
docker-compose ps

# Reiniciar serviços
docker-compose restart chat-app

# Verificar conectividade
curl http://localhost:8000/api/health
```

## 📈 **Próximas Melhorias**

### **Funcionalidades Planejadas:**
- **Anexos** em emails
- **Templates** personalizados
- **Agendamento** de envios
- **Filtros** avançados
- **Integração** com CRM
- **Relatórios** detalhados

### **Integrações Futuras:**
- **Calendário** para agendamentos
- **WhatsApp** Business API
- **Telegram** Bot
- **Slack** notifications

## 🎯 **Casos de Uso**

### **Exemplos Práticos:**

1. **Atendimento ao Cliente:**
   - "Escreva um email de resposta para um cliente que está reclamando de atraso na entrega"

2. **Vendas:**
   - "Crie um email de follow-up para um lead que demonstrou interesse no produto X"

3. **Suporte Técnico:**
   - "Redija um email explicando como resolver o problema Y de forma didática"

4. **Marketing:**
   - "Escreva um email promocional para o lançamento do produto Z"

## 📞 **Suporte**

Para dúvidas ou problemas:
- **Email**: atende@grupoalves.net
- **Sistema**: http://localhost:8000/email
- **Logs**: `docker-compose logs chat-app`

---

**Sistema desenvolvido com IA para Grupo Alves** 🚀
