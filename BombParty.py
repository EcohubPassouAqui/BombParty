import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from groq import Groq

API_KEY        = ""
MODEL          = "llama-3.3-70b-versatile"
POLL_INTERVAL  = 0.3
SITE_URL       = ""
MAX_TENTATIVAS = 15

client = Groq(api_key=API_KEY)


def log(tipo, msg):
    prefixos = {
        "info":    "[INFO]   ",
        "aviso":   "[AVISO]  ",
        "erro":    "[ERRO]   ",
        "palavra": "[PALAVRA]",
        "aceita":  "[ACEITA] ",
        "rejeita": "[REJEIT] ",
        "silaba":  "[SILABA] ",
        "sistema": "[SISTEM] ",
        "digita":  "[DIGITA] ",
    }
    prefixo = prefixos.get(tipo, "[LOG]    ")
    print(f"{prefixo} {msg}")


def digitar_humano(box, palavra: str) -> bool:
    try:
        box.click()
        time.sleep(random.uniform(0.1, 0.3))
        box.clear()
        for letra in palavra:
            box.send_keys(letra)
            time.sleep(random.uniform(0.08, 0.20))
        time.sleep(random.uniform(0.15, 0.4))
        box.send_keys(Keys.RETURN)
        return True
    except Exception as e:
        log("erro", f"Falha ao digitar '{palavra}': {e}")
        return False


def contem_silaba(palavra: str, silaba: str) -> bool:
    return silaba.lower() in palavra.lower()


def pedir_palavra(silaba: str, tentativas: list):
    bloqueadas = ""
    if tentativas:
        bloqueadas = f"Nao use essas palavras: {', '.join(tentativas)}."

    try:
        resposta = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Voce e um assistente de jogo BombaParty em portugues brasileiro. "
                        "Sua tarefa: dar UMA palavra em portugues do Brasil que contenha a silaba informada. "
                        "A silaba pode estar em qualquer posicao da palavra: inicio, meio ou fim. "
                        "Exemplos: silaba 'am' aceita 'amei', 'amar', 'cama', 'exame', 'trama'. "
                        "Exemplos: silaba 'ca' aceita 'casa', 'caro', 'barca', 'vaca', 'musica'. "
                        "Exemplos: silaba 'pe' aceita 'pedir', 'tapete', 'papel'. "
                        "A palavra deve ter entre 3 e 10 letras. "
                        "Pode ser substantivo, verbo, adjetivo, pais, cidade, nome, animal, objeto. "
                        "NUNCA use ingles. NUNCA repita palavras bloqueadas. "
                        "Responda SOMENTE a palavra, sem acento, sem pontuacao, tudo minusculo."
                    )
                },
                {
                    "role": "user",
                    "content": f"Silaba obrigatoria: '{silaba}'. {bloqueadas} Responda so a palavra."
                }
            ],
            max_tokens=20,
            temperature=0.8,
        )
        palavra = resposta.choices[0].message.content.strip().split()[0].lower()
        return palavra
    except Exception as e:
        log("erro", f"Falha na API para silaba '{silaba}': {e}")
        return None


def entrar_iframe(driver) -> bool:
    driver.switch_to.default_content()
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            driver.switch_to.frame(iframes[0])
            return True
    except Exception as e:
        log("erro", f"Falha ao entrar no iframe: {e}")
    return False


