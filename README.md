# Forwarder Bluetooth para MQTT-SN

## Objetivo

Este projeto implementa um **forwarder**: um programa que atua como ponte entre
um dispositivo cliente que se comunica por **Bluetooth** e um **Gateway
MQTT-SN**, que só entende mensagens vindas pela rede (UDP).

O dispositivo cliente não tem interface de rede IP, então não consegue falar
diretamente com o gateway. O forwarder resolve isso repassando os pacotes de
um lado para o outro, **sem alterar o conteúdo** deles.

## Arquitetura

```
[Dispositivo cliente]  --Bluetooth (RFCOMM)-->  [forwarder.py]  --UDP:10000-->  [Gateway MQTT-SN]  --TCP:1883-->  [Broker Mosquitto]
```

- O **dispositivo cliente** (neste projeto, um celular Android com o app
  "Serial Bluetooth Terminal") envia pacotes MQTT-SN em modo hexadecimal.
- O **forwarder** abre um servidor Bluetooth RFCOMM, recebe os pacotes,
  interpreta apenas o campo de **tamanho** de cada pacote (para separar um
  pacote do outro dentro do fluxo de bytes do Bluetooth) e os repassa
  intactos ao gateway via UDP. As respostas do gateway seguem o caminho
  inverso.
- O **Gateway MQTT-SN** (Eclipse Paho) traduz as mensagens MQTT-SN para MQTT
  e as entrega ao broker.
- O **broker Mosquitto** distribui as mensagens aos assinantes.

## Por que essa abordagem

- **Um socket UDP por cliente Bluetooth:** o gateway identifica cada cliente
  pelo IP e pela porta UDP de origem. Criando um socket dedicado por conexão
  Bluetooth, cada dispositivo aparece como um cliente MQTT-SN distinto para o
  gateway, sem precisar de nenhum protocolo de encapsulamento adicional.
- **Sem alterar os pacotes:** o forwarder não interpreta o conteúdo MQTT-SN
  (CONNECT, PUBLISH etc.). Ele só lê o cabeçalho de tamanho para saber onde um
  pacote termina, porque o Bluetooth entrega um fluxo contínuo de bytes, sem
  marcar os limites de cada mensagem.

## Requisitos

- Linux (testado em Linux Mint, baseado em Ubuntu/Debian)
- Adaptador Bluetooth (interno ou USB)
- Python 3 (nativo no Linux Mint)
- Pacotes do sistema: `bluez`, `bluetooth`, `mosquitto`, `mosquitto-clients`,
  `tcpdump`, `build-essential`, `cmake`, `libssl-dev`, `git`
- Um dispositivo cliente Bluetooth para os testes (neste projeto, um celular
  Android com o app **Serial Bluetooth Terminal**, disponível na Play Store)

## Instalação

### 1. Pacotes do sistema

```bash
sudo apt update
sudo apt install -y git build-essential cmake libssl-dev \
    mosquitto mosquitto-clients bluez bluetooth tcpdump python3
```

### 2. Compilar o Gateway MQTT-SN

O gateway usado é a implementação de referência da Eclipse Paho.

```bash
cd ~
git clone https://github.com/eclipse/paho.mqtt-sn.embedded-c.git
cd paho.mqtt-sn.embedded-c/MQTTSNGateway
CMAKE_POLICY_VERSION_MINIMUM=3.5 ./build.sh udp
```

O binário compilado fica em `MQTTSNGateway/bin/MQTT-SNGateway`.

## Configuração

### 1. Gateway (`gateway.conf`)

No arquivo `bin/gateway.conf`, ajuste:

```
BrokerName=127.0.0.1
BrokerPortNo=1883
GatewayPortNo=10000
Forwarder=NO
```

- `BrokerName=127.0.0.1`: o gateway se conecta ao Mosquitto rodando
  localmente, em vez do broker público padrão do arquivo original.
- `GatewayPortNo=10000`: porta UDP em que o gateway escuta os clientes
  MQTT-SN. É a porta usada pelo forwarder.
- `Forwarder=NO`: esse campo é sobre o encapsulamento de forwarder da
  própria especificação MQTT-SN (mensagem `0xFE`), que este projeto **não**
  usa. O forwarder aqui repassa os pacotes sem encapsulamento.

### 2. Bluetooth

**a) Ativar e desbloquear o adaptador:**

```bash
sudo systemctl enable --now bluetooth
sudo rfkill unblock bluetooth
bluetoothctl list        # deve listar um controller (hci0)
```

**b) Parear o dispositivo cliente:**

```bash
bluetoothctl
power on
discoverable on
pairable on
agent on
scan on
# quando o dispositivo aparecer:
pair <MAC_DO_DISPOSITIVO>
trust <MAC_DO_DISPOSITIVO>
exit
```

**c) Registrar o serviço Bluetooth serial (SDP):**

Apps de terminal Bluetooth encontram o notebook por meio de um serviço
registrado (Serial Port Profile). O `bluetoothd` do systemd precisa do modo
de compatibilidade para isso funcionar:

