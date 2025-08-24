from flask import Flask, render_template, request, jsonify, session, redirect
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import requests
import json
import os
import uuid
from datetime import datetime
import sqlite3
from threading import Lock, Thread
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import time
import ssl
from bs4 import BeautifulSoup
import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
import re
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import mysql.connector
from pymongo import MongoClient
import redis

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*")

# Database lock for thread safety
db_lock = Lock()

# Configurações padrão
DEFAULT_CONFIG = {
    'provider': 'openrouter',  # Iniciar com gratuito
    'ollama_host': os.getenv('LLM_HOST', 'host.docker.internal'),
    'ollama_port': os.getenv('LLM_PORT', '11434'),
    'ollama_model': 'llama3.2:1b',
    'openrouter_api_key': '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',
    'openrouter_model': 'google/gemma-2-9b-it:free',  # Modelo gratuito
    'max_conversation_length': 20,  # Maximum messages to keep in memory
    'conversation_summary_threshold': 15  # When to start summarizing
}

# Configurações de Email
EMAIL_CONFIG = {
    'smtp_server': 'smtp.uni5.net',
    'smtp_port': 587,
    'imap_server': 'imap.uni5.net',
    'imap_port': 143,
    'email': 'atende@grupoalves.net',
    'password': '123Leo456@7',
    'use_tls': True
}

# Configurações do Tavily AI (Web Search & Scraping)
TAVILY_CONFIG = {
    'api_key': 'cac6b7c6-516b-4360-93b5-a05d1c2e0dae',
    'base_url': 'https://api.tavily.com/search',
    'max_results': 10,
    'include_domains': [],
    'exclude_domains': [],
    'search_depth': 'basic'  # basic, advanced
}

# Configurações do MCP Server para Bases de Dados Externas
MCP_DATABASE_CONFIG = {
    'api_key': 'cac6b7c6-516b-4360-93b5-a05d1c2e0dae',
    'base_url': 'https://server.smithery.ai/@ichewm/mcp-add-test/mcp',
    'profile': 'cool-egret-8qaexx',
    'timeout': 30,
    'max_connections': 10
}

# Configurações de Bases de Dados Externas
EXTERNAL_DB_CONFIG = {
    'postgresql': {
        'enabled': False,
        'host': 'localhost',
        'port': 5432,
        'database': 'grupo_alves',
        'username': '',
        'password': ''
    },
    'mongodb': {
        'enabled': False,
        'host': 'localhost',
        'port': 27017,
        'database': 'grupo_alves',
        'username': '',
        'password': ''
    },
    'redis': {
        'enabled': False,
        'host': 'localhost',
        'port': 6379,
        'database': 0,
        'password': ''
    }
}

# Configuração atual (em memória, pode ser salva em arquivo depois)
current_config = DEFAULT_CONFIG.copy()

# Database path
DB_PATH = '/app/data/conversations.db'

# Ensure data directory exists
os.makedirs('/app/data', exist_ok=True)

# Initialize database
def init_db():
    """Initialize SQLite database for conversation and email storage"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                provider TEXT,
                model TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                session_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                message_id TEXT UNIQUE,
                subject TEXT NOT NULL,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                body TEXT NOT NULL,
                html_body TEXT,
                status TEXT DEFAULT 'draft',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                sent_at DATETIME,
                received_at DATETIME,
                session_id TEXT,
                llm_generated BOOLEAN DEFAULT 0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS email_monitoring (
                id TEXT PRIMARY KEY,
                email_id TEXT NOT NULL,
                check_type TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS web_searches (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                results TEXT NOT NULL,
                search_type TEXT DEFAULT 'web',
                session_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                results_count INTEGER DEFAULT 0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS scraped_content (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                metadata TEXT,
                session_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                content_type TEXT DEFAULT 'html'
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS external_data_context (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                data_source TEXT NOT NULL,
                query TEXT NOT NULL,
                results TEXT NOT NULL,
                context_type TEXT DEFAULT 'database',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                metadata TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS database_connections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                db_type TEXT NOT NULL,
                connection_string TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME,
                metadata TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversation_context (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                context_data TEXT NOT NULL,
                context_type TEXT DEFAULT 'general',
                priority INTEGER DEFAULT 1,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                FOREIGN KEY (session_id) REFERENCES conversations (session_id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS db_connections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                db_type TEXT NOT NULL,
                host TEXT,
                port INTEGER,
                database_name TEXT,
                username TEXT,
                password TEXT,
                connection_string TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_tested DATETIME,
                test_status TEXT DEFAULT 'untested'
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sql_queries (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                natural_language TEXT NOT NULL,
                generated_sql TEXT NOT NULL,
                db_connection_id TEXT,
                execution_result TEXT,
                execution_time REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (db_connection_id) REFERENCES db_connections (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS customer_profiles (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                company TEXT,
                communication_style TEXT,
                response_time_avg REAL,
                interaction_count INTEGER DEFAULT 0,
                last_interaction DATETIME,
                satisfaction_score REAL,
                topics_of_interest TEXT,
                student_status TEXT,
                enrollment_date DATETIME,
                course_history TEXT,
                lead_score INTEGER DEFAULT 0,
                lifecycle_stage TEXT DEFAULT 'prospect',
                preferred_contact_method TEXT DEFAULT 'email',
                timezone TEXT,
                phone TEXT,
                address TEXT,
                emergency_contact TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS customer_interactions (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                email_id TEXT,
                interaction_type TEXT NOT NULL,
                content TEXT,
                sentiment_score REAL,
                response_time REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customer_profiles (id),
                FOREIGN KEY (email_id) REFERENCES emails (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS email_threads (
                id TEXT PRIMARY KEY,
                thread_subject TEXT NOT NULL,
                participants TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                last_message_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS student_enrollments (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                course_name TEXT NOT NULL,
                enrollment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                start_date DATETIME,
                end_date DATETIME,
                status TEXT DEFAULT 'enrolled',
                progress_percentage REAL DEFAULT 0,
                grade TEXT,
                completion_date DATETIME,
                FOREIGN KEY (customer_id) REFERENCES customer_profiles (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS marketing_campaigns (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                start_date DATETIME,
                end_date DATETIME,
                target_audience TEXT,
                conversion_rate REAL DEFAULT 0,
                total_leads INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS lead_activities (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                activity_data TEXT,
                source TEXT,
                campaign_id TEXT,
                score_change INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customer_profiles (id),
                FOREIGN KEY (campaign_id) REFERENCES marketing_campaigns (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'medium',
                category TEXT,
                assigned_to TEXT,
                resolution TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME,
                FOREIGN KEY (customer_id) REFERENCES customer_profiles (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS email_crm_mapping (
                id TEXT PRIMARY KEY,
                email_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                mapped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                confidence_score REAL DEFAULT 1.0,
                mapping_method TEXT DEFAULT 'exact_match',
                FOREIGN KEY (email_id) REFERENCES emails (id),
                FOREIGN KEY (customer_id) REFERENCES customer_profiles (id)
            )
        ''')
        conn.commit()

# Initialize database on startup
init_db()

# Conversation Management Functions
def get_session_id():
    """Get or create session ID for conversation tracking"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def save_message(session_id, role, content, provider=None, model=None):
    """Save a message to the conversation history"""
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO conversations (id, session_id, role, content, provider, model)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), session_id, role, content, provider, model))
            conn.commit()

def get_conversation_history(session_id, limit=None):
    """Get conversation history for a session"""
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            if limit:
                cursor = conn.execute('''
                    SELECT role, content, timestamp FROM conversations
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (session_id, limit))
                # Reverse the order for limited results to get chronological order
                results = cursor.fetchall()
                results.reverse()
            else:
                cursor = conn.execute('''
                    SELECT role, content, timestamp FROM conversations
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                ''', (session_id,))
                results = cursor.fetchall()

            return [{'role': row[0], 'content': row[1], 'timestamp': row[2]}
                   for row in results]

def get_conversation_summary(session_id):
    """Get conversation summary if it exists"""
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT summary FROM conversation_summaries
                WHERE session_id = ?
            ''', (session_id,))
            result = cursor.fetchone()
            return result[0] if result else None

def save_conversation_summary(session_id, summary):
    """Save or update conversation summary"""
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO conversation_summaries (session_id, summary)
                VALUES (?, ?)
            ''', (session_id, summary))
            conn.commit()

def build_conversation_context(session_id):
    """Build conversation context for LLM with memory management"""
    history = get_conversation_history(session_id)
    max_length = current_config['max_conversation_length']
    summary_threshold = current_config['conversation_summary_threshold']

    # If conversation is getting long, use summarization
    if len(history) > summary_threshold:
        summary = get_conversation_summary(session_id)
        if not summary and len(history) > 5:
            # Create summary of older messages
            older_messages = history[:-max_length//2]
            summary_text = "Previous conversation summary: "
            for msg in older_messages[-5:]:  # Summarize last 5 older messages
                summary_text += f"{msg['role']}: {msg['content'][:100]}... "
            save_conversation_summary(session_id, summary_text)
            summary = summary_text

        # Use summary + recent messages
        recent_history = history[-max_length//2:]
        if summary:
            context = [{"role": "system", "content": summary}]
            context.extend([{"role": msg['role'], "content": msg['content']}
                          for msg in recent_history])
        else:
            context = [{"role": msg['role'], "content": msg['content']}
                      for msg in history[-max_length:]]
    else:
        # Use full history if it's short enough
        context = [{"role": msg['role'], "content": msg['content']}
                  for msg in history[-max_length:]]

    return context

# Email Functions
def send_email(to_email, subject, body, html_body=None, session_id=None):
    """Send email using SMTP"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = to_email
        msg['Subject'] = subject

        # Add text part
        text_part = MIMEText(body, 'plain', 'utf-8')
        msg.attach(text_part)

        # Add HTML part if provided
        if html_body:
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)

        # Connect to SMTP server
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            if EMAIL_CONFIG['use_tls']:
                server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            server.send_message(msg)

        # Save to database
        email_id = str(uuid.uuid4())
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO emails (id, subject, sender, recipient, body, html_body,
                                      status, sent_at, session_id, llm_generated)
                    VALUES (?, ?, ?, ?, ?, ?, 'sent', ?, ?, 1)
                ''', (email_id, subject, EMAIL_CONFIG['email'], to_email, body,
                     html_body, datetime.now().isoformat(), session_id))
                conn.commit()

        # Emit real-time notification
        socketio.emit('email_sent', {
            'id': email_id,
            'to': to_email,
            'subject': subject,
            'timestamp': datetime.now().isoformat()
        })

        return {'success': True, 'email_id': email_id, 'message': 'Email enviado com sucesso'}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def check_new_emails():
    """Check for new emails using IMAP"""
    try:
        # Connect to IMAP server
        with imaplib.IMAP4(EMAIL_CONFIG['imap_server'], EMAIL_CONFIG['imap_port']) as mail:
            if EMAIL_CONFIG['use_tls']:
                mail.starttls()
            mail.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
            mail.select('INBOX')

            # Search for unseen emails
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                return []

            new_emails = []
            for msg_id in messages[0].split():
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if status != 'OK':
                    continue

                # Parse email
                email_message = email.message_from_bytes(msg_data[0][1])

                # Extract email details
                subject = decode_header(email_message['Subject'])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode('utf-8')

                sender = email_message['From']
                recipient = email_message['To']
                message_id = email_message['Message-ID']

                # Get email body
                body = ""
                html_body = None
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode('utf-8')
                        elif part.get_content_type() == "text/html":
                            html_body = part.get_payload(decode=True).decode('utf-8')
                else:
                    body = email_message.get_payload(decode=True).decode('utf-8')

                # Save to database
                email_id = str(uuid.uuid4())
                with db_lock:
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute('''
                            INSERT OR IGNORE INTO emails (id, message_id, subject, sender,
                                                        recipient, body, html_body, status, received_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 'received', ?)
                        ''', (email_id, message_id, subject, sender, recipient, body,
                             html_body, datetime.now().isoformat()))
                        conn.commit()

                new_emails.append({
                    'id': email_id,
                    'subject': subject,
                    'sender': sender,
                    'body': body[:200] + '...' if len(body) > 200 else body,
                    'timestamp': datetime.now().isoformat()
                })

                # Emit real-time notification
                socketio.emit('email_received', {
                    'id': email_id,
                    'subject': subject,
                    'sender': sender,
                    'preview': body[:100] + '...' if len(body) > 100 else body,
                    'timestamp': datetime.now().isoformat()
                })

            return new_emails

    except Exception as e:
        print(f"Error checking emails: {e}")
        return []

