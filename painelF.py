import tkinter as tk
from gtts import gTTS
import pygame
import os
import socket
import threading
import time
import datetime
from pynput.keyboard import Listener, Key
from PIL import Image, ImageDraw, ImageTk
from queue import Queue
import sys
import tempfile
import sqlite3
import win32print
import ctypes
import subprocess
import win32api
# Inicializar o pygame mixer uma única vez
pygame.mixer.init()

# Fila para gerenciar as chamadas de senha
fila_senhas = Queue()



def obter_ip_local():
    try:
        # Obtém o IP local consultando uma conexão de teste
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception as e:
        print(f"Erro ao obter o IP local: {e}")
        return "127.0.0.1"  # Fallback em casos de falha

ip_local = obter_ip_local()

def configurar_permissoes_ntfs(caminho):
    """
    Configura permissões NTFS para o grupo 'Todos' ou 'Everyone' no caminho especificado.
    """
    try:
        grupo_todos = "Todos"  # Nome do grupo para sistemas em inglês
        try:
            import locale
            # Detecta idioma do sistema e ajusta o nome do grupo para sistemas em português
            if "pt" in locale.setlocale(locale.LC_ALL, "").lower():
                grupo_todos = "Todos"
        except Exception as e:
            print(f"Erro ao detectar idioma do sistema, utilizando 'Everyone' como padrão: {e}")

        # Configura permissões NTFS no diretório
        comando_permissoes = f'icacls "{caminho}" /grant "{grupo_todos}:(OI)(CI)F" /T'
        resultado = subprocess.run(comando_permissoes, shell=True, capture_output=True, text=True)

        if resultado.returncode == 0:
            print(f"Permissões NTFS configuradas com sucesso para a pasta: {caminho}")
        else:
            print(f"Erro ao configurar permissões NTFS. Detalhes:\n{resultado.stderr}")
            return False

        return True

    except Exception as e:
        print(f"Erro ao configurar permissões NTFS: {e}")
        return False

def criar_compartilhar_pasta():

    nome_pasta = "Banco"
    caminho = os.path.join("C:\\", nome_pasta)

    try:
        # Verificar se a pasta já está compartilhada
        comando_verificar = f'net share {nome_pasta}'
        resultado_verificar = subprocess.run(comando_verificar, shell=True, capture_output=True, text=True)

        if resultado_verificar.returncode == 0:
            print(f"A pasta '{nome_pasta}' já está compartilhada.")
            ip_local = obter_ip_local()
            return f"\\\\{ip_local}\\{nome_pasta}"  # Retorna o caminho do compartilhamento para uso

        # Criar a pasta se ela não existir
        if not os.path.exists(caminho):
            os.makedirs(caminho, exist_ok=True)
            print(f"Pasta '{caminho}' criada com sucesso.")

        # Configurar permissões NTFS para o grupo 'Todos'
        permissoes_configuradas = configurar_permissoes_ntfs(caminho)
        if not permissoes_configuradas:
            print("Falha ao configurar permissões NTFS. Verifique as configurações do sistema.")
            return None

        # Compartilhar a pasta usando "net share"
        comando_compartilhar = f'net share {nome_pasta}="{caminho}" /GRANT:"Todos",FULL'
        resultado = subprocess.run(comando_compartilhar, shell=True, capture_output=True, text=True)

        if resultado.returncode == 0:
            print(f"Pasta '{nome_pasta}' compartilhada com sucesso.")
            ip_local = obter_ip_local()
            return f"\\\\{ip_local}\\{nome_pasta}"  # Retorna o caminho do compartilhamento para uso
        else:
            print(f"Erro ao compartilhar a pasta. Detalhes:\n{resultado.stderr}")
            return None

    except PermissionError:
        print("Erro: É necessário executar como administrador para compartilhar a pasta.")
    except Exception as e:
        print(f"Erro ao criar ou compartilhar a pasta: {e}")
        return None


