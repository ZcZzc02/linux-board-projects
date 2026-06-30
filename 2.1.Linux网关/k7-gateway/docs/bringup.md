# K7 网关 Bring-up 步骤

本文档记录从当前 K7 状态继续开发时的最小验证顺序。

## 1. 不要先做的事

- 不要先重刷系统。
- 不要先改设备树。
- 不要先重插 E22 全部线。
- 不要先假设 SSH、GUI 或网络一定可用。

## 2. 串口控制台确认

优先用调试串口进入 K7 shell。官方资料中 K7 调试串口波特率为 `1500000`。

## 3. 系统基线自检

```bash
python3 -m k7_gateway self-check
```

重点看：

- `/dev/ttyS3`
- UART3 设备树状态
- I2C7 设备树状态
- `/dev/ttyUSB2`
- `/usr/bin/4G_dialing.sh`
- 默认路由

## 4. E22 配置读取

确认 E22 处于配置模式后执行：

```bash
python3 -m k7_gateway e22-read-config --device /dev/ttyS3
```

## 5. LoRa 透明接收

切到 E22 透明传输模式后执行：

```bash
python3 -m k7_gateway listen-lora --device /dev/ttyS3 --seconds 60
```

如果没有任何数据，先确认节点板是否在发送，再确认 E22 模式和接线。

## 6. 5G/4G/WiFi 自动链路状态

K7 资料中 4G/5G 模块通常通过 Mini-PCIe 接入，系统侧会检测 `/dev/ttyUSB2`，并使用 `/usr/bin/4G_dialing.sh` 或 `quectel-CM` 进行拨号。

当前 Linux 网关程序不在应用层复刻完整拨号状态机，而是让 NetworkManager 负责实际联网和默认路由选择。网关程序通过 `--transport auto` 检测当前默认出口并上报后台：

- 默认路由是 RG200U 的 USB/NCM 网卡时，通过 `AT+COPS?` 判断 `4g` / `5g`。
- 默认路由是 `wlan0` 时，上报 `wifi`。
- MQTT 暂时不可用时，网关服务不退出，继续收 LoRa 并写本地日志，网络恢复后自动重连 MQTT。

推荐 NetworkManager 优先级：

```bash
nmcli con mod 'Wired connection 3' connection.autoconnect yes connection.autoconnect-priority 100 ipv4.route-metric 100 ipv6.route-metric 100
nmcli con mod '你的WiFi连接名' connection.autoconnect yes connection.autoconnect-priority 0 ipv4.route-metric 600 ipv6.route-metric 600
```

检查当前默认出口和上报链路：

```bash
ip route
PYTHONPATH=/root/k7-gateway/src python3 - <<'PY'
from k7_gateway.network_status import default_route_interface, resolve_transport
print(default_route_interface())
print(resolve_transport("auto"))
PY
```

如果 WiFi 兜底没有连上，先确认热点能被扫描到：

```bash
nmcli dev wifi list
nmcli con up '你的WiFi连接名'
```