def start_email_monitoring():
    """Start background email monitoring"""
    def monitor_emails():
        while True:
            try:
                check_new_emails()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"Email monitoring error: {e}")
                time.sleep(60)  # Wait longer on error

    monitor_thread = Thread(target=monitor_emails, daemon=True)
    monitor_thread.start()

# Web Search and Scraping Functions
def tavily_web_search(query, search_type='search', max_results=5):
    """Perform web search using Tavily AI or fallback to DuckDuckGo"""
    try:
        # Try Tavily first
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {TAVILY_CONFIG["api_key"]}'
        }

        payload = {
            'query': query,
            'search_depth': TAVILY_CONFIG['search_depth'],
            'include_answer': True,
            'include_raw_content': True,
            'max_results': max_results,
            'include_domains': TAVILY_CONFIG.get('include_domains', []),
            'exclude_domains': TAVILY_CONFIG.get('exclude_domains', [])
        }

        response = requests.post(TAVILY_CONFIG['base_url'], json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()

            results = []
            for result in data.get('results', []):
                results.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('content', ''),
                    'raw_content': result.get('raw_content', ''),
                    'score': result.get('score', 0)
                })

            return {
                'success': True,
                'query': query,
                'answer': data.get('answer', ''),
                'results': results,
                'images': data.get('images', []),
                'follow_up_questions': data.get('follow_up_questions', []),
                'source': 'tavily'
            }
        else:
            # Fallback to DuckDuckGo search
            return duckduckgo_search(query, max_results)

    except Exception as e:
        # Fallback to DuckDuckGo search
        return duckduckgo_search(query, max_results)

def duckduckgo_search(query, max_results=5):
    """Fallback web search using DuckDuckGo"""
    try:
        # DuckDuckGo Instant Answer API
        search_url = "https://api.duckduckgo.com/"
        params = {
            'q': query,
            'format': 'json',
            'no_html': '1',
            'skip_disambig': '1'
        }

        response = requests.get(search_url, params=params, timeout=15)

        if response.status_code == 200:
            data = response.json()

            results = []

            # Add abstract if available
            if data.get('Abstract'):
                results.append({
                    'title': data.get('AbstractText', query),
                    'url': data.get('AbstractURL', ''),
                    'content': data.get('Abstract', ''),
                    'score': 1.0
                })

            # Add related topics
            for topic in data.get('RelatedTopics', [])[:max_results-1]:
                if isinstance(topic, dict) and topic.get('Text'):
                    results.append({
                        'title': topic.get('Text', '')[:100] + '...',
                        'url': topic.get('FirstURL', ''),
                        'content': topic.get('Text', ''),
                        'score': 0.8
                    })

            # If no results, try web scraping of search results
            if not results:
                return scrape_search_results(query, max_results)

            return {
                'success': True,
                'query': query,
                'answer': data.get('Abstract', ''),
                'results': results,
                'images': [],
                'follow_up_questions': [],
                'source': 'duckduckgo'
            }
        else:
            return scrape_search_results(query, max_results)

    except Exception as e:
        return scrape_search_results(query, max_results)

def scrape_search_results(query, max_results=5):
    """Scrape search results as last resort"""
    try:
        # Use DuckDuckGo HTML search
        search_url = f"https://duckduckgo.com/html/?q={query}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(search_url, headers=headers, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            results = []
            search_results = soup.find_all('div', class_='result')[:max_results]

            for result in search_results:
                title_elem = result.find('a', class_='result__a')
                snippet_elem = result.find('a', class_='result__snippet')

                if title_elem:
                    title = title_elem.get_text().strip()
                    url = title_elem.get('href', '')
                    content = snippet_elem.get_text().strip() if snippet_elem else ''

                    results.append({
                        'title': title,
                        'url': url,
                        'content': content,
                        'score': 0.6
                    })

            return {
                'success': True,
                'query': query,
                'answer': f'Encontrados {len(results)} resultados para "{query}"',
                'results': results,
                'images': [],
                'follow_up_questions': [],
                'source': 'scraping'
            }
        else:
            return {'success': False, 'error': 'Não foi possível realizar a pesquisa'}

    except Exception as e:
        return {'success': False, 'error': f'Erro na pesquisa: {str(e)}'}

