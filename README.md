# N8N com Chat LLM - Setup Docker

Este projeto configura um ambiente Docker com n8n e uma aplicação de chat que se conecta com uma LLM local.

## Serviços Incluídos

- **n8n**: Plataforma de automação de workflows
- **chat-app**: Aplicação web de chat com interface visual que se conecta com LLM local

## Como Usar

### 1. Iniciar os Serviços

```bash
docker-compose up -d
```

### 2. Acessar o n8n

- URL: http://localhost:4000
- Usuário: admin
- Senha: admin123

### 3. Acessar a Aplicação de Chat

- URL: http://localhost:8000
- Interface visual para chat com LLM
- Conecta automaticamente com o modelo `gpt-oss:latest` na porta 11434

### 4. Configurar a LLM

Certifique-se de que sua LLM está rodando na porta 11434. A aplicação tentará se conectar com:
- Host: `host.docker.internal:11434`
- Modelo: `gpt-oss:latest`
- Endpoint: `/api/generate`

### 5. Testar a Aplicação

Você pode testar a API diretamente:

```powershell
# Verificar status
Invoke-WebRequest -Uri "http://localhost:8000/api/health"

# Enviar mensagem para o chat
Invoke-WebRequest -Uri "http://localhost:8000/api/chat" -Method POST -Headers @{"Content-Type"="application/json"} -Body '{"message": "Olá!"}'
```

## Estrutura do Projeto

```
n8napp/
├── docker-compose.yml           # Configuração dos serviços Docker
├── chat-app/                   # Aplicação de chat
│   ├── Dockerfile              # Imagem Docker da aplicação
│   ├── app.py                  # Backend Flask
│   ├── requirements.txt        # Dependências Python
│   └── templates/
│       └── index.html          # Interface web do chat
├── workflows/                  # Diretório para workflows do n8n
└── README.md                  # Este arquivo
```

## Comandos Úteis

```bash
# Iniciar serviços
docker-compose up -d

# Reconstruir e iniciar
docker-compose up --build -d

# Ver logs
docker-compose logs -f

# Ver logs de um serviço específico
docker-compose logs -f chat-app

# Parar serviços
docker-compose down

# Parar e remover volumes (limpa dados)
docker-compose down -v
```

## Portas Utilizadas

- 4000: n8n Web Interface
- 8000: Chat Application
- 11434: LLM Local (externa ao Docker Compose)

## Volumes

- `n8n_data`: Dados persistentes do n8n
- `./workflows`: Workflows do n8n (mapeado para o host)