def is_admin():
    """
    Verifica se o script está sendo executado com privilégios de administrador.
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


caminho_banco = os.path.join("C:\\Banco", "painel.db")
if not os.path.exists(os.path.dirname(caminho_banco)):
    os.makedirs(os.path.dirname(caminho_banco), exist_ok=True)
# Variável global para armazenar a última senha chamada
ultima_senha = None

botao_habilitado = True


mapa_tipos = {
    "1": "Agendamento",
    "2": "Exame",
    "3": "Preferencial"
}



def zerar_senhas_no_banco():
    try:
        conexao = sqlite3.connect(caminho_banco)  # Atualize o caminho aqui
        cursor = conexao.cursor()
        cursor.execute("DELETE FROM senhas")
        cursor.execute("UPDATE ultimas_senhas SET ultima_senha = 0")
        conexao.commit()
        conexao.close()
        print("As senhas foram zeradas com sucesso!")
    except Exception as e:
        print(f"Erro ao zerar as senhas no banco: {e}")

def zerar_senhas_diariamente():
    while True:
        agora = datetime.datetime.now()
        if agora.hour == 6 and agora.minute == 0:
            print("Iniciando o processo de limpeza de senhas...")
            zerar_senhas_no_banco()
            time.sleep(60)  # Aguarda 1 minuto para evitar múltiplas execuções
        time.sleep(1)  # Verifica o horário a cada segundo

def inicializar_banco():
    """
    Inicializa o banco de dados, criando as tabelas necessárias dentro da pasta compartilhada 'Banco'.
    """
    global caminho_banco

    # Garante que o banco de dados seja sempre salvo na pasta compartilhada
    caminho_banco = os.path.join("C:\\Banco", "painel.db")
    if not os.path.exists(os.path.dirname(caminho_banco)):
        os.makedirs(os.path.dirname(caminho_banco), exist_ok=True)

    conexao = sqlite3.connect(caminho_banco)
    cursor = conexao.cursor()

    # Criação das tabelas (se não existirem)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS senhas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            senha TEXT NOT NULL,
            tipo_atendimento TEXT NOT NULL,
            chamada INTEGER DEFAULT 0,
            data_hora TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ultimas_senhas (
            tipo TEXT PRIMARY KEY,
            ultima_senha INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contadores (
            id INTEGER PRIMARY KEY,
            tipo TEXT UNIQUE,
            contador INTEGER
        )
    """)

    # Verifica se a coluna data_hora existe e a adiciona se necessário
    cursor.execute("PRAGMA table_info(senhas)")
    colunas = [coluna[1] for coluna in cursor.fetchall()]
    if 'data_hora' not in colunas:
        cursor.execute("ALTER TABLE senhas ADD COLUMN data_hora TEXT")

    conexao.commit()
    conexao.close()
if __name__ == "__main__":
    if is_admin():
        # Garante que a pasta compartilhada seja sempre chamada de 'Banco'
        caminho_compartilhamento = criar_compartilhar_pasta()

        if caminho_compartilhamento:
            print(f"Sua pasta está acessível em: {caminho_compartilhamento}")
        else:
            print("Falha ao criar ou compartilhar a pasta 'Banco'.")
    else:
        print("Execute o script como administrador para compartilhar a pasta.")

    # Inicializa o banco de dados na pasta compartilhada
    inicializar_banco()

# Função para obter o caminho correto para o arquivo (tanto no script quanto no executável)
def obter_caminho_arquivo(arquivo):
    if getattr(sys, 'frozen', False):
        # Quando o código está sendo executado como um executável gerado pelo PyInstaller
        caminho = os.path.join(sys._MEIPASS, arquivo)
    else:
        # Quando o código está sendo executado normalmente como um script Python
        caminho = os.path.join(os.path.dirname(__file__), arquivo)
    return caminho


