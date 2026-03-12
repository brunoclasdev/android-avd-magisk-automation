# android-avd-magisk-automation

Script em Python para automatizar a criacao de um Android Virtual Device (`AVD`) e aplicar root com `Magisk` usando o projeto `rootAVD`.

O fluxo automatizado e:

1. Validar a instalacao do Android SDK.
2. Instalar os pacotes necessarios do SDK.
3. Criar o AVD, se ele ainda nao existir.
4. Iniciar o emulador com `-writable-system`.
5. Aguardar o dispositivo aparecer no `adb`.
6. Localizar o `ramdisk` correto.
7. Executar o `rootAVD.sh` e selecionar a opcao do Magisk.

## Arquivo principal

- [`android-avd-magisk-automation.py`](~/android-avd-magisk-automation/android-avd-magisk-automation.py)

## Requisitos

- macOS com Android SDK instalado
- Android SDK Command-line Tools (`cmdline-tools/latest`)
- `platform-tools`
- `emulator`
- Python 3
- `rootAVD`

Por padrao, o script espera:

- SDK em `~/Library/Android/Sdk`
- `rootAVD.sh` em `~/tools/rootAVD/rootAVD.sh`

## O que o script faz

- Detecta a arquitetura do host (`arm64` ou `x86_64`)
- Seleciona automaticamente a `system image` adequada quando `--pkg auto` e usado
- Instala:
  - `platform-tools`
  - `emulator`
  - `platforms;android-<api>`
  - `system-images;android-<api>;<channel>;<abi>`
- Cria o AVD se necessario
- Inicia o emulador com proxy HTTP configuravel
- Executa o `rootAVD` apontando para o `ramdisk` correto do AVD

## Parametros principais

- `target`
  - Atalho opcional para informar o nome do AVD ou um pacote `system-images;...`
- `--sdk`
  - Caminho do Android SDK
- `--avd`
  - Nome do AVD a criar/usar
- `--pkg`
  - Pacote da system image
- `--api`
  - API Android usada para montar o pacote automatico
- `--channel`
  - Canal da imagem, por exemplo `google_apis_playstore`
- `--device`
  - Perfil do device no `avdmanager`
- `--proxy`
  - Proxy HTTP passado ao emulador
- `--rootavd`
  - Caminho do script `rootAVD.sh`
- `--skip-sdk-download`
  - Nao instala/atualiza dependencias do SDK
- `--magisk-choice`
  - Opcao enviada ao menu do `rootAVD`
- `--no-emulator`
  - Nao inicia o emulador; assume que ja existe um device online no `adb`

## Uso

Ajuda:

```bash
python3 android-avd-magisk-automation.py -h
```

Criar um AVD automaticamente usando a imagem compativel com o host:

```bash
python3 android-avd-magisk-automation.py --avd Pentest_ARM2 --pkg auto --api 34
```

Usar argumento posicional como nome do AVD:

```bash
python3 android-avd-magisk-automation.py ehtmobile
```

Usar uma `system image` explicita:

```bash
python3 android-avd-magisk-automation.py \
  --avd ehtmobile \
  --pkg 'system-images;android-34;google_apis_playstore;arm64-v8a'
```

Executar sem baixar pacotes do SDK:

```bash
python3 android-avd-magisk-automation.py \
  --avd ehtmobile \
  --skip-sdk-download
```

Executar contra um emulador que ja esta online:

```bash
python3 android-avd-magisk-automation.py \
  --avd ehtmobile \
  --no-emulator
```

Definir proxy customizado:

```bash
python3 android-avd-magisk-automation.py \
  --avd ehtmobile \
  --proxy http://127.0.0.1:8080
```

## Exemplo de fluxo recomendado

Para Apple Silicon:

```bash
python3 android-avd-magisk-automation.py \
  --avd Pentest_ARM2 \
  --api 34 \
  --channel google_apis_playstore \
  --pkg auto \
  --proxy http://127.0.0.1:8080
```

Depois da execucao:

1. Faça `Cold Boot` no AVD.
2. Abra o app `Magisk`.
3. Finalize a configuracao inicial do Magisk, se solicitada.
4. Reinicie o emulador se necessario.

## Comportamento importante

- O script detecta o host e recomenda `arm64-v8a` em Apple Silicon e `x86_64` em hosts Intel.
- Quando `--pkg auto` e usado, a imagem e montada automaticamente com base em `--api`, `--channel` e na arquitetura do host.
- A localizacao do `ramdisk` e resolvida a partir do `config.ini` do AVD e, como fallback, do caminho derivado do pacote `system-images`.
- A opcao de menu do `rootAVD` pode mudar entre versoes. Se necessario, ajuste `--magisk-choice`.

## Troubleshooting

### `rootAVD nao encontrado`

Verifique se o arquivo existe no caminho esperado:

```bash
ls ~/tools/rootAVD/rootAVD.sh
```

Ou informe manualmente:

```bash
python3 android-avd-magisk-automation.py \
  --rootavd /caminho/para/rootAVD.sh
```

### Ferramentas do SDK ausentes

O script exige pelo menos:

- `cmdline-tools/latest/bin/avdmanager`
- `cmdline-tools/latest/bin/sdkmanager`
- `platform-tools/adb`
- `emulator/emulator`

Se estiver usando um SDK fora do padrao:

```bash
python3 android-avd-magisk-automation.py --sdk /caminho/do/sdk
```

### Timeout esperando `adb`

Verifique se o emulador realmente iniciou:

```bash
~/Library/Android/Sdk/platform-tools/adb devices
```

Se o device ja estiver online, rode com:

```bash
python3 android-avd-magisk-automation.py --no-emulator
```

### Pacote de system image incompativel com o host

Em Apple Silicon, prefira `arm64-v8a`.

Exemplo:

```bash
system-images;android-34;google_apis_playstore;arm64-v8a
```

Em macOS Intel, prefira `x86_64`.

### Nao foi possivel localizar o `ramdisk`

O script tenta localizar:

- `ramdisk.img`
- `ramdisk-qemu.img`

Caso o layout da imagem seja diferente, valide o conteudo de:

```bash
~/.android/avd/<nome>.avd/config.ini
```

e o diretorio da `system image` no SDK.

## Limitacoes

- O script foi escrito com foco em macOS.
- A automacao depende do comportamento atual do menu do `rootAVD`.
- O processo nao conclui a configuracao final dentro do app Magisk; ainda e necessario abrir o app apos o `Cold Boot`.

## Licenca

Este repositorio nao define licenca no estado atual. Se o projeto for publicado ou compartilhado, vale adicionar uma licenca explicita.