def scrape_website(url, extract_type='full'):
    """Scrape website content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract title
        title = soup.find('title')
        title_text = title.get_text().strip() if title else 'No title'

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Extract content based on type
        if extract_type == 'text':
            content = soup.get_text()
            # Clean up text
            lines = (line.strip() for line in content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            content = ' '.join(chunk for chunk in chunks if chunk)
        elif extract_type == 'articles':
            # Try to find main content areas
            content_selectors = ['article', 'main', '.content', '#content', '.post', '.entry']
            content = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = ' '.join([elem.get_text().strip() for elem in elements])
                    break
            if not content:
                content = soup.get_text()
        else:  # full
            content = str(soup)

        # Extract metadata
        metadata = {
            'description': '',
            'keywords': '',
            'author': '',
            'published_date': ''
        }

        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            metadata['description'] = meta_desc.get('content', '')

        # Meta keywords
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords:
            metadata['keywords'] = meta_keywords.get('content', '')

        # Author
        meta_author = soup.find('meta', attrs={'name': 'author'})
        if meta_author:
            metadata['author'] = meta_author.get('content', '')

        return {
            'success': True,
            'url': url,
            'title': title_text,
            'content': content[:10000],  # Limit content size
            'metadata': metadata,
            'content_length': len(content)
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def save_search_result(query, results, search_type='web', session_id=None):
    """Save search results to database"""
    try:
        search_id = str(uuid.uuid4())
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO web_searches (id, query, results, search_type, session_id, results_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (search_id, query, json.dumps(results), search_type, session_id, len(results.get('results', []))))
                conn.commit()
        return search_id
    except Exception as e:
        print(f"Error saving search result: {e}")
        return None

def save_scraped_content(url, title, content, metadata, session_id=None):
    """Save scraped content to database"""
    try:
        content_id = str(uuid.uuid4())
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO scraped_content (id, url, title, content, metadata, session_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (content_id, url, title, content, json.dumps(metadata), session_id))
                conn.commit()
        return content_id
    except Exception as e:
        print(f"Error saving scraped content: {e}")
        return None

# MCP Database Integration Functions
def mcp_database_query(query, db_type='auto', session_id=None):
    """Execute database query via MCP server"""
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {MCP_DATABASE_CONFIG["api_key"]}'
        }

        payload = {
            'query': query,
            'database_type': db_type,
            'profile': MCP_DATABASE_CONFIG['profile'],
            'session_id': session_id,
            'maintain_context': True
        }

        response = requests.post(
            f"{MCP_DATABASE_CONFIG['base_url']}/query",
            json=payload,
            headers=headers,
            timeout=MCP_DATABASE_CONFIG['timeout']
        )

        if response.status_code == 200:
            data = response.json()

            # Save context for future queries
            if session_id and data.get('results'):
                save_external_data_context(
                    session_id, db_type, query, data, 'database'
                )

            return {
                'success': True,
                'results': data.get('results', []),
                'metadata': data.get('metadata', {}),
                'query_type': data.get('query_type', 'select'),
                'affected_rows': data.get('affected_rows', 0),
                'execution_time': data.get('execution_time', 0)
            }
        else:
            return {'success': False, 'error': f'MCP API error: {response.status_code}'}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def mcp_database_schema(db_name=None, session_id=None):
    """Get database schema via MCP server"""
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {MCP_DATABASE_CONFIG["api_key"]}'
        }

        payload = {
            'action': 'get_schema',
            'database': db_name,
            'profile': MCP_DATABASE_CONFIG['profile'],
            'session_id': session_id
        }

        response = requests.post(
            f"{MCP_DATABASE_CONFIG['base_url']}/schema",
            json=payload,
            headers=headers,
            timeout=MCP_DATABASE_CONFIG['timeout']
        )

        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'schema': data.get('schema', {}),
                'tables': data.get('tables', []),
                'relationships': data.get('relationships', [])
            }
        else:
            return {'success': False, 'error': f'MCP API error: {response.status_code}'}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def save_external_data_context(session_id, data_source, query, results, context_type='database'):
    """Save external data context for conversation continuity"""
    try:
        from datetime import timedelta
        context_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=24)  # Context expires in 24 hours

        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO external_data_context
                    (id, session_id, data_source, query, results, context_type, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (context_id, session_id, data_source, query,
                     json.dumps(results), context_type, expires_at.isoformat()))
                conn.commit()

        return context_id
    except Exception as e:
        print(f"Error saving external data context: {e}")
        return None

def get_external_data_context(session_id, limit=5):
    """Get recent external data context for session"""
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT data_source, query, results, context_type, timestamp
                    FROM external_data_context
                    WHERE session_id = ? AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY timestamp DESC LIMIT ?
                ''', (session_id, datetime.now().isoformat(), limit))

                contexts = []
                for row in cursor.fetchall():
                    contexts.append({
                        'data_source': row[0],
                        'query': row[1],
                        'results': json.loads(row[2]) if row[2] else {},
                        'context_type': row[3],
                        'timestamp': row[4]
                    })

                return contexts
    except Exception as e:
        print(f"Error getting external data context: {e}")
        return []

def build_enhanced_conversation_context(session_id):
    """Build conversation context enhanced with external data"""
    # Get regular conversation context
    conversation_context = build_conversation_context(session_id)

    # Get external data context
    external_contexts = get_external_data_context(session_id)

    # Add external data context to conversation
    if external_contexts:
        context_summary = "Dados externos disponíveis na conversa:\n"
        for ctx in external_contexts:
            context_summary += f"- {ctx['data_source']}: {ctx['query']}\n"
            if ctx['results'].get('results'):
                context_summary += f"  Resultados: {len(ctx['results']['results'])} registros\n"

        # Insert context before the last user message
        if conversation_context:
            conversation_context.insert(-1, {
                "role": "system",
                "content": context_summary
            })

    return conversation_context

# Database Connection Management Functions
def create_db_connection(name, db_type, host, port, database_name, username, password):
    """Create and test a new database connection"""
    try:
        connection_id = str(uuid.uuid4())

        # Build connection string based on database type
        if db_type == 'postgresql':
            connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database_name}"
        elif db_type == 'mysql':
            connection_string = f"mysql+mysqlconnector://{username}:{password}@{host}:{port}/{database_name}"
        elif db_type == 'sqlite':
            connection_string = f"sqlite:///{database_name}"
        elif db_type == 'mongodb':
            connection_string = f"mongodb://{username}:{password}@{host}:{port}/{database_name}"
        else:
            return {'success': False, 'error': 'Unsupported database type'}

        # Test connection
        test_result = test_db_connection(connection_string, db_type)

        # Save connection
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO db_connections
                    (id, name, db_type, host, port, database_name, username, password,
                     connection_string, last_tested, test_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (connection_id, name, db_type, host, port, database_name, username,
                     password, connection_string, datetime.now().isoformat(),
                     'success' if test_result['success'] else 'failed'))
                conn.commit()

        return {
            'success': True,
            'connection_id': connection_id,
            'test_result': test_result
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_db_connection(connection_string, db_type):
    """Test database connection"""
    try:
        if db_type in ['postgresql', 'mysql', 'sqlite']:
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            return {'success': True, 'message': 'Connection successful'}

        elif db_type == 'mongodb':
            client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
            client.server_info()
            return {'success': True, 'message': 'MongoDB connection successful'}

        else:
            return {'success': False, 'error': 'Unsupported database type'}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_db_schema(connection_id):
    """Get database schema information"""
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT connection_string, db_type FROM db_connections WHERE id = ?
                ''', (connection_id,))
                row = cursor.fetchone()

                if not row:
                    return {'success': False, 'error': 'Connection not found'}

                connection_string, db_type = row

        if db_type in ['postgresql', 'mysql', 'sqlite']:
            engine = create_engine(connection_string)
            inspector = inspect(engine)

            tables = []
            for table_name in inspector.get_table_names():
                columns = inspector.get_columns(table_name)
                tables.append({
                    'name': table_name,
                    'columns': [{'name': col['name'], 'type': str(col['type'])} for col in columns]
                })

            return {'success': True, 'tables': tables}

        elif db_type == 'mongodb':
            client = MongoClient(connection_string)
            db = client.get_default_database()
            collections = db.list_collection_names()

            tables = []
            for collection_name in collections[:10]:  # Limit to 10 collections
                collection = db[collection_name]
                sample_doc = collection.find_one()
                fields = list(sample_doc.keys()) if sample_doc else []
                tables.append({
                    'name': collection_name,
                    'columns': [{'name': field, 'type': 'document'} for field in fields]
                })

            return {'success': True, 'tables': tables}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def generate_sql_from_natural_language(natural_query, connection_id, session_id):
    """Generate SQL query from natural language using LLM"""
    try:
        # Get database schema
        schema_result = get_db_schema(connection_id)
        if not schema_result['success']:
            return schema_result

        # Build schema context for LLM
        schema_context = "Database Schema:\n"
        for table in schema_result['tables']:
            schema_context += f"\nTable: {table['name']}\n"
            for column in table['columns']:
                schema_context += f"  - {column['name']} ({column['type']})\n"

        # Create LLM prompt for SQL generation
        sql_prompt = f"""
        You are an expert SQL developer. Convert the following natural language query into a proper SQL statement.

        {schema_context}

        Natural Language Query: {natural_query}

        Instructions:
        1. Generate ONLY the SQL query, no explanations
        2. Use proper SQL syntax
        3. Include appropriate WHERE clauses, JOINs, and ORDER BY as needed
        4. Limit results to reasonable numbers (use LIMIT)
        5. Use table and column names exactly as shown in the schema

        SQL Query:
        """

        # Get SQL from LLM using existing conversation context
        conversation_context = [{"role": "system", "content": sql_prompt}]

        if current_config['provider'] == 'ollama':
            sql_response = get_ollama_response(conversation_context)
        elif current_config['provider'] == 'openrouter':
            sql_response = get_openrouter_response(conversation_context)
        else:
            return {'success': False, 'error': 'No LLM provider configured'}

        # Clean up SQL response
        sql_query = sql_response.strip()
        # Remove common prefixes/suffixes
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()

        # Save the generated query
        query_id = str(uuid.uuid4())
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO sql_queries (id, session_id, natural_language, generated_sql, db_connection_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (query_id, session_id, natural_query, sql_query, connection_id))
                conn.commit()

        return {
            'success': True,
            'sql_query': sql_query,
            'query_id': query_id,
            'schema': schema_result['tables']
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def execute_generated_sql(query_id, connection_id):
    """Execute a generated SQL query"""
    try:
        # Get query and connection details
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT sq.generated_sql, dc.connection_string, dc.db_type
                    FROM sql_queries sq
                    JOIN db_connections dc ON sq.db_connection_id = dc.id
                    WHERE sq.id = ? AND dc.id = ?
                ''', (query_id, connection_id))
                row = cursor.fetchone()

                if not row:
                    return {'success': False, 'error': 'Query or connection not found'}

                sql_query, connection_string, db_type = row

        start_time = time.time()

        if db_type in ['postgresql', 'mysql', 'sqlite']:
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                result = conn.execute(text(sql_query))
                rows = result.fetchall()
                columns = list(result.keys()) if rows else []

                # Convert to list of dictionaries
                data = [dict(zip(columns, row)) for row in rows]

        elif db_type == 'mongodb':
            # For MongoDB, we'd need to convert SQL to MongoDB query
            return {'success': False, 'error': 'MongoDB SQL conversion not implemented yet'}

        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Update query with execution result
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    UPDATE sql_queries
                    SET execution_result = ?, execution_time = ?
                    WHERE id = ?
                ''', (json.dumps(data), execution_time, query_id))
                conn.commit()

        return {
            'success': True,
            'data': data,
            'execution_time': execution_time,
            'row_count': len(data)
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

# Customer Profiling and Email Analysis Functions
def analyze_email_sentiment(content):
    """Analyze email sentiment using LLM"""
    try:
        sentiment_prompt = f"""
        Analyze the sentiment and tone of the following email content.
        Respond with a JSON object containing:
        - sentiment_score: number between -1 (very negative) and 1 (very positive)
        - tone: one of "professional", "casual", "urgent", "friendly", "formal", "concerned"
        - key_topics: array of main topics discussed
        - urgency_level: number between 1 (low) and 5 (high)

        Email content: {content[:1000]}

        Response (JSON only):
        """

        conversation_context = [{"role": "system", "content": sentiment_prompt}]

        if current_config['provider'] == 'ollama':
            response = get_ollama_response(conversation_context)
        elif current_config['provider'] == 'openrouter':
            response = get_openrouter_response(conversation_context)
        else:
            return {'sentiment_score': 0, 'tone': 'neutral', 'key_topics': [], 'urgency_level': 3}

        try:
            # Try to parse JSON response
            analysis = json.loads(response.strip())
            return analysis
        except:
            # Fallback if JSON parsing fails
            return {'sentiment_score': 0, 'tone': 'neutral', 'key_topics': [], 'urgency_level': 3}

    except Exception as e:
        return {'sentiment_score': 0, 'tone': 'neutral', 'key_topics': [], 'urgency_level': 3}

def create_or_update_customer_profile(email_address, name=None, company=None, email_content=None):
    """Create or update customer profile based on email interaction"""
    try:
        customer_id = str(uuid.uuid4())

        # Analyze email if provided
        analysis = {}
        if email_content:
            analysis = analyze_email_sentiment(email_content)

        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                # Check if customer exists
                cursor = conn.execute('''
                    SELECT id, interaction_count, topics_of_interest FROM customer_profiles WHERE email = ?
                ''', (email_address,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing customer
                    customer_id, interaction_count, existing_topics = existing

                    # Merge topics
                    topics = json.loads(existing_topics) if existing_topics else []
                    if analysis.get('key_topics'):
                        topics.extend(analysis['key_topics'])
                        topics = list(set(topics))  # Remove duplicates

                    conn.execute('''
                        UPDATE customer_profiles
                        SET name = COALESCE(?, name),
                            company = COALESCE(?, company),
                            interaction_count = interaction_count + 1,
                            last_interaction = ?,
                            topics_of_interest = ?,
                            updated_at = ?
                        WHERE email = ?
                    ''', (name, company, datetime.now().isoformat(),
                         json.dumps(topics), datetime.now().isoformat(), email_address))
                else:
                    # Create new customer
                    topics = analysis.get('key_topics', [])
                    conn.execute('''
                        INSERT INTO customer_profiles
                        (id, email, name, company, communication_style, interaction_count,
                         last_interaction, topics_of_interest)
                        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    ''', (customer_id, email_address, name, company, analysis.get('tone', 'neutral'),
                         datetime.now().isoformat(), json.dumps(topics)))

                conn.commit()

        return {'success': True, 'customer_id': customer_id}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def log_customer_interaction(customer_id, email_id, interaction_type, content, response_time=None):
    """Log customer interaction for analysis"""
    try:
        interaction_id = str(uuid.uuid4())

        # Analyze content sentiment
        analysis = analyze_email_sentiment(content) if content else {}

        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO customer_interactions
                    (id, customer_id, email_id, interaction_type, content,
                     sentiment_score, response_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (interaction_id, customer_id, email_id, interaction_type, content,
                     analysis.get('sentiment_score', 0), response_time))
                conn.commit()

        return {'success': True, 'interaction_id': interaction_id}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def generate_email_reply_suggestions(email_content, thread_history=None, customer_profile=None, email_metadata=None):
    """Generate AI-powered email reply suggestions with enhanced CRM context"""
    try:
        # Build comprehensive context for reply generation
        context = f"Email to reply to:\n{email_content}\n\n"

        if thread_history:
            context += f"Previous conversation:\n{thread_history}\n\n"

        if customer_profile:
            context += f"Customer profile:\n"
            context += f"- Name: {customer_profile.get('name', 'Unknown')}\n"
            context += f"- Communication style: {customer_profile.get('communication_style', 'neutral')}\n"
            context += f"- Student status: {customer_profile.get('student_status', 'prospect')}\n"
            context += f"- Lifecycle stage: {customer_profile.get('lifecycle_stage', 'prospect')}\n"
            context += f"- Interaction count: {customer_profile.get('interaction_count', 0)}\n"
            context += f"- Satisfaction score: {customer_profile.get('satisfaction_score', 'N/A')}\n"
            context += f"- Topics of interest: {', '.join(customer_profile.get('topics_of_interest', []))}\n"
            context += f"- Course history: {customer_profile.get('course_history', 'None')}\n\n"

        if email_metadata:
            context += f"Email metadata:\n"
            context += f"- Sender: {email_metadata.get('sender', 'Unknown')}\n"
            context += f"- Subject: {email_metadata.get('subject', 'No subject')}\n"
            context += f"- Timestamp: {email_metadata.get('timestamp', 'Unknown')}\n\n"

        reply_prompt = f"""
        {context}

        You are an AI assistant for a student support and digital marketing system. Generate 3 different email reply suggestions that are:
        1. Contextually appropriate based on the customer's profile and history
        2. Aligned with their current lifecycle stage (prospect, enrolled, graduate, alumni)
        3. Personalized to their communication style and preferences

        Generate replies with these tones:
        1. Professional and supportive (ideal for formal inquiries and support requests)
        2. Friendly and encouraging (ideal for student engagement and motivation)
        3. Concise and action-oriented (ideal for quick responses and next steps)

        For each suggestion, provide:
        - subject: appropriate subject line that references context when relevant
        - body: complete email body with personalized greeting and relevant information
        - tone: description of the tone used
        - next_actions: suggested follow-up actions for the customer

        Important guidelines:
        - Use the customer's name if available
        - Reference their student status or course history when relevant
        - Provide helpful resources or next steps based on their lifecycle stage
        - Maintain a supportive and educational tone appropriate for student services

        Respond in JSON format:
        {{
            "suggestions": [
                {{"subject": "...", "body": "...", "tone": "professional", "next_actions": ["..."]}},
                {{"subject": "...", "body": "...", "tone": "friendly", "next_actions": ["..."]}},
                {{"subject": "...", "body": "...", "tone": "concise", "next_actions": ["..."]}}
            ]
        }}
        """

        conversation_context = [{"role": "system", "content": reply_prompt}]

        if current_config['provider'] == 'ollama':
            response = get_ollama_response(conversation_context)
        elif current_config['provider'] == 'openrouter':
            response = get_openrouter_response(conversation_context)
        else:
            return {'success': False, 'error': 'No LLM provider configured'}

        try:
            suggestions = json.loads(response.strip())
            return {'success': True, 'suggestions': suggestions.get('suggestions', [])}
        except:
            # Fallback if JSON parsing fails
            return {
                'success': True,
                'suggestions': [
                    {
                        'subject': 'Re: Your inquiry',
                        'body': response[:500] + '...',
                        'tone': 'professional'
                    }
                ]
            }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_customer_analytics():
    """Get customer relationship analytics"""
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                # Get customer statistics
                cursor = conn.execute('''
                    SELECT
                        COUNT(*) as total_customers,
                        AVG(interaction_count) as avg_interactions,
                        AVG(response_time_avg) as avg_response_time,
                        AVG(satisfaction_score) as avg_satisfaction
                    FROM customer_profiles
                ''')
                stats = cursor.fetchone()

                # Get top customers by interaction
                cursor = conn.execute('''
                    SELECT email, name, interaction_count, last_interaction, communication_style
                    FROM customer_profiles
                    ORDER BY interaction_count DESC
                    LIMIT 10
                ''')
                top_customers = cursor.fetchall()

                # Get recent interactions
                cursor = conn.execute('''
                    SELECT ci.interaction_type, ci.sentiment_score, ci.timestamp, cp.email
                    FROM customer_interactions ci
                    JOIN customer_profiles cp ON ci.customer_id = cp.id
                    ORDER BY ci.timestamp DESC
                    LIMIT 20
                ''')
                recent_interactions = cursor.fetchall()

                return {
                    'success': True,
                    'stats': {
                        'total_customers': stats[0] or 0,
                        'avg_interactions': round(stats[1] or 0, 2),
                        'avg_response_time': round(stats[2] or 0, 2),
                        'avg_satisfaction': round(stats[3] or 0, 2)
                    },
                    'top_customers': [
                        {
                            'email': row[0],
                            'name': row[1],
                            'interaction_count': row[2],
                            'last_interaction': row[3],
                            'communication_style': row[4]
                        } for row in top_customers
                    ],
                    'recent_interactions': [
                        {
                            'type': row[0],
                            'sentiment': row[1],
                            'timestamp': row[2],
                            'customer_email': row[3]
                        } for row in recent_interactions
                    ]
                }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_ollama_response(messages):
    """Fazer requisição para Ollama com contexto de conversa"""
    url = f"http://{current_config['ollama_host']}:{current_config['ollama_port']}/api/generate"

    # Convert conversation context to Ollama format (single prompt)
    prompt = ""
    for msg in messages:
        if msg['role'] == 'system':
            prompt += f"System: {msg['content']}\n"
        elif msg['role'] == 'user':
            prompt += f"User: {msg['content']}\n"
        elif msg['role'] == 'assistant':
            prompt += f"Assistant: {msg['content']}\n"
    prompt += "Assistant: "

    payload = {
        "model": current_config['ollama_model'],
        "prompt": prompt,
        "stream": False
    }
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code == 200:
        return response.json().get('response', 'Erro ao processar resposta')
    else:
        raise Exception(f'Ollama error: {response.status_code}')

def get_openrouter_response(messages):
    """Fazer requisição para OpenRouter com contexto de conversa"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {current_config['openrouter_api_key']}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Chat LLM Application"
    }
    payload = {
        "model": current_config['openrouter_model'],
        "messages": messages
    }
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        raise Exception(f'OpenRouter error: {response.status_code} - {response.text}')