def verificar_impressora():
    try:
        # Obtém o nome da impressora padrão
        impressora_padrao = win32print.GetDefaultPrinter()
        print(f"Impressora padrão: {impressora_padrao}")

        # Abre a impressora para obter informações detalhadas
        handle = win32print.OpenPrinter(impressora_padrao)
        status = win32print.GetPrinter(handle, 2)  # Obtém informações do nível 2 da impressora
        win32print.ClosePrinter(handle)

        # Verifica o status da impressora
        if status.get('Attributes') & win32print.PRINTER_ATTRIBUTE_WORK_OFFLINE:
            print("Erro: A impressora está offline.")
            return False
        elif status.get('Status', 0) & win32print.PRINTER_STATUS_OFFLINE:
            print("Erro: A impressora está offline.")
            return False
        elif status.get('Status', 0) & win32print.PRINTER_STATUS_PAPER_OUT:
            print("Erro: A impressora está sem papel.")
            return False
        elif status.get('Status', 0) & win32print.PRINTER_STATUS_ERROR:
            print("Erro: A impressora está com erro.")
            return False
        elif status.get('Status', 0) & win32print.PRINTER_STATUS_OUT_OF_MEMORY:
            print("Erro: A impressora está sem memória.")
            return False
        elif status.get('Status', 0) & win32print.PRINTER_STATUS_DOOR_OPEN:
            print("Erro: A porta da impressora está aberta.")
            return False
        else:
            print("Impressora conectada e pronta para uso.")
            return True
    except Exception as e:
        print(f"Erro ao verificar a impressora: {e}")
        return False


def salvar_senha_no_banco(senha, tipo_atendimento):
    if not verificar_impressora():
        print("Erro: A impressora está offline ou sem papel. A senha não será salva no banco de dados.")
        return

    data_hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conexao = sqlite3.connect(caminho_banco)  # Atualize o caminho
    cursor = conexao.cursor()
    cursor.execute(
        "INSERT INTO senhas (senha, tipo_atendimento, data_hora) VALUES (?, ?, ?)",
        (senha, tipo_atendimento, data_hora),
    )
    conexao.commit()
    conexao.close()
    print(f"Senha {senha} ({tipo_atendimento}) salva no banco de dados com sucesso.")


def imprimir_senha(numero_senha, tipo_atendimento):
    if not verificar_impressora():
        print("Erro: A impressora está sem papel ou offline.")
        return

    try:
        # Data e Hora
        data_hora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # Configuração da impressora padrão
        nome_impressora = win32print.GetDefaultPrinter()  # Obtém a impressora padrão do sistema
        hprinter = win32print.OpenPrinter(nome_impressora)
        try:
            # Iniciar o job de impressão
            hprinter_job = win32print.StartDocPrinter(hprinter, 1, ("Impressão de Senha", None, "RAW"))
            win32print.StartPagePrinter(hprinter)

            # Comandos ESC/POS para inicialização e centralização
            conteudo = "\x1b\x40"  # Inicializa a impressora (comando ESC @)
            conteudo += "\x1b\x61\x01"  # Centraliza o texto (comando ESC a 1)

            # Adiciona o texto "Sidi - Medicina por Imagem"
            conteudo += "\x1b\x21\x10"  # Texto médio (negrito e altura dobrada)
            conteudo += "Sidi - Medicina por Imagem\n\n"  # Texto com espaçamento

            # Cabeçalho - SENHA DE ATENDIMENTO
            conteudo += "\x1b\x21\x20"  # Define o texto como grande (negrito e largura dobrada)
            conteudo += "SENHA DE ATENDIMENTO\n\n"  # Cabeçalho com espaçamento

            # Tipo de Atendimento - Ajustado
            conteudo += "\x1b\x21\x10"  # Texto médio (negrito e altura dobrada)
            conteudo += f"TIPO: {tipo_atendimento}\n\n"  # Tipo de Atendimento com espaçamento

            # Número da Senha - Sem zeros à esquerda
            conteudo += "\x1b\x21\x20"  # Texto grande (negrito e largura dobrada)
            conteudo += f"SENHA: {numero_senha}\n\n\n"  # Apenas número da senha sem zeros à esquerda

            # Informações adicionais (Data e separador)
            conteudo += "\x1b\x21\x00"  # Texto padrão (normal)
            conteudo += f"Data/Hora: {data_hora}\n"
            conteudo += "---------------------------\n"
            conteudo += "\n\n\n"  # Avanço de papel para facilitar manuseio

            # Comando de corte (parcial)
            conteudo += "\x1d\x56\x01"  # Comando ESC/POS para corte parcial

            # Enviar os dados para a impressora
            win32print.WritePrinter(hprinter, conteudo.encode('latin1'))  # Codifica o texto para bytes

            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
            print("Depuração: Impressão concluída com sucesso.")
        finally:
            win32print.ClosePrinter(hprinter)

    except Exception as e:
        print(f"Erro ao imprimir: {e}")

