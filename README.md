# PadDesk

Adapta jogos de teclado e mouse para uso com controles **Xbox** e **PlayStation** no Windows, com mapeamento de botões e sequências temporizadas.

**Desenvolvido por Victor Emanuel Lobato**

A interface abre em `http://127.0.0.1:8765` e só escuta localmente.

## Requisitos

- Windows 10 ou 11
- [Python 3.10 ou mais novo](https://www.python.org/downloads/) (3.10, 3.11, 3.12, 3.13 ou 3.14). Sem bibliotecas extras.

Na instalação do Python, marque **Add python.exe to PATH**.

## Como rodar

1. Baixe o ZIP do GitHub ou clone o repositório e extraia a pasta.
2. Dê dois cliques em `start.bat` (ou no terminal: `py -3 app.py`).
3. O navegador abre sozinho em `http://127.0.0.1:8765`. **F12** liga/desliga o mapeamento. **F11** para qualquer sequência.

## Controles suportados

- **Xbox** 360 / One / Series / Elite (XInput, inclusive o slot 2–4)
- **PlayStation** DualShock 3 / 4 e DualSense / DualSense Edge (USB ou Bluetooth)
- Outros pads genéricos visíveis no Windows (DirectInput / HID)

Cross, Circle, Square e Triangle do PlayStation entram como A, B, X e Y na interface.

## Sequências de exemplo

O `config.json` inicial traz três templates para copiar e adaptar:

| Template | O que ensina |
| --- | --- |
| **Exemplo — mover e clicar** | Ir até um ponto da tela e clicar |
| **Exemplo — teclas em sequência** | Toques de tecla com pausa entre eles |
| **Exemplo — tecla com modificador** | Segurar Ctrl, tocar C, soltar Ctrl |

Duplique um template, edite os passos e, se quiser, atribua um botão do controle para disparar com o mapeamento ligado.

## Atalhos

| Tecla | Ação |
| --- | --- |
| F12 | Liga / desliga o mapeamento do controle |
| F11 | Para a sequência em execução |

## Licença

[MIT](LICENSE) © Victor Emanuel Lobato
