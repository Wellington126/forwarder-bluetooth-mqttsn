# Forwarder Bluetooth para MQTT-SN

Ponte entre um dispositivo cliente (Bluetooth RFCOMM) e um Gateway MQTT-SN (UDP).
Os pacotes MQTT-SN são repassados sem alteração, nos dois sentidos.

## Arquitetura
Dispositivo --Bluetooth--> forwarder.py --UDP:10000--> Gateway MQTT-SN --> Broker Mosquitto

## Requisitos
- Linux Mint (Ubuntu/Debian), Python 3, adaptador Bluetooth
- Pacotes: bluez, mosquitto, mosquitto-clients, tcpdump
- Gateway: Eclipse Paho MQTT-SN Gateway (paho.mqtt-sn.embedded-c)

## Instalação e compilação
sudo apt install -y bluez bluetooth mosquitto mosquitto-clients tcpdump python3
git clone https://github.com/eclipse/paho.mqtt-sn.embedded-c.git
cd paho.mqtt-sn.embedded-c/MQTTSNGateway
CMAKE_POLICY_VERSION_MINIMUM=3.5 ./build.sh udp
(O forwarder é Python e não precisa de compilação.)

## Configuração
1. gateway.conf: BrokerName=127.0.0.1, BrokerPortNo=1883, GatewayPortNo=10000
2. Bluetooth: parear o dispositivo (bluetoothctl) e registrar o serviço serial:
   bluetoothd com --compat + `sudo sdptool add --channel=1 SP`

## Execução
1. sudo systemctl start mosquitto
2. ./MQTT-SNGateway -f gateway.conf
3. python3 forwarder.py --gw-host 127.0.0.1 --gw-port 10000 --channel 1
4. mosquitto_sub -h 127.0.0.1 -t /teste -v
5. No dispositivo cliente, enviar (HEX): CONNECT, REGISTER e PUBLISH

## Testes
Pacotes usados e resultados: ver a pasta `evidencias/`.
| Pacote | Bytes (HEX) | Resposta |
|---|---|---|
| CONNECT | 08 04 04 01 03 84 63 31 | CONNACK 03 05 00 |
| REGISTER | 0C 0A 00 00 00 01 2F 74 65 73 74 65 | REGACK |
| PUBLISH | 09 0C 00 00 01 00 00 6F 69 | mosquitto_sub: /teste oi |