def get_proxima_senha(tipo_atendimento):
    conexao = sqlite3.connect(caminho_banco)  # Atualize o caminho
    cursor = conexao.cursor()

    # Verificar última senha do tipo
    cursor.execute("SELECT ultima_senha FROM ultimas_senhas WHERE tipo = ?", (tipo_atendimento,))
    resultado = cursor.fetchone()

    if resultado:
        # Incrementa a última senha gerada para este tipo
        proxima_senha = resultado[0] + 1
        if proxima_senha > 999:
            proxima_senha = 1
        cursor.execute("UPDATE ultimas_senhas SET ultima_senha = ? WHERE tipo = ?",
                       (proxima_senha, tipo_atendimento))
    else:
        # Primeiro registro para este tipo
        proxima_senha = 1
        cursor.execute("INSERT INTO ultimas_senhas (tipo, ultima_senha) VALUES (?, ?)",
                       (tipo_atendimento, proxima_senha))

    # Salvar as mudanças no banco
    conexao.commit()
    conexao.close()

    return proxima_senha

def capturar_teclas():
    def habilitar_botao():
        global botao_habilitado
        botao_habilitado = True

    def on_press(key):
        global botao_habilitado
        try:
            tipo_atendimento = None

            # Define os tipos de atendimento capturados pelas teclas
            if key == Key.end:
                tipo_atendimento = "Agendamento"
            elif key == Key.down:
                tipo_atendimento = "Exame do Dia"
            elif key == Key.page_down:
                tipo_atendimento = "Atendimento Preferencial"

            # Apenas se houver um tipo de atendimento e o botão estiver habilitado
            if tipo_atendimento and botao_habilitado:
                botao_habilitado = False  # Desabilita o botão
                # Gerar o próximo número da senha para o tipo de atendimento clicado
                numero_senha = get_proxima_senha(tipo_atendimento)

                # Salvar no banco
                salvar_senha_no_banco(numero_senha, tipo_atendimento)

                # Imprimir a senha
                imprimir_senha(numero_senha, tipo_atendimento)

                print(f"Senha {numero_senha} ({tipo_atendimento}) salva e impressa com sucesso.")

                # Esperar 2 segundos antes de permitir nova impressão
                threading.Timer(2, habilitar_botao).start()

            elif not botao_habilitado:
                print("Aguarde 2 segundos antes de imprimir novamente.")

        except Exception as e:
            print(f"Erro ao capturar tecla ou processar senha: {e}")

    # Listener para capturar teclas
    with Listener(on_press=on_press) as listener:
        listener.join()


def determinar_tipo_mensagem(guiche, senha, tipo):
    tipo_texto = "Desconhecido"
    mensagem_audio = f"Guichê {guiche}, senha desconhecida {senha}."

    if tipo == "Agendamento":
        tipo_texto = "Agendamento"
        mensagem_audio = f"Guichê {guiche}, senha de agendamento {senha}."
    elif tipo == "Exame":
        tipo_texto = "Exame"
        mensagem_audio = f"Guichê {guiche}, senha de Exame {senha}."
    elif tipo == "Preferencial":
        tipo_texto = "Preferencial"
        mensagem_audio = f"Guichê {guiche}, senha Preferencial {senha}."

    return tipo_texto, mensagem_audio

fala_bloqueio = threading.Lock()

