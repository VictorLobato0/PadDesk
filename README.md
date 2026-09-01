# PadDesk

Mapeia um controle (Xbox / XInput e paddles extras) para mouse e teclado no Windows, com um editor de sequências temporizadas.

**Desenvolvido por Victor Emanuel Lobato**

A interface abre em `http://127.0.0.1:8765` e só escuta localmente.

## Requisitos

- Windows
- [Python 3.10+](https://www.python.org/downloads/) (sem bibliotecas extras — só a stdlib)

## Como rodar

1. Clone o repositório.
2. Dê dois cliques em `start.bat`, ou no terminal:

```bat
python app.py
```

3. O navegador abre sozinho. **F12** liga/desliga o mapeamento. **F8** para qualquer sequência.

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
| F8 | Para a sequência em execução |

## Licença

[MIT](LICENSE) © Victor Emanuel Lobato