def fetch_openrouter_models():
    """Fetch available models from OpenRouter API"""
    try:
        url = "https://openrouter.ai/api/v1/models"
        headers = {
            "Authorization": f"Bearer {current_config['openrouter_api_key']}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            models_data = response.json()
            models = []
            for model in models_data.get('data', []):
                models.append({
                    'id': model['id'],
                    'name': model.get('name', model['id']),
                    'description': model.get('description', ''),
                    'pricing': model.get('pricing', {}),
                    'context_length': model.get('context_length', 0),
                    'is_free': model.get('pricing', {}).get('prompt', '0') == '0'
                })
            return sorted(models, key=lambda x: (not x['is_free'], x['name']))
        else:
            return []
    except Exception as e:
        print(f"Error fetching OpenRouter models: {e}")
        return []

# Enhanced CRM-Email Integration Functions
def process_email_for_crm(email_data):
    """Process incoming email and automatically update CRM"""
    try:
        email_id = email_data.get('id')
        sender = email_data.get('sender', email_data.get('contact'))
        subject = email_data.get('subject', '')
        body = email_data.get('body', email_data.get('content', ''))
        timestamp = email_data.get('timestamp', datetime.now().isoformat())

        if not sender or not email_id:
            return {'success': False, 'error': 'Missing required email data'}

        # Analyze email sentiment and content
        analysis = analyze_email_sentiment(body)

        # Create or update customer profile
        customer_result = create_or_update_customer_profile_enhanced(
            email_address=sender,
            email_content=body,
            email_subject=subject,
            sentiment_analysis=analysis
        )

        if customer_result['success']:
            customer_id = customer_result['customer_id']

            # Create email-CRM mapping
            mapping_result = create_email_crm_mapping(email_id, customer_id, sender)

            # Log interaction
            interaction_result = log_customer_interaction_enhanced(
                customer_id=customer_id,
                email_id=email_id,
                interaction_type='email_received',
                content=body,
                sentiment_data=analysis,
                timestamp=timestamp
            )

            # Update lead score based on email content and engagement
            score_result = update_lead_score(customer_id, analysis, body)

            return {
                'success': True,
                'customer_id': customer_id,
                'mapping_created': mapping_result['success'],
                'interaction_logged': interaction_result['success'],
                'lead_score_updated': score_result['success']
            }
        else:
            return customer_result

    except Exception as e:
        return {'success': False, 'error': str(e)}

def create_or_update_customer_profile_enhanced(email_address, name=None, company=None, email_content=None, email_subject=None, sentiment_analysis=None):
    """Enhanced customer profile creation with student support features"""
    try:
        customer_id = str(uuid.uuid4())

        # Extract additional information from email content
        extracted_info = extract_student_info_from_email(email_content, email_subject)

        # Determine lifecycle stage based on email content
        lifecycle_stage = determine_lifecycle_stage(email_content, email_subject)

        # Calculate initial lead score
        lead_score = calculate_initial_lead_score(email_content, sentiment_analysis)

        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                # Check if customer exists
                cursor = conn.execute('''
                    SELECT id, interaction_count, topics_of_interest, lead_score, lifecycle_stage
                    FROM customer_profiles WHERE email = ?
                ''', (email_address,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing customer
                    customer_id, interaction_count, existing_topics, current_lead_score, current_stage = existing

                    # Merge topics
                    topics = json.loads(existing_topics) if existing_topics else []
                    if sentiment_analysis and sentiment_analysis.get('key_topics'):
                        topics.extend(sentiment_analysis['key_topics'])
                        topics = list(set(topics))  # Remove duplicates

                    # Update lead score
                    new_lead_score = max(current_lead_score or 0, lead_score)

                    # Update lifecycle stage if progressed
                    new_lifecycle_stage = update_lifecycle_stage(current_stage, lifecycle_stage)

                    conn.execute('''
                        UPDATE customer_profiles
                        SET name = COALESCE(?, name),
                            company = COALESCE(?, company),
                            interaction_count = interaction_count + 1,
                            last_interaction = ?,
                            topics_of_interest = ?,
                            lead_score = ?,
                            lifecycle_stage = ?,
                            student_status = COALESCE(?, student_status),
                            communication_style = ?,
                            updated_at = ?
                        WHERE email = ?
                    ''', (name, company, datetime.now().isoformat(),
                         json.dumps(topics), new_lead_score, new_lifecycle_stage,
                         extracted_info.get('student_status'),
                         sentiment_analysis.get('tone', 'neutral') if sentiment_analysis else 'neutral',
                         datetime.now().isoformat(), email_address))
                else:
                    # Create new customer
                    topics = sentiment_analysis.get('key_topics', []) if sentiment_analysis else []
                    conn.execute('''
                        INSERT INTO customer_profiles
                        (id, email, name, company, communication_style, interaction_count,
                         last_interaction, topics_of_interest, student_status, lead_score,
                         lifecycle_stage, phone, timezone)
                        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                    ''', (customer_id, email_address, name, company,
                         sentiment_analysis.get('tone', 'neutral') if sentiment_analysis else 'neutral',
                         datetime.now().isoformat(), json.dumps(topics),
                         extracted_info.get('student_status', 'prospect'), lead_score, lifecycle_stage,
                         extracted_info.get('phone'), extracted_info.get('timezone')))

                conn.commit()

        return {'success': True, 'customer_id': customer_id}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def extract_student_info_from_email(email_content, email_subject):
    """Extract student-specific information from email content"""
    try:
        info = {}

        if not email_content:
            return info

        content_lower = email_content.lower()
        subject_lower = email_subject.lower() if email_subject else ''

        # Detect student status
        if any(word in content_lower for word in ['enrolled', 'student', 'course', 'class']):
            info['student_status'] = 'enrolled'
        elif any(word in content_lower for word in ['prospect', 'interested', 'inquiry']):
            info['student_status'] = 'prospect'
        elif any(word in content_lower for word in ['graduate', 'completed', 'finished']):
            info['student_status'] = 'graduate'
        elif any(word in content_lower for word in ['alumni', 'former student']):
            info['student_status'] = 'alumni'

        # Extract phone number
        import re
        phone_pattern = r'(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})'
        phone_match = re.search(phone_pattern, email_content)
        if phone_match:
            info['phone'] = phone_match.group(1)

        # Extract timezone mentions
        timezone_keywords = ['EST', 'PST', 'CST', 'MST', 'UTC', 'GMT']
        for tz in timezone_keywords:
            if tz in email_content.upper():
                info['timezone'] = tz
                break

        return info

    except Exception as e:
        return {}

def determine_lifecycle_stage(email_content, email_subject):
    """Determine customer lifecycle stage based on email content"""
    try:
        if not email_content:
            return 'prospect'

        content_lower = email_content.lower()
        subject_lower = email_subject.lower() if email_subject else ''

        # Check for enrollment indicators
        if any(word in content_lower for word in ['enrolled', 'registration', 'tuition', 'semester']):
            return 'enrolled'

        # Check for completion indicators
        if any(word in content_lower for word in ['graduated', 'completed', 'certificate', 'diploma']):
            return 'graduate'

        # Check for alumni indicators
        if any(word in content_lower for word in ['alumni', 'former student', 'years ago']):
            return 'alumni'

        # Check for inquiry indicators
        if any(word in content_lower for word in ['interested', 'information', 'inquiry', 'question']):
            return 'prospect'

        return 'prospect'

    except Exception as e:
        return 'prospect'

def calculate_initial_lead_score(email_content, sentiment_analysis):
    """Calculate initial lead score based on email content and sentiment"""
    try:
        score = 50  # Base score

        if not email_content:
            return score

        content_lower = email_content.lower()

        # Positive sentiment increases score
        if sentiment_analysis and sentiment_analysis.get('sentiment_score', 0) > 0.3:
            score += 20

        # Specific interest keywords
        interest_keywords = ['enroll', 'register', 'sign up', 'interested', 'when can I start']
        for keyword in interest_keywords:
            if keyword in content_lower:
                score += 15
                break

        # Urgency indicators
        urgency_keywords = ['urgent', 'asap', 'immediately', 'soon', 'deadline']
        for keyword in urgency_keywords:
            if keyword in content_lower:
                score += 10
                break

        # Budget/payment mentions
        budget_keywords = ['budget', 'cost', 'price', 'payment', 'tuition']
        for keyword in budget_keywords:
            if keyword in content_lower:
                score += 10
                break

        return min(score, 100)  # Cap at 100

    except Exception as e:
        return 50

def create_email_crm_mapping(email_id, customer_id, email_address):
    """Create mapping between email and CRM customer"""
    try:
        mapping_id = str(uuid.uuid4())

        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                # Check if mapping already exists
                cursor = conn.execute('''
                    SELECT id FROM email_crm_mapping WHERE email_id = ? AND customer_id = ?
                ''', (email_id, customer_id))

                if not cursor.fetchone():
                    conn.execute('''
                        INSERT INTO email_crm_mapping
                        (id, email_id, customer_id, confidence_score, mapping_method)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (mapping_id, email_id, customer_id, 1.0, 'email_match'))
                    conn.commit()

        return {'success': True, 'mapping_id': mapping_id}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def log_customer_interaction_enhanced(customer_id, email_id, interaction_type, content, sentiment_data=None, timestamp=None):
    """Enhanced customer interaction logging with sentiment data"""
    try:
        interaction_id = str(uuid.uuid4())

        if not timestamp:
            timestamp = datetime.now().isoformat()

        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO customer_interactions
                    (id, customer_id, interaction_type, content, sentiment_score,
                     response_time, timestamp, email_id, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (interaction_id, customer_id, interaction_type, content,
                     sentiment_data.get('sentiment_score', 0) if sentiment_data else 0,
                     sentiment_data.get('response_time', 0) if sentiment_data else 0,
                     timestamp, email_id,
                     json.dumps(sentiment_data) if sentiment_data else None))
                conn.commit()

        return {'success': True, 'interaction_id': interaction_id}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def update_lead_score(customer_id, sentiment_analysis, email_content):
    """Update customer lead score based on interaction"""
    try:
        score_change = 0

        # Positive sentiment increases score
        if sentiment_analysis and sentiment_analysis.get('sentiment_score', 0) > 0.3:
            score_change += 5

        # Negative sentiment decreases score
        if sentiment_analysis and sentiment_analysis.get('sentiment_score', 0) < -0.3:
            score_change -= 5

        # Engagement indicators
        if email_content and len(email_content) > 100:  # Longer emails show engagement
            score_change += 3

        if score_change != 0:
            with db_lock:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute('''
                        UPDATE customer_profiles
                        SET lead_score = COALESCE(lead_score, 50) + ?
                        WHERE id = ?
                    ''', (score_change, customer_id))
                    conn.commit()

        return {'success': True, 'score_change': score_change}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def update_lifecycle_stage(current_stage, new_stage):
    """Update lifecycle stage with progression logic"""
    stage_order = ['prospect', 'enrolled', 'graduate', 'alumni']

    try:
        current_index = stage_order.index(current_stage) if current_stage in stage_order else 0
        new_index = stage_order.index(new_stage) if new_stage in stage_order else 0

        # Only progress forward, never backward
        return stage_order[max(current_index, new_index)]

    except Exception:
        return new_stage or current_stage or 'prospect'

@app.route('/')
def index():
    return redirect('/util-tools')

@app.route('/chat')
def chat_interface():
    return render_template('index.html')

@app.route('/config')
def config():
    return render_template('config.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(current_config)

@app.route('/api/config', methods=['POST'])
def update_config():
    global current_config
    try:
        data = request.get_json()
        current_config.update(data)
        return jsonify({'success': True, 'config': current_config})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/openrouter/models', methods=['GET'])
def get_openrouter_models():
    """Get available OpenRouter models"""
    try:
        models = fetch_openrouter_models()
        return jsonify({'success': True, 'models': models})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/conversation/history', methods=['GET', 'POST'])
def get_conversation():
    """Get conversation history for session"""
    try:
        if request.method == 'POST':
            data = request.get_json()
            session_id = data.get('session_id') if data else None
        else:
            session_id = request.args.get('session_id')

        if not session_id:
            session_id = str(uuid.uuid4())

        history = get_conversation_history(session_id)
        return jsonify({'success': True, 'history': history, 'session_id': session_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/conversation/clear', methods=['POST'])
def clear_conversation():
    """Clear conversation history for session"""
    try:
        data = request.get_json()
        session_id = data.get('session_id') if data else None

        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400

        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('DELETE FROM conversations WHERE session_id = ?', (session_id,))
                conn.execute('DELETE FROM conversation_summaries WHERE session_id = ?', (session_id,))
                conn.commit()
        return jsonify({'success': True, 'message': 'Conversation cleared'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/conversation/context', methods=['POST'])
def get_conversation_context():
    """Debug endpoint to check conversation context"""
    try:
        data = request.get_json()
        session_id = data.get('session_id') if data else None

        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400

        context = build_conversation_context(session_id)
        return jsonify({'success': True, 'context': context, 'session_id': session_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/database', methods=['GET'])
def debug_database():
    """Debug endpoint to check database contents"""
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('SELECT session_id, role, content, timestamp FROM conversations ORDER BY timestamp DESC LIMIT 20')
                results = cursor.fetchall()

                return jsonify({
                    'success': True,
                    'recent_messages': [
                        {'session_id': row[0], 'role': row[1], 'content': row[2][:100] + '...', 'timestamp': row[3]}
                        for row in results
                    ]
                })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        session_id = data.get('session_id')  # Allow client to provide session_id

        if not user_message:
            return jsonify({'error': 'Mensagem não pode estar vazia'}), 400

        # Get or create session ID
        if not session_id:
            session_id = str(uuid.uuid4())

        # Check for special commands
        if user_message.startswith('/search '):
            # Web search command
            query = user_message[8:].strip()
            search_results = tavily_web_search(query, max_results=3)

            if search_results['success']:
                # Save search result
                save_search_result(query, search_results, 'web', session_id)

                # Format response
                bot_message = f"🔍 **Pesquisa Web: {query}**\n\n"

                if search_results.get('answer'):
                    bot_message += f"**Resposta Direta:**\n{search_results['answer']}\n\n"

                bot_message += "**Resultados Encontrados:**\n"
                for i, result in enumerate(search_results['results'][:3], 1):
                    bot_message += f"{i}. **{result['title']}**\n"
                    bot_message += f"   {result['url']}\n"
                    bot_message += f"   {result['content'][:200]}...\n\n"

                if search_results.get('follow_up_questions'):
                    bot_message += "**Perguntas Relacionadas:**\n"
                    for question in search_results['follow_up_questions'][:3]:
                        bot_message += f"• {question}\n"
            else:
                bot_message = f"❌ Erro na pesquisa: {search_results.get('error', 'Erro desconhecido')}"

        elif user_message.startswith('/scrape '):
            # Web scraping command
            url = user_message[8:].strip()
            scrape_result = scrape_website(url, 'text')

            if scrape_result['success']:
                # Save scraped content
                save_scraped_content(url, scrape_result['title'], scrape_result['content'],
                                   scrape_result['metadata'], session_id)

                bot_message = f"🌐 **Conteúdo Extraído de: {url}**\n\n"
                bot_message += f"**Título:** {scrape_result['title']}\n\n"
                bot_message += f"**Conteúdo:** {scrape_result['content'][:1000]}...\n\n"
                bot_message += f"**Tamanho Total:** {scrape_result['content_length']} caracteres"
            else:
                bot_message = f"❌ Erro ao extrair conteúdo: {scrape_result.get('error', 'Erro desconhecido')}"

        elif user_message.startswith('/db '):
            # Database query command
            query = user_message[4:].strip()
            db_result = mcp_database_query(query, session_id=session_id)

            if db_result['success']:
                bot_message = f"🗄️ **Consulta ao Banco de Dados**\n\n"
                bot_message += f"**Query:** {query}\n\n"
                bot_message += f"**Resultados:** {len(db_result['results'])} registros encontrados\n\n"

                # Show first few results
                for i, result in enumerate(db_result['results'][:3], 1):
                    bot_message += f"**Registro {i}:**\n"
                    if isinstance(result, dict):
                        for key, value in result.items():
                            bot_message += f"  • {key}: {value}\n"
                    else:
                        bot_message += f"  {result}\n"
                    bot_message += "\n"

                if len(db_result['results']) > 3:
                    bot_message += f"... e mais {len(db_result['results']) - 3} registros\n\n"

                bot_message += f"**Tempo de execução:** {db_result.get('execution_time', 0)}ms"
            else:
                bot_message = f"❌ Erro na consulta: {db_result.get('error', 'Erro desconhecido')}"

        elif user_message.startswith('/schema'):
            # Database schema command
            db_name = user_message[7:].strip() if len(user_message) > 7 else None
            schema_result = mcp_database_schema(db_name, session_id)

            if schema_result['success']:
                bot_message = f"📋 **Schema do Banco de Dados**\n\n"

                if schema_result.get('tables'):
                    bot_message += "**Tabelas disponíveis:**\n"
                    for table in schema_result['tables'][:10]:  # Limit to 10 tables
                        if isinstance(table, dict):
                            bot_message += f"• {table.get('name', 'N/A')} ({table.get('rows', 0)} registros)\n"
                        else:
                            bot_message += f"• {table}\n"

                    if len(schema_result['tables']) > 10:
                        bot_message += f"... e mais {len(schema_result['tables']) - 10} tabelas\n"

                if schema_result.get('relationships'):
                    bot_message += f"\n**Relacionamentos:** {len(schema_result['relationships'])} encontrados"
            else:
                bot_message = f"❌ Erro ao obter schema: {schema_result.get('error', 'Erro desconhecido')}"

        else:
            # Regular chat with AI
            # Save user message
            save_message(session_id, 'user', user_message,
                        current_config['provider'], current_config.get(f"{current_config['provider']}_model"))

            # Build enhanced conversation context with external data
            conversation_context = build_enhanced_conversation_context(session_id)

            # Enhanced automatic web search detection
            search_keywords = [
                # Portuguese
                'pesquise', 'busque', 'procure', 'o que é', 'como está', 'notícias', 'últimas', 'atual', 'hoje', 'agora',
                'preço', 'cotação', 'valor', 'clima', 'tempo', 'temperatura', 'acontecendo', 'novidades',
                'quando', 'onde', 'quem', 'qual', 'como', 'por que', 'porque',
                # English
                'search', 'find', 'what is', 'how is', 'news', 'latest', 'current', 'today', 'now',
                'price', 'weather', 'temperature', 'happening', 'when', 'where', 'who', 'what', 'how', 'why'
            ]

            # Time-sensitive keywords that always trigger search
            time_sensitive = ['hoje', 'agora', 'atual', 'últimas', 'today', 'now', 'current', 'latest', 'preço', 'price', 'cotação']

            # Question patterns that suggest need for current information
            question_patterns = ['o que é', 'what is', 'como está', 'how is', 'qual é', 'what is the']

            should_search = (
                any(keyword in user_message.lower() for keyword in search_keywords) or
                any(pattern in user_message.lower() for pattern in question_patterns) or
                any(word in user_message.lower() for word in time_sensitive) or
                '?' in user_message  # Questions often need current info
            )

            if should_search:
                # Enhance with web search
                search_query = user_message
                search_results = tavily_web_search(search_query, max_results=3)

                if search_results['success'] and search_results['results']:
                    # Save search result for context
                    save_search_result(search_query, search_results, 'auto', session_id)

                    # Add search context to conversation
                    search_context = f"🔍 Informações atuais da web sobre '{search_query}':\n\n"
                    for i, result in enumerate(search_results['results'][:3], 1):
                        search_context += f"{i}. **{result['title']}**\n"
                        search_context += f"   {result['content'][:200]}...\n\n"

                    if search_results.get('answer'):
                        search_context += f"Resposta direta: {search_results['answer']}\n\n"

                    search_context += "Use essas informações para responder de forma precisa e atualizada."

                    conversation_context.append({"role": "system", "content": search_context})

            conversation_context.append({"role": "user", "content": user_message})

            # Debug: Log conversation context (remove in production)
            print(f"DEBUG: Session {session_id} - Conversation context: {conversation_context}")

            # Get response from chosen provider
            if current_config['provider'] == 'ollama':
                bot_message = get_ollama_response(conversation_context)
            elif current_config['provider'] == 'openrouter':
                bot_message = get_openrouter_response(conversation_context)
            else:
                return jsonify({'error': 'Provedor não configurado'}), 400

        # Save assistant response
        save_message(session_id, 'assistant', bot_message,
                    current_config['provider'], current_config.get(f"{current_config['provider']}_model"))

        return jsonify({
            'success': True,
            'message': bot_message,
            'provider': current_config['provider'],
            'session_id': session_id,
            'conversation_length': len(get_conversation_history(session_id))
        })

    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'Erro de conexão: {str(e)}'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@app.route('/api/test-provider', methods=['POST'])
def test_provider():
    """Testar conectividade de um provedor específico"""
    try:
        data = request.get_json()
        provider = data.get('provider')

        if provider == 'ollama':
            # Testar Ollama
            url = f"http://{data.get('ollama_host', 'host.docker.internal')}:{data.get('ollama_port', '11434')}/api/generate"
            payload = {
                "model": data.get('ollama_model', 'llama3.2:1b'),
                "prompt": "test",
                "stream": False
            }
            response = requests.post(url, json=payload, timeout=10)
            status = "online" if response.status_code == 200 else "offline"

        elif provider == 'openrouter':
            # Testar OpenRouter
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {data.get('openrouter_api_key', '')}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": data.get('openrouter_model', 'google/gemma-2-9b-it:free'),
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 10
            }
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            status = "online" if response.status_code == 200 else "offline"
        else:
            return jsonify({'success': False, 'error': 'Provedor inválido'}), 400

        return jsonify({
            'success': True,
            'status': status,
            'provider': provider,
            'response_code': response.status_code
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'offline',
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Status geral da aplicação"""
    # Testar provedor atual
    current_status = "offline"
    try:
        if current_config['provider'] == 'ollama':
            current_status = get_ollama_response("test")[:10] + "..." if get_ollama_response("test") else "online"
        elif current_config['provider'] == 'openrouter':
            current_status = get_openrouter_response("test")[:10] + "..." if get_openrouter_response("test") else "online"
        current_status = "online"
    except:
        current_status = "offline"

    return jsonify({
        'status': 'online',
        'current_provider': current_config['provider'],
        'provider_status': current_status,
        'config': current_config
    })

# Email Routes
@app.route('/email')
def email_interface():
    return render_template('email.html')

@app.route('/api/email/compose', methods=['POST'])
def compose_email():
    """Generate email content using LLM"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        session_id = data.get('session_id')

        if not prompt:
            return jsonify({'error': 'Prompt não pode estar vazio'}), 400

        # Create email composition prompt
        email_prompt = f"""
        Você é um assistente especializado em escrever emails profissionais.

        TAREFA: {prompt}

        INSTRUÇÕES:
        - Escreva um email completo e profissional
        - Use linguagem formal e cortês
        - Inclua um assunto claro e objetivo
        - O corpo deve ser bem estruturado
        - Assine como "Equipe Grupo Alves"

        FORMATO OBRIGATÓRIO:
        ASSUNTO: [escreva o assunto aqui]

        CORPO:
        [escreva o corpo do email aqui]

        Responda APENAS no formato acima, sem explicações adicionais.
        """

        # Get response from LLM
        if not session_id:
            session_id = str(uuid.uuid4())

        # Build conversation context
        conversation_context = build_conversation_context(session_id)
        conversation_context.append({"role": "user", "content": email_prompt})

        # Get response from chosen provider
        if current_config['provider'] == 'ollama':
            llm_response = get_ollama_response(conversation_context)
        elif current_config['provider'] == 'openrouter':
            llm_response = get_openrouter_response(conversation_context)
        else:
            return jsonify({'error': 'Provedor não configurado'}), 400

        # Parse LLM response
        subject = ""
        body = ""
        html_body = ""

        # Try to extract subject
        if 'ASSUNTO:' in llm_response:
            subject_start = llm_response.find('ASSUNTO:') + len('ASSUNTO:')
            subject_end = llm_response.find('\n', subject_start)
            if subject_end == -1:
                subject_end = llm_response.find('CORPO:', subject_start)
            if subject_end != -1:
                subject = llm_response[subject_start:subject_end].strip()

        # Try to extract body
        if 'CORPO:' in llm_response:
            body_start = llm_response.find('CORPO:') + len('CORPO:')
            body_end = llm_response.find('HTML:', body_start)
            if body_end == -1:
                body_end = len(llm_response)
            body = llm_response[body_start:body_end].strip()

        # Try to extract HTML
        if 'HTML:' in llm_response:
            html_start = llm_response.find('HTML:') + len('HTML:')
            html_body = llm_response[html_start:].strip()
            if not html_body:
                html_body = None

        # Fallback if parsing failed
        if not subject:
            subject = "Email gerado por IA"
        if not body:
            body = llm_response.strip()

        return jsonify({
            'success': True,
            'subject': subject,
            'body': body,
            'html_body': html_body,
            'session_id': session_id
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/email/send', methods=['POST'])
def send_email_api():
    """Send email"""
    try:
        data = request.get_json()
        to_email = data.get('to_email', '')
        subject = data.get('subject', '')
        body = data.get('body', '')
        html_body = data.get('html_body')
        session_id = data.get('session_id')

        if not to_email or not subject or not body:
            return jsonify({'error': 'Email, assunto e corpo são obrigatórios'}), 400

        result = send_email(to_email, subject, body, html_body, session_id)
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/email/list', methods=['GET'])
def list_emails():
    """List emails from database"""
    try:
        email_type = request.args.get('type', 'all')  # sent, received, all
        limit = int(request.args.get('limit', 50))

        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                if email_type == 'sent':
                    cursor = conn.execute('''
                        SELECT id, subject, recipient as contact, body, status, sent_at as timestamp, llm_generated
                        FROM emails WHERE status = 'sent'
                        ORDER BY sent_at DESC LIMIT ?
                    ''', (limit,))
                elif email_type == 'received':
                    cursor = conn.execute('''
                        SELECT id, subject, sender as contact, body, status, received_at as timestamp, 0 as llm_generated
                        FROM emails WHERE status = 'received'
                        ORDER BY received_at DESC LIMIT ?
                    ''', (limit,))
                else:
                    cursor = conn.execute('''
                        SELECT id, subject,
                               CASE WHEN status = 'sent' THEN recipient ELSE sender END as contact,
                               body, status,
                               CASE WHEN status = 'sent' THEN sent_at ELSE received_at END as timestamp,
                               llm_generated
                        FROM emails
                        ORDER BY timestamp DESC LIMIT ?
                    ''', (limit,))

                emails = []
                for row in cursor.fetchall():
                    emails.append({
                        'id': row[0],
                        'subject': row[1],
                        'contact': row[2],
                        'preview': row[3][:100] + '...' if len(row[3]) > 100 else row[3],
                        'status': row[4],
                        'timestamp': row[5],
                        'llm_generated': bool(row[6])
                    })

                return jsonify({'success': True, 'emails': emails})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/email/<email_id>', methods=['GET'])
def get_email(email_id):
    """Get specific email details"""
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT id, subject, sender, recipient, body, html_body, status,
                           created_at, sent_at, received_at, llm_generated
                    FROM emails WHERE id = ?
                ''', (email_id,))

                row = cursor.fetchone()
                if not row:
                    return jsonify({'error': 'Email não encontrado'}), 404

                email_data = {
                    'id': row[0],
                    'subject': row[1],
                    'sender': row[2],
                    'recipient': row[3],
                    'body': row[4],
                    'html_body': row[5],
                    'status': row[6],
                    'created_at': row[7],
                    'sent_at': row[8],
                    'received_at': row[9],
                    'llm_generated': bool(row[10])
                }

                return jsonify({'success': True, 'email': email_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/email/check', methods=['POST'])
def check_emails_api():
    """Manually check for new emails"""
    try:
        new_emails = check_new_emails()
        return jsonify({'success': True, 'new_emails': new_emails, 'count': len(new_emails)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Web Search and Scraping Routes
@app.route('/search')
def search_interface():
    return render_template('search.html')

@app.route('/api/search/web', methods=['POST'])
def web_search_api():
    """Perform web search using Tavily AI"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        max_results = data.get('max_results', 5)
        session_id = data.get('session_id')

        if not query:
            return jsonify({'error': 'Query não pode estar vazia'}), 400

        # Perform search
        results = tavily_web_search(query, max_results=max_results)

        if results['success']:
            # Save to database
            search_id = save_search_result(query, results, 'web', session_id)
            results['search_id'] = search_id

            # Emit real-time notification
            socketio.emit('search_completed', {
                'query': query,
                'results_count': len(results.get('results', [])),
                'search_id': search_id
            })

        return jsonify(results)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search/scrape', methods=['POST'])
def scrape_website_api():
    """Scrape website content"""
    try:
        data = request.get_json()
        url = data.get('url', '')
        extract_type = data.get('extract_type', 'full')
        session_id = data.get('session_id')

        if not url:
            return jsonify({'error': 'URL não pode estar vazia'}), 400

        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return jsonify({'error': 'URL inválida'}), 400

        # Perform scraping
        result = scrape_website(url, extract_type)

        if result['success']:
            # Save to database
            content_id = save_scraped_content(
                url, result['title'], result['content'],
                result['metadata'], session_id
            )
            result['content_id'] = content_id

            # Emit real-time notification
            socketio.emit('scrape_completed', {
                'url': url,
                'title': result['title'],
                'content_length': result['content_length'],
                'content_id': content_id
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search/history', methods=['GET'])
def search_history():
    """Get search history"""
    try:
        session_id = request.args.get('session_id')
        search_type = request.args.get('type', 'all')  # web, scrape, all
        limit = int(request.args.get('limit', 50))

        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                if search_type == 'web':
                    cursor = conn.execute('''
                        SELECT id, query, results_count, timestamp FROM web_searches
                        WHERE session_id = ? OR session_id IS NULL
                        ORDER BY timestamp DESC LIMIT ?
                    ''', (session_id, limit))

                    searches = []
                    for row in cursor.fetchall():
                        searches.append({
                            'id': row[0],
                            'query': row[1],
                            'results_count': row[2],
                            'timestamp': row[3],
                            'type': 'web'
                        })

                elif search_type == 'scrape':
                    cursor = conn.execute('''
                        SELECT id, url, title, timestamp FROM scraped_content
                        WHERE session_id = ? OR session_id IS NULL
                        ORDER BY timestamp DESC LIMIT ?
                    ''', (session_id, limit))

                    searches = []
                    for row in cursor.fetchall():
                        searches.append({
                            'id': row[0],
                            'url': row[1],
                            'title': row[2],
                            'timestamp': row[3],
                            'type': 'scrape'
                        })
                else:  # all
                    # Get both web searches and scraped content
                    web_cursor = conn.execute('''
                        SELECT id, query as title, results_count, timestamp, 'web' as type FROM web_searches
                        WHERE session_id = ? OR session_id IS NULL
                        ORDER BY timestamp DESC LIMIT ?
                    ''', (session_id, limit//2))

                    scrape_cursor = conn.execute('''
                        SELECT id, title, 1 as results_count, timestamp, 'scrape' as type FROM scraped_content
                        WHERE session_id = ? OR session_id IS NULL
                        ORDER BY timestamp DESC LIMIT ?
                    ''', (session_id, limit//2))

                    searches = []
                    for row in web_cursor.fetchall():
                        searches.append({
                            'id': row[0],
                            'title': row[1],
                            'results_count': row[2],
                            'timestamp': row[3],
                            'type': row[4]
                        })

                    for row in scrape_cursor.fetchall():
                        searches.append({
                            'id': row[0],
                            'title': row[1],
                            'results_count': row[2],
                            'timestamp': row[3],
                            'type': row[4]
                        })

                    # Sort by timestamp
                    searches.sort(key=lambda x: x['timestamp'], reverse=True)

                return jsonify({'success': True, 'searches': searches})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search/<search_id>', methods=['GET'])
def get_search_result(search_id):
    """Get specific search result"""
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                # Try web searches first
                cursor = conn.execute('''
                    SELECT query, results, search_type, timestamp FROM web_searches WHERE id = ?
                ''', (search_id,))

                row = cursor.fetchone()
                if row:
                    return jsonify({
                        'success': True,
                        'type': 'web',
                        'query': row[0],
                        'results': json.loads(row[1]),
                        'search_type': row[2],
                        'timestamp': row[3]
                    })

                # Try scraped content
                cursor = conn.execute('''
                    SELECT url, title, content, metadata, timestamp FROM scraped_content WHERE id = ?
                ''', (search_id,))

                row = cursor.fetchone()
                if row:
                    return jsonify({
                        'success': True,
                        'type': 'scrape',
                        'url': row[0],
                        'title': row[1],
                        'content': row[2],
                        'metadata': json.loads(row[3]) if row[3] else {},
                        'timestamp': row[4]
                    })

                return jsonify({'error': 'Resultado não encontrado'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Database Integration Routes
@app.route('/database')
def database_interface():
    return render_template('database.html')

@app.route('/api/database/query', methods=['POST'])
def database_query_api():
    """Execute database query via MCP"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        db_type = data.get('db_type', 'auto')
        session_id = data.get('session_id')

        if not query:
            return jsonify({'error': 'Query não pode estar vazia'}), 400

        # Execute query via MCP
        result = mcp_database_query(query, db_type, session_id)

        if result['success']:
            # Emit real-time notification
            socketio.emit('database_query_completed', {
                'query': query,
                'results_count': len(result.get('results', [])),
                'execution_time': result.get('execution_time', 0)
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database/schema', methods=['GET'])
def database_schema_api():
    """Get database schema via MCP"""
    try:
        db_name = request.args.get('database')
        session_id = request.args.get('session_id')

        result = mcp_database_schema(db_name, session_id)
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database/context', methods=['GET'])
def database_context_api():
    """Get database context for session"""
    try:
        session_id = request.args.get('session_id')
        limit = int(request.args.get('limit', 10))

        if not session_id:
            return jsonify({'error': 'Session ID é obrigatório'}), 400

        contexts = get_external_data_context(session_id, limit)
        return jsonify({'success': True, 'contexts': contexts})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Export Routes
@app.route('/api/export/search', methods=['POST'])
def export_search_results():
    """Export search results to file"""
    try:
        data = request.get_json()
        results = data.get('results', {})
        format_type = data.get('format', 'markdown')  # markdown, text, json

        if not results:
            return jsonify({'error': 'Nenhum resultado para exportar'}), 400

        content = generate_search_export_content(results, format_type)
        filename = f"pesquisa_{results.get('query', 'resultado').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if format_type == 'json':
            filename += '.json'
            content = json.dumps(results, indent=2, ensure_ascii=False)
        elif format_type == 'text':
            filename += '.txt'
        else:
            filename += '.md'

        return jsonify({
            'success': True,
            'content': content,
            'filename': filename,
            'mime_type': get_mime_type(format_type)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export/scrape', methods=['POST'])
def export_scrape_results():
    """Export scrape results to file"""
    try:
        data = request.get_json()
        results = data.get('results', {})
        format_type = data.get('format', 'markdown')

        if not results:
            return jsonify({'error': 'Nenhum resultado para exportar'}), 400

        content = generate_scrape_export_content(results, format_type)
        filename = f"raspagem_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if format_type == 'json':
            filename += '.json'
            content = json.dumps(results, indent=2, ensure_ascii=False)
        elif format_type == 'text':
            filename += '.txt'
        else:
            filename += '.md'

        return jsonify({
            'success': True,
            'content': content,
            'filename': filename,
            'mime_type': get_mime_type(format_type)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def generate_search_export_content(results, format_type):
    """Generate export content for search results"""
    if format_type == 'markdown':
        content = f"# Pesquisa Web: {results.get('query', 'N/A')}\n\n"
        content += f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"

        if results.get('answer'):
            content += f"## Resposta Direta\n\n{results['answer']}\n\n"

        content += f"## Resultados Encontrados ({len(results.get('results', []))})\n\n"

        for i, result in enumerate(results.get('results', []), 1):
            content += f"### {i}. {result.get('title', 'Sem título')}\n\n"
            content += f"**URL:** {result.get('url', 'N/A')}\n\n"
            content += f"**Conteúdo:** {result.get('content', 'N/A')}\n\n"
            content += "---\n\n"

        if results.get('follow_up_questions'):
            content += "## Perguntas Relacionadas\n\n"
            for question in results['follow_up_questions']:
                content += f"- {question}\n"

    else:  # text format
        content = f"PESQUISA WEB: {results.get('query', 'N/A')}\n"
        content += f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"

        if results.get('answer'):
            content += f"RESPOSTA DIRETA:\n{results['answer']}\n\n"

        content += f"RESULTADOS ENCONTRADOS ({len(results.get('results', []))}):\n\n"

        for i, result in enumerate(results.get('results', []), 1):
            content += f"{i}. {result.get('title', 'Sem título')}\n"
            content += f"URL: {result.get('url', 'N/A')}\n"
            content += f"Conteúdo: {result.get('content', 'N/A')}\n\n"

    return content

def generate_scrape_export_content(results, format_type):
    """Generate export content for scrape results"""
    if format_type == 'markdown':
        content = f"# Conteúdo Extraído\n\n"
        content += f"**URL:** {results.get('url', 'N/A')}\n\n"
        content += f"**Título:** {results.get('title', 'N/A')}\n\n"
        content += f"**Data de Extração:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        content += f"**Tamanho:** {results.get('content_length', 0)} caracteres\n\n"
        content += "---\n\n"
        content += f"## Conteúdo\n\n{results.get('content', 'N/A')}\n\n"

        if results.get('metadata'):
            content += "## Metadados\n\n"
            for key, value in results['metadata'].items():
                if value:
                    content += f"**{key}:** {value}\n\n"

    else:  # text format
        content = f"CONTEÚDO EXTRAÍDO\n"
        content += f"URL: {results.get('url', 'N/A')}\n"
        content += f"Título: {results.get('title', 'N/A')}\n"
        content += f"Data de Extração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        content += f"Tamanho: {results.get('content_length', 0)} caracteres\n\n"
        content += f"CONTEÚDO:\n{results.get('content', 'N/A')}\n"

    return content

def get_mime_type(format_type):
    """Get MIME type for format"""
    mime_types = {
        'markdown': 'text/markdown',
        'text': 'text/plain',
        'json': 'application/json'
    }
    return mime_types.get(format_type, 'text/plain')

# SQL Query Generation Routes
@app.route('/sql-assistant')
def sql_assistant_interface():
    return render_template('sql_assistant.html')

@app.route('/api/db-connections', methods=['GET'])
def list_db_connections():
    """List all database connections"""
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT id, name, db_type, host, port, database_name,
                           is_active, last_tested, test_status
                    FROM db_connections
                    ORDER BY created_at DESC
                ''')

                connections = []
                for row in cursor.fetchall():
                    connections.append({
                        'id': row[0],
                        'name': row[1],
                        'db_type': row[2],
                        'host': row[3],
                        'port': row[4],
                        'database_name': row[5],
                        'is_active': bool(row[6]),
                        'last_tested': row[7],
                        'test_status': row[8]
                    })

                return jsonify({'success': True, 'connections': connections})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/db-connections', methods=['POST'])
def create_db_connection_api():
    """Create new database connection"""
    try:
        data = request.get_json()

        result = create_db_connection(
            data.get('name'),
            data.get('db_type'),
            data.get('host'),
            data.get('port'),
            data.get('database_name'),
            data.get('username'),
            data.get('password')
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/db-connections/<connection_id>/test', methods=['POST'])
def test_db_connection_api(connection_id):
    """Test database connection"""
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT connection_string, db_type FROM db_connections WHERE id = ?
                ''', (connection_id,))
                row = cursor.fetchone()

                if not row:
                    return jsonify({'error': 'Connection not found'}), 404

                connection_string, db_type = row

        result = test_db_connection(connection_string, db_type)

        # Update test status
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    UPDATE db_connections
                    SET last_tested = ?, test_status = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(),
                     'success' if result['success'] else 'failed', connection_id))
                conn.commit()

        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/db-connections/<connection_id>/schema', methods=['GET'])
def get_db_schema_api(connection_id):
    """Get database schema"""
    try:
        result = get_db_schema(connection_id)
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sql/generate', methods=['POST'])
def generate_sql_api():
    """Generate SQL from natural language"""
    try:
        data = request.get_json()
        natural_query = data.get('query', '')
        connection_id = data.get('connection_id', '')
        session_id = data.get('session_id', str(uuid.uuid4()))

        if not natural_query or not connection_id:
            return jsonify({'error': 'Query and connection ID are required'}), 400

        result = generate_sql_from_natural_language(natural_query, connection_id, session_id)
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sql/execute', methods=['POST'])
def execute_sql_api():
    """Execute generated SQL query"""
    try:
        data = request.get_json()
        query_id = data.get('query_id', '')
        connection_id = data.get('connection_id', '')

        if not query_id or not connection_id:
            return jsonify({'error': 'Query ID and connection ID are required'}), 400

        result = execute_generated_sql(query_id, connection_id)

        if result['success']:
            # Emit real-time notification
            socketio.emit('sql_executed', {
                'query_id': query_id,
                'row_count': result['row_count'],
                'execution_time': result['execution_time']
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Customer Profiling and CRM Routes
@app.route('/crm')
def crm_interface():
    return render_template('crm.html')

@app.route('/util-tools')
def util_tools_interface():
    return render_template('util_tools.html')

@app.route('/help')
def help_interface():
    return render_template('help.html')

@app.route('/api-docs')
def api_docs_interface():
    return render_template('api_docs.html')

@app.route('/api/customers', methods=['GET'])
def list_customers():
    """List all customers with profiles"""
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT id, email, name, company, communication_style,
                           interaction_count, last_interaction, satisfaction_score,
                           topics_of_interest, created_at
                    FROM customer_profiles
                    ORDER BY last_interaction DESC
                ''')

                customers = []
                for row in cursor.fetchall():
                    customers.append({
                        'id': row[0],
                        'email': row[1],
                        'name': row[2],
                        'company': row[3],
                        'communication_style': row[4],
                        'interaction_count': row[5],
                        'last_interaction': row[6],
                        'satisfaction_score': row[7],
                        'topics_of_interest': json.loads(row[8]) if row[8] else [],
                        'created_at': row[9]
                    })

                return jsonify({'success': True, 'customers': customers})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/customers/<customer_id>', methods=['GET'])
def get_customer_profile(customer_id):
    """Get detailed customer profile"""
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                # Get customer profile
                cursor = conn.execute('''
                    SELECT * FROM customer_profiles WHERE id = ?
                ''', (customer_id,))
                customer = cursor.fetchone()

                if not customer:
                    return jsonify({'error': 'Customer not found'}), 404

                # Get customer interactions
                cursor = conn.execute('''
                    SELECT interaction_type, content, sentiment_score,
                           response_time, timestamp
                    FROM customer_interactions
                    WHERE customer_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 50
                ''', (customer_id,))
                interactions = cursor.fetchall()

                customer_data = {
                    'id': customer[0],
                    'email': customer[1],
                    'name': customer[2],
                    'company': customer[3],
                    'communication_style': customer[4],
                    'response_time_avg': customer[5],
                    'interaction_count': customer[6],
                    'last_interaction': customer[7],
                    'satisfaction_score': customer[8],
                    'topics_of_interest': json.loads(customer[9]) if customer[9] else [],
                    'created_at': customer[10],
                    'updated_at': customer[11],
                    'interactions': [
                        {
                            'type': row[0],
                            'content': row[1][:200] + '...' if len(row[1]) > 200 else row[1],
                            'sentiment_score': row[2],
                            'response_time': row[3],
                            'timestamp': row[4]
                        } for row in interactions
                    ]
                }

                return jsonify({'success': True, 'customer': customer_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/customers/analytics', methods=['GET'])
def customer_analytics_api():
    """Get customer analytics dashboard data"""
    try:
        result = get_customer_analytics()
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/email/<email_id>/reply-suggestions', methods=['POST'])
def get_reply_suggestions(email_id):
    """Get AI-powered reply suggestions for an email with enhanced CRM context"""
    try:
        # Get email content
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT subject, sender, body, 
                           CASE WHEN status = 'sent' THEN sent_at ELSE received_at END as timestamp 
                    FROM emails WHERE id = ?
                ''', (email_id,))
                email_data = cursor.fetchone()

                if not email_data:
                    return jsonify({'error': 'Email not found'}), 404

                subject, sender, body, timestamp = email_data

        # Process email for CRM if not already done
        email_for_crm = {
            'id': email_id,
            'sender': sender,
            'subject': subject,
            'body': body,
            'timestamp': timestamp
        }
        crm_result = process_email_for_crm(email_for_crm)

        # Get enhanced customer profile and interaction history
        customer_profile = None
        thread_history = None

        if crm_result['success']:
            customer_id = crm_result['customer_id']

            # Get comprehensive customer profile
            with db_lock:
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.execute('''
                        SELECT name, communication_style, student_status, lifecycle_stage,
                               interaction_count, satisfaction_score, topics_of_interest,
                               course_history, lead_score, phone, timezone
                        FROM customer_profiles WHERE id = ?
                    ''', (customer_id,))
                    profile_data = cursor.fetchone()

                    if profile_data:
                        customer_profile = {
                            'name': profile_data[0],
                            'communication_style': profile_data[1],
                            'student_status': profile_data[2],
                            'lifecycle_stage': profile_data[3],
                            'interaction_count': profile_data[4],
                            'satisfaction_score': profile_data[5],
                            'topics_of_interest': json.loads(profile_data[6]) if profile_data[6] else [],
                            'course_history': profile_data[7],
                            'lead_score': profile_data[8],
                            'phone': profile_data[9],
                            'timezone': profile_data[10]
                        }

                    # Get recent interaction history for context
                    cursor = conn.execute('''
                        SELECT content, interaction_type, timestamp, sentiment_score
                        FROM customer_interactions
                        WHERE customer_id = ?
                        ORDER BY timestamp DESC LIMIT 5
                    ''', (customer_id,))
                    interactions = cursor.fetchall()

                    if interactions:
                        thread_history = "\n".join([
                            f"{row[2]}: {row[1]} - {row[0][:100]}..."
                            for row in interactions
                        ])

        # Prepare email metadata
        email_metadata = {
            'sender': sender,
            'subject': subject,
            'timestamp': timestamp
        }

        # Generate enhanced reply suggestions with full CRM context
        result = generate_email_reply_suggestions(
            email_content=body,
            thread_history=thread_history,
            customer_profile=customer_profile,
            email_metadata=email_metadata
        )

        # Add customer context information to response
        if result['success']:
            result['customer_context'] = {
                'has_profile': customer_profile is not None,
                'interaction_count': customer_profile.get('interaction_count', 0) if customer_profile else 0,
                'lifecycle_stage': customer_profile.get('lifecycle_stage', 'unknown') if customer_profile else 'unknown',
                'student_status': customer_profile.get('student_status', 'unknown') if customer_profile else 'unknown',
                'lead_score': customer_profile.get('lead_score', 0) if customer_profile else 0
            }

        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/email/<email_id>/analyze', methods=['POST'])
def analyze_email_api(email_id):
    """Analyze email and update customer profile"""
    try:
        # Get email content
        with db_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT sender, body FROM emails WHERE id = ?
                ''', (email_id,))
                email_data = cursor.fetchone()

                if not email_data:
                    return jsonify({'error': 'Email not found'}), 404

                sender, body = email_data

        # Create or update customer profile
        profile_result = create_or_update_customer_profile(sender, email_content=body)

        if profile_result['success']:
            # Log interaction
            log_customer_interaction(
                profile_result['customer_id'],
                email_id,
                'email_received',
                body
            )

        # Analyze email sentiment
        analysis = analyze_email_sentiment(body)

        return jsonify({
            'success': True,
            'analysis': analysis,
            'profile_updated': profile_result['success']
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    # Start email monitoring
    start_email_monitoring()

    # Run the app with SocketIO
    socketio.run(app, host='0.0.0.0', port=8000, debug=True, allow_unsafe_werkzeug=True)