def falar_senha(guiche, senha, tipo):
    def reproduzir_audio():
        with fala_bloqueio:
            try:
                tipo_texto, mensagem_audio = determinar_tipo_mensagem(guiche, senha, tipo)
                print(f"Mensagem gerada para áudio: {mensagem_audio}")

                arquivo_campainha = obter_caminho_arquivo('campainha.mp3')
                if os.path.exists(arquivo_campainha):
                    pygame.mixer.music.load(arquivo_campainha)
                    pygame.mixer.music.play()
                    time.sleep(1.4)

                temp_dir = tempfile.gettempdir()
                filename = os.path.join(temp_dir, f"senha_audio_{guiche}_{senha}.mp3")
                tts = gTTS(text=mensagem_audio, lang='pt')
                tts.save(filename)

                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)

                os.remove(filename)
            except Exception as e:
                print(f"Erro ao gerar ou reproduzir som: {e}")
            finally:
                if not fila_senhas.empty():
                    fila_senhas.task_done()

    threading.Thread(target=reproduzir_audio).start()



def processar_fila_senhas():
    while True:
        print("Aguardando na fila...")
        guiche, senha, tipo = fila_senhas.get()
        print(f"Processando mensagem: Guichê={guiche}, Senha={senha}, Tipo={tipo}")
        atualizar_painel(guiche, senha, tipo)
        fila_senhas.task_done()


def adicionar_senha(guiche, senha, tipo):
    fila_senhas.put((guiche, senha, tipo))


def atualizar_painel(guiche, senha, tipo):
    atualizar_painel_thread(guiche, senha, tipo)


# Histórico de chamadas
historico_labels = []


def atualizar_historico(guiche, senha, tipo):
    hora = datetime.datetime.now().strftime("%H:%M")
    historico_labels.insert(0, (senha, guiche, hora, tipo))

    if len(historico_labels) > 5:
        historico_labels.pop()

    for widget in historico_chamadas_frame.grid_slaves():
        if int(widget.grid_info()["row"]) > 1:
            widget.destroy()

    # Atualiza o histórico na interface gráfica
    for i, (senha, guiche, hora, tipo) in enumerate(historico_labels):
        tk.Label(historico_chamadas_frame, text=senha, font=("Helvetica", 12), fg="white", bg="#1a2537").grid(row=i + 2,
                                                                                                              column=0,
                                                                                                              padx=5,
                                                                                                              pady=5)
        tk.Label(historico_chamadas_frame, text=guiche, font=("Helvetica", 12), fg="white", bg="#1a2537").grid(
            row=i + 2, column=1, padx=5, pady=5)
        tk.Label(historico_chamadas_frame, text=hora, font=("Helvetica", 12), fg="white", bg="#1a2537").grid(row=i + 2,
                                                                                                             column=2,
                                                                                                             padx=5,
                                                                                                             pady=5)
        tk.Label(historico_chamadas_frame, text=tipo, font=("Helvetica", 12), fg="white", bg="#1a2537").grid(row=i + 2,
                                                                                                             column=3,
                                                                                                             padx=5,
                                                                                                             pady=5)


# Mapeamento de tipos para cores (fundo do Label)
cores_tipos = {
    "Agendamento": "#4CAF50",  # Verde suave
    "Exame": "#2196F3",  # Amarelo ouro
    "Preferencial": "#F44336",  # Vermelho suave
    "Tipo desconhecido": "#9E9E9E"  # Cinza neutro
}

def atualizar_painel_thread(guiche, senha, tipo):
    """
    Atualiza o painel com guichê, senha e tipo de atendimento.
    """
    # Atualizar labels de senha, guichê e tipo
    senha_label.config(text=f"Senha: {senha}")
    guiche_label.config(text=f"Guichê: {guiche}")
    tipo_label.config(text=f"{tipo}")

    # Define o fundo baseado no tipo de atendimento
    cor_fundo_tipo = cores_tipos.get(tipo, "#9E9E9E")  # Cor padrão para tipos desconhecidos
    imagem_tipo_label = criar_borda_arredondada(largura, altura, cor_borda, cor_fundo_tipo, raio)

    # Atualizar o Label com a nova imagem
    tipo_label.config(image=imagem_tipo_label, bg="#2a3d66")  # Use o fundo geral do painel
    tipo_label.image = imagem_tipo_label  # Manter referência para evitar garbage collection

    # Atualiza o histórico
    atualizar_historico(guiche, senha, tipo)

    # Fala a chamada
    falar_senha(guiche, senha, tipo)

    global ultima_senha
    ultima_senha = senha

