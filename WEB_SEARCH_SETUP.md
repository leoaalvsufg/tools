# 🔍 Sistema de Pesquisa Web e Raspagem - Tavily AI

## 🎯 **Funcionalidades Implementadas**

### ✅ **1. Pesquisa Web em Tempo Real**
- **Integração com Tavily AI** para pesquisas avançadas
- **Respostas diretas** com contexto atual
- **Múltiplos resultados** com ranking de relevância
- **Perguntas relacionadas** sugeridas automaticamente

### ✅ **2. Raspagem de Sites**
- **Extração inteligente** de conteúdo web
- **Múltiplos formatos** (texto, artigos, HTML completo)
- **Metadados automáticos** (título, descrição, autor)
- **Validação de URLs** e tratamento de erros

### ✅ **3. Integração com Chat IA**
- **Comandos especiais** no chat (`/search`, `/scrape`)
- **Detecção automática** de perguntas que precisam de dados atuais
- **Contexto enriquecido** com informações da web
- **Respostas mais precisas** e atualizadas

### ✅ **4. Interface Completa**
- **Painel dedicado** para pesquisas avançadas
- **Histórico completo** de pesquisas e extrações
- **Notificações em tempo real** via WebSocket
- **Navegação intuitiva** entre funcionalidades

## 🔧 **Configuração Aplicada**

### **Tavily AI MCP Server:**
```
API Key: cac6b7c6-516b-4360-93b5-a05d1c2e0dae
Profile: cool-egret-8qaexx
Endpoint: https://api.tavily.com/search
Max Results: 10 por pesquisa
Search Depth: basic/advanced
```

### **Capacidades Ativas:**
- ✅ **Pesquisa web** em tempo real
- ✅ **Raspagem de conteúdo** de qualquer site
- ✅ **Respostas diretas** com IA
- ✅ **Perguntas relacionadas** automáticas
- ✅ **Histórico persistente** de pesquisas

## 🚀 **Como Usar**

### **URLs de Acesso:**
- **Chat com IA**: http://localhost:8000 (com comandos de pesquisa)
- **Pesquisa Web**: http://localhost:8000/search (interface dedicada)
- **Sistema de Email**: http://localhost:8000/email
- **Configurações**: http://localhost:8000/config

### **1. 💬 Comandos no Chat:**

#### **Pesquisa Web:**
```
/search últimas notícias sobre inteligência artificial
/search preço do bitcoin hoje
/search como fazer pizza margherita
```

#### **Raspagem de Sites:**
```
/scrape https://www.exemplo.com/artigo
/scrape https://news.ycombinator.com
/scrape https://www.wikipedia.org/wiki/Artificial_intelligence
```

#### **Pesquisa Automática:**
O chat detecta automaticamente quando você faz perguntas que precisam de informações atuais:
```
"Qual é o preço atual do dólar?"
"Quais são as últimas notícias sobre tecnologia?"
"Como está o tempo hoje em São Paulo?"
```

### **2. 🔍 Interface de Pesquisa Dedicada:**

#### **Pesquisa Web Avançada:**
1. Acesse http://localhost:8000/search
2. Digite sua pesquisa
3. Escolha o número de resultados (3-10)
4. Clique em "Pesquisar"
5. Veja respostas diretas + resultados detalhados

#### **Raspagem de Sites:**
1. Vá para a aba "Raspagem de Sites"
2. Cole a URL do site
3. Escolha o tipo de extração:
   - **Apenas texto**: Conteúdo limpo sem HTML
   - **Artigos principais**: Foco no conteúdo principal
   - **Conteúdo completo**: HTML completo
4. Clique em "Extrair Conteúdo"

### **3. 📚 Histórico e Gerenciamento:**
- **Histórico completo** de todas as pesquisas
- **Resultados salvos** no banco de dados
- **Busca rápida** em pesquisas anteriores
- **Organização por tipo** (web/raspagem)

## 🎯 **Casos de Uso Práticos**