```bash
sudo systemctl edit bluetooth
```

No arquivo de override que abre, adicione:

```
[Service]
ExecStart=
ExecStart=/usr/libexec/bluetooth/bluetoothd --compat
```

(o caminho do `bluetoothd` pode variar; confira antes com
`systemctl cat bluetooth | grep ExecStart`)

```bash
sudo systemctl restart bluetooth
sudo sdptool add --channel=1 SP
```

> **Atenção:** o registro do `sdptool` se perde a cada restart do serviço
> Bluetooth. Se reiniciar o Bluetooth, rode o `sdptool add` de novo.

## Execução

Abra um terminal para cada processo (ou use abas separadas):

**Terminal 1 — Broker:**
```bash
sudo systemctl start mosquitto
```

**Terminal 2 — Gateway:**
```bash
cd ~/paho.mqtt-sn.embedded-c/MQTTSNGateway/bin
./MQTT-SNGateway -f gateway.conf
```

**Terminal 3 — Forwarder:**
```bash
cd ~/forwarder-bt
python3 forwarder.py --gw-host 127.0.0.1 --gw-port 10000 --channel 1 | tee evidencias/forwarder.log
```

Parâmetros do forwarder:
- `--gw-host`: IP do gateway (127.0.0.1 se estiver na mesma máquina)
- `--gw-port`: porta UDP do gateway (igual ao `GatewayPortNo` do
  `gateway.conf`)
- `--channel`: canal RFCOMM Bluetooth (igual ao usado no `sdptool add`)

**Terminal 4 — Captura de tráfego (evidência):**
```bash
sudo tcpdump -i lo -n -X udp port 10000 -w ~/forwarder-bt/evidencias/captura.pcap
```

**Terminal 5 — Assinante do broker (evidência):**
```bash
mosquitto_sub -h 127.0.0.1 -t /teste -v
```

### No dispositivo cliente

1. Abra o **Serial Bluetooth Terminal**.
2. Em **Devices → Bluetooth Classic**, conecte ao nome do notebook.
3. Ative o **modo HEX** de envio e desative a quebra de linha automática
   (**Settings → Send → Newline: None**), para os bytes chegarem exatamente
   como digitados.
4. Envie os pacotes na ordem da tabela abaixo, um de cada vez.

## Testes e evidências

Pacotes MQTT-SN enviados manualmente pelo dispositivo cliente, em hexadecimal:

| Passo | Pacote MQTT-SN | Bytes (HEX) | Resposta do gateway |
|---|---|---|---|
| 1 | CONNECT (clientId `c1`, keepalive 900s) | `08 04 04 01 03 84 63 31` | CONNACK `03 05 00` (aceito) |
| 2 | REGISTER do tópico `/teste` | `0C 0A 00 00 00 01 2F 74 65 73 74 65` | REGACK `07 0B 00 01 00 01 00` (topicId = 1, aceito) |
| 3 | PUBLISH payload "oi" no topicId 1, QoS 0 | `09 0C 00 00 01 00 00 6F 69` | (sem resposta — QoS 0 não gera confirmação) |

**Resultado observado no broker:**

```
mosquitto_sub -h 127.0.0.1 -t /teste -v
/teste oi
```

Isso confirma o funcionamento completo do fluxo: o dispositivo cliente enviou
a mensagem por Bluetooth, o forwarder recebeu e repassou os pacotes ao
gateway pela rede, o gateway processou o MQTT-SN e publicou no broker MQTT, e
o assinante recebeu a mensagem.

### Evidências anexadas (pasta `evidencias/`)

- `forwarder.log`: log do forwarder mostrando as linhas `[BT->GW]` (pacotes
  recebidos do dispositivo) e `[GW->BT]` (respostas do gateway).
- `captura.pcap`: captura de tráfego UDP na porta 10000, aberta com Wireshark
  (`udp.port == 10000`), mostrando os pacotes chegando ao gateway.
- Prints do terminal do gateway, do `mosquitto_sub` e do app do celular
  durante o teste.

## Código-fonte

O código completo do forwarder está em [`forwarder.py`](./forwarder.py).
Resumo do funcionamento:

- Abre um servidor Bluetooth RFCOMM (`socket.AF_BLUETOOTH`,
  `BTPROTO_RFCOMM`).
- Para cada cliente que conecta, cria uma thread e um socket UDP dedicado.
- `read_packet()` lê o cabeçalho de tamanho de cada pacote MQTT-SN e monta o
  pacote completo antes de repassá-lo, mesmo que o Bluetooth entregue os
  bytes fragmentados.
- Uma segunda thread (`gateway_para_bluetooth`) escuta respostas do gateway
  no socket UDP e as envia de volta ao dispositivo pelo Bluetooth.

## Limitações conhecidas

- Testado com um único dispositivo cliente por vez.
- O envio dos pacotes de teste foi manual (hexadecimal digitado no app), sem
  um dispositivo MQTT-SN real (como um ESP32) gerando as mensagens.