def atualizar_data_hora():
    agora = datetime.datetime.now()
    data_value.config(text=agora.strftime("%d/%m/%Y"))
    hora_value.config(text=agora.strftime("%H:%M:%S"))
    root.after(1000, atualizar_data_hora)



def receber_senhas():
    while True:
        try:
            ip_local = obter_ip_local()
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind((ip_local, 12345))
            print(f"Servidor iniciado em {ip_local}:12345")

            while True:
                data, addr = s.recvfrom(1024)
                mensagem = data.decode()
                if mensagem == "ping":
                    s.sendto("pong".encode(), addr)
                else:
                    partes = mensagem.split(',')
                    if len(partes) == 3:
                        guiche, senha, tipo_codigo = partes
                        tipo = mapa_tipos.get(tipo_codigo, "Desconhecido")
                        fila_senhas.put((guiche, senha, tipo))
                        # Enviar resposta de confirmação
                        s.sendto("ok".encode(), addr)
                    else:
                        print(f"[ERRO] Mensagem no formato incorreto: {mensagem}")
        except socket.error as e:
            print(f"Erro de socket: {e}. Tentando reconectar...")
            time.sleep(5)

def carregar_imagem_local():
    logo_path = obter_caminho_arquivo("Logo.png")
    try:
        img = Image.open(logo_path)
        img = img.convert("RGBA")

        # Transformar a imagem em branco
        datas = img.getdata()
        new_data = []
        for item in datas:
            if item[3] > 0:
                new_data.append((255, 255, 255, item[3]))
            else:
                new_data.append(item)
        img.putdata(new_data)

        return img
    except Exception as e:
        print(f"Erro ao carregar a imagem: {e}")
        return None


def criar_borda_arredondada(w, h, cor_borda, cor_fundo, raio):
    """
    Cria uma imagem com bordas arredondadas usando Pillow.
    """
    # Criar imagem inicial com fundo transparente
    imagem = Image.new("RGBA", (w, h), (0, 0, 0, 0))  # Fundo transparente

    # Criar objeto de desenho
    draw = ImageDraw.Draw(imagem)

    # Desenhar retângulo arredondado (borda externa)
    draw.rounded_rectangle(
        (0, 0, w, h),  # Coordenadas completas
        radius=raio,  # Raio das bordas
        fill=cor_fundo,  # Cor de preenchimento interno (do tipo)
        outline=cor_borda,  # Cor da borda
        width=2  # Espessura da borda
    )

    return ImageTk.PhotoImage(imagem)

# Configurando o tamanho do label com borda arredondada
largura, altura = 800, 100  # Largura e altura do Label
raio = 30  # Raio da borda arredondada
cor_borda = "#FFFFFF"  # Cor da borda branca
cor_fundo = "#2a3d66"  # Cor do fundo do painel