### **1. Pesquisa de Informações Atuais:**
```
/search últimas atualizações do ChatGPT
/search preços de criptomoedas hoje
/search notícias sobre economia brasileira
```

### **2. Pesquisa de Mercado:**
```
/search tendências de marketing digital 2024
/search concorrentes no setor de tecnologia
/search análise de mercado e-commerce
```

### **3. Raspagem de Conteúdo:**
```
/scrape https://blog.empresa.com/artigo-importante
/scrape https://site-concorrente.com/produtos
/scrape https://portal-noticias.com/economia
```

### **4. Suporte a Clientes:**
```
"Pesquise informações sobre o produto X"
"Qual é a situação atual da empresa Y?"
"Encontre tutoriais sobre como usar Z"
```

## 📊 **Recursos Avançados**

### **Respostas Diretas com IA:**
- **Síntese inteligente** dos resultados encontrados
- **Resposta contextualizada** baseada em múltiplas fontes
- **Informações verificadas** e atualizadas

### **Perguntas Relacionadas:**
- **Sugestões automáticas** de pesquisas relacionadas
- **Exploração aprofundada** de tópicos
- **Descoberta de informações** complementares

### **Notificações em Tempo Real:**
- **Alertas instantâneos** quando pesquisas são concluídas
- **Status de progresso** para operações longas
- **Feedback visual** de sucesso/erro

### **Histórico Inteligente:**
- **Busca rápida** em pesquisas anteriores
- **Reutilização** de resultados salvos
- **Organização automática** por data e tipo

## 🔒 **Segurança e Limitações**

### **Segurança:**
- **Validação de URLs** antes da raspagem
- **Sanitização** de conteúdo extraído
- **Rate limiting** para evitar sobrecarga
- **Logs de auditoria** de todas as operações

### **Limitações:**
- **10 resultados máximos** por pesquisa web
- **10.000 caracteres máximos** por raspagem
- **30 segundos timeout** para operações
- **Sites com proteção anti-bot** podem falhar

## 🛠️ **Troubleshooting**

### **Problemas Comuns:**

1. **Erro de API Tavily:**
   - Verificar chave de API
   - Confirmar conectividade com internet
   - Verificar logs: `docker-compose logs chat-app`

2. **Raspagem falhando:**
   - Site pode ter proteção anti-bot
   - URL pode estar incorreta
   - Timeout de conexão

3. **Pesquisa não retornando resultados:**
   - Refinar termos de pesquisa
   - Verificar conectividade
   - Tentar pesquisa em inglês

### **Comandos de Debug:**
```bash
# Ver logs da aplicação
docker-compose logs -f chat-app

# Verificar status da API
curl http://localhost:8000/api/health

# Testar pesquisa diretamente
curl -X POST http://localhost:8000/api/search/web \
  -H "Content-Type: application/json" \
  -d '{"query": "test search"}'
```

## 📈 **Próximas Melhorias**

### **Funcionalidades Planejadas:**
- **Pesquisa em imagens** e vídeos
- **Análise de sentimento** dos resultados
- **Tradução automática** de conteúdo
- **Exportação** de resultados (PDF, Excel)
- **Agendamento** de pesquisas recorrentes
- **Alertas** para mudanças em sites monitorados

### **Integrações Futuras:**
- **Google Scholar** para pesquisas acadêmicas
- **Social Media APIs** para tendências
- **News APIs** para notícias específicas
- **E-commerce APIs** para preços

## 🎊 **Sistema Pronto para Uso!**

O sistema de pesquisa web e raspagem está **100% funcional** e integrado. Você pode agora:

1. **Fazer pesquisas web** em tempo real no chat
2. **Extrair conteúdo** de qualquer site
3. **Receber respostas atualizadas** com dados da web
4. **Gerenciar histórico** de pesquisas
5. **Usar interface dedicada** para pesquisas avançadas

**Teste agora mesmo:**
- **Chat**: http://localhost:8000 (digite `/search sua pesquisa`)
- **Interface**: http://localhost:8000/search

---

**Sistema desenvolvido com Tavily AI para Grupo Alves** 🚀