def get_silaba(driver):
    for sel in [".canvasArea .round .syllable", ".round .syllable", ".syllable"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            texto = el.text.strip()
            if texto and len(texto) <= 8:
                return texto.lower()
        except Exception:
            pass
    return None


def get_input(driver):
    try:
        box = driver.find_element(By.CSS_SELECTOR, "form input.styled")
        if box.is_displayed() and box.is_enabled():
            return box
    except Exception:
        pass
    return None


def limpar_input(driver):
    try:
        box = driver.find_element(By.CSS_SELECTOR, "form input.styled")
        if box.is_displayed() and box.is_enabled():
            box.click()
            box.clear()
            box.send_keys(Keys.CONTROL + "a")
            box.send_keys(Keys.DELETE)
    except Exception:
        pass


def palavra_aceita(driver, palavra: str) -> bool:
    time.sleep(0.5)
    try:
        box = driver.find_element(By.CSS_SELECTOR, "form input.styled")
        valor = box.get_attribute("value") or ""
        if valor.strip() == "":
            return True
        if palavra in valor.lower():
            return False
    except Exception:
        return True
    return True


def jogar_rodada(driver, silaba: str):
    tentativas = []
    log("silaba", f"Nova silaba detectada: [{silaba}]")

    for i in range(MAX_TENTATIVAS):
        log("info", f"Tentativa {i + 1} de {MAX_TENTATIVAS} | Silaba: [{silaba}]")

        palavra = pedir_palavra(silaba, tentativas)

        if palavra is None:
            log("erro", "IA nao retornou palavra. Tentando novamente...")
            time.sleep(0.5)
            continue

        if not contem_silaba(palavra, silaba):
            log("aviso", f"'{palavra}' nao contem '{silaba}'. Descartando...")
            tentativas.append(palavra)
            continue

        log("digita", f"Digitando '{palavra}' letra por letra...")

        box = get_input(driver)
        if box is None:
            log("aviso", "Input sumiu antes de digitar. Aguardando voltar...")
            for _ in range(10):
                time.sleep(0.3)
                box = get_input(driver)
                if box:
                    break
            if box is None:
                log("aviso", "Input nao voltou. Minha vez passou.")
                return

        ok = digitar_humano(box, palavra)
        if not ok:
            log("erro", f"Erro ao digitar '{palavra}'. Limpando e tentando outra...")
            tentativas.append(palavra)
            limpar_input(driver)
            time.sleep(0.3)
            continue

        log("palavra", f"Enviada: '{palavra}' | Silaba: [{silaba}] | Tentativa {i + 1}")

        if palavra_aceita(driver, palavra):
            log("aceita", f"'{palavra}' aceita pelo jogo!")
            return
        else:
            log("rejeita", f"'{palavra}' rejeitada. Limpando e tentando outra...")
            tentativas.append(palavra)
            limpar_input(driver)
            time.sleep(0.3)
            for _ in range(15):
                box = get_input(driver)
                if box:
                    break
                time.sleep(0.2)
            else:
                log("aviso", "Input sumiu apos rejeicao. Minha vez passou.")
                return

    log("aviso", f"Esgotou {MAX_TENTATIVAS} tentativas para [{silaba}]. Passando a vez.")


def main():
    log("sistema", "BOMBA HELPER INICIANDO...")

    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    driver.get(SITE_URL)

    log("sistema", f"Abrindo site: {SITE_URL}")
    log("sistema", "Entre na partida e espere comecar.")
    log("sistema", "Pressione Ctrl+C para encerrar.")
    print("-" * 50)

    ultima_silaba = ""
    ja_digitou    = False
    tick          = 0
    iframe_ok     = False

    try:
        while True:
            if not iframe_ok:
                iframe_ok = entrar_iframe(driver)
                if iframe_ok:
                    log("sistema", "Iframe acessado. Sistema ativo e monitorando.")

            silaba = get_silaba(driver)
            box    = get_input(driver)

            if silaba and silaba != ultima_silaba:
                ultima_silaba = silaba
                ja_digitou    = False

            if box and silaba and not ja_digitou:
                ja_digitou = True
                jogar_rodada(driver, silaba)

                box_depois = get_input(driver)
                silaba_depois = get_silaba(driver)
                if box_depois and silaba_depois == silaba:
                    log("aviso", "Input ainda ativo apos rodada. Resetando para tentar de novo...")
                    ja_digitou = False

            if not silaba:
                if ultima_silaba != "":
                    log("info", "Silaba sumiu. Aguardando proxima rodada...")
                ultima_silaba = ""
                ja_digitou    = False
                tick += 1
                if tick % 20 == 0:
                    entrar_iframe(driver)
                    log("sistema", "Monitorando... aguardando silaba.")

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        log("sistema", "Encerrado pelo usuario.")
    except Exception as e:
        log("erro", f"Erro inesperado no loop principal: {e}")
    finally:
        driver.quit()
        log("sistema", "Navegador fechado. Ate mais!")


if __name__ == "__main__":
    main()