if __name__ == "__main__":
    inicializar_banco()

    root = tk.Tk()
    root.title("Painel de Senha")
    root.geometry("1024x768")
    root.config(bg="#2a3d66")
    root.attributes("-fullscreen", True)

    imagem_tipo_label = criar_borda_arredondada(largura, altura, cor_borda, cor_fundo, raio)

    painel = tk.Frame(root, bg="#2a3d66")
    painel.pack(fill=tk.BOTH, expand=True)

    topo_frame = tk.Frame(painel, bg="#2a3d66")
    topo_frame.pack(side="top", pady=20, fill=tk.X)

    logo_img = carregar_imagem_local()
    if logo_img:
        logo_img = logo_img.resize((300, 150), Image.Resampling.LANCZOS)
        logo_img = ImageTk.PhotoImage(logo_img)
    else:
        logo_img = ImageTk.PhotoImage(Image.new('RGBA', (300, 150), color='grey'))
    logo_label = tk.Label(topo_frame, image=logo_img, bg="#2a3d66")
    logo_label.pack(pady=10)

    esquerda_frame = tk.Frame(painel, bg="#2a3d66")
    esquerda_frame.pack(side="left", padx=30, pady=50, anchor="n")

    # Criar o Label com a imagem de fundo arredondada
    tipo_label = tk.Label(
        esquerda_frame,
        image=imagem_tipo_label,
        text=" Aguardando chamada... ",
        font=("Helvetica", 45, "bold"),
        fg="white",
        compound="center",
        bg="#2a3d66",  # Neutra (se for usada), mas será coberta pela imagem
        bd=0  # Sem borda adicional
    )
    tipo_label.image = imagem_tipo_label  # Manter referência da imagem para evitar garbage collection
    tipo_label.pack(pady=(20, 10))

    guiche_label = tk.Label(esquerda_frame, text=" Aguardando chamada...", font=("Helvetica", 40, "bold"), bg="#2a3d66", fg="white",
                            anchor="center")
    guiche_label.pack(pady=(30, 0))

    senha_label = tk.Label(esquerda_frame, text=" Aguardando chamada...", font=("Helvetica", 40, "bold"), bg="#2a3d66", fg="white",
                           anchor="center")
    senha_label.pack(pady=(50, 10))

    historico_chamadas_frame = tk.Frame(painel, bg="#1a2537", padx=5, pady=5, width=270, height=300,highlightbackground="white", highlightthickness=2)
    historico_chamadas_frame.pack(side="right", anchor="n", padx=5, pady=50)

    titulo_historico = tk.Label(historico_chamadas_frame, text="                 HISTÓRICO DE CHAMADAS",
                                font=("Helvetica", 16, "bold"), fg="white", bg="#1a2537")
    titulo_historico.grid(row=0, column=0, columnspan=3, pady=10)

    header_tipo = tk.Label(historico_chamadas_frame, text="TIPO", font=("Helvetica", 12, "bold"), fg="white", bg="#1a2537")
    header_tipo.grid(row=1, column=3, padx=5, pady=5)
    header_senha = tk.Label(historico_chamadas_frame, text="SENHA", font=("Helvetica", 12, "bold"), fg="white",
                            bg="#1a2537")
    header_senha.grid(row=1, column=0, padx=5, pady=5)
    header_guiche = tk.Label(historico_chamadas_frame, text="GUICHÊ", font=("Helvetica", 12, "bold"), fg="white",
                             bg="#1a2537")
    header_guiche.grid(row=1, column=1, padx=5, pady=5)
    header_hora = tk.Label(historico_chamadas_frame, text="HORA", font=("Helvetica", 12, "bold"), fg="white", bg="#1a2537")
    header_hora.grid(row=1, column=2, padx=5, pady=5)

    barra_inferior = tk.Frame(root, bg="black", height=80)
    barra_inferior.pack(side="bottom", fill=tk.X)
    barra_inferior.pack_propagate(False)

    rodape_label = tk.Label(barra_inferior, text="Criado por: ©Wilian Leal Miyai e ©Lucas da Silva Dorneles",
                            font=("Helvetica", 14), fg="white", bg="black", anchor="w")
    rodape_label.pack(side="left", padx=20, pady=10)

    data_hora_frame = tk.Frame(barra_inferior, bg="black")
    data_hora_frame.pack(side="right", padx=20)

    data_label = tk.Label(data_hora_frame, text="Data:", font=("Helvetica", 14), fg="white", bg="black")
    data_label.pack(side="left")

    data_value = tk.Label(data_hora_frame, text="", font=("Helvetica", 14), fg="white", bg="black")
    data_value.pack(side="left", padx=5)

    hora_label = tk.Label(data_hora_frame, text="Hora:", font=("Helvetica", 14), fg="white", bg="black")
    hora_label.pack(side="left")

    hora_value = tk.Label(data_hora_frame, text="", font=("Helvetica", 14), fg="white", bg="black")
    hora_value.pack(side="left", padx=5)

    atualizar_data_hora()

    # Iniciar thread para processar a fila de senhas
    threading.Thread(target=processar_fila_senhas, daemon=True).start()

    # Iniciar thread para receber as senhas via socket
    threading.Thread(target=receber_senhas, daemon=True).start()

    threading.Thread(target=capturar_teclas, daemon=True).start()

    threading.Thread(target=zerar_senhas_diariamente, daemon=True).start()

    # Iniciar o loop principal do Tkinter
    root.mainloop()